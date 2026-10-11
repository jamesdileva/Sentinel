"""Ingest barrier tests (audit A6).

The barrier is what makes "SQLite and Chroma describe one instant" true, so
the properties under test are the lock's own: mutual exclusion, write
preference, per-thread reentrancy and the timeout that refuses a backup
rather than snapshotting a half-write.
"""

import threading
import time

import pytest

from app.services.ingest_barrier import (
    Barrier,
    KnowledgeBusyError,
    ingest_transaction,
    maintenance_window,
)


def test_readers_do_not_exclude_each_other():
    """Two ingest passes must still run concurrently (they did before A6) —
    the barrier is about consistency with a backup, not serialisation."""
    barrier = Barrier()
    both_inside = threading.Event()
    entered = []

    def reader():
        with barrier.reading():
            entered.append(threading.get_ident())
            if len(entered) >= 2:
                both_inside.set()
            both_inside.wait(2.0)

    threads = [threading.Thread(target=reader), threading.Thread(target=reader)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5.0)
    assert both_inside.is_set()


def test_writer_excludes_new_readers():
    barrier = Barrier()
    inside_writer = threading.Event()
    let_writer_out = threading.Event()
    reader_entered = threading.Event()

    def writer():
        with barrier.writing(timeout=2.0):
            inside_writer.set()
            assert let_writer_out.wait(2.0)

    def reader():
        with barrier.reading():
            inside_writer.wait(2.0)
            reader_entered.set()

    handle = threading.Thread(target=writer)
    handle.start()
    reader_thread = threading.Thread(target=reader)
    reader_thread.start()
    # Still inside the writer's window: the reader must not have run.
    assert not reader_entered.wait(0.3)
    let_writer_out.set()
    handle.join(5.0)
    reader_thread.join(5.0)
    assert reader_entered.is_set()


def test_writer_waits_for_in_flight_reader_to_drain():
    """The audit's "wait for active Chroma writes to finish".

    The writer has to run on its own thread here: it cannot be granted while
    the reader holds the side, and the reader is only released by the test —
    so the main thread coordinates rather than trying to be both.
    """
    barrier = Barrier()
    inside_reader = threading.Event()
    release_reader = threading.Event()
    granted = threading.Event()

    def reader():
        with barrier.reading():
            inside_reader.set()
            release_reader.wait(5.0)

    def writer():
        with barrier.writing(timeout=5.0):
            granted.set()

    handle = threading.Thread(target=reader)
    handle.start()
    assert inside_reader.wait(2.0)
    writer_thread = threading.Thread(target=writer)
    writer_thread.start()
    try:
        # Blocked by the active read, not merely slow.
        assert not granted.wait(0.3), "writer ignored an in-flight reader"
        started = time.monotonic()
        release_reader.set()
        assert granted.wait(2.0), "writer never acquired after the reader left"
        assert time.monotonic() - started < 2.0
    finally:
        release_reader.set()
    handle.join(5.0)
    writer_thread.join(5.0)
    assert granted.is_set()


def test_nested_read_does_not_deadlock_against_a_waiting_writer():
    """`ingest_files` calls `_retract_obsolete_chunks` inside its own
    transaction. Without per-thread reentrancy the inner acquisition would
    block behind a writer the same thread is already blocking."""
    barrier = Barrier()
    inner_entered = threading.Event()
    outer_release = threading.Event()
    writer_done = threading.Event()

    def writer():
        # Starts while the outer read is held; new readers now wait.
        time.sleep(0.1)
        with barrier.writing(timeout=5.0):
            writer_done.set()

    def reader():
        with barrier.reading():
            with barrier.reading():  # nested — must not block
                inner_entered.set()
            outer_release.wait(5.0)

    writer_thread = threading.Thread(target=writer)
    writer_thread.start()
    handle = threading.Thread(target=reader)
    handle.start()
    assert inner_entered.wait(2.0), "nested read deadlocked"
    outer_release.set()
    handle.join(5.0)
    writer_thread.join(5.0)
    assert writer_done.is_set()


def test_writing_times_out_instead_of_snapshotting_a_half_write():
    """The point of the timeout: no zip is better than a zip that lies."""
    barrier = Barrier()
    hold = threading.Event()

    def reader():
        with barrier.reading():
            assert hold.wait(5.0)

    handle = threading.Thread(target=reader)
    handle.start()
    time.sleep(0.05)
    with pytest.raises(KnowledgeBusyError):
        with barrier.writing(timeout=0.2):
            pytest.fail("the write side must not have been granted")
    hold.set()
    handle.join(5.0)


def test_write_preference_starves_no_reader_forever():
    """Once the writer leaves, waiting readers proceed (they are not dead)."""
    barrier = Barrier()
    with barrier.writing(timeout=2.0):
        pass
    with barrier.reading():
        pass  # would block forever if the writer never released


def test_module_helpers_share_one_barrier():
    """`ingest_transaction` and `maintenance_window` must be the same lock,
    or the backup and the ingest paths would each hold their own."""
    done = threading.Event()
    hold = threading.Event()

    def ingest():
        with ingest_transaction():
            done.set()
            assert hold.wait(5.0)

    handle = threading.Thread(target=ingest)
    handle.start()
    assert done.wait(2.0)
    with pytest.raises(KnowledgeBusyError):
        with maintenance_window(timeout=0.2):
            pytest.fail("maintenance_window ignored an active ingest")
    hold.set()
    handle.join(5.0)


def test_maintenance_window_passes_when_index_is_idle():
    with maintenance_window(timeout=1.0):
        pass
