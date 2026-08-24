"""add feedback layer tables (review_queue_items, correction_samples, evaluation_records)

Revision ID: f1a2b3c4d5e6
Revises: d18dbadf87e7
Create Date: 2026-07-04 00:00:00.000000

回饋學習層三張新表(純加法,不影響既有表):
- review_queue_items: 人工複核佇列
- correction_samples: 校正樣本 / 黃金範例(含 layout_signature、purpose、GIN 索引)
- evaluation_records: 評估紀錄
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'a0b1c2d3e4f5'  # 2026-08-24 插入 baseline:本遷移的外鍵需要 documents 表
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # review_queue_items(需先建立,供 correction_samples 外鍵參照)
    op.create_table(
        'review_queue_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('document_type', sa.String(length=50), nullable=False),
        sa.Column('overall_confidence', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('reviewer', sa.String(length=100), nullable=True),
        sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('original_result', postgresql.JSONB(), nullable=False),
        sa.Column('corrected_result', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_review_status', 'review_queue_items', ['status'], unique=False)
    op.create_index('idx_review_doc_type', 'review_queue_items', ['document_type'], unique=False)

    # correction_samples
    op.create_table(
        'correction_samples',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_type', sa.String(length=50), nullable=False),
        sa.Column('layout_signature', sa.String(length=120), nullable=False),
        sa.Column('purpose', sa.String(length=10), nullable=False),
        sa.Column('input_ref', sa.Text(), nullable=False),
        sa.Column('corrected_fields', postgresql.JSONB(), nullable=False),
        sa.Column('is_golden', sa.Boolean(), nullable=False),
        sa.Column('source_review_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['source_review_id'], ['review_queue_items.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'idx_sample_select', 'correction_samples',
        ['document_type', 'purpose', 'is_golden', 'layout_signature'], unique=False,
    )
    op.create_index(
        'idx_sample_corrected_fields', 'correction_samples',
        ['corrected_fields'], unique=False, postgresql_using='gin',
    )

    # evaluation_records
    op.create_table(
        'evaluation_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_type', sa.String(length=50), nullable=False),
        sa.Column('metric_type', sa.String(length=30), nullable=False),
        sa.Column('value', sa.Numeric(precision=6, scale=4), nullable=False),
        sa.Column('labeled_set_version', sa.String(length=50), nullable=False),
        sa.Column('is_baseline', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_eval_type_metric', 'evaluation_records', ['document_type', 'metric_type'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_eval_type_metric', table_name='evaluation_records')
    op.drop_table('evaluation_records')

    op.drop_index('idx_sample_corrected_fields', table_name='correction_samples')
    op.drop_index('idx_sample_select', table_name='correction_samples')
    op.drop_table('correction_samples')

    op.drop_index('idx_review_doc_type', table_name='review_queue_items')
    op.drop_index('idx_review_status', table_name='review_queue_items')
    op.drop_table('review_queue_items')
