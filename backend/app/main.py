"""
AI Document Intelligence Demo - FastAPI Backend
Main application entry point
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import documents, chat, ocr_test
from app.config import settings

# 配置日誌級別為 INFO
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 設定特定模組的日誌級別
logging.getLogger('app.lib.multi_type_ocr').setLevel(logging.INFO)
logging.getLogger('app.lib.llm_service').setLevel(logging.INFO)

# Create FastAPI app instance
app = FastAPI(
    title="DocuMind AI 文件智能處理系統",
    description="""
    ## 🤖 AI 文件智能處理 API

    提供以下功能：

    ### 📄 OCR 辨識與增強
    - **OCR 測試**: 上傳 PDF/圖片進行 OCR 辨識測試
    - **視覺修正**: 使用 LLM 看圖修正 OCR 錯誤
    - **多頁處理**: 自動處理多頁 PDF 文件
    - **準確率對比**: 對比原始 OCR、規則後處理、LLM 修正的效果

    ### 📁 文件管理
    - 文件上傳、查詢、刪除
    - 文件分類與標籤

    ### 💬 智能對話
    - 基於文件內容的 AI 問答
    - 上下文理解與推理

    ---

    **版本**: 1.0.0
    **技術棧**: FastAPI + Vue 3 + PostgreSQL
    """,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(documents.router, prefix="/api/v1/documents", tags=["📁 文件管理"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["💬 智能對話"])
app.include_router(ocr_test.router, prefix="/api/v1/ocr", tags=["📄 OCR 辨識"])


@app.get("/", tags=["系統"])
async def root():
    """
    ## 根路徑

    檢查 API 服務是否運行中

    **返回**: 服務狀態資訊
    """
    return {
        "message": "DocuMind AI 文件智能處理系統",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/api/health", tags=["系統"])
async def health_check():
    """
    ## 健康檢查

    檢查 API 服務健康狀態

    **返回**: 健康狀態
    """
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
