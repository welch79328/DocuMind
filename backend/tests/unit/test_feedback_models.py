"""
測試回饋層資料模型(任務 2.1)

以 SQLAlchemy metadata 內省驗證三張新表的欄位、型別、預設值與索引,
不需資料庫連線。

模型:
- ReviewQueueItem(review_queue_items):人工複核佇列
- CorrectionSample(correction_samples):校正樣本 / 黃金範例(含 layout_signature、purpose)
- EvaluationRecord(evaluation_records):評估紀錄

對應需求: 6.2, 7.1, 7.2, 8.2
"""

from sqlalchemy import String, Text, Numeric, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base
from app.models import ReviewQueueItem, CorrectionSample, EvaluationRecord


def _col(model, name):
    return model.__table__.columns[name]


def _index_names(model):
    return {idx.name for idx in model.__table__.indexes}


class TestReviewQueueItem:
    def test_tablename(self):
        assert ReviewQueueItem.__tablename__ == "review_queue_items"

    def test_primary_key_is_uuid(self):
        col = _col(ReviewQueueItem, "id")
        assert col.primary_key is True
        assert isinstance(col.type, UUID)

    def test_document_id_foreign_key_cascade(self):
        col = _col(ReviewQueueItem, "document_id")
        # nullable:analyze 無狀態流程可不帶 document_id(見模型註解)
        assert col.nullable is True
        fk = list(col.foreign_keys)[0]
        assert fk.column.table.name == "documents"
        assert fk.ondelete == "CASCADE"

    def test_status_default_pending(self):
        col = _col(ReviewQueueItem, "status")
        assert isinstance(col.type, String)
        assert col.nullable is False
        assert col.default.arg == "pending"

    def test_overall_confidence_numeric_not_null(self):
        col = _col(ReviewQueueItem, "overall_confidence")
        assert isinstance(col.type, Numeric)
        assert col.nullable is False

    def test_reviewer_and_claimed_at_nullable(self):
        assert _col(ReviewQueueItem, "reviewer").nullable is True
        assert _col(ReviewQueueItem, "claimed_at").nullable is True

    def test_result_columns_jsonb(self):
        assert isinstance(_col(ReviewQueueItem, "original_result").type, JSONB)
        assert _col(ReviewQueueItem, "original_result").nullable is False
        assert isinstance(_col(ReviewQueueItem, "corrected_result").type, JSONB)
        assert _col(ReviewQueueItem, "corrected_result").nullable is True

    def test_indexes(self):
        names = _index_names(ReviewQueueItem)
        assert "idx_review_status" in names
        assert "idx_review_doc_type" in names


class TestCorrectionSample:
    def test_tablename(self):
        assert CorrectionSample.__tablename__ == "correction_samples"

    def test_layout_signature_default_empty(self):
        col = _col(CorrectionSample, "layout_signature")
        assert isinstance(col.type, String)
        assert col.nullable is False
        assert col.default.arg == ""

    def test_purpose_default_train(self):
        col = _col(CorrectionSample, "purpose")
        assert col.nullable is False
        assert col.default.arg == "train"

    def test_corrected_fields_jsonb_not_null(self):
        col = _col(CorrectionSample, "corrected_fields")
        assert isinstance(col.type, JSONB)
        assert col.nullable is False

    def test_input_ref_text(self):
        assert isinstance(_col(CorrectionSample, "input_ref").type, Text)

    def test_is_golden_default_false(self):
        col = _col(CorrectionSample, "is_golden")
        assert isinstance(col.type, Boolean)
        assert col.default.arg is False

    def test_source_review_id_fk_nullable(self):
        col = _col(CorrectionSample, "source_review_id")
        assert col.nullable is True
        fk = list(col.foreign_keys)[0]
        assert fk.column.table.name == "review_queue_items"

    def test_select_index_covers_expected_columns(self):
        idx = next(i for i in CorrectionSample.__table__.indexes
                   if i.name == "idx_sample_select")
        cols = [c.name for c in idx.columns]
        assert cols == ["document_type", "purpose", "is_golden", "layout_signature"]

    def test_corrected_fields_has_gin_index(self):
        gin = [
            i for i in CorrectionSample.__table__.indexes
            if i.dialect_options.get("postgresql", {}).get("using") == "gin"
        ]
        assert len(gin) == 1
        assert "corrected_fields" in [c.name for c in gin[0].columns]


class TestEvaluationRecord:
    def test_tablename(self):
        assert EvaluationRecord.__tablename__ == "evaluation_records"

    def test_metric_and_value_columns(self):
        assert isinstance(_col(EvaluationRecord, "metric_type").type, String)
        assert isinstance(_col(EvaluationRecord, "value").type, Numeric)
        assert _col(EvaluationRecord, "value").nullable is False

    def test_labeled_set_version_column(self):
        col = _col(EvaluationRecord, "labeled_set_version")
        assert isinstance(col.type, String)
        assert col.nullable is False

    def test_is_baseline_default_false(self):
        col = _col(EvaluationRecord, "is_baseline")
        assert isinstance(col.type, Boolean)
        assert col.default.arg is False

    def test_index(self):
        assert "idx_eval_type_metric" in _index_names(EvaluationRecord)


class TestRegistration:
    def test_models_registered_in_metadata(self):
        for tbl in ["review_queue_items", "correction_samples", "evaluation_records"]:
            assert tbl in Base.metadata.tables

    def test_created_at_present_on_all(self):
        for model in [ReviewQueueItem, CorrectionSample, EvaluationRecord]:
            assert isinstance(_col(model, "created_at").type, DateTime)
