"""
基準測試執行器測試(任務 2.1 / 2.2 / 2.3)

- 執行環境檢查與架構守衛:不支援的處理器架構明確拒絕,不得產出無效基準
- 指標產出:CER、欄位準確率、低信心攔截觸發率,並可持久化為基準線
- 樣本數守衛:低於門檻時拒絕標記為正式基準線

對應需求: 1.3, 1.4, 1.5, 1.6, 1.10
"""

import pytest

from app.services import baseline_runner as br
from app.services.baseline_runner import (
    BaselineRunner,
    InsufficientSamplesError,
    UnsupportedArchitectureError,
)
from app.services.correction_sample_service import CorrectionSampleService
from app.services.evaluation_service import EvaluationService


@pytest.fixture
def ctx(feedback_session):
    return (
        EvaluationService(feedback_session),
        CorrectionSampleService(feedback_session),
    )


@pytest.fixture
def x86_env(monkeypatch):
    """預設把環境偽裝為可執行主力引擎的 x86_64,個別測試再覆寫"""
    monkeypatch.setattr(br.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(br, "_is_engine_installed", lambda engine: True)


def _predictor(table):
    """以查表方式模擬辨識;table = {input_ref: (fields, confidence)}"""

    async def predict(input_ref):
        fields, confidence = table.get(input_ref, ({}, 0.0))
        return {"fields": fields, "confidence": confidence}

    return predict


# --------------------------------------------------------------------------- #
# 任務 2.1:執行環境檢查與架構守衛
# --------------------------------------------------------------------------- #
class TestEnvironmentCheck:
    def test_reports_architecture_and_availability(self, x86_env):
        check = BaselineRunner.check_environment(["paddleocr", "tesseract"])
        assert check["architecture"] == "x86_64"
        assert check["primary_engine_available"] is True
        assert check["reason"] is None

    def test_arm64_marks_primary_engine_unavailable(self, monkeypatch):
        monkeypatch.setattr(br.platform, "machine", lambda: "arm64")
        monkeypatch.setattr(br, "_is_engine_installed", lambda engine: True)

        check = BaselineRunner.check_environment(["paddleocr", "tesseract"])

        assert check["architecture"] == "arm64"
        assert check["primary_engine_available"] is False
        assert "x86_64" in check["reason"]

    @pytest.mark.parametrize("machine", ["aarch64", "arm64", "ARM64"])
    def test_all_arm_variants_detected(self, monkeypatch, machine):
        monkeypatch.setattr(br.platform, "machine", lambda: machine)
        monkeypatch.setattr(br, "_is_engine_installed", lambda engine: True)
        assert BaselineRunner.check_environment(["paddleocr"])[
            "primary_engine_available"
        ] is False

    def test_engine_without_arm_defect_stays_available(self, monkeypatch):
        """備援引擎於 ARM 無上游缺陷,不應被架構守衛擋下"""
        monkeypatch.setattr(br.platform, "machine", lambda: "arm64")
        monkeypatch.setattr(br, "_is_engine_installed", lambda engine: True)

        check = BaselineRunner.check_environment(["tesseract"])

        assert check["primary_engine_available"] is True

    def test_uninstalled_engine_marked_unavailable(self, monkeypatch):
        monkeypatch.setattr(br.platform, "machine", lambda: "x86_64")
        monkeypatch.setattr(br, "_is_engine_installed", lambda engine: False)

        check = BaselineRunner.check_environment(["paddleocr"])

        assert check["primary_engine_available"] is False
        assert "paddleocr" in check["reason"]

    def test_defaults_to_configured_engines(self, x86_env):
        """未指定引擎時採用設定值,呼叫方式與設計文件一致"""
        assert BaselineRunner.check_environment()["primary_engine_available"] is True


class TestArchitectureGuard:
    async def test_run_refuses_on_unsupported_architecture(self, ctx, monkeypatch):
        eval_svc, samples = ctx
        monkeypatch.setattr(br.platform, "machine", lambda: "arm64")
        monkeypatch.setattr(br, "_is_engine_installed", lambda engine: True)
        samples.save("transcript", "d1", {"area": "1"}, purpose="holdout")

        runner = BaselineRunner(eval_svc, predictor=_predictor({"d1": ({"area": "1"}, 0.9)}))

        with pytest.raises(UnsupportedArchitectureError) as exc:
            await runner.run("transcript", "paddleocr+tesseract")

        assert "x86_64" in str(exc.value)

    async def test_refusal_writes_no_records(self, ctx, monkeypatch, feedback_session):
        """拒絕行為不得表現為異常數值或空結果:不留下任何指標紀錄"""
        eval_svc, samples = ctx
        monkeypatch.setattr(br.platform, "machine", lambda: "arm64")
        monkeypatch.setattr(br, "_is_engine_installed", lambda engine: True)
        samples.save("transcript", "d1", {"area": "1"}, purpose="holdout")

        runner = BaselineRunner(eval_svc, predictor=_predictor({"d1": ({"area": "1"}, 0.9)}))
        with pytest.raises(UnsupportedArchitectureError):
            await runner.run("transcript", "paddleocr")

        assert eval_svc.list_records("transcript") == []
        assert eval_svc.summary("transcript") == {"latest": None, "baseline": None}


# --------------------------------------------------------------------------- #
# 任務 2.2:指標產出
# --------------------------------------------------------------------------- #
class TestMetrics:
    async def test_produces_cer_and_field_accuracy(self, ctx, x86_env):
        eval_svc, samples = ctx
        samples.save("transcript", "d1", {"area": "105"}, purpose="holdout")
        samples.save("transcript", "d2", {"area": "200"}, purpose="holdout")

        runner = BaselineRunner(eval_svc, predictor=_predictor({
            "d1": ({"area": "105"}, 0.9),
            "d2": ({"area": "XXX"}, 0.9),
        }), min_samples=1)
        report = await runner.run("transcript", "paddleocr+tesseract")

        assert report["sample_count"] == 2
        assert report["field_accuracy"] == 0.5   # d1 對、d2 錯
        assert report["cer"] > 0
        assert report["engine_profile"] == "paddleocr+tesseract"
        assert report["document_type"] == "transcript"

    async def test_produces_review_trigger_rate(self, ctx, x86_env):
        eval_svc, samples = ctx
        for ref in ("d1", "d2", "d3", "d4"):
            samples.save("transcript", ref, {"area": "1"}, purpose="holdout")

        # 門檻 0.8:d3 / d4 低於門檻 → 觸發率 0.5
        runner = BaselineRunner(eval_svc, predictor=_predictor({
            "d1": ({"area": "1"}, 0.95), "d2": ({"area": "1"}, 0.85),
            "d3": ({"area": "1"}, 0.60), "d4": ({"area": "1"}, 0.20),
        }), min_samples=1, threshold=0.8)
        report = await runner.run("transcript", "paddleocr")

        assert report["review_trigger_rate"] == 0.5

    async def test_trigger_rate_uses_configured_threshold(self, ctx, x86_env):
        eval_svc, samples = ctx
        for ref in ("d1", "d2"):
            samples.save("transcript", ref, {"area": "1"}, purpose="holdout")

        runner = BaselineRunner(eval_svc, predictor=_predictor({
            "d1": ({"area": "1"}, 0.95), "d2": ({"area": "1"}, 0.85),
        }), min_samples=1, threshold=0.9)
        report = await runner.run("transcript", "paddleocr")

        assert report["review_trigger_rate"] == 0.5  # 0.85 落到門檻下

    async def test_produces_per_field_accuracy(self, ctx, x86_env):
        eval_svc, samples = ctx
        samples.save("transcript", "d1", {"area": "1", "owner": "王"}, purpose="holdout")
        samples.save("transcript", "d2", {"area": "2", "owner": "李"}, purpose="holdout")

        runner = BaselineRunner(eval_svc, predictor=_predictor({
            "d1": ({"area": "1", "owner": "王"}, 0.9),
            "d2": ({"area": "X", "owner": "李"}, 0.9),
        }), min_samples=1)
        report = await runner.run("transcript", "paddleocr")

        assert report["per_field_accuracy"]["owner"] == 1.0
        assert report["per_field_accuracy"]["area"] == 0.5

    async def test_report_carries_environment_and_timestamp(self, ctx, x86_env):
        eval_svc, samples = ctx
        samples.save("transcript", "d1", {"area": "1"}, purpose="holdout")

        runner = BaselineRunner(
            eval_svc, predictor=_predictor({"d1": ({"area": "1"}, 0.9)}), min_samples=1
        )
        report = await runner.run("transcript", "paddleocr")

        assert report["environment"]["architecture"] == "x86_64"
        assert report["environment"]["primary_engine_available"] is True
        assert report["executed_at"]  # ISO 8601 執行時間標記

    async def test_missing_prediction_counts_as_worst(self, ctx, x86_env):
        """預測缺漏視為最差,且必然觸發複核,不得靜默略過"""
        eval_svc, samples = ctx
        samples.save("transcript", "d1", {"area": "1"}, purpose="holdout")

        runner = BaselineRunner(eval_svc, predictor=_predictor({}), min_samples=1)
        report = await runner.run("transcript", "paddleocr")

        assert report["field_accuracy"] == 0.0
        assert report["review_trigger_rate"] == 1.0


class TestPersistence:
    async def test_baseline_persisted_with_engine_profile(self, ctx, x86_env):
        eval_svc, samples = ctx
        samples.save("transcript", "d1", {"area": "1"}, purpose="holdout")

        runner = BaselineRunner(
            eval_svc, predictor=_predictor({"d1": ({"area": "1"}, 0.9)}), min_samples=1
        )
        report = await runner.run("transcript", "paddleocr+tesseract", is_baseline=True)

        records = eval_svc.list_records("transcript")
        metric_types = {r["metric_type"] for r in records}
        assert {"cer", "field_accuracy", "review_trigger_rate"} <= metric_types
        assert all(r["is_baseline"] for r in records)
        assert all("paddleocr+tesseract" in r["labeled_set_version"] for r in records)
        assert report["labeled_set_version"] == records[0]["labeled_set_version"]
        assert len(report["labeled_set_version"]) <= 50  # 欄位長度上限

    async def test_non_baseline_run_is_not_marked_baseline(self, ctx, x86_env):
        eval_svc, samples = ctx
        samples.save("transcript", "d1", {"area": "1"}, purpose="holdout")

        runner = BaselineRunner(
            eval_svc, predictor=_predictor({"d1": ({"area": "1"}, 0.9)}), min_samples=1
        )
        await runner.run("transcript", "paddleocr", is_baseline=False)

        assert all(not r["is_baseline"] for r in eval_svc.list_records("transcript"))
        assert eval_svc.summary("transcript")["baseline"] is None

    async def test_runs_per_document_type_independently(self, ctx, x86_env):
        eval_svc, samples = ctx
        samples.save("transcript", "t1", {"area": "1"}, purpose="holdout")
        samples.save("contract", "c1", {"party_a": "甲"}, purpose="holdout")

        runner = BaselineRunner(eval_svc, predictor=_predictor({
            "t1": ({"area": "1"}, 0.9), "c1": ({"party_a": "乙"}, 0.9),
        }), min_samples=1)

        transcript = await runner.run("transcript", "paddleocr")
        contract = await runner.run("contract", "paddleocr")

        assert transcript["sample_count"] == 1 and transcript["field_accuracy"] == 1.0
        assert contract["sample_count"] == 1 and contract["field_accuracy"] == 0.0
        assert eval_svc.list_records("contract") and eval_svc.list_records("transcript")


# --------------------------------------------------------------------------- #
# 任務 2.3:樣本數守衛
# --------------------------------------------------------------------------- #
class TestSampleCountGuard:
    async def test_refuses_baseline_when_samples_below_threshold(self, ctx, x86_env):
        eval_svc, samples = ctx
        samples.save("transcript", "d1", {"area": "1"}, purpose="holdout")

        runner = BaselineRunner(
            eval_svc, predictor=_predictor({"d1": ({"area": "1"}, 0.9)}), min_samples=30
        )

        with pytest.raises(InsufficientSamplesError) as exc:
            await runner.run("transcript", "paddleocr", is_baseline=True)

        message = str(exc.value)
        assert "樣本不足" in message
        assert "1" in message and "30" in message

    async def test_refusal_writes_no_records(self, ctx, x86_env):
        eval_svc, samples = ctx
        samples.save("transcript", "d1", {"area": "1"}, purpose="holdout")

        runner = BaselineRunner(
            eval_svc, predictor=_predictor({"d1": ({"area": "1"}, 0.9)}), min_samples=30
        )
        with pytest.raises(InsufficientSamplesError):
            await runner.run("transcript", "paddleocr", is_baseline=True)

        assert eval_svc.list_records("transcript") == []

    async def test_non_baseline_run_allowed_below_threshold(self, ctx, x86_env):
        """樣本不足僅擋「標記為正式基準線」,探索性執行仍可進行"""
        eval_svc, samples = ctx
        samples.save("transcript", "d1", {"area": "1"}, purpose="holdout")

        runner = BaselineRunner(
            eval_svc, predictor=_predictor({"d1": ({"area": "1"}, 0.9)}), min_samples=30
        )
        report = await runner.run("transcript", "paddleocr", is_baseline=False)

        assert report["sample_count"] == 1
        assert report["baseline_eligible"] is False
        assert "樣本不足" in report["warnings"][0]

    async def test_report_eligible_when_threshold_met(self, ctx, x86_env):
        eval_svc, samples = ctx
        for i in range(3):
            samples.save("transcript", f"d{i}", {"area": "1"}, purpose="holdout")

        runner = BaselineRunner(eval_svc, predictor=_predictor(
            {f"d{i}": ({"area": "1"}, 0.9) for i in range(3)}
        ), min_samples=3)
        report = await runner.run("transcript", "paddleocr", is_baseline=True)

        assert report["baseline_eligible"] is True
        assert report["warnings"] == []

    async def test_empty_holdout_refused_as_baseline(self, ctx, x86_env):
        eval_svc, _ = ctx
        runner = BaselineRunner(eval_svc, predictor=_predictor({}), min_samples=1)

        with pytest.raises(InsufficientSamplesError):
            await runner.run("transcript", "paddleocr", is_baseline=True)

    async def test_empty_holdout_writes_no_orphan_metric(self, ctx, x86_env):
        """無樣本時不得留下孤立的觸發率紀錄(會被 summary 誤讀為已有量測)"""
        eval_svc, _ = ctx
        runner = BaselineRunner(eval_svc, predictor=_predictor({}), min_samples=1)

        report = await runner.run("transcript", "paddleocr", is_baseline=False)

        assert report["sample_count"] == 0
        assert eval_svc.list_records("transcript") == []

    async def test_min_samples_defaults_to_settings(self, ctx, x86_env):
        from app.config import settings

        eval_svc, _ = ctx
        runner = BaselineRunner(eval_svc, predictor=_predictor({}))
        assert runner.min_samples == settings.BASELINE_MIN_SAMPLES


class TestPredictorContract:
    async def test_missing_predictor_is_rejected(self, ctx, x86_env):
        eval_svc, samples = ctx
        samples.save("transcript", "d1", {"area": "1"}, purpose="holdout")

        runner = BaselineRunner(eval_svc, min_samples=1)

        with pytest.raises(ValueError) as exc:
            await runner.run("transcript", "paddleocr")
        assert "辨識來源" in str(exc.value)

    async def test_predictor_failure_counts_as_worst_not_crash(self, ctx, x86_env):
        eval_svc, samples = ctx
        samples.save("transcript", "d1", {"area": "1"}, purpose="holdout")

        async def failing(input_ref):
            raise RuntimeError("引擎爆炸")

        runner = BaselineRunner(eval_svc, predictor=failing, min_samples=1)
        report = await runner.run("transcript", "paddleocr")

        assert report["field_accuracy"] == 0.0
        assert report["review_trigger_rate"] == 1.0
        assert any("d1" in w for w in report["warnings"])

    async def test_predictor_may_return_field_confidences(self, ctx, x86_env):
        """欄位級信心度存在時,交由 QualityAssessor 以既有保守策略判定"""
        eval_svc, samples = ctx
        samples.save("transcript", "d1", {"area": "1"}, purpose="holdout")

        async def predict(input_ref):
            return {
                "fields": {"area": "1"},
                "confidence": 0.95,
                "field_confidences": {"area": 0.30},
            }

        runner = BaselineRunner(eval_svc, predictor=predict, min_samples=1, threshold=0.8)
        report = await runner.run("transcript", "paddleocr")

        assert report["review_trigger_rate"] == 1.0  # 取最差值 → 觸發複核
