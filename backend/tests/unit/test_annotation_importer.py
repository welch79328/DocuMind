"""
標註匯入器測試(任務 1.3)

涵蓋三條路徑:正常匯入、空值略過、格式錯誤;並驗證匯入的保留評估集
與 few-shot 訓練池的隔離(防資料洩漏)。

對應需求: 1.7, 1.8
"""

import json
from pathlib import Path

import pytest

from app.services.annotation_importer import (
    AnnotationImporter,
    InvalidAnnotationFormatError,
)
from app.services.correction_sample_service import CorrectionSampleService

# parents[2] 是 backend 根,在兩種佈局下都成立:
#   本機   .../DocuMind/backend/tests/unit/  → .../DocuMind/backend
#   容器   /app/tests/unit/                  → /app        (compose 掛 ./backend:/app)
# 原本用 parents[3] 再接 "backend/",那是 repo 根的算法——容器裡只掛了 backend,
# repo 根不存在,會算成 /backend/... 而找不到檔案(2026-08-24 於線上實測)。
BACKEND_ROOT = Path(__file__).resolve().parents[2]
ANNOTATION_DIR = BACKEND_ROOT / "tests_all" / "fixtures"


@pytest.fixture
def ctx(feedback_session):
    samples = CorrectionSampleService(feedback_session)
    return AnnotationImporter(samples), samples


def _write(tmp_path: Path, name: str, payload) -> str:
    path = tmp_path / name
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(path)


# --------------------------------------------------------------------------- #
# 路徑 1:正常匯入
# --------------------------------------------------------------------------- #
class TestNormalImport:
    def test_transcript_shape_imports_key_fields(self, ctx, tmp_path):
        importer, samples = ctx
        path = _write(tmp_path, "gt.json", {
            "A.jpg": {
                "document_type": "building_transcript",
                "full_text": "全文",
                "key_fields": {"land_number": "0231-0000", "area": 105.0},
                "metadata": {"pages": 1},
            },
        })

        report = importer.import_from_file(path, "transcript")

        assert report["imported"] == 1
        assert report["skipped"] == 0
        assert report["errors"] == []

        stored = samples.list_samples("transcript", purpose="holdout")
        assert len(stored) == 1
        assert stored[0]["input_ref"] == "A.jpg"
        assert stored[0]["corrected_fields"] == {
            "land_number": "0231-0000", "area": 105.0,
        }

    def test_contract_shape_imports_from_contracts_wrapper(self, ctx, tmp_path):
        importer, samples = ctx
        path = _write(tmp_path, "contract.json", {
            "description": "合約標註",
            "version": "1.0",
            "critical_fields": ["contract_number", "party_a"],
            "contracts": {
                "c1.pdf": {
                    "contract_number": "A-001",
                    "party_a": "甲公司",
                    "contract_amount": None,
                    "currency": "TWD",
                    "notes": "已標註",
                },
            },
        })

        report = importer.import_from_file(path, "contract")

        assert report["imported"] == 1
        stored = samples.list_samples("contract", purpose="holdout")
        assert stored[0]["input_ref"] == "c1.pdf"
        # 未標註欄位(None)不寫入;notes 為備註非標註欄位
        assert stored[0]["corrected_fields"] == {
            "contract_number": "A-001", "party_a": "甲公司", "currency": "TWD",
        }

    def test_reserved_metadata_keys_are_not_documents(self, ctx, tmp_path):
        importer, samples = ctx
        path = _write(tmp_path, "gt.json", {
            "A.jpg": {"key_fields": {"area": 1.0}},
            "annotation_metadata": {"annotator": "人工", "created_at": "2026-08-04"},
        })

        report = importer.import_from_file(path, "transcript")

        assert report["imported"] == 1
        assert report["skipped"] == 0
        refs = {s["input_ref"] for s in samples.list_samples("transcript")}
        assert refs == {"A.jpg"}

    def test_defaults_to_holdout_purpose(self, ctx, tmp_path):
        importer, samples = ctx
        path = _write(tmp_path, "gt.json", {"A.jpg": {"key_fields": {"area": 1.0}}})

        importer.import_from_file(path, "transcript")

        assert samples.count("transcript", purpose="holdout") == 1
        assert samples.count("transcript", purpose="train") == 0

    def test_can_import_as_train_when_explicitly_requested(self, ctx, tmp_path):
        importer, samples = ctx
        path = _write(tmp_path, "gt.json", {"A.jpg": {"key_fields": {"area": 1.0}}})

        importer.import_from_file(path, "transcript", purpose="train")

        assert samples.count("transcript", purpose="train") == 1
        assert samples.count("transcript", purpose="holdout") == 0

    def test_accepts_document_type_enum(self, ctx, tmp_path):
        from app.lib.document_types import DocumentType

        importer, samples = ctx
        path = _write(tmp_path, "gt.json", {"A.jpg": {"key_fields": {"area": 1.0}}})

        importer.import_from_file(path, DocumentType.TRANSCRIPT)

        assert samples.count("transcript", purpose="holdout") == 1


# --------------------------------------------------------------------------- #
# 路徑 2:空值略過
# --------------------------------------------------------------------------- #
class TestUnannotatedSkipped:
    @pytest.mark.parametrize("placeholder", [None, "", "[待標註]", "需人工標註"])
    def test_placeholder_values_count_as_unannotated(self, ctx, tmp_path, placeholder):
        importer, samples = ctx
        path = _write(tmp_path, "gt.json", {
            "empty.jpg": {"key_fields": {"land_number": placeholder, "area": None}},
        })

        report = importer.import_from_file(path, "transcript")

        assert report["imported"] == 0
        assert report["skipped"] == 1
        assert report["skipped_refs"] == ["empty.jpg"]
        assert samples.count("transcript", purpose="holdout") == 0

    def test_partially_annotated_item_keeps_only_annotated_fields(self, ctx, tmp_path):
        importer, samples = ctx
        path = _write(tmp_path, "gt.json", {
            "A.jpg": {"key_fields": {"land_number": "0231-0000", "area": None}},
        })

        report = importer.import_from_file(path, "transcript")

        assert report["imported"] == 1
        stored = samples.list_samples("transcript", purpose="holdout")
        assert stored[0]["corrected_fields"] == {"land_number": "0231-0000"}

    def test_only_default_values_without_critical_field_is_skipped(self, ctx, tmp_path):
        """宣告 critical_fields 時,僅有 currency 等預設值不算已標註"""
        importer, samples = ctx
        path = _write(tmp_path, "contract.json", {
            "critical_fields": ["contract_number", "party_a"],
            "contracts": {
                "c1.pdf": {
                    "contract_number": None, "party_a": None,
                    "currency": "TWD", "notes": "需人工標註",
                },
            },
        })

        report = importer.import_from_file(path, "contract")

        assert report["imported"] == 0
        assert report["skipped"] == 1
        assert report["skipped_refs"] == ["c1.pdf"]
        assert samples.count("contract", purpose="holdout") == 0

    def test_mixed_file_reports_both_counts(self, ctx, tmp_path):
        importer, samples = ctx
        path = _write(tmp_path, "gt.json", {
            "ok.jpg": {"key_fields": {"area": 1.0}},
            "todo.pdf": {"key_fields": {"area": None, "owner": "[待標註]"}},
        })

        report = importer.import_from_file(path, "transcript")

        assert report["imported"] == 1
        assert report["skipped"] == 1
        assert report["skipped_refs"] == ["todo.pdf"]
        assert samples.count("transcript", purpose="holdout") == 1


# --------------------------------------------------------------------------- #
# 路徑 3:格式錯誤
# --------------------------------------------------------------------------- #
class TestFormatErrors:
    def test_missing_file_raises_file_not_found(self, ctx, tmp_path):
        importer, _ = ctx
        with pytest.raises(FileNotFoundError):
            importer.import_from_file(str(tmp_path / "nope.json"), "transcript")

    def test_malformed_json_raises_invalid_format(self, ctx, tmp_path):
        importer, _ = ctx
        path = _write(tmp_path, "bad.json", "{ not json ")
        with pytest.raises(InvalidAnnotationFormatError):
            importer.import_from_file(path, "transcript")

    def test_top_level_not_object_raises_invalid_format(self, ctx, tmp_path):
        importer, _ = ctx
        path = _write(tmp_path, "list.json", [{"A.jpg": {}}])
        with pytest.raises(InvalidAnnotationFormatError):
            importer.import_from_file(path, "transcript")

    def test_unsupported_document_type_raises_invalid_format(self, ctx, tmp_path):
        importer, _ = ctx
        path = _write(tmp_path, "gt.json", {"A.jpg": {"key_fields": {"area": 1.0}}})
        with pytest.raises(InvalidAnnotationFormatError):
            importer.import_from_file(path, "invoice")

    def test_malformed_entry_is_reported_without_aborting(self, ctx, tmp_path):
        """單筆項目結構錯誤記入 errors,其餘項目照常匯入"""
        importer, samples = ctx
        path = _write(tmp_path, "gt.json", {
            "broken.jpg": "應為物件卻是字串",
            "ok.jpg": {"key_fields": {"area": 1.0}},
        })

        report = importer.import_from_file(path, "transcript")

        assert report["imported"] == 1
        assert len(report["errors"]) == 1
        assert "broken.jpg" in report["errors"][0]
        assert samples.count("transcript", purpose="holdout") == 1

    def test_entry_without_recognizable_fields_is_reported(self, ctx, tmp_path):
        importer, _ = ctx
        path = _write(tmp_path, "gt.json", {
            "A.jpg": {"document_type": "x", "metadata": {"pages": 1}},
        })

        report = importer.import_from_file(path, "transcript")

        assert report["imported"] == 0
        assert len(report["errors"]) == 1
        assert "A.jpg" in report["errors"][0]


# --------------------------------------------------------------------------- #
# 資料隔離:匯入的評估集不得進入 few-shot
# --------------------------------------------------------------------------- #
class TestEvaluationSetIsolation:
    def test_imported_holdout_absent_from_fewshot_selection(self, ctx, tmp_path):
        importer, samples = ctx
        samples.save("transcript", "train-1", {"area": 9.0}, purpose="train")
        path = _write(tmp_path, "gt.json", {
            "holdout-1.jpg": {"key_fields": {"area": 1.0}},
            "holdout-2.jpg": {"key_fields": {"area": 2.0}},
        })

        importer.import_from_file(path, "transcript")

        refs = {s["input_ref"] for s in samples.list_for_fewshot("transcript")}
        assert refs == {"train-1"}
        assert "holdout-1.jpg" not in refs and "holdout-2.jpg" not in refs

    def test_imported_holdout_visible_to_evaluation(self, ctx, tmp_path, feedback_session):
        from app.services.evaluation_service import EvaluationService

        importer, _ = ctx
        path = _write(tmp_path, "gt.json", {
            "d1.jpg": {"key_fields": {"area": "105"}},
        })
        importer.import_from_file(path, "transcript")

        metrics = EvaluationService(feedback_session).evaluate(
            "transcript", {"d1.jpg": {"area": "105"}}, "v1", persist=False
        )
        assert metrics["sample_count"] == 1
        assert metrics["field_accuracy"] == 1.0


# --------------------------------------------------------------------------- #
# 專案實際標註檔
# --------------------------------------------------------------------------- #
class TestRepositoryAnnotationFiles:
    def test_transcript_annotation_file_imports(self, ctx):
        importer, samples = ctx
        report = importer.import_from_file(
            str(ANNOTATION_DIR / "ground_truth.json"), "transcript"
        )
        # 現況:1 份已標註、1 份待標註(任務 3.1 補齊)
        assert report["imported"] == 1
        assert report["skipped"] == 1
        assert "建物土地謄本-杭州南路一段.pdf" in report["skipped_refs"]
        assert samples.count("transcript", purpose="holdout") == 1

    def test_contract_annotation_file_all_unannotated(self, ctx):
        importer, samples = ctx
        report = importer.import_from_file(
            str(ANNOTATION_DIR / "contract_ground_truth.json"), "contract"
        )
        # 現況:11 份合約關鍵欄位全未標註(任務 3.2 補齊)
        assert report["imported"] == 0
        assert report["skipped"] == 11
        assert samples.count("contract", purpose="holdout") == 0
