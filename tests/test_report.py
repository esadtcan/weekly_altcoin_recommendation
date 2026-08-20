from datetime import datetime, timezone
import unittest

from coin_advisor.models import CoinMetrics, RankedCoin
from coin_advisor.report import render_report


class ReportTests(unittest.TestCase):
    def test_report_limits_candidates_and_escapes_html(self):
        ranked = []
        for index in range(6):
            metrics = CoinMetrics(str(index), f"Coin <{index}>", "TST", 1e9, 1e8, 1)
            ranked.append(RankedCoin(metrics, 80 - index, {"Likidite": 70}, 0, ["Test"], [], ["Piyasa"]))
        plain, html = render_report(ranked, datetime.now(timezone.utc), top_n=5)
        self.assertIn("Coin &lt;0&gt;", html)
        self.assertNotIn("Coin &lt;5&gt;", html)
        self.assertIn("Coin <0>", plain)


if __name__ == "__main__":
    unittest.main()
