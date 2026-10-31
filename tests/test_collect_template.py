from __future__ import annotations

import importlib.util
import tempfile
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

    def test_intraday_uses_only_target_cash_session(self) -> None:
        stale_and_target = pd.DataFrame(
            {
                "open": [200.0, 198.0, 100.0, 104.0, 106.0, 107.0],
                "high": [201.0, 199.0, 102.0, 106.0, 108.0, 107.0],
                "low": [199.0, 197.0, 99.0, 103.0, 105.0, 107.0],
                "close": [200.5, 198.5, 101.0, 105.0, 107.0, 107.0],
                "volume": [100.0, 100.0, 1_000.0, 2_000.0, 3_000.0, 0.0],
            },
            index=pd.DatetimeIndex(
                [
                    "2026-10-13 09:30",
                    "2026-10-13 15:55",
                    "2026-10-30 09:30",
                    "2026-10-30 15:40",
                    "2026-10-30 15:55",
                    "2026-10-30 16:00",
                ]
            ),
        )
        target_bars = pd.date_range("2026-10-30 09:30", "2026-10-30 15:55", freq="5min")
        target_frame = pd.DataFrame(
            {
                "open": [100.0] * len(target_bars),
                "high": [101.0] * len(target_bars),
                "low": [99.0] * len(target_bars),
                "close": [100.0] * len(target_bars),
                "volume": [1_000.0] * len(target_bars),
            },
            index=target_bars,
        )
        target_frame.loc[pd.Timestamp("2026-10-30 15:40"), ["open", "close"]] = [104.0, 105.0]
        target_frame.loc[pd.Timestamp("2026-10-30 15:55"), ["open", "close"]] = [106.0, 107.0]
        stale_and_target = pd.concat([stale_and_target.loc[stale_and_target.index.normalize() != MODULE.DAY], target_frame])

        original_fetch = MODULE.fetch_chart
        original_root = MODULE.ROOT
        calls = []

        def fake_fetch(symbol, start, end, interval):
            calls.append((start, end, interval))
            return stale_and_target.copy()

        with tempfile.TemporaryDirectory() as temp_dir:
            MODULE.fetch_chart = fake_fetch
            MODULE.ROOT = Path(temp_dir)
            MODULE.FETCH_END = "2026-10-31"
            try:
                rows = MODULE.collect_intraday()
            finally:
                MODULE.fetch_chart = original_fetch
                MODULE.ROOT = original_root

        self.assertEqual(len(rows), 9)
        self.assertTrue(all("error" not in row for row in rows), rows)
        self.assertTrue(all(row["trade_date"] == "2026-10-30" for row in rows))
        self.assertTrue(all(row["bars"] == len(target_bars) for row in rows))
        self.assertTrue(all(call == ("2026-10-30", "2026-10-31", "5m") for call in calls))
        expected_late = (107.0 / 104.0 - 1) * 100
        self.assertTrue(all(abs(row["late_return"] - expected_late) < 1e-9 for row in rows))


if __name__ == "__main__":
    unittest.main()
