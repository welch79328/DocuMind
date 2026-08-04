"""
標註成果存放與版控規範測試(任務 1.1)

規範:標註成果(ground truth JSON)進版控、標註對象(原始文件,含個資)不進版控。
單一真相來源為 `backend/tests_all/fixtures/`;根目錄 `tests/` 與 `data/` 為
被版控排除的本機工作區,不得作為標註成果的存放位置。

對應需求: 1.9
"""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

# 標註成果單一真相來源(須納入版控)
ANNOTATION_DIR = REPO_ROOT / "backend" / "tests_all" / "fixtures"
TRANSCRIPT_ANNOTATION = ANNOTATION_DIR / "ground_truth.json"
CONTRACT_ANNOTATION = ANNOTATION_DIR / "contract_ground_truth.json"

# 標註對象(原始文件,含個資;須排除於版控外)
ANNOTATION_TARGET_DIRS = [REPO_ROOT / "data", REPO_ROOT / "tests"]

# 規範文件
ANNOTATION_GUIDE = REPO_ROOT / "docs" / "ANNOTATION_GUIDE.md"


def _is_git_ignored(path: Path) -> bool:
    """以 git check-ignore 判定路徑是否被版控排除"""
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(path)],
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


@pytest.fixture(scope="module", autouse=True)
def _require_git():
    probe = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if probe.returncode != 0:
        pytest.skip("非 git 工作區,無法驗證版控規範")


class TestAnnotationResultsAreVersionControlled:
    """標註成果檔案位於納入版本控制的路徑"""

    def test_transcript_annotation_exists_in_versioned_path(self):
        assert TRANSCRIPT_ANNOTATION.is_file(), (
            f"謄本標註成果不在單一真相來源:{TRANSCRIPT_ANNOTATION}"
        )
        assert not _is_git_ignored(TRANSCRIPT_ANNOTATION), "謄本標註成果被版控排除"

    def test_contract_annotation_exists_in_versioned_path(self):
        assert CONTRACT_ANNOTATION.is_file(), (
            f"合約標註成果不在單一真相來源:{CONTRACT_ANNOTATION}"
        )
        assert not _is_git_ignored(CONTRACT_ANNOTATION), "合約標註成果被版控排除"


class TestAnnotationTargetsAreExcluded:
    """標註對象(含個資的原始文件)維持排除於版本控制之外"""

    @pytest.mark.parametrize("target_dir", ANNOTATION_TARGET_DIRS, ids=lambda p: p.name)
    def test_target_directory_is_ignored(self, target_dir):
        assert _is_git_ignored(target_dir), (
            f"標註對象目錄未被版控排除,個資有進版控風險:{target_dir}"
        )

    def test_no_pdf_or_image_under_annotation_dir(self):
        """標註成果目錄僅存放標註 JSON,不得混入標註對象本體"""
        binaries = [
            p.name
            for p in ANNOTATION_DIR.iterdir()
            if p.suffix.lower() in {".pdf", ".jpg", ".jpeg", ".png"}
        ]
        assert binaries == [], f"標註對象本體混入版控目錄:{binaries}"


class TestSingleSourceOfTruth:
    """避免分歧:被版控排除的舊副本不得再被視為標註來源"""

    def test_legacy_contract_annotation_removed_from_ignored_path(self):
        legacy = REPO_ROOT / "data" / "contracts" / "ground_truth.json"
        assert not legacy.exists(), (
            f"合約標註仍留在被版控排除的舊路徑,與單一真相來源分歧:{legacy}"
        )


class TestPolicyIsDocumented:
    """規範寫入專案文件,後續人員可依循"""

    def test_guide_exists_and_names_source_of_truth(self):
        assert ANNOTATION_GUIDE.is_file(), f"缺少標註規範文件:{ANNOTATION_GUIDE}"
        content = ANNOTATION_GUIDE.read_text(encoding="utf-8")
        assert "backend/tests_all/fixtures" in content, "規範未指明標註成果單一真相來源"
        assert "ground_truth.json" in content, "規範未指明謄本標註檔名"
        assert "contract_ground_truth.json" in content, "規範未指明合約標註檔名"
