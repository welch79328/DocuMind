"""
Few-shot 選取器與版型指紋

版型指紋(v1):以粗略版面特徵區分不同版型,供「同版型優先」選取。
FewShotSelector:依策略選取可回灌的 few-shot 範例——
  強制同類型 → 同版型優先 → 黃金優先 → 最近 N,上限控成本;僅取 train(防洩漏)。

註:精確版型/影像相似度為 Phase 2 PoC;v1 先以此基線確保「不注入不相關版型」。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# 版型指紋所用的關鍵標題詞(判別文件版型)
_LAYOUT_KEYWORDS = [
    "謄本", "登記", "所有權", "合約", "租賃", "立合約書",
    "帳單", "水費", "電費", "管理費", "應繳",
]


def _bucket(value: int, thresholds: List[int]) -> int:
    for i, threshold in enumerate(thresholds):
        if value < threshold:
            return i
    return len(thresholds)


def compute_layout_signature(page_result: Optional[Dict[str, Any]]) -> str:
    """
    由頁面結果計算版型指紋(v1)

    以行數分桶 + 文字長度分桶 + 關鍵標題詞組成穩定字串;
    僅需「足以區分不同版型」,非精確影像相似度。
    """
    text = ""
    if isinstance(page_result, dict):
        for key in ("ocr_raw", "rule_postprocessed"):
            section = page_result.get(key) or {}
            if isinstance(section, dict) and section.get("text"):
                text = section["text"]
                break

    lines = [ln for ln in text.splitlines() if ln.strip()]
    line_bucket = _bucket(len(lines), [10, 30, 60])
    length_bucket = _bucket(len(text), [200, 800, 2000])
    keywords = "".join(k for k in _LAYOUT_KEYWORDS if k in text) or "none"
    return f"L{line_bucket}-C{length_bucket}-{keywords}"


class FewShotSelector:
    """few-shot 範例選取器"""

    def __init__(self, sample_service, max_examples: int = 5):
        self.samples = sample_service
        self.max_examples = max_examples

    def select(
        self,
        document_type: Any,
        layout_signature: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        選取可回灌的 few-shot 範例。

        list_for_fewshot 已保證「僅 train、同類型、黃金優先(其次最近)」;
        本方法再以「同版型優先」穩定排序(Python 穩定排序保留組內既有順序)。
        """
        # 僅 train、同類型;已依 (黃金, 最近) 排序
        candidates = self.samples.list_for_fewshot(document_type)

        if layout_signature:
            candidates = sorted(
                candidates,
                key=lambda s: 1 if s.get("layout_signature") == layout_signature else 0,
                reverse=True,
            )

        return candidates[: self.max_examples]

    def seed(
        self,
        document_type: Any,
        examples: List[Dict[str, Any]],
    ) -> List[str]:
        """種子範例冷啟動(委派校正樣本服務,存為 train)"""
        ids = []
        for example in examples:
            ids.append(self.samples.save(
                document_type=document_type,
                input_ref=example.get("input_ref", ""),
                corrected_fields=example.get("corrected_fields", {}),
                layout_signature=example.get("layout_signature", ""),
                purpose="train",
            ))
        return ids
