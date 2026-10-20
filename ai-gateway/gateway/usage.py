"""用量監控：每個使用者依平常用量設基線，當格用量異常突增就警示（只標不擋）。

時間以 bucket（預設 60 秒）切格；基線＝前 N 格的平均，至少要有 N 格歷史才判斷。
時鐘可注入，測試用壓縮時間重播 30 分鐘份量。
"""
import time
from collections import defaultdict

from . import config, flags


class UsageMonitor:
    def __init__(self, bucket_s=config.USAGE_BUCKET_S, baseline_buckets=config.USAGE_BASELINE_BUCKETS,
                 k=config.USAGE_K, min_count=config.USAGE_MIN_COUNT):
        self.bucket_s, self.n, self.k, self.min_count = bucket_s, baseline_buckets, k, min_count
        self.counts: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self.alerted: set[tuple[str, int]] = set()
        self.alerts: list[dict] = []

    def record(self, user: str, now: float | None = None) -> dict | None:
        b = int((time.time() if now is None else now) // self.bucket_s)
        c = self.counts[user]
        c[b] += 1
        if flags.off("usage"):
            return None
        history = [c.get(b - i, 0) for i in range(1, self.n + 1)]
        if min(c) > b - self.n:  # 歷史不足 N 格，不判斷
            return None
        baseline = sum(history) / self.n
        if c[b] >= self.min_count and c[b] > self.k * max(baseline, 1) and (user, b) not in self.alerted:
            self.alerted.add((user, b))
            alert = {"user": user, "bucket": b, "count": c[b], "baseline": round(baseline, 2)}
            self.alerts.append(alert)
            return alert
        return None
