"""G8 用量：30 分鐘份量的正常節奏（壓縮時間重播）警示 0 次，接著 10 倍突增 ≥1 次。反向檢核：停用 usage。"""
from conftest import chat
from gateway.usage import UsageMonitor

T0 = 1_800_000_000  # 固定起點，與牆上時間無關
NORMAL = [5, 4, 6, 5, 5, 4, 6, 5, 6, 4] * 3  # 每分鐘請求數，30 分鐘，平均 5
BURST = 50  # 10 倍


def test_g8_baseline_then_burst(gw, gw_app, tokens):
    gw_app.usage = UsageMonitor()  # 從乾淨狀態開始
    tok = tokens["u-green"]
    normal_alerts = 0
    for minute, n in enumerate(NORMAL):
        for i in range(n):
            r = chat(gw, tok, "P-A", "green", x_test_clock=str(T0 + minute * 60 + i))
            assert r.status_code == 200
            normal_alerts += bool(r.json()["usage_alert"])
    burst_alerts = 0
    minute = len(NORMAL)
    for i in range(BURST):
        r = chat(gw, tok, "P-A", "green", x_test_clock=str(T0 + minute * 60 + i % 60))
        burst_alerts += bool(r.json()["usage_alert"])
    assert normal_alerts == 0, f"正常段誤報 {normal_alerts} 次"
    assert burst_alerts >= 1, "突增段沒有警示"
