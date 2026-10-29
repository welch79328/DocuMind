"""document_fields 固定帶鍵(2.7.0,.kiro/specs/document-fields-fixed-keys C1)

站內幫手 2026-10-29 實測:看不出損壞的修繕照片,document_fields 沒有 damaged_items／defect_labels,
因為舊的合併只在值非空時才寫入鍵。改為:各頁有的鍵一律出現,各頁都空時值為頁面上的空值。
問答 context 維持改前內容(不含空值鍵),提示詞不變。
"""
import asyncio
import sys
from typing import Any, Dict

sys.path.insert(0, "backend")

from app.services import analyze_service
from app.services.analyze_service import AnalyzeService, _merge_page_structured_data


def page(structured):
    return {"structured_data": structured}


def _old_merge_fill_missing(target: Dict[str, Any], source: Dict[str, Any]) -> None:
    """改前的合併(2.6.0),只當問答 context 的對照組。"""
    for key, value in source.items():
        if key == "field_confidences" and isinstance(value, dict):
            existing = target.get(key)
            existing = existing if isinstance(existing, dict) else {}
            for fk, fv in value.items():
                if not isinstance(fv, (int, float)):
                    continue
                if fk not in existing or fv > existing[fk]:
                    existing[fk] = fv
            target[key] = existing
            continue
        if isinstance(value, dict):
            existing = target.get(key)
            if not isinstance(existing, dict):
                existing = {}
                target[key] = existing
            _old_merge_fill_missing(existing, value)
            continue
        current = target.get(key)
        is_missing = current is None or current == "" or current == []
        if is_missing and value not in (None, "", []):
            target[key] = value


class TestEmptyKeysArePresent:
    def test_repair_photo_without_damage_keeps_both_lists(self):
        """站內幫手回報的情境:看不出損壞時兩個陣列都要在、且為 []"""
        merged = _merge_page_structured_data([page(
            {"defect_labels": [], "damaged_items": [], "description": "", "confidence": 0.0}
        )])
        assert merged["defect_labels"] == []
        assert merged["damaged_items"] == []
        assert merged["description"] == ""
        assert merged["confidence"] == 0.0

    def test_null_value_keeps_key_as_null(self):
        merged = _merge_page_structured_data([page({"amount": None, "date": "2026-10-01"})])
        assert "amount" in merged and merged["amount"] is None
        assert merged["date"] == "2026-10-01"

    def test_empty_value_type_follows_page(self):
        merged = _merge_page_structured_data([page({"a": [], "b": "", "c": None})])
        assert merged["a"] == [] and merged["b"] == "" and merged["c"] is None


class TestFillAcrossPagesUnchanged:
    def test_earlier_empty_is_filled_by_later_value(self):
        merged = _merge_page_structured_data([
            page({"amount": None, "damaged_items": []}),
            page({"amount": "1,200", "damaged_items": ["水龍頭"]}),
        ])
        assert merged["amount"] == "1,200"
        assert merged["damaged_items"] == ["水龍頭"]

    def test_later_empty_does_not_overwrite_earlier_value(self):
        merged = _merge_page_structured_data([
            page({"amount": "1,200", "damaged_items": ["水龍頭"]}),
            page({"amount": None, "damaged_items": []}),
        ])
        assert merged["amount"] == "1,200"
        assert merged["damaged_items"] == ["水龍頭"]

    def test_key_only_on_later_page_still_appears(self):
        merged = _merge_page_structured_data([page({"a": "x"}), page({"b": None})])
        assert merged == {"a": "x", "b": None}


class TestMetaKeysStillRemoved:
    def test_has_building_evidence_and_share_slots_not_in_document_fields(self):
        merged = _merge_page_structured_data([page(
            {"owner": None, "has_building_evidence": False, "share_slots": []}
        )])
        assert "has_building_evidence" not in merged
        assert "share_slots" not in merged
        assert "owner" in merged


class TestNestedEmptyKeys:
    def test_contract_nested_empty_subkeys_are_kept(self):
        merged = _merge_page_structured_data([
            page({"parties": {"party_a": "王小明", "party_b": None},
                  "rental_terms": {"monthly_rent": None, "parking_fee": None}}),
            page({"parties": {"party_a": None, "party_b": None},
                  "rental_terms": {"monthly_rent": "25,000", "parking_fee": None}}),
        ])
        assert merged["parties"] == {"party_a": "王小明", "party_b": None}
        assert merged["rental_terms"] == {"monthly_rent": "25,000", "parking_fee": None}


class TestQuestionContextUnchanged:
    def _context_for(self, pages, monkeypatch):
        captured = {}

        async def fake_answer(question, context):
            captured.update(context)
            return "ok"

        monkeypatch.setattr(analyze_service, "answer_question", fake_answer)
        service = AnalyzeService.__new__(AnalyzeService)
        asyncio.run(service._answer_question("租金多少?", pages, "contract"))
        return captured["extracted_data"]

    def test_question_context_has_no_empty_keys_and_matches_old_merge(self, monkeypatch):
        pages = [
            page({"parties": {"party_a": "王小明", "party_b": None},
                  "rental_terms": {"monthly_rent": None, "parking_fee": None},
                  "contract_metadata": {"contract_number": None},
                  "needs_confirmation": [], "extraction_confidence": 0.5}),
            page({"parties": {"party_a": None, "party_b": None},
                  "rental_terms": {"monthly_rent": "25,000", "parking_fee": None},
                  "contract_metadata": {"contract_number": None}}),
        ]
        extracted = self._context_for(pages, monkeypatch)

        old: Dict[str, Any] = {}
        for p in pages:
            _old_merge_fill_missing(old, p["structured_data"])
        assert extracted == old
        assert "party_b" not in extracted["parties"]
        assert "parking_fee" not in extracted["rental_terms"]
        assert extracted["contract_metadata"] == {}
