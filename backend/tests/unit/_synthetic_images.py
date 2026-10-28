"""
測試用合成影像(不依賴任何外部檔案、無亂數,每次產生的位元組相同)。

供 Bedrock 分流的影像測試使用(test_llm_bedrock_routing_images.py):
12MP 與 24MP 的 JPEG、從 JPEG 做成的無文字層 PDF,以及超過 Bedrock
單張 3.75MB 上限的 PNG。

圖案刻意用座標函數而不是亂數:亂數的 JPEG 很大、而且產生器版本一換就不同;
座標函數只依賴 numpy 的整數運算,跨機器結果一致。
"""

from __future__ import annotations

import io

import numpy as np
from PIL import Image


def _pattern(width: int, height: int) -> np.ndarray:
    """平滑漸層 + 棋盤 + 斜紋,讓縮圖與 JPEG 都有東西可壓、可比對。"""
    y = np.arange(height, dtype=np.uint32)[:, None]
    x = np.arange(width, dtype=np.uint32)[None, :]
    r = (x * 255 // max(1, width - 1)).astype(np.uint8)
    g = (y * 255 // max(1, height - 1)).astype(np.uint8)
    b = ((((x // 97) + (y // 89)) % 2) * 150 + ((x + 2 * y) % 64)).astype(np.uint8)
    r = np.broadcast_to(r, (height, width))
    g = np.broadcast_to(g, (height, width))
    b = np.broadcast_to(b, (height, width))
    return np.ascontiguousarray(np.stack([r, g, b], axis=-1))


def synthetic_jpeg(width: int, height: int, quality: int = 90) -> bytes:
    """產生指定尺寸的 JPEG 位元組(12MP 用 4000x3000、24MP 用 6000x4000)。"""
    buf = io.BytesIO()
    Image.fromarray(_pattern(width, height), "RGB").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def pdf_from_jpeg(jpeg_bytes: bytes) -> bytes:
    """把 JPEG 鋪滿一頁 A4 的 PDF(沒有文字層,analyze_service 會走 fitz 渲染 + OCR)。"""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=jpeg_bytes)
    data = doc.tobytes()
    doc.close()
    return data


def noisy_png(width: int, height: int) -> bytes:
    """幾乎無法壓縮的 PNG(用整數雜湊產生,不用亂數),用來做出超過 3.75MB 的影像。"""
    y = np.arange(height, dtype=np.uint64)[:, None]
    x = np.arange(width, dtype=np.uint64)[None, :]
    channels = []
    for salt in (0x9E3779B1, 0x85EBCA77, 0xC2B2AE3D):
        h = (x * np.uint64(73856093)) ^ (y * np.uint64(19349663)) ^ np.uint64(salt)
        h = (h * np.uint64(0x27D4EB2D)) & np.uint64(0xFFFFFFFF)
        h ^= h >> np.uint64(15)
        channels.append((h & np.uint64(0xFF)).astype(np.uint8))
    array = np.ascontiguousarray(np.stack(channels, axis=-1))
    buf = io.BytesIO()
    Image.fromarray(array, "RGB").save(buf, format="PNG")
    return buf.getvalue()
