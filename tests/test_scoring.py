import unittest

from daily_altcoin_recommendation.models import CoinMetrics
from daily_altcoin_recommendation.providers import _relative_return
from daily_altcoin_recommendation.scoring import _percentiles, rank_coins


def coin(coin_id, name, symbol, usd7, btc7, volume, tvl=None, usd24=1, usd30=10):
    return CoinMetrics(
        coin_id=coin_id, name=name, symbol=symbol, market_cap=1_000_000_000,
        volume_24h=volume, price_usd=1, usd_24h=usd24, usd_7d=usd7,
        usd_30d=usd30, btc_7d=btc7, eth_7d=btc7, tvl=tvl,
        tvl_change_1d=1 if tvl else None, tvl_change_7d=5 if tvl else None,
    )


class ScoringTests(unittest.TestCase):
    def test_equal_values_receive_equal_percentiles(self):
        first = coin("a", "A", "A", 1, 1, 10_000_000)
        second = coin("b", "B", "B", 1, 1, 10_000_000)
        scores = _percentiles([first, second], lambda item: item.usd_7d)
        self.assertEqual(scores["a"], scores["b"])

    def test_relative_return_is_computed_from_usd_returns(self):
        asset = {"price_change_percentage_7d_in_currency": 20}
        benchmark = {"price_change_percentage_7d_in_currency": 10}
        self.assertAlmostEqual(_relative_return(asset, benchmark, "7d"), 9.0909, places=3)

    def test_stronger_coin_ranks_first(self):
        weak = coin("weak", "Weak", "WEAK", -10, -12, 10_000_000, 10_000_000)
        strong = coin("strong", "Strong", "STR", 20, 18, 100_000_000, 500_000_000)
        result = rank_coins([weak, strong])
        self.assertEqual(result[0].metrics.coin_id, "strong")
        self.assertGreater(result[0].score, result[1].score)

    def test_pump_receives_risk_penalty(self):
        normal = coin("normal", "Normal", "NOR", 10, 10, 50_000_000, usd24=3)
        pump = coin("pump", "Pump", "PMP", 20, 20, 60_000_000, usd24=35, usd30=150)
        result = {item.metrics.coin_id: item for item in rank_coins([normal, pump])}
        self.assertEqual(result["pump"].risk_penalty, 30)
        self.assertTrue(result["pump"].risks)

    def test_minimum_liquidity_filter(self):
        illiquid = coin("tiny", "Tiny", "TNY", 99, 99, 1000)
        self.assertEqual(rank_coins([illiquid]), [])

    def test_bitcoin_is_used_as_benchmark_not_candidate(self):
        bitcoin = coin("bitcoin", "Bitcoin", "BTC", 10, 0, 1_000_000_000)
        altcoin = coin("altcoin", "Altcoin", "ALT", 5, -2, 100_000_000)
        result = rank_coins([bitcoin, altcoin])
        self.assertEqual([item.metrics.coin_id for item in result], ["altcoin"])

    def test_all_falling_market_reduces_momentum_score(self):
        falling = coin("falling", "Falling", "FAL", -18, -12, 100_000_000, usd30=-35)
        worse = coin("worse", "Worse", "WRS", -25, -20, 80_000_000, usd30=-45)
        result = rank_coins([falling, worse])
        self.assertLess(result[0].component_scores["Son 7 gün teyidi"], 75)

    def test_missing_long_history_gets_penalty(self):
        new_coin = coin("new", "New", "NEW", 15, 12, 100_000_000)
        mature = coin("mature", "Mature", "MAT", 8, 6, 90_000_000)
        mature.usd_200d = 40
        mature.usd_1y = 80
        result = {item.metrics.coin_id: item for item in rank_coins([new_coin, mature])}
        self.assertIn("Uzun dönem fiyat geçmişi yetersiz", result["new"].risks)
        self.assertGreaterEqual(result["new"].risk_penalty, 8)

    def test_catchup_requires_fundamental_support_and_rewards_divergence(self):
        lagger = coin("lagger", "Lagger", "LAG", -4, -8, 80_000_000, 500_000_000, usd30=-10)
        winner = coin("winner", "Winner", "WIN", 18, 12, 90_000_000, 500_000_000, usd30=30)
        for item in (lagger, winner):
            item.fully_diluted_valuation = 1_100_000_000
            item.usd_200d = 30
            item.usd_1y = 60
            item.tvl_change_1m = 20
            item.dex_volume_30d = 400_000_000
            item.dex_change_1m = 15
            item.btc_24h = 1
            item.eth_24h = 1
            item.btc_30d = -12 if item is lagger else 20
            item.eth_30d = -14 if item is lagger else 18
        result = {item.metrics.coin_id: item for item in rank_coins([lagger, winner])}
        self.assertGreater(
            result["lagger"].component_scores["Catch-up/Mismatch"],
            result["winner"].component_scores["Catch-up/Mismatch"],
        )

    def test_low_mc_fdv_receives_dilution_penalty(self):
        diluted = coin("diluted", "Diluted", "DIL", 5, 2, 50_000_000)
        diluted.fully_diluted_valuation = 4_000_000_000
        result = rank_coins([diluted])[0]
        self.assertIn("yüksek gelecekteki arz baskısı", " ".join(result.risks))
        self.assertGreaterEqual(result.risk_penalty, 12)

    def test_missing_defi_does_not_reweight_other_components(self):
        uncovered = coin("uncovered", "Uncovered", "UNC", 20, 20, 100_000_000)
        uncovered.fully_diluted_valuation = uncovered.market_cap
        uncovered.usd_200d = 100
        uncovered.usd_1y = 150
        result = rank_coins([uncovered])[0]
        self.assertNotIn("DeFi/Ekosistem", result.component_scores)
        self.assertLess(result.score, 80)


if __name__ == "__main__":
    unittest.main()
