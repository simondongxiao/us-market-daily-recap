from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import pandas as pd


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "templates" / "collect_template.py"
SPEC = importlib.util.spec_from_file_location("collect_template", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FillTargetCashSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        MODULE.DAY = pd.Timestamp("2026-10-30")

    def test_backfills_all_missing_recent_sessions(self) -> None:
        daily = pd.DataFrame(
            {
                "open": [100.0],
                "high": [102.0],
                "low": [99.0],
                "close": [101.0],
                "volume": [1_000.0],
            },
            index=pd.DatetimeIndex(["2026-10-28"]),
        )
        intraday = pd.DataFrame(
            {
                "open": [102.0, 103.0, 105.0, 104.0],
                "high": [103.0, 104.0, 106.0, 105.0],
                "low": [101.0, 102.0, 103.0, 102.0],
                "close": [102.5, 103.5, 104.5, 103.0],
                "volume": [100.0, 200.0, 300.0, 400.0],
            },
            index=pd.DatetimeIndex(
                [
                    "2026-10-29 09:30",
                    "2026-10-29 16:00",
                    "2026-10-30 09:30",
                    "2026-10-30 16:00",
                ]
            ),
        )
        original_fetch = MODULE.fetch_chart
        MODULE.fetch_chart = lambda *args, **kwargs: intraday
        try:
            result = MODULE.fill_target_cash_session("TEST", daily)
        finally:
            MODULE.fetch_chart = original_fetch

        self.assertEqual(result.loc[pd.Timestamp("2026-10-29"), "close"], 103.5)
        self.assertEqual(result.loc[pd.Timestamp("2026-10-30"), "close"], 103.0)
        self.assertEqual(result.loc[pd.Timestamp("2026-10-30"), "volume"], 700.0)
        previous = result.loc[result.index < MODULE.DAY, "close"].iloc[-1]
        self.assertAlmostEqual((result.loc[MODULE.DAY, "close"] / previous - 1) * 100, -0.4830918)

    def test_existing_target_does_not_refetch(self) -> None:
        daily = pd.DataFrame(
            {"close": [100.0, 101.0]},
            index=pd.DatetimeIndex(["2026-10-29", "2026-10-30"]),
        )
        original_fetch = MODULE.fetch_chart
        MODULE.fetch_chart = lambda *args, **kwargs: self.fail("unexpected intraday request")
        try:
            result = MODULE.fill_target_cash_session("TEST", daily)
        finally:
            MODULE.fetch_chart = original_fetch
        self.assertEqual(result.loc[MODULE.DAY, "close"], 101.0)


if __name__ == "__main__":
    unittest.main()
