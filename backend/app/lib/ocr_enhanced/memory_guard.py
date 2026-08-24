"""可用記憶體偵測——供並行守衛判斷「現在並行安全嗎」。

2026-08-24 背景:主機實體記憶體 3.7GB,容器**沒有** mem_limit(cgroup 的
`memory.max` 讀出來是 `max`),四個容器共用全部記憶體。在該機跑
300 DPI 合約頁 + 去噪 + 雙引擎並行時觸發 OOM
(`docker inspect .State.OOMKilled` = true),load average 衝到 51.35。

並行的代價是峰值記憶體由「兩引擎取大」變成「兩引擎相加」,因此並行與否
不該只看設定,還要看當下這台機器撐不撐得住。

刻意不依賴 psutil:它未列在 `backend/requirements.txt`,容器內雖然裝著
(7.2.2)但屬未釘版的間接相依,隨時可能在重建 image 後消失。
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_CGROUP_LIMIT_PATHS = (
    "/sys/fs/cgroup/memory.max",                        # cgroup v2
    "/sys/fs/cgroup/memory/memory.limit_in_bytes",      # cgroup v1
)
_CGROUP_USAGE_PATHS = (
    "/sys/fs/cgroup/memory.current",
    "/sys/fs/cgroup/memory/memory.usage_in_bytes",
)


def _read_int(path: str) -> Optional[int]:
    try:
        with open(path) as fh:
            raw = fh.read().strip()
    except OSError:
        return None
    if raw == "max":            # cgroup v2 的「無上限」
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    # cgroup v1 未設限時填一個接近 2^63 的哨兵值,不是真的上限
    return None if value > (1 << 62) else value


def _cgroup_available_bytes() -> Optional[int]:
    """容器自身的餘裕。有設 mem_limit 時,這才是真正的天花板。"""
    limit = next((v for p in _CGROUP_LIMIT_PATHS if (v := _read_int(p))), None)
    if limit is None:
        return None
    usage = next((v for p in _CGROUP_USAGE_PATHS if (v := _read_int(p))), None)
    return limit if usage is None else max(0, limit - usage)


def _host_available_bytes() -> Optional[int]:
    """主機層可用記憶體。容器沒設上限時,這才是實際的天花板。

    ⚠️ **macOS 沒有 `SC_AVPHYS_PAGES`**(只有 `SC_PHYS_PAGES`),此處會回傳 None,
    於是守衛退回「允許並行」。這是刻意的:生產環境是 Linux 容器,而開發機
    (Apple Silicon)本來就跑不了 PaddleOCR,守衛在那裡沒有作用對象。
    不為 macOS 補 vm_stat 分支,是為了不替一個跑不動這個工作的平台增加程式碼。
    """
    try:
        return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (ValueError, OSError, AttributeError):
        return None


def available_mb() -> Optional[int]:
    """回傳可用記憶體(MB);兩個來源都取不到時回傳 None。

    取兩者較小值:容器有上限時受容器約束,沒上限時受主機約束,
    兩邊都拿得到時以較緊的那個為準。
    """
    candidates = [b for b in (_cgroup_available_bytes(), _host_available_bytes())
                  if b is not None]
    return min(candidates) // (1024 * 1024) if candidates else None


def parallel_is_safe(min_available_mb: int) -> bool:
    """記憶體是否足以並行執行多引擎。

    `min_available_mb <= 0` 表示停用此保護。
    偵測失敗(回傳 None)時**允許**並行——寧可維持既有行為,
    也不要因為讀不到 /proc 就讓所有人默默變慢。
    """
    if min_available_mb <= 0:
        return True
    avail = available_mb()
    if avail is None:
        logger.debug("無法偵測可用記憶體,維持並行設定")
        return True
    if avail < min_available_mb:
        logger.warning(
            "可用記憶體 %dMB 低於並行門檻 %dMB,本次退回循序執行以避免 OOM",
            avail, min_available_mb,
        )
        return False
    return True
