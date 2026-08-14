"""Native Sim non-workflow workspace resources.

Revision ID: 0007_native_workspace
Revises: 0006_agent_task_management
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_native_workspace"
down_revision = "0006"
branch_labels = None
depends_on = None


def _json():
    return sa.JSON()


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False, server_default="灵犀智学"),
        sa.Column("appearance", _json(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("learner_id", name="uq_workspaces_learner"),
    )
    op.create_index("ix_workspaces_learner_id", "workspaces", ["learner_id"])
    op.create_table(
        "workspace_folders",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("parent_id", sa.String(96), sa.ForeignKey("workspace_folders.id"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "parent_id", "name", name="uq_workspace_folder_name"),
    )
    op.create_index("ix_workspace_folders_workspace_id", "workspace_folders", ["workspace_id"])
    op.create_index("ix_workspace_folders_workspace_archived", "workspace_folders", ["workspace_id", "archived"])
    op.create_table(
        "workspace_files",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("folder_id", sa.String(96), sa.ForeignKey("workspace_folders.id"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(160), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("storage_key", sa.String(512), nullable=False, unique=True),
        sa.Column("path", sa.String(1024), nullable=False, server_default=""),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("metadata", _json(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workspace_files_workspace_id", "workspace_files", ["workspace_id"])
    op.create_index("ix_workspace_files_workspace_archived", "workspace_files", ["workspace_id", "archived"])
    op.create_index("ix_workspace_files_workspace_folder", "workspace_files", ["workspace_id", "folder_id"])
    op.create_table(
        "workspace_upload_sessions",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(160), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("temp_key", sa.String(512), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="uploading"),
        sa.Column("file_id", sa.String(96), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workspace_upload_sessions_workspace_id", "workspace_upload_sessions", ["workspace_id"])
    op.create_index("ix_workspace_upload_sessions_learner_id", "workspace_upload_sessions", ["learner_id"])
    op.create_index("ix_workspace_upload_sessions_learner_status", "workspace_upload_sessions", ["learner_id", "status"])
    op.create_index("ix_workspace_upload_sessions_status", "workspace_upload_sessions", ["status"])
    op.create_index("ix_workspace_upload_sessions_expires_at", "workspace_upload_sessions", ["expires_at"])
    op.create_table(
        "workspace_tables",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("workspace_id", sa.String(64), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metadata", _json(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workspace_tables_workspace_id", "workspace_tables", ["workspace_id"])
    op.create_index("ix_workspace_tables_workspace_archived", "workspace_tables", ["workspace_id", "archived"])
    op.create_table(
        "workspace_table_columns",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("table_id", sa.String(96), sa.ForeignKey("workspace_tables.id"), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(24), nullable=False, server_default="string"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("options", _json(), nullable=False),
        sa.UniqueConstraint("table_id", "key", name="uq_workspace_table_column_key"),
    )
    op.create_index("ix_workspace_table_columns_table_id", "workspace_table_columns", ["table_id"])
    op.create_index("ix_workspace_table_columns_table_position", "workspace_table_columns", ["table_id", "position"])
    op.create_table(
        "workspace_table_rows",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("table_id", sa.String(96), sa.ForeignKey("workspace_tables.id"), nullable=False),
        sa.Column("values", _json(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workspace_table_rows_table_id", "workspace_table_rows", ["table_id"])
    op.create_index("ix_workspace_table_rows_table_position", "workspace_table_rows", ["table_id", "position"])
    op.create_table(
        "workspace_table_views",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("table_id", sa.String(96), sa.ForeignKey("workspace_tables.id"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("config", _json(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("table_id", "name", name="uq_workspace_table_view_name"),
    )
    op.create_index("ix_workspace_table_views_table_id", "workspace_table_views", ["table_id"])
    op.create_table(
        "workspace_knowledge_bases",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metadata", _json(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workspace_knowledge_bases_learner_id", "workspace_knowledge_bases", ["learner_id"])
    op.create_index("ix_workspace_knowledge_bases_learner_archived", "workspace_knowledge_bases", ["learner_id", "archived"])
    op.create_table(
        "workspace_knowledge_documents",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("base_id", sa.String(96), sa.ForeignKey("workspace_knowledge_bases.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(160), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("metadata", _json(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workspace_knowledge_documents_base_id", "workspace_knowledge_documents", ["base_id"])
    op.create_index("ix_workspace_knowledge_documents_base_archived", "workspace_knowledge_documents", ["base_id", "archived"])
    op.create_table(
        "workspace_knowledge_chunks",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("document_id", sa.String(96), sa.ForeignKey("workspace_knowledge_documents.id"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("metadata", _json(), nullable=False),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_workspace_knowledge_chunk_ordinal"),
    )
    op.create_index("ix_workspace_knowledge_chunks_document_id", "workspace_knowledge_chunks", ["document_id"])
    op.create_table(
        "workspace_knowledge_tags",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("base_id", sa.String(96), sa.ForeignKey("workspace_knowledge_bases.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("field_type", sa.String(32), nullable=False, server_default="string"),
        sa.UniqueConstraint("base_id", "name", name="uq_workspace_knowledge_tag_name"),
    )
    op.create_index("ix_workspace_knowledge_tags_base_id", "workspace_knowledge_tags", ["base_id"])
    op.create_table(
        "workspace_knowledge_document_tags",
        sa.Column("document_id", sa.String(96), sa.ForeignKey("workspace_knowledge_documents.id"), primary_key=True),
        sa.Column("tag_id", sa.String(96), sa.ForeignKey("workspace_knowledge_tags.id"), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
    )
    op.create_table(
        "workspace_personal_skills",
        sa.Column("id", sa.String(96), primary_key=True),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version", sa.String(32), nullable=False, server_default="1.0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("learner_id", "name", name="uq_workspace_personal_skill_name"),
    )
    op.create_index("ix_workspace_personal_skills_learner_id", "workspace_personal_skills", ["learner_id"])
    op.create_table(
        "workspace_activity_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("learner_id", sa.String(64), sa.ForeignKey("learners.id"), nullable=False),
        sa.Column("kind", sa.String(96), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False, server_default=""),
        sa.Column("resource_id", sa.String(96), nullable=False, server_default=""),
        sa.Column("payload", _json(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workspace_activity_events_learner_id", "workspace_activity_events", ["learner_id"])
    op.create_index("ix_workspace_activity_events_learner_created", "workspace_activity_events", ["learner_id", "created_at"])

    # PostgreSQL gets the bilingual full-text/fuzzy indexes used by Knowledge.
    # SQLite remains the zero-setup development backend and uses the API's
    # deterministic substring fallback instead.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        op.execute(
            "ALTER TABLE workspace_knowledge_documents ADD COLUMN search_vector tsvector "
            "GENERATED ALWAYS AS (to_tsvector('simple', coalesce(name, '') || ' ' || coalesce(content, ''))) STORED"
        )
        op.execute(
            "CREATE INDEX ix_workspace_knowledge_documents_search_vector "
            "ON workspace_knowledge_documents USING GIN (search_vector)"
        )
        op.execute(
            "CREATE INDEX ix_workspace_knowledge_documents_content_trgm "
            "ON workspace_knowledge_documents USING GIN (content gin_trgm_ops)"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_workspace_knowledge_documents_content_trgm")
        op.execute("DROP INDEX IF EXISTS ix_workspace_knowledge_documents_search_vector")
        op.execute("ALTER TABLE workspace_knowledge_documents DROP COLUMN IF EXISTS search_vector")
    for table in (
        "workspace_activity_events",
        "workspace_personal_skills",
        "workspace_knowledge_document_tags",
        "workspace_knowledge_tags",
        "workspace_knowledge_chunks",
        "workspace_knowledge_documents",
        "workspace_knowledge_bases",
        "workspace_table_views",
        "workspace_table_rows",
        "workspace_table_columns",
        "workspace_tables",
        "workspace_upload_sessions",
        "workspace_files",
        "workspace_folders",
        "workspaces",
    ):
        op.drop_table(table)
