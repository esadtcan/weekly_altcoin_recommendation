from datetime import date, datetime, timezone
import unittest

from weekly_altcoin_recommendation.backtest import _daily_map, _on_or_before, _return


class BacktestTests(unittest.TestCase):
    def test_daily_series_and_return_use_only_prior_values(self):
        values = _daily_map([
            [datetime(2026, 8, 20, tzinfo=timezone.utc).timestamp() * 1000, 100],
            [datetime(2026, 8, 21, tzinfo=timezone.utc).timestamp() * 1000, 110],
        ])
        self.assertEqual(_on_or_before(values, date(2026, 8, 20)), 100)
        self.assertAlmostEqual(_return(values, date(2026, 8, 21), 1), 10)

    def test_on_or_before_does_not_read_future_value(self):
        values = {date(2026, 8, 14): 200}
        self.assertIsNone(_on_or_before(values, date(2026, 8, 13)))


if __name__ == "__main__":
    unittest.main()
