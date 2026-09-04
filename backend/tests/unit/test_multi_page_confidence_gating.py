"""_apply_confidence_gating 的多頁信心度彙整必須取最大值，不得逐頁覆蓋。

2026-09-03 發現的真實案例：一份 4 頁謄本，欄位散在多頁抽取
（地號在 p1/p2、建號在 p3/p4），原本用
`field_confidences.update(page_fields)` 逐頁覆蓋——後面頁面即使沒抽到
某欄位（信心度 0.0）也會蓋掉前面頁面已抽到的高信心度值。

實測數字（線上真實回應）：

    p1: {land_number: 0.9, building_number: 0.0, area: 0.9, owner: 0.9}
    p2: {land_number: 0.9, building_number: 0.0, area: 0.0, owner: 0.0}
    p3: {land_number: 0.0, building_number: 0.9, area: 0.9, owner: 0.9}
    p4: {land_number: 0.0, building_number: 0.9, area: 0.0, owner: 0.0}

    update() 彙整結果：land_number=0.0, area=0.0, owner=0.0（只剩 building_number=0.9）
    正確彙整（取最大值）：land_number=0.9, building_number=0.9, area=0.9, owner=0.9

四個關鍵欄位裡三個被錯誤覆蓋成 0.0，導致明明已抽到的欄位仍被判定需要複核。
"""

import pytest

from app.api.v1.analyze import _apply_confidence_gating


def _page(land=0.0, building=0.0, area=0.0, owner=0.0):
    return {
        "ocr_raw": {"text": "x", "confidence": 0.9},
        "structured_data": {
            "land_number": "0555-0000" if land else None,
            "building_number": "00004-000" if building else None,
            "area": "3,406.98" if area else None,
            "owner": "林順山" if owner else None,
            "field_confidences": {
                "land_number": land,
                "building_number": building,
                "area": area,
                "owner": owner,
            },
        },
    }


class TestMultiPageConfidenceTakesMax:
    def test_scattered_high_confidence_fields_survive(self, feedback_session):
        """重現真實案例：四頁各自殘缺，合併後應保留每個欄位曾出現過的最高信心度"""
        pages = [
            _page(land=0.9, building=0.0, area=0.9, owner=0.9),
            _page(land=0.9, building=0.0, area=0.0, owner=0.0),
            _page(land=0.0, building=0.9, area=0.9, owner=0.9),
            _page(land=0.0, building=0.9, area=0.0, owner=0.0),
        ]
        result = {"document_type": "transcript", "pages": pages}
        _apply_confidence_gating(result, feedback_session)

        fc = result["field_confidences"]
        assert fc["land_number"] == 0.9
        assert fc["building_number"] == 0.9
        assert fc["area"] == 0.9
        assert fc["owner"] == 0.9

    def test_all_fields_high_confidence_does_not_need_review(self, feedback_session):
        """核心行為驗證：欄位實際上都齊全時,不該因為彙整方式錯誤而誤判需複核"""
        pages = [
            _page(land=0.9, building=0.0, area=0.9, owner=0.9),
            _page(land=0.0, building=0.9, area=0.0, owner=0.0),
        ]
        result = {"document_type": "transcript", "pages": pages}
        _apply_confidence_gating(result, feedback_session)

        assert result["needs_review"] is False, (
            f"欄位彙整後皆為高信心度,不應判定需複核。實際 field_confidences="
            f"{result['field_confidences']}"
        )


class TestOptionalFieldsDoNotForceReview:
    """選配欄位缺席不得觸發人工複核。

    2026-09-04 實測：NFKC 修正後一份謄本抽到 17/23 欄、全部 0.9、
    needs_confirmation 為空，needs_review 卻仍是 True——因為
    QualityAssessor 取最差值，而 field_confidences 裡還有 6 個選配欄位
    是 0.0（附屬建物、共有部分、查封註記等，這份謄本本來就沒有）。

    等於一份抽得完整的謄本，因為「沒有附屬建物」「沒有被查封」而被判需複核。
    """

    def _page_with_optional_zeros(self):
        return {
            "ocr_raw": {"text": "x", "confidence": 0.95},
            "structured_data": {
                "land_number": "0555-0000",
                "owner": "林順山",
                # 選配欄位：這份文件本來就沒有
                "seizure_mark": None,
                "shared_area": None,
                "field_confidences": {
                    "land_number": 0.9,
                    "owner": 0.9,
                    "seizure_mark": 0.0,
                    "shared_area": 0.0,
                },
                # 抽取器已依 REQUIRED_FIELDS 算好：選配欄位不在待確認清單
                "needs_confirmation": [],
            },
        }

    def test_optional_zero_confidence_does_not_trigger_review(self, feedback_session):
        result = {
            "document_type": "transcript",
            "pages": [self._page_with_optional_zeros()],
        }
        _apply_confidence_gating(result, feedback_session)

        assert result["needs_review"] is False, (
            "選配欄位（沒有附屬建物、沒有查封）不該讓完整的謄本被判需複核。"
            f"實際 field_confidences={result['field_confidences']}"
        )

    def test_field_confidences_still_reported_in_full(self, feedback_session):
        """判定時排除選配欄位，但回傳給下游的仍須完整——下游要知道每欄的狀態"""
        result = {
            "document_type": "transcript",
            "pages": [self._page_with_optional_zeros()],
        }
        _apply_confidence_gating(result, feedback_session)

        assert "seizure_mark" in result["field_confidences"]
        assert result["field_confidences"]["seizure_mark"] == 0.0

    def test_required_field_missing_still_triggers_review(self, feedback_session):
        """必要欄位真的沒抽到時，仍須進複核——不能為了放行就全部忽略"""
        page = self._page_with_optional_zeros()
        page["structured_data"]["field_confidences"]["land_number"] = 0.0
        page["structured_data"]["land_number"] = None
        page["structured_data"]["needs_confirmation"] = ["land_number"]

        result = {"document_type": "transcript", "pages": [page]}
        _apply_confidence_gating(result, feedback_session)

        assert result["needs_review"] is True
