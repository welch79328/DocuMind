"""C2：用目前 checkout 的程式，對存檔回應的 pages 重算 document_fields，對照存檔值。

用法（在 backend/ 下，用 venv python）：python replay.py <輸出 json>
每份判三項：(a) 各頁 structured_data 的鍵路徑（巢狀展開、扣中繼鍵）全在重算結果；
(b) 存檔 document_fields 有的葉路徑，重算值相同；(c) 重算多出的葉路徑，值都是空值。
field_confidences 整包當一個葉比對。
另報「重算 vs 存檔完全相同」的份數（改前應為全部，作為工具正對照）。
"""
import json
import pathlib
import subprocess
import sys

from app.services.analyze_service import _attach_full_transcripts, _merge_page_structured_data

ROOTS = [
    pathlib.Path.home() / "jgb-archive/bedrock-qwen-switch-20261028",
    pathlib.Path.home() / "jgb-archive/qwen-direct-read-20261029",
]
META_POPPED = {"has_building_evidence", "share_slots"}
EMPTY = (None, "", [], {})


def responses():
    for root in ROOTS:
        for p in sorted(root.rglob("*.json")):
            try:
                d = json.loads(p.read_text())
            except Exception:
                continue
            r = d.get("response", d) if isinstance(d, dict) else None
            if isinstance(r, dict) and isinstance(r.get("pages"), list) and "document_fields" in r:
                yield str(p), r
            elif isinstance(r, dict) and isinstance(r.get("results"), list):
                for i, it in enumerate(r["results"]):
                    rr = it.get("result") if isinstance(it, dict) else None
                    if isinstance(rr, dict) and isinstance(rr.get("pages"), list) and "document_fields" in rr:
                        yield f"{p}#{i}", rr


def paths(d, prefix=()):
    """dict 的所有鍵路徑(巢狀展開);回 {路徑: 值},值為葉(非 dict)或空 dict。"""
    out = {}
    for k, v in d.items():
        p = prefix + (k,)
        if isinstance(v, dict) and v and k != "field_confidences":
            out.update(paths(v, p))
        else:
            out[p] = v
    return out


def page_keys(pages):
    keys = set()
    for pg in pages:
        sd = pg.get("structured_data")
        if isinstance(sd, dict):
            keys |= {p for p in paths(sd) if p[0] not in META_POPPED}
    return keys


def main():
    out = pathlib.Path(sys.argv[1])
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "app"], capture_output=True, text=True).stdout.strip()
    rows, by_type = [], {}
    for name, r in responses():
        dt = r.get("document_type")
        pages = r["pages"]
        archived = r.get("document_fields")
        new = _merge_page_structured_data(json.loads(json.dumps(pages)))
        _attach_full_transcripts(new, pages, dt)
        archived = archived or {}
        new = new or {}
        np_, ap = paths(new), paths(archived)
        missing = sorted(".".join(p) for p in page_keys(pages) - set(np_))
        changed = sorted(".".join(p) for p in ap if json.dumps(ap[p], sort_keys=True) != json.dumps(np_.get(p, "<absent>"), sort_keys=True))
        added = sorted(".".join(p) for p in set(np_) - set(ap))
        added_nonempty = sorted(".".join(p) for p in set(np_) - set(ap) if np_[p] not in EMPTY)
        identical = json.dumps(new, sort_keys=True) == json.dumps(archived, sort_keys=True)
        ok = not missing and not changed and not added_nonempty
        rows.append({"file": name, "type": dt, "a_missing": missing, "b_changed": changed,
                     "added": added, "c_added_nonempty": added_nonempty, "identical": identical, "ok": ok})
        t = by_type.setdefault(dt, {"n": 0, "ok": 0, "identical": 0, "lacking_page_keys": 0})
        t["n"] += 1
        t["ok"] += ok
        t["identical"] += identical
        t["lacking_page_keys"] += bool(missing)
    if not rows:
        print("沒有讀到任何存檔回應，前置條件不成立", file=sys.stderr)
        sys.exit(2)
    summary = {"head": head, "app_dirty": bool(dirty), "total": len(rows), "by_type": by_type,
               "all_ok": all(x["ok"] for x in rows)}
    out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1))
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    bad = [x for x in rows if not x["ok"]][:5]
    for x in bad:
        print("例:", x["type"], x["file"].split("jgb-archive/")[-1], "缺", x["a_missing"][:6], "變", x["b_changed"][:6], "多非空", x["c_added_nonempty"][:6])


if __name__ == "__main__":
    main()
