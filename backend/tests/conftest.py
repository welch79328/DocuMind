"""
Pytest 全域設定

在載入應用設定(app.config.settings)前,將本地儲存路徑指向可寫的臨時目錄,
避免在非容器環境(無 /app 寫入權限)下,StorageService 初始化建立
預設路徑 /app/uploads 時發生 OSError。
"""

import os
import tempfile

import pytest

# 必須在任何 app.* 模組被匯入前設定,才能被 pydantic Settings 讀取
_TEST_UPLOAD_DIR = tempfile.mkdtemp(prefix="documind_test_uploads_")
os.environ.setdefault("LOCAL_STORAGE_PATH", _TEST_UPLOAD_DIR)
os.environ.setdefault("STORAGE_TYPE", "local")


@pytest.fixture
def feedback_session():
    """
    提供 in-memory SQLite session,僅建立回饋層三張新表。

    模型的 UUID/JSONB 欄位於 sqlite 方言自動降級(見 models/_column_types),
    使服務層可離線做真實資料庫測試(PG 專屬型別於 production 不受影響)。
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.database import Base
    from app.models import ReviewQueueItem, CorrectionSample, EvaluationRecord

    tables = [
        ReviewQueueItem.__table__,
        CorrectionSample.__table__,
        EvaluationRecord.__table__,
    ]
    # StaticPool + check_same_thread=False:共用單一連線,使 in-memory DB
    # 在同步端點的 worker thread 也可見(FastAPI 同步路由於 threadpool 執行)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=tables)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=tables)
