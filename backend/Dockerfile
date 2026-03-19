# Backend Dockerfile for FastAPI
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# PaddleOCR ARM64 Docker Fix: Environment Variables
# 解決 Segmentation fault 問題
ENV OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    NUMBA_NUM_THREADS=1 \
    PADDLE_THREAD_COUNT=1 \
    FLAGS_use_mkldnn=0 \
    FLAGS_use_xdnn=0 \
    GOTOBLAS_NUM_THREADS=1 \
    VECLIB_MAXIMUM_THREADS=1 \
    CUDA_VISIBLE_DEVICES="" \
    PADDLE_READER_POOL_SIZE=1

# Install system dependencies
# PaddleOCR ARM64 Docker Fix: 添加 libgomp1 等必要庫
RUN apt-get update && apt-get install -y \
    postgresql-client \
    tesseract-ocr \
    tesseract-ocr-chi-tra \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/health')"

# Start command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
