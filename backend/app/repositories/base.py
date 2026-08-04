"""Generic repository base with session management.

Concrete repositories (project, build, test, ...) extend `Repository` and
receive a SQLModel `Session` from the `get_session` dependency.

Sprint 2 scope: base class only; concrete repositories land with their
services (Sprint 3+).
"""

from typing import Any, TypeVar

from sqlmodel import Session, select

from app.core.logging import get_logger

logger = get_logger(__name__)

ModelT = TypeVar("ModelT")


class Repository:
    """Base CRUD operations over a single SQLModel table.

    Concrete repositories set `model` as a class attribute (e.g.
    `class ProjectRepository(Repository): model = Project`); a model can
    also be passed to the constructor for ad-hoc usage.
    """

    model: type[Any] | None = None

    def __init__(self, session: Session, model: type[Any] | None = None):
        self.session = session
        if model is not None:
            self.model = model
        if self.model is None:
            raise TypeError(
                "Repository requires a model (class attribute or constructor argument)"
            )

    def get(self, model_id: str) -> ModelT | None:
        """Fetch a single row by primary key."""
        return self.session.get(self.model, model_id)

    def list(self, skip: int = 0, limit: int = 50) -> list[ModelT]:
        """Fetch a page of rows."""
        stmt = select(self.model).offset(skip).limit(limit)
        return list(self.session.exec(stmt).all())

    def count(self) -> int:
        """Count all rows."""
        return len(self.session.exec(select(self.model)).all())

    def add(self, instance: ModelT) -> ModelT:
        """Insert a row, flush, and return it with its generated fields."""
        self.session.add(instance)
        self.session.flush()
        logger.debug(
            "Added %s row %s", self.model.__name__, getattr(instance, "id", None)
        )
        return instance

    def update(self, instance: ModelT) -> ModelT:
        """Persist changes to an already-attached row."""
        self.session.add(instance)
        self.session.flush()
        return instance

    def delete(self, instance: ModelT) -> None:
        """Delete a row."""
        self.session.delete(instance)
        self.session.flush()
