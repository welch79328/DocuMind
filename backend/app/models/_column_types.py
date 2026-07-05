"""
跨方言欄位型別輔助

production 使用 PostgreSQL 專屬型別(UUID / JSONB);於單元測試的 SQLite
方言自動降級(UUID → String(36)、JSONB → JSON),使服務層可用 in-memory
SQLite 進行真實資料庫測試,而不影響 production 的 PG 型別與遷移。
"""

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


def uuid_column_type():
    """UUID 欄位型別(sqlite 降級為 String(36))"""
    return UUID(as_uuid=True).with_variant(sa.String(36), "sqlite")


def jsonb_column_type():
    """JSONB 欄位型別(sqlite 降級為 JSON)"""
    return JSONB().with_variant(sa.JSON(), "sqlite")


def new_uuid() -> str:
    """產生字串型 UUID(跨方言相容:PostgreSQL 的 UUID 欄位亦接受字串形式)"""
    return str(uuid.uuid4())
