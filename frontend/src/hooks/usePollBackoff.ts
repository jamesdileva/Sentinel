/**
 * Generic poll backoff for job waits (v1.17.19.21, audit Batch 4).
 *
 * The dashboard is the backend's only client, but a 10-minute build polled
 * every 2 s is ~300 requests for one answer. This grows the interval as the
 * wait gets longer (2 s → 4 s → 8 s, capped at 10 s) so long jobs stop
 * hammering while short ones still resolve fast. The callers keep their own
 * terminal-state check and overall cap — this only decides the *next* delay.
 *
 * Deterministic and pure, so it is unit-tested directly.
 */

export const FIRST_POLL_MS = 2_000;
export const MAX_POLL_MS = 10_000;

/** Delay before the next tick, given how long the wait has already lasted. */
export function nextPollDelay(elapsedMs: number): number {
  const step = Math.floor(elapsedMs / FIRST_POLL_MS);
  const delay = FIRST_POLL_MS * 2 ** step;
  return Math.min(delay, MAX_POLL_MS);
}
