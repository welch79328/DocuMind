"""
測試版型指紋與 few-shot 選取策略(任務 9.1)

- compute_layout_signature:由頁面結果產生穩定版型指紋
- FewShotSelector.select:強制同類型 → 同版型優先 → 黃金優先 → 最近 N,上限控成本;
  僅取 train,holdout 絕不被選取

對應需求: 7.3
"""

import pytest

from app.services.few_shot_selector import FewShotSelector, compute_layout_signature
from app.services.correction_sample_service import CorrectionSampleService


@pytest.fixture
def ctx(feedback_session):
    samples = CorrectionSampleService(feedback_session)
    return FewShotSelector(samples, max_examples=3), samples


# --------------------------------------------------------------------------- #
class TestLayoutSignature:
    def test_returns_stable_string(self):
        page = {"ocr_raw": {"text": "土地登記第一類謄本\n地號 123\n面積 128.45", "confidence": 0.8}}
        sig1 = compute_layout_signature(page)
        sig2 = compute_layout_signature(page)
        assert isinstance(sig1, str) and sig1
        assert sig1 == sig2

    def test_different_layouts_differ(self):
        transcript = {"ocr_raw": {"text": "土地登記第一類謄本\n地號\n面積", "confidence": 0.8}}
        bill = {"ocr_raw": {"text": "水費帳單\n本期應繳 500 元\n戶號 A123", "confidence": 0.8}}
        assert compute_layout_signature(transcript) != compute_layout_signature(bill)

    def test_empty_page_handled(self):
        assert isinstance(compute_layout_signature({}), str)


# --------------------------------------------------------------------------- #
class TestSelect:
    def test_empty_when_no_samples(self, ctx):
        selector, _ = ctx
        assert selector.select("transcript") == []

    def test_same_type_only(self, ctx):
        selector, samples = ctx
        samples.save("transcript", "t1", {"area": "1"})
        samples.save("bill", "b1", {"amount": "1"})
        result = selector.select("transcript")
        refs = {r["input_ref"] for r in result}
        assert refs == {"t1"}

    def test_same_layout_ranked_first(self, ctx):
        selector, samples = ctx
        samples.save("transcript", "other", {"a": 1}, layout_signature="SIG-B")
        samples.save("transcript", "match", {"a": 2}, layout_signature="SIG-A")
        result = selector.select("transcript", layout_signature="SIG-A")
        assert result[0]["input_ref"] == "match"

    def test_golden_preferred(self, ctx):
        selector, samples = ctx
        samples.save("transcript", "plain", {"a": 1})
        gid = samples.save("transcript", "golden", {"a": 2})
        samples.mark_golden(gid, True)
        result = selector.select("transcript")
        assert result[0]["input_ref"] == "golden"

    def test_max_examples_cap(self, ctx):
        selector, samples = ctx  # max_examples=3
        for i in range(6):
            samples.save("transcript", f"s{i}", {"a": i})
        assert len(selector.select("transcript")) == 3

    def test_holdout_never_selected(self, ctx):
        selector, samples = ctx
        samples.save("transcript", "train1", {"a": 1}, purpose="train")
        samples.save("transcript", "hold1", {"a": 2}, purpose="holdout")
        refs = {r["input_ref"] for r in selector.select("transcript")}
        assert "hold1" not in refs
        assert refs == {"train1"}

    def test_selected_examples_usable_by_provider(self, ctx):
        # 選出的樣本應可直接供 provider few-shot 注入(含 input_ref / corrected_fields)
        selector, samples = ctx
        samples.save("transcript", "ref-x", {"area": "128.45"})
        example = selector.select("transcript")[0]
        assert "input_ref" in example
        assert example["corrected_fields"] == {"area": "128.45"}
