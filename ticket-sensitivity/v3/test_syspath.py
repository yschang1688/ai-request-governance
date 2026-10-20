#!/usr/bin/env python3
"""系統路徑規則測試，含反向檢核。執行：python3 test_syspath.py"""
import unittest

import syspath
from syspath import classify_path

RED = [
    r"掃 \\plm-srv\eng\ECN\rev\ 底下的 xlsx",          # v2 漏判那張
    r"資料在 //erp01/export/cost_2026.csv",
    r"讀 https://hris.corp.local/report/annual",
    r"放在 \\fs02\業務\報價\Q3.xlsx",
    r"路徑 D:\payroll\2026\10.xlsx",
]
YELLOW = [r"從 \\mes01\downtime\2026\ 拿資料", r"檔案在 //qc-nas/aoi/L3"]
GREEN = [r"教材放在 \\fs01\share\training\ 公告區", r"參考 https://www.example.com/public/faq", "沒有任何路徑的描述"]


class T(unittest.TestCase):
    def test_red(self):
        for t in RED:
            self.assertEqual(classify_path(t)[0], "紅", t)

    def test_yellow(self):
        for t in YELLOW:
            self.assertEqual(classify_path(t)[0], "黃", t)

    def test_green(self):
        for t in GREEN:
            self.assertEqual(classify_path(t)[0], "綠", t)

    def test_share_not_hr(self):
        self.assertEqual(classify_path(r"\\fs01\share\x")[0], "綠")

    def test_reverse_red_list_is_load_bearing(self):
        saved = set(syspath.RED_SYS)
        try:
            syspath.RED_SYS.clear()
            self.assertTrue(any(classify_path(t)[0] != "紅" for t in RED), "清空紅燈系統清單後測試仍全過")
        finally:
            syspath.RED_SYS.update(saved)


if __name__ == "__main__":
    unittest.main(verbosity=2)
