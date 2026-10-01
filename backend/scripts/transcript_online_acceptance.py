"""
謄本線上驗收:把 8 份範本送到指定的 DocuMind,逐欄比對基準結果,並列出耗時。

為什麼要送線上:本機測試環境不裝 OCR 引擎,圖片與掃描件的辨識品質與速度只能在線上量。
本機 unit 測試只證明「給定文字時抽取對不對」,證明不了「這張圖實際讀得出什麼、要多久」。

用法(在 backend/ 下):
    python scripts/transcript_online_acceptance.py --base http://54.248.201.66:8085 --out /tmp/acceptance

  - 比對對象是 data/transcript_samples/expected/*.json(最近一次確認過的線上 document_fields)。
    改了抽取邏輯、預期輸出會變時,先確認新結果對照 truth.json 是對的,再用 --update-expected 更新基準。
  - 一律 enable_llm=false:不產生費用,而且量到的是規則抽取本身。
  - ⚠️ 每份圖片都會被判定需要人工複核,在線上複核佇列留下一筆(API 目前沒有略過選項)。
    每跑一輪約多 7 筆,跑完記下印出的 review id。

範本說明見 docs/testing/transcript-online-acceptance.md。
"""

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

DATA = Path(__file__).resolve().parents[1] / "data"
SAMPLES = DATA / "transcript_samples"
FILES = {
    "01_shilin_land": SAMPLES / "01_shilin_land.jpg",
    "02_shilin_build": SAMPLES / "02_shilin_build.jpg",
    "03_kcg_build_multifloor": SAMPLES / "03_kcg_build_multifloor.jpg",
    "04_kcg_apartment_shared": SAMPLES / "04_kcg_apartment_shared.jpg",
    "05_ntpc_land_mortgage": SAMPLES / "05_ntpc_land_mortgage.jpg",
    "06_ruifang_build": SAMPLES / "06_ruifang_build.jpg",
    "07_repo_build_scan": DATA / "建物謄本.jpg",
    "08_repo_etranscript": DATA / "建物土地謄本-杭州南路一段.pdf",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="例如 http://54.248.201.66:8085")
    ap.add_argument("--out", required=True, help="完整回應存放目錄")
    ap.add_argument("--update-expected", action="store_true",
                    help="以這次結果覆寫基準(確認新結果正確後才用)")
    args = ap.parse_args()

    missing = [name for name, path in FILES.items() if not path.exists()]
    if missing:
        print(f"範本檔不存在:{missing}", file=sys.stderr)
        return 2

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    url = args.base.rstrip("/") + "/api/v1/analyze"
    changed, review_ids = 0, []

    with httpx.Client(timeout=900) as client:
        for name, path in FILES.items():
            started = time.time()
            with path.open("rb") as fh:
                resp = client.post(
                    url,
                    files={"file": (path.name, fh)},
                    data={"document_type": "transcript", "enable_llm": "false"},
                )
            elapsed = time.time() - started
            if resp.status_code != 200:
                print(f"{name}: HTTP {resp.status_code} {resp.text[:200]}")
                changed += 1
                continue
            body = resp.json()
            (out / f"{name}.json").write_text(json.dumps(body, ensure_ascii=False, indent=2))
            if body.get("review_item_id"):
                review_ids.append(body["review_item_id"])

            fields = body.get("document_fields") or {}
            expected_path = SAMPLES / "expected" / f"{name}.json"
            if args.update_expected:
                expected_path.write_text(json.dumps(fields, ensure_ascii=False, indent=2, sort_keys=True))
                print(f"{name}: 基準已更新 | {elapsed:.1f}s")
                continue
            expected = json.loads(expected_path.read_text())
            diff = sorted(k for k in set(expected) | set(fields) if expected.get(k) != fields.get(k))
            changed += bool(diff)
            print(f"{name}: {'與基準相同' if not diff else '差異 ' + str(diff)} | "
                  f"伺服器 {body['stats']['total_time_ms'] / 1000:.1f}s / 往返 {elapsed:.1f}s")

    print(f"\n新增複核佇列項目 {len(review_ids)} 筆:{review_ids}")
    if args.update_expected:
        return 0
    print("全部與基準相同" if not changed else f"{changed} 份與基準不同,逐欄對照 truth.json 判斷是改善還是退步")
    return 0 if not changed else 1


if __name__ == "__main__":
    sys.exit(main())
