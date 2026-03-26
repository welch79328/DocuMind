"""
圖片處理工具模組

提供圖片壓縮、大小檢查等工具函數。
"""

import os
from pathlib import Path
from typing import Tuple, Optional
import numpy as np
import cv2
from PIL import Image


def get_file_size_mb(file_path: str) -> float:
    """
    獲取檔案大小（MB）

    Args:
        file_path: 檔案路徑

    Returns:
        檔案大小（MB）
    """
    if not os.path.exists(file_path):
        return 0.0
    return os.path.getsize(file_path) / (1024 * 1024)


def compress_image_to_limit(
    image: np.ndarray,
    output_path: str,
    max_size_mb: float = 4.5,
    initial_quality: int = 95,
    min_quality: int = 50
) -> Tuple[str, float]:
    """
    將圖片壓縮到指定大小限制以下

    策略：
    1. 先嘗試降低 JPEG 品質
    2. 如果還是太大，則降低解析度

    Args:
        image: OpenCV 圖片（BGR 或灰階）
        output_path: 輸出路徑
        max_size_mb: 最大檔案大小（MB），預設 4.5MB（留一些 buffer）
        initial_quality: 初始 JPEG 品質（0-100）
        min_quality: 最小可接受品質

    Returns:
        (輸出路徑, 最終檔案大小MB)
    """
    output_path = str(output_path)

    # 確保輸出目錄存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 嘗試不同的壓縮品質
    quality = initial_quality

    while quality >= min_quality:
        # 保存為 JPEG 格式
        temp_path = output_path.replace('.png', '.jpg')
        cv2.imwrite(temp_path, image, [cv2.IMWRITE_JPEG_QUALITY, quality])

        file_size = get_file_size_mb(temp_path)

        if file_size <= max_size_mb:
            print(f"✅ 壓縮成功: {file_size:.2f} MB (品質: {quality})")
            return temp_path, file_size

        # 降低品質
        quality -= 10

    # 如果降低品質還不夠，則降低解析度
    print(f"⚠️  降低品質不足，開始降低解析度...")

    scale = 0.9
    while scale >= 0.3:
        h, w = image.shape[:2]
        new_h, new_w = int(h * scale), int(w * scale)
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

        temp_path = output_path.replace('.png', '.jpg')
        cv2.imwrite(temp_path, resized, [cv2.IMWRITE_JPEG_QUALITY, min_quality])

        file_size = get_file_size_mb(temp_path)

        if file_size <= max_size_mb:
            print(f"✅ 壓縮成功: {file_size:.2f} MB (縮放: {scale:.1%}, 品質: {min_quality})")
            return temp_path, file_size

        scale -= 0.1

    # 最後手段：使用極低品質
    temp_path = output_path.replace('.png', '.jpg')
    cv2.imwrite(temp_path, resized, [cv2.IMWRITE_JPEG_QUALITY, 30])
    file_size = get_file_size_mb(temp_path)
    print(f"⚠️  最終壓縮: {file_size:.2f} MB (品質: 30)")

    return temp_path, file_size


def save_image_smart(
    image: np.ndarray,
    output_path: str,
    max_size_mb: float = 4.5,
    prefer_png: bool = False
) -> Tuple[str, float]:
    """
    智能保存圖片（自動處理大小限制）

    Args:
        image: OpenCV 圖片（BGR 或灰階）
        output_path: 輸出路徑
        max_size_mb: 最大檔案大小（MB）
        prefer_png: 優先使用 PNG 格式（如果大小允許）

    Returns:
        (實際保存路徑, 檔案大小MB)
    """
    output_path = str(output_path)

    # 先嘗試保存為 PNG
    if prefer_png or output_path.endswith('.png'):
        cv2.imwrite(output_path, image)
        file_size = get_file_size_mb(output_path)

        if file_size <= max_size_mb:
            print(f"✅ PNG 保存成功: {file_size:.2f} MB")
            return output_path, file_size
        else:
            print(f"⚠️  PNG 過大 ({file_size:.2f} MB)，轉為 JPEG 壓縮...")
            os.remove(output_path)

    # 使用壓縮
    return compress_image_to_limit(image, output_path, max_size_mb)


def check_and_compress_if_needed(
    file_path: str,
    max_size_mb: float = 4.5
) -> Tuple[str, float]:
    """
    檢查已存在的圖片，如果超過大小限制則壓縮

    Args:
        file_path: 圖片路徑
        max_size_mb: 最大檔案大小（MB）

    Returns:
        (最終檔案路徑, 檔案大小MB)
    """
    file_size = get_file_size_mb(file_path)

    if file_size <= max_size_mb:
        print(f"✅ 檔案大小正常: {file_size:.2f} MB")
        return file_path, file_size

    print(f"⚠️  檔案過大 ({file_size:.2f} MB)，開始壓縮...")

    # 讀取圖片
    image = cv2.imread(file_path)
    if image is None:
        raise ValueError(f"無法讀取圖片: {file_path}")

    # 壓縮並覆蓋原檔案
    output_path, new_size = compress_image_to_limit(image, file_path, max_size_mb)

    # 如果輸出路徑改變（PNG -> JPG），刪除原檔案
    if output_path != file_path and os.path.exists(file_path):
        os.remove(file_path)
        print(f"🗑️  已刪除原始 PNG 檔案")

    return output_path, new_size


def batch_compress_directory(
    directory: str,
    pattern: str = "*.png",
    max_size_mb: float = 4.5
) -> dict:
    """
    批次壓縮目錄下的圖片

    Args:
        directory: 目錄路徑
        pattern: 檔案模式
        max_size_mb: 最大檔案大小（MB）

    Returns:
        處理結果字典
    """
    from pathlib import Path

    results = {
        "total": 0,
        "compressed": 0,
        "skipped": 0,
        "failed": 0,
        "space_saved_mb": 0.0
    }

    directory = Path(directory)
    files = list(directory.glob(pattern))

    print(f"\n📁 掃描目錄: {directory}")
    print(f"🔍 找到 {len(files)} 個檔案\n")

    for file_path in files:
        results["total"] += 1
        original_size = get_file_size_mb(str(file_path))

        print(f"\n處理: {file_path.name} ({original_size:.2f} MB)")

        try:
            if original_size <= max_size_mb:
                print(f"  ⏭️  跳過（大小正常）")
                results["skipped"] += 1
                continue

            new_path, new_size = check_and_compress_if_needed(str(file_path), max_size_mb)

            space_saved = original_size - new_size
            results["space_saved_mb"] += space_saved
            results["compressed"] += 1

            print(f"  💾 節省空間: {space_saved:.2f} MB")

        except Exception as e:
            print(f"  ❌ 失敗: {e}")
            results["failed"] += 1

    return results
