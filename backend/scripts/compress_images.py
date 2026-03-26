"""
批次壓縮圖片腳本

壓縮 data/processed/ 目錄下超過 5MB 的圖片檔案。
"""

import sys
from pathlib import Path

# 添加專案根目錄到 Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.lib.ocr_enhanced.image_utils import batch_compress_directory


def main():
    """主函數"""
    print("=" * 60)
    print("批次壓縮圖片工具")
    print("=" * 60)

    # 要處理的目錄
    directories = [
        project_root / "data" / "processed",
        project_root.parent / "data" / "processed",  # 也檢查專案根目錄的 data/
    ]

    total_results = {
        "total": 0,
        "compressed": 0,
        "skipped": 0,
        "failed": 0,
        "space_saved_mb": 0.0
    }

    for directory in directories:
        if not directory.exists():
            print(f"\n⏭️  跳過不存在的目錄: {directory}")
            continue

        print(f"\n{'=' * 60}")
        print(f"處理目錄: {directory}")
        print(f"{'=' * 60}")

        # 處理 PNG 檔案
        results = batch_compress_directory(
            str(directory),
            pattern="*.png",
            max_size_mb=4.5
        )

        # 累加結果
        for key in total_results:
            total_results[key] += results[key]

    # 顯示總結
    print("\n" + "=" * 60)
    print("處理總結")
    print("=" * 60)
    print(f"總檔案數: {total_results['total']}")
    print(f"已壓縮: {total_results['compressed']}")
    print(f"已跳過: {total_results['skipped']}")
    print(f"失敗: {total_results['failed']}")
    print(f"節省空間: {total_results['space_saved_mb']:.2f} MB")
    print("=" * 60)


if __name__ == "__main__":
    main()
