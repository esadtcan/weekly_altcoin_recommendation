import unittest

from daily_altcoin_recommendation.models import CoinMetrics, RankedCoin
from daily_altcoin_recommendation.portfolio import allocate_basket


def ranked(index: int, score: float) -> RankedCoin:
    metrics = CoinMetrics(str(index), f"Coin {index}", f"C{index}", 1e9, 1e8, 1)
    return RankedCoin(metrics, score, {}, 0, [], [], [])


class PortfolioTests(unittest.TestCase):
    def test_allocations_total_exact_budget_and_favor_stronger_scores(self):
        basket = allocate_basket([ranked(0, 80), ranked(1, 70), ranked(2, 60)], 100, 3)
        self.assertEqual(round(sum(amount for _, amount in basket), 2), 100.00)
        self.assertGreater(basket[0][1], basket[1][1])
        self.assertGreater(basket[1][1], basket[2][1])

    def test_basket_respects_top_n(self):
        basket = allocate_basket([ranked(i, 80 - i) for i in range(6)], 100, 5)
        self.assertEqual(len(basket), 5)


if __name__ == "__main__":
    unittest.main()
