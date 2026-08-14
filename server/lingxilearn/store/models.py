"""Database schema.

Deliberately small.  LingxiGraph's checkpointer already owns the authoritative
run state; these tables own the things that must outlive a single run:

* who the learner is and what they have demonstrated (``mastery``),
* a durable, monotonically sequenced event log per session, which is what makes
  the SSE stream resumable rather than a fire-and-forget pipe.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Learner(Base):
    __tablename__ = "learners"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IdentityUser(Base):
    """The verified LingxiIdentity subject mapped to one internal learner."""

    __tablename__ = "identity_users"
    __table_args__ = (
        UniqueConstraint("issuer", "subject", name="uq_identity_users_issuer_subject"),
        UniqueConstraint("learner_id", name="uq_identity_users_learner"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issuer: Mapped[str] = mapped_column(String(256))
    subject: Mapped[str] = mapped_column(String(256))
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LearnerProfile(Base):
    """Small, extensible profile owned by LingxiLearn."""

    __tablename__ = "learner_profiles"

    learner_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("learners.id"), primary_key=True
    )
    locale: Mapped[str] = mapped_column(String(32), default="zh-CN")
    level: Mapped[str] = mapped_column(String(64), default="undergraduate")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    pack_id: Mapped[str] = mapped_column(String(64))
    pack_version: Mapped[str] = mapped_column(String(32))
    mission_id: Mapped[str] = mapped_column(String(64))
    checkpoint_ns: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(24), default="created", index=True)
    """created | running | awaiting_learner | done | failed"""
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class AgentTask(Base):
    """A one-shot intent-routing task and its specialist outputs."""

    __tablename__ = "agent_tasks"

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, default="")
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_unread: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    resources: Mapped[list] = mapped_column(JSON, default=list)
    graph_version: Mapped[str] = mapped_column(String(32), default="difficult_knowledge.v2")
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    intent: Mapped[dict] = mapped_column(JSON, default=dict)
    lecture_result: Mapped[dict] = mapped_column(JSON, default=dict)
    deck_result: Mapped[dict] = mapped_column(JSON, default=dict)
    quiz_result: Mapped[dict] = mapped_column(JSON, default=dict)
    adaptive_result: Mapped[dict] = mapped_column(JSON, default=dict)
    handoff_result: Mapped[dict] = mapped_column(JSON, default=dict)
    user_messages: Mapped[list] = mapped_column(JSON, default=list)
    # Kept for backwards-compatible reads of tasks created before the subgraph
    # refactor. New code never creates or renders this artifact.
    visual_result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class QuizSubmission(Base):
    """The single durable submission allowed for one AgentTask."""

    __tablename__ = "quiz_submissions"
    __table_args__ = (
        UniqueConstraint("task_id", name="uq_quiz_submissions_task"),
        UniqueConstraint("submission_id", name="uq_quiz_submissions_submission"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(96), ForeignKey("agent_tasks.id"), index=True)
    submission_id: Mapped[str] = mapped_column(String(128))
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    per_question: Mapped[list] = mapped_column(JSON, default=list)
    total_score: Mapped[float] = mapped_column(Float, default=0)
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    handoff_reason: Mapped[str] = mapped_column(String(64), default="quiz_completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentTaskEvent(Base):
    """Durable SSE projection log for Agent Tasks."""

    __tablename__ = "agent_task_events"
    __table_args__ = (
        UniqueConstraint("task_id", "sequence", name="uq_agent_task_events_sequence"),
        Index("ix_agent_task_events_task_sequence", "task_id", "sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(96), ForeignKey("agent_tasks.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(64))
    agent: Mapped[str] = mapped_column(String(64), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentTaskSidecar(Base):
    """Durable background work attached to one intent-driven task."""

    __tablename__ = "agent_task_sidecars"
    __table_args__ = (
        UniqueConstraint("task_id", "kind", name="uq_agent_task_sidecars_task_kind"),
        Index("ix_agent_task_sidecars_task_status", "task_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(96), ForeignKey("agent_tasks.id"), index=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    kind: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    input: Mapped[dict] = mapped_column(JSON, default=dict)
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class KnowledgeGraph(Base):
    """One learner-owned curriculum graph and its monotonic revision."""

    __tablename__ = "knowledge_graphs"
    __table_args__ = (
        UniqueConstraint("learner_id", "graph_id", name="uq_knowledge_graphs_learner_graph"),
        Index("ix_knowledge_graphs_learner_updated", "learner_id", "updated_at"),
    )

    graph_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    domain: Mapped[str] = mapped_column(String(120), default="")
    revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class KnowledgeGraphNode(Base):
    """Curriculum structure for one graph; learner state lives in the overlay."""

    __tablename__ = "knowledge_graph_nodes"
    __table_args__ = (
        Index("ix_knowledge_graph_nodes_graph", "graph_id"),
    )

    graph_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("knowledge_graphs.graph_id"), primary_key=True
    )
    node_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    label: Mapped[str] = mapped_column(String(80))
    type: Mapped[str] = mapped_column(String(32))
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text, default="")
    source_refs: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class KnowledgeGraphEdge(Base):
    """Explicitly directed or symmetric curricular relation."""

    __tablename__ = "knowledge_graph_edges"
    __table_args__ = (
        Index("ix_knowledge_graph_edges_graph", "graph_id"),
        UniqueConstraint(
            "graph_id", "source_node_id", "target_node_id", "relation",
            name="uq_knowledge_graph_edges_semantic",
        ),
    )

    graph_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("knowledge_graphs.graph_id"), primary_key=True
    )
    edge_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_node_id: Mapped[str] = mapped_column(String(128))
    target_node_id: Mapped[str] = mapped_column(String(128))
    relation: Mapped[str] = mapped_column(String(48))
    relation_label: Mapped[str] = mapped_column(String(20))
    directed: Mapped[bool] = mapped_column(default=True)
    importance: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_refs: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class KnowledgeGraphLearnerOverlay(Base):
    """Per-learner state labels over immutable curriculum structure."""

    __tablename__ = "knowledge_graph_learner_overlay"
    graph_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("knowledge_graphs.graph_id"), primary_key=True
    )
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    node_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    is_current: Mapped[bool] = mapped_column(default=False)
    learning_state: Mapped[str] = mapped_column(String(32), default="unknown")
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class KnowledgeGraphEvent(Base):
    """Audit record for every accepted graph patch."""

    __tablename__ = "knowledge_graph_events"

    event_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    graph_id: Mapped[str] = mapped_column(String(128), index=True)
    task_id: Mapped[str] = mapped_column(String(96), ForeignKey("agent_tasks.id"), index=True)
    base_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    patch: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RunEvent(Base):
    """The durable projection log. SSE serves from here, never from the live run."""

    __tablename__ = "run_events"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_run_events_session_sequence"),
        Index("ix_run_events_session_sequence", "session_id", "sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("sessions.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(48))
    node: Mapped[str] = mapped_column(String(64), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Mastery(Base):
    """Cross-session learner model. Every score is backed by counted evidence."""

    __tablename__ = "mastery"
    __table_args__ = (UniqueConstraint("learner_id", "concept", name="uq_mastery_learner_concept"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    concept: Mapped[str] = mapped_column(String(96))
    score: Mapped[float] = mapped_column(Float, default=0.35)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Misconception(Base):
    """Aggregated misconception observations for one learner."""

    __tablename__ = "misconceptions"
    __table_args__ = (
        UniqueConstraint("learner_id", "tag", name="uq_misconceptions_learner_tag"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    tag: Mapped[str] = mapped_column(String(128))
    occurrence_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LearningEvidence(Base):
    """Canonical learner evidence; graph-local evidence ids are session-scoped."""

    __tablename__ = "learning_evidence"
    __table_args__ = (
        UniqueConstraint("session_id", "evidence_id", name="uq_learning_evidence_session_id"),
        Index("ix_learning_evidence_learner_created", "learner_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(192), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    session_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("sessions.id"), nullable=True, index=True
    )
    evidence_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(256))
    summary: Mapped[str] = mapped_column(Text, default="")
    locator: Mapped[dict] = mapped_column(JSON, default=dict)
    value: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    digest: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LearningPreference(Base):
    """Per-learner preference document, shallow-merged by the service."""

    __tablename__ = "learning_preferences"

    learner_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("learners.id"), primary_key=True
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class LearningEvent(Base):
    """Append-only, idempotent learning event separate from the SSE projection."""

    __tablename__ = "learning_events"
    __table_args__ = (
        UniqueConstraint(
            "learner_id", "idempotency_key", name="uq_learning_events_learner_idempotency"
        ),
        Index("ix_learning_events_learner_created", "learner_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    session_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("sessions.id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(96))
    idempotency_key: Mapped[str] = mapped_column(String(192))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReportRecord(Base):
    """Finished learning reports, kept so a learner can revisit past sessions."""

    __tablename__ = "reports"

    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id"), primary_key=True
    )
    learner_id: Mapped[str] = mapped_column(String(64), index=True)
    mission_id: Mapped[str] = mapped_column(String(64))
    probe_score: Mapped[float] = mapped_column(Float, default=0.0)
    verify_score: Mapped[float] = mapped_column(Float, default=0.0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------------------
# Native Sim non-workflow workspace projection
# ---------------------------------------------------------------------------


class Workspace(Base):
    """The single private workspace projected for one Lingxi learner."""

    __tablename__ = "workspaces"
    __table_args__ = (UniqueConstraint("learner_id", name="uq_workspaces_learner"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), default="灵犀智学")
    appearance: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class WorkspaceFolder(Base):
    __tablename__ = "workspace_folders"
    __table_args__ = (
        UniqueConstraint("workspace_id", "parent_id", "name", name="uq_workspace_folder_name"),
        Index("ix_workspace_folders_workspace_archived", "workspace_id", "archived"),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), ForeignKey("workspaces.id"), index=True)
    parent_id: Mapped[str | None] = mapped_column(
        String(96), ForeignKey("workspace_folders.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class WorkspaceFile(Base):
    __tablename__ = "workspace_files"
    __table_args__ = (
        Index("ix_workspace_files_workspace_archived", "workspace_id", "archived"),
        Index("ix_workspace_files_workspace_folder", "workspace_id", "folder_id"),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), ForeignKey("workspaces.id"), index=True)
    folder_id: Mapped[str | None] = mapped_column(
        String(96), ForeignKey("workspace_folders.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(160), default="application/octet-stream")
    size: Mapped[int] = mapped_column(Integer, default=0)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    path: Mapped[str] = mapped_column(String(1024), default="")
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_payload: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class WorkspaceUploadSession(Base):
    """Durable metadata for a resumable local upload transfer."""

    __tablename__ = "workspace_upload_sessions"
    __table_args__ = (
        Index("ix_workspace_upload_sessions_learner_status", "learner_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), ForeignKey("workspaces.id"), index=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(160), default="application/octet-stream")
    size: Mapped[int] = mapped_column(Integer, default=0)
    temp_key: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(24), default="uploading", index=True)
    file_id: Mapped[str | None] = mapped_column(String(96), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class WorkspaceTable(Base):
    __tablename__ = "workspace_tables"
    __table_args__ = (Index("ix_workspace_tables_workspace_archived", "workspace_id", "archived"),)

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), ForeignKey("workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    metadata_payload: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class WorkspaceTableColumn(Base):
    __tablename__ = "workspace_table_columns"
    __table_args__ = (
        UniqueConstraint("table_id", "key", name="uq_workspace_table_column_key"),
        Index("ix_workspace_table_columns_table_position", "table_id", "position"),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    table_id: Mapped[str] = mapped_column(String(96), ForeignKey("workspace_tables.id"), index=True)
    key: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(24), default="string")
    position: Mapped[int] = mapped_column(Integer, default=0)
    options: Mapped[dict] = mapped_column(JSON, default=dict)


class WorkspaceTableRow(Base):
    __tablename__ = "workspace_table_rows"
    __table_args__ = (Index("ix_workspace_table_rows_table_position", "table_id", "position"),)

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    table_id: Mapped[str] = mapped_column(String(96), ForeignKey("workspace_tables.id"), index=True)
    values: Mapped[dict] = mapped_column(JSON, default=dict)
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class WorkspaceTableView(Base):
    __tablename__ = "workspace_table_views"
    __table_args__ = (UniqueConstraint("table_id", "name", name="uq_workspace_table_view_name"),)

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    table_id: Mapped[str] = mapped_column(String(96), ForeignKey("workspace_tables.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class KnowledgeBase(Base):
    __tablename__ = "workspace_knowledge_bases"
    __table_args__ = (
        Index("ix_workspace_knowledge_bases_learner_archived", "learner_id", "archived"),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    metadata_payload: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class KnowledgeDocument(Base):
    __tablename__ = "workspace_knowledge_documents"
    __table_args__ = (Index("ix_workspace_knowledge_documents_base_archived", "base_id", "archived"),)

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    base_id: Mapped[str] = mapped_column(String(96), ForeignKey("workspace_knowledge_bases.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(160), default="text/plain")
    content: Mapped[str] = mapped_column(Text, default="")
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    metadata_payload: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class KnowledgeChunk(Base):
    __tablename__ = "workspace_knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal", name="uq_workspace_knowledge_chunk_ordinal"),
    )

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(96), ForeignKey("workspace_knowledge_documents.id"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text, default="")
    metadata_payload: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class KnowledgeTag(Base):
    __tablename__ = "workspace_knowledge_tags"
    __table_args__ = (UniqueConstraint("base_id", "name", name="uq_workspace_knowledge_tag_name"),)

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    base_id: Mapped[str] = mapped_column(String(96), ForeignKey("workspace_knowledge_bases.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    field_type: Mapped[str] = mapped_column(String(32), default="string")


class KnowledgeDocumentTag(Base):
    __tablename__ = "workspace_knowledge_document_tags"
    document_id: Mapped[str] = mapped_column(
        String(96), ForeignKey("workspace_knowledge_documents.id"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(String(96), ForeignKey("workspace_knowledge_tags.id"), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class PersonalSkill(Base):
    __tablename__ = "workspace_personal_skills"
    __table_args__ = (UniqueConstraint("learner_id", "name", name="uq_workspace_personal_skill_name"),)

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class WorkspaceActivityEvent(Base):
    __tablename__ = "workspace_activity_events"
    __table_args__ = (
        Index("ix_workspace_activity_events_learner_created", "learner_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    learner_id: Mapped[str] = mapped_column(String(64), ForeignKey("learners.id"), index=True)
    kind: Mapped[str] = mapped_column(String(96))
    resource_type: Mapped[str] = mapped_column(String(64), default="")
    resource_id: Mapped[str] = mapped_column(String(96), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
