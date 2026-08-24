"""baseline: 補上核心文件表(documents 等 5 張)

起因(2026-08-24):
`f1a2b3c4d5e6_add_feedback_layer_tables` 建立 `review_queue_items` 時,外鍵指向
`documents.id`,但**沒有任何遷移會建立 `documents`**——那 5 張核心表過去是靠
`Base.metadata.create_all()` 在開發機臨時建出來的,從未進入遷移鏈。

後果:在乾淨資料庫上 `alembic upgrade head` 必定失敗:
    sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedTable)
    relation "documents" does not exist

本遷移補上這 5 張表,並刻意排在 `d18dbadf87e7` 之後、feedback layer 之前:

    None → d18dbadf87e7 → **a0b1c2d3e4f5(本檔)** → f1a2b3c4d5e6

排在 d18dbadf87e7 **之後**而非最前面,是因為既有資料庫已停在 d18dbadf87e7;
若插在它之前,alembic 會認為該版本以前的都做過了,本遷移永遠不會執行。

每張表都先檢查是否存在才建立——已用 create_all 建過表的環境不能因此炸掉。

Revision ID: a0b1c2d3e4f5
Revises: d18dbadf87e7
Create Date: 2026-08-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a0b1c2d3e4f5"
down_revision: Union[str, None] = "d18dbadf87e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _existing_tables() -> set:
    """目前資料庫已存在的表;用於跳過已由 create_all 建好的表"""
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing = _existing_tables()

    if "documents" not in existing:
        op.create_table(
            "documents",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("file_name", sa.String(length=255), nullable=False),
            sa.Column("file_url", sa.Text(), nullable=False),
            sa.Column("mime_type", sa.String(length=100), nullable=False),
            sa.Column("file_size", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    if "document_ai_results" not in existing:
        op.create_table(
            "document_ai_results",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("doc_type", sa.String(length=50), nullable=False),
            sa.Column("confidence", sa.Numeric(precision=5, scale=2), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("risks", postgresql.JSONB(), nullable=True),
            sa.Column("extracted_data", postgresql.JSONB(), nullable=False),
            sa.Column("ai_model", sa.String(length=50), nullable=True),
            sa.Column("processing_time", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if "document_ocr_results" not in existing:
        op.create_table(
            "document_ocr_results",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("raw_text", sa.Text(), nullable=False),
            sa.Column("page_count", sa.Integer(), nullable=False),
            sa.Column("ocr_confidence", sa.Numeric(precision=5, scale=2), nullable=True),
            sa.Column("ocr_service", sa.String(length=50), nullable=True),
            sa.Column("processing_time", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if "document_chat_logs" not in existing:
        op.create_table(
            "document_chat_logs",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("answer", sa.Text(), nullable=False),
            sa.Column("ai_model", sa.String(length=50), nullable=True),
            sa.Column("response_time", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )

    if "created_records" not in existing:
        op.create_table(
            "created_records",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "source_document_id", postgresql.UUID(as_uuid=True), nullable=False
            ),
            sa.Column("record_type", sa.String(length=50), nullable=False),
            sa.Column("payload", postgresql.JSONB(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.ForeignKeyConstraint(
                ["source_document_id"], ["documents.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    # 依外鍵相依的反序刪除
    for table in (
        "created_records",
        "document_chat_logs",
        "document_ocr_results",
        "document_ai_results",
        "documents",
    ):
        op.drop_table(table)
