"""ObservatoryService — deterministic project overviews (docs/02 §14.6).

Three read-only views over stored data (no AI, no parsing at query time):
- galaxy: which technologies are shared by 2+ projects (framework + package
  dependencies), as a project<->tech node-link graph
- timeline: chronological activity (project creation, git commits, build runs,
  test runs, security findings) bounded by a days window
- architecture: nested component tree derived from indexed file paths
"""

import datetime
from collections import defaultdict

from sqlmodel import Session, select

from app.core.logging import get_logger
from app.db.models import (
    BuildLog,
    Dependency,
    GitCommit,
    Project,
    ProjectFile,
    SecurityFinding,
    TestResult,
)
from app.schemas import (
    ArchitectureNode,
    GalaxyGraph,
    GalaxyLink,
    GalaxyNode,
    TimelineEvent,
)

logger = get_logger(__name__)

MAX_TIMELINE_EVENTS = 500
_MAX_MESSAGE_LENGTH = 120


def _clip(message: str, length: int = _MAX_MESSAGE_LENGTH) -> str:
    message = message.replace("\n", " ").strip()
    return message if len(message) <= length else f"{message[:length - 1]}…"


class ObservatoryService:
    def __init__(self, session: Session):
        self.session = session

    # --- galaxy ---------------------------------------------------------------

    def galaxy(self) -> GalaxyGraph:
        projects = self._all_projects()
        techs_by_project: dict[str, set[str]] = defaultdict(set)
        for project in projects:
            if project.framework:
                techs_by_project[project.id].add(project.framework)
            deps = self.session.exec(
                select(Dependency).where(Dependency.project_id == project.id)
            ).all()
            techs_by_project[project.id].update(dep.name for dep in deps)

        # only technologies shared by at least two projects appear as nodes
        shared: dict[str, set[str]] = defaultdict(set)
        for project_id, techs in techs_by_project.items():
            for tech in techs:
                shared[tech].add(project_id)
        shared_techs = {
            tech: project_ids
            for tech, project_ids in shared.items()
            if len(project_ids) >= 2
        }

        nodes: list[GalaxyNode] = [
            GalaxyNode(
                id=f"p:{project.id}", kind="project", label=project.name, detail=None
            )
            for project in projects
        ]
        for tech in sorted(shared_techs):
            nodes.append(
                GalaxyNode(
                    id=f"t:{tech}",
                    kind="tech",
                    label=tech,
                    detail=f"used by {len(shared_techs[tech])} projects",
                )
            )

        links: list[GalaxyLink] = []
        for project in projects:
            for tech in sorted(techs_by_project[project.id] & set(shared_techs)):
                links.append(
                    GalaxyLink(source=f"p:{project.id}", target=f"t:{tech}", tech=tech)
                )
        links.sort(key=lambda link: (link.source, link.target))
        return GalaxyGraph(nodes=nodes, links=links)

    # --- timeline -------------------------------------------------------------

    def timeline(self, days: int = 365) -> list[TimelineEvent]:
        if days < 1:
            days = 365
        # SQLite returns naive UTC datetimes; compare against a naive cutoff.
        cutoff = datetime.datetime.now(datetime.timezone.utc).replace(
            tzinfo=None
        ) - datetime.timedelta(days=days)
        projects = self._all_projects()
        by_id = {project.id: project for project in projects}
        events: list[TimelineEvent] = []

        for project in projects:
            if project.created_at and project.created_at >= cutoff:
                events.append(
                    self._event(
                        project.created_at,
                        "project-created",
                        project,
                        "Project indexed",
                    )
                )

        commit_stmt = select(GitCommit).where(
            GitCommit.timestamp >= cutoff, GitCommit.timestamp.is_not(None)
        )
        for commit in self.session.exec(commit_stmt).all():
            project = by_id.get(commit.project_id)
            if project is None:
                continue
            events.append(
                self._event(
                    commit.timestamp,
                    "commit",
                    project,
                    f"{commit.hash[:8]} {_clip(commit.message or '')}",
                )
            )

        build_stmt = select(BuildLog).where(BuildLog.started_at >= cutoff)
        for build in self.session.exec(build_stmt).all():
            project = by_id.get(build.project_id)
            if project is None:
                continue
            status = "success" if build.success is True else "failed"
            events.append(
                self._event(build.started_at, "build", project, f"Build {status}")
            )

        test_stmt = select(TestResult).where(TestResult.run_at >= cutoff)
        for test in self.session.exec(test_stmt).all():
            project = by_id.get(test.project_id)
            if project is None:
                continue
            events.append(
                self._event(
                    test.run_at,
                    "test",
                    project,
                    f"Tests {test.passed} passed / {test.failed} failed",
                )
            )

        finding_stmt = select(SecurityFinding).where(
            SecurityFinding.detected_at >= cutoff,
            # v1.17.7.7: resolved findings are stale scan leftovers — exclude
            # them so a history of fixed false positives does not spam the
            # timeline (open findings only).
            SecurityFinding.resolved == False,  # noqa: E712
        )
        for finding in self.session.exec(finding_stmt).all():
            project = by_id.get(finding.project_id)
            if project is None:
                continue
            events.append(
                self._event(
                    finding.detected_at,
                    "finding",
                    project,
                    f"{finding.severity.value}: {_clip(finding.title or '')}",
                )
            )

        events.sort(key=lambda event: event.at, reverse=True)
        return events[:MAX_TIMELINE_EVENTS]

    def _event(
        self, at: datetime.datetime, kind: str, project: Project, message: str
    ) -> TimelineEvent:
        return TimelineEvent(
            at=at,
            kind=kind,
            project_id=project.id,
            project_name=project.name,
            message=message,
        )

    # --- architecture ---------------------------------------------------------

    def architecture(self, project_id: str) -> ArchitectureNode:
        project = self.session.get(Project, project_id)
        if project is None:
            raise KeyError(project_id)

        files = self.session.exec(
            select(ProjectFile)
            .where(ProjectFile.project_id == project_id)
            .order_by(ProjectFile.path)
        ).all()

        root: dict = {
            "name": project.name,
            "path": "",
            "kind": "dir",
            "children": {},
            "count": 0,
        }

        for file in files:
            segments = [s for s in file.path.replace("\\", "/").split("/") if s]
            if not segments:
                continue
            cursor = root
            for index, segment in enumerate(segments):
                cursor["count"] += 1  # this directory contains this file
                is_file = index == len(segments) - 1
                child = cursor["children"].get(segment)
                if child is None:
                    child = {
                        "name": segment,
                        "path": (cursor["path"] + "/" + segment).strip("/"),
                        "kind": "file" if is_file else "dir",
                        "children": {},
                        "count": 0,
                    }
                    cursor["children"][segment] = child
                cursor = child
            cursor["count"] += 1  # the file itself

        def to_node(raw: dict) -> ArchitectureNode:
            children = [to_node(child) for child in raw["children"].values()]
            children.sort(key=lambda node: (node.kind == "file", node.name))
            return ArchitectureNode(
                name=raw["name"],
                path=raw["path"],
                kind=raw["kind"],
                count=raw["count"],
                children=children,
            )

        return to_node(root)

    # --- helpers --------------------------------------------------------------

    def _all_projects(self) -> list[Project]:
        stmt = select(Project).order_by(Project.name)
        return list(self.session.exec(stmt).all())
