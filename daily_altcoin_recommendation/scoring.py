import math
from typing import Callable, Dict, Iterable, List, Optional

from .models import CoinMetrics, RankedCoin


def _percentiles(coins: List[CoinMetrics], getter: Callable[[CoinMetrics], Optional[float]]) -> Dict[str, float]:
    values = sorted((value, coin.coin_id) for coin in coins if (value := getter(coin)) is not None)
    if not values:
        return {}
    if len(values) == 1:
        return {values[0][1]: 50.0}
    result: Dict[str, float] = {}
    index = 0
    while index < len(values):
        end = index + 1
        while end < len(values) and values[end][0] == values[index][0]:
            end += 1
        average_rank = (index + end - 1) / 2
        percentile = average_rank * 100.0 / (len(values) - 1)
        for _, coin_id in values[index:end]:
            result[coin_id] = percentile
        index = end
    return result


def rank_coins(
    coins: Iterable[CoinMetrics],
    min_market_cap: float = 50_000_000,
    min_volume: float = 5_000_000,
) -> List[RankedCoin]:
    eligible = [
        coin for coin in coins
        if coin.coin_id != "bitcoin"
        and coin.market_cap >= min_market_cap
        and coin.volume_24h >= min_volume
    ]
    if not eligible:
        return []

    metrics = {
        "usd24": _percentiles(eligible, lambda c: c.usd_24h),
        "usd7": _percentiles(eligible, lambda c: c.usd_7d),
        "usd30": _percentiles(eligible, lambda c: c.usd_30d),
        "usd200": _percentiles(eligible, lambda c: c.usd_200d),
        "usd1y": _percentiles(eligible, lambda c: c.usd_1y),
        "catchup_lag": _percentiles(eligible, _catchup_lag),
        "fundamental_gap": _percentiles(eligible, _fundamental_price_gap),
        "tvl_mcap": _percentiles(eligible, lambda c: c.tvl / c.market_cap if c.tvl and c.market_cap else None),
        "dex_mcap": _percentiles(eligible, lambda c: c.dex_volume_30d / c.market_cap if c.dex_volume_30d and c.market_cap else None),
        "btc7": _percentiles(eligible, lambda c: c.btc_7d),
        "btc30": _percentiles(eligible, lambda c: c.btc_30d),
        "btc200": _percentiles(eligible, lambda c: c.btc_200d),
        "btc1y": _percentiles(eligible, lambda c: c.btc_1y),
        "eth7": _percentiles(eligible, lambda c: c.eth_7d),
        "eth30": _percentiles(eligible, lambda c: c.eth_30d),
        "eth200": _percentiles(eligible, lambda c: c.eth_200d),
        "eth1y": _percentiles(eligible, lambda c: c.eth_1y),
        "volume": _percentiles(eligible, lambda c: math.log10(max(c.volume_24h, 1))),
        "turnover": _percentiles(eligible, lambda c: c.volume_24h / max(c.market_cap, 1)),
        "tvl": _percentiles(eligible, lambda c: math.log10(max(c.tvl or 0, 1)) if c.tvl else None),
        "tvl7": _percentiles(eligible, lambda c: c.tvl_change_7d),
        "tvl1m": _percentiles(eligible, lambda c: c.tvl_change_1m),
        "dex": _percentiles(eligible, lambda c: math.log10(max(c.dex_volume_24h or 0, 1)) if c.dex_volume_24h else None),
        "dex30": _percentiles(eligible, lambda c: math.log10(max(c.dex_volume_30d or 0, 1)) if c.dex_volume_30d else None),
        "dex1": _percentiles(eligible, lambda c: c.dex_change_1d),
        "dex7": _percentiles(eligible, lambda c: c.dex_change_7d),
        "dex1m": _percentiles(eligible, lambda c: c.dex_change_1m),
    }
    ranked = [_score_coin(coin, metrics) for coin in eligible]
    return sorted(ranked, key=lambda item: item.score, reverse=True)


def _average(values: List[Optional[float]]) -> Optional[float]:
    present = [value for value in values if value is not None]
    return sum(present) / len(present) if present else None


def _weighted_average(values: List[tuple[Optional[float], float]]) -> Optional[float]:
    present = [(value, weight) for value, weight in values if value is not None]
    if not present:
        return None
    return sum(value * weight for value, weight in present) / sum(weight for _, weight in present)


def _bounded_score(value: Optional[float], low: float, high: float) -> Optional[float]:
    if value is None:
        return None
    return max(0.0, min(100.0, (value - low) * 100.0 / (high - low)))


def _score_coin(coin: CoinMetrics, p: Dict[str, Dict[str, float]]) -> RankedCoin:
    key = coin.coin_id
    components: Dict[str, float] = {}
    # The basket is rebuilt weekly, so seven-day signals receive three times
    # the influence of the noisier 24-hour move.
    short_relative = _weighted_average([
        (p["usd24"].get(key), 1), (p["usd7"].get(key), 3),
        (p["btc7"].get(key), 3), (p["eth7"].get(key), 3),
    ])
    short_absolute = _weighted_average([
        (_bounded_score(coin.usd_24h, -12, 12), 1),
        (_bounded_score(coin.usd_7d, -20, 20), 3),
        (_bounded_score(coin.btc_7d, -15, 15), 3),
        (_bounded_score(coin.eth_7d, -15, 15), 3),
    ])
    short_term = _blend(short_relative, short_absolute, 0.55)
    long_relative = _average([
        p["usd30"].get(key), p["usd200"].get(key), p["usd1y"].get(key),
        p["btc30"].get(key), p["btc200"].get(key), p["btc1y"].get(key),
        p["eth30"].get(key), p["eth200"].get(key), p["eth1y"].get(key),
    ])
    long_absolute = _average([
        _bounded_score(coin.usd_30d, -40, 70),
        _bounded_score(coin.usd_200d, -70, 200),
        _bounded_score(coin.usd_1y, -80, 300),
        _bounded_score(coin.btc_30d, -25, 25),
        _bounded_score(coin.btc_200d, -50, 100),
        _bounded_score(coin.btc_1y, -60, 150),
        _bounded_score(coin.eth_30d, -25, 25),
        _bounded_score(coin.eth_200d, -50, 100),
        _bounded_score(coin.eth_1y, -60, 150),
    ])
    long_term = _blend(long_relative, long_absolute, 0.55)
    liquidity = _average([p["volume"].get(key), p["turnover"].get(key)])
    defi = _weighted_average([
        (p["tvl"].get(key), 1), (p["tvl7"].get(key), 3), (p["tvl1m"].get(key), 1),
        (p["dex"].get(key), 1), (p["dex30"].get(key), 1), (p["dex1"].get(key), 1),
        (p["dex7"].get(key), 3), (p["dex1m"].get(key), 1),
    ])
    tokenomics = _tokenomics_score(coin)
    catch_up = None
    if defi is not None:
        catch_up = _average([
            p["catchup_lag"].get(key),
            p["fundamental_gap"].get(key),
            p["tvl_mcap"].get(key),
            p["dex_mcap"].get(key),
            _catchup_confirmation(coin),
        ])
        support = _average([defi, long_term, tokenomics])
        if catch_up is not None and (support is None or support < 50):
            catch_up = min(catch_up, 45.0)
        if catch_up is not None and coin.usd_200d is not None and coin.usd_200d < -60:
            ecosystem_growth = _average([coin.tvl_change_1m, coin.dex_change_1m])
            if ecosystem_growth is None or ecosystem_growth <= 0:
                catch_up = min(catch_up, 25.0)
    if short_term is not None:
        components["Son 7 gün teyidi"] = short_term
    if long_term is not None:
        components["Uzun vadeli güç"] = long_term
    if liquidity is not None:
        components["Likidite"] = liquidity
    if defi is not None:
        components["DeFi/Ekosistem"] = defi
    if tokenomics is not None:
        components["Tokenomics"] = tokenomics
    if catch_up is not None:
        components["Catch-up/Mismatch"] = catch_up

    base_weights = {
        "Son 7 gün teyidi": 0.30,
        "Uzun vadeli güç": 0.15,
        "Likidite": 0.15,
        "DeFi/Ekosistem": 0.20,
        "Tokenomics": 0.10,
        "Catch-up/Mismatch": 0.10,
    }
    # Missing coverage must not make the remaining strong components more
    # influential. Unknown components stay neutral until a provider supplies data.
    raw = sum(components.get(name, 50.0) * weight for name, weight in base_weights.items())
    penalty, risks = _risk_penalty(coin)
    score = max(0.0, min(100.0, raw - penalty))

    reasons: List[str] = []
    if coin.btc_7d is not None and coin.eth_7d is not None:
        reasons.append(f"7 günde BTC'ye göre %{coin.btc_7d:+.1f}, ETH'ye göre %{coin.eth_7d:+.1f}")
    if catch_up is not None:
        gap = _fundamental_price_gap(coin)
        if gap is not None:
            reasons.append(f"30 günlük fundamental/fiyat ayrışması {gap:+.1f} puan")
    if coin.usd_30d is not None:
        long_parts = [f"30g %{coin.usd_30d:+.1f}"]
        if coin.usd_200d is not None:
            long_parts.append(f"200g %{coin.usd_200d:+.1f}")
        if coin.usd_1y is not None:
            long_parts.append(f"1y %{coin.usd_1y:+.1f}")
        reasons.append("USD performansı: " + ", ".join(long_parts))
    if coin.tvl is not None and coin.tvl > 0:
        context = coin.defi_context or "ekosistem/protokol"
        reasons.append(f"Eşleşen {context} TVL'si ${_compact(coin.tvl)}")
    if coin.dex_volume_24h is not None:
        dex_text = f"24s ${_compact(coin.dex_volume_24h)}"
        if coin.dex_volume_30d is not None:
            dex_text += f", 30g ${_compact(coin.dex_volume_30d)}"
        reasons.append(f"DEX hacmi: {dex_text}")
    reasons.append(f"24 saatlik piyasa hacmi ${_compact(coin.volume_24h)}")
    if coin.fully_diluted_valuation and coin.market_cap:
        reasons.append(f"MC/FDV oranı {coin.market_cap / coin.fully_diluted_valuation:.2f}")

    coverage = ["24s/7g piyasa", "30g/200g/1y fiyat", "BTC/ETH göreli güç", "MC/FDV"]
    if defi is not None:
        coverage.append("DeFiLlama")
    else:
        coverage.append("DeFi verisi yok")
    coverage.extend(["Haberler: henüz bağlı değil", "X/Reddit: henüz bağlı değil"])
    return RankedCoin(coin, round(score, 1), {k: round(v, 1) for k, v in components.items()}, penalty, reasons, risks, coverage)


def _risk_penalty(coin: CoinMetrics):
    penalty = 0.0
    risks: List[str] = []
    if coin.usd_24h is not None and coin.usd_24h > 20:
        penalty += 12
        risks.append("24 saatte aşırı fiyat artışı; tepeden alım riski")
    if coin.usd_30d is not None and coin.usd_30d > 100:
        penalty += 10
        risks.append("30 günlük artış %100 üzerinde")
    if coin.tvl_change_1d is not None and coin.tvl_change_1d < -10:
        penalty += 18
        risks.append("TVL son 24 saatte %10'dan fazla düştü")
    if coin.volume_24h / max(coin.market_cap, 1) > 1.5:
        penalty += 8
        risks.append("Olağandışı yüksek hacim/piyasa değeri oranı")
    if coin.usd_200d is None and coin.usd_1y is None:
        penalty += 8
        risks.append("Uzun dönem fiyat geçmişi yetersiz")
    if coin.fully_diluted_valuation and coin.market_cap:
        mc_fdv = coin.market_cap / coin.fully_diluted_valuation
        if mc_fdv < 0.35:
            penalty += 12
            risks.append("MC/FDV %35 altında; yüksek gelecekteki arz baskısı")
        elif mc_fdv < 0.55:
            penalty += 6
            risks.append("MC/FDV %55 altında; belirgin gelecekteki arz baskısı")
    return penalty, risks


def _blend(relative: Optional[float], absolute: Optional[float], relative_weight: float) -> Optional[float]:
    if relative is not None and absolute is not None:
        return relative * relative_weight + absolute * (1 - relative_weight)
    return relative if relative is not None else absolute


def _tokenomics_score(coin: CoinMetrics) -> Optional[float]:
    if not coin.fully_diluted_valuation or not coin.market_cap:
        return None
    return _bounded_score(coin.market_cap / coin.fully_diluted_valuation, 0.25, 1.0)


def _catchup_lag(coin: CoinMetrics) -> Optional[float]:
    relative_performance = _average([coin.btc_7d, coin.eth_7d, coin.btc_30d, coin.eth_30d])
    return -relative_performance if relative_performance is not None else None


def _fundamental_price_gap(coin: CoinMetrics) -> Optional[float]:
    fundamental_growth = _average([coin.tvl_change_1m, coin.dex_change_1m])
    if fundamental_growth is None or coin.usd_30d is None:
        return None
    return max(-200.0, min(200.0, fundamental_growth - coin.usd_30d))


def _catchup_confirmation(coin: CoinMetrics) -> Optional[float]:
    # A laggard only receives a strong confirmation score once very recent
    # relative performance starts to improve; persistent weakness is not rewarded.
    return _average([
        _bounded_score(coin.btc_24h, -6, 6),
        _bounded_score(coin.eth_24h, -6, 6),
    ])


def _compact(value: float) -> str:
    for divisor, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if value >= divisor:
            return f"{value / divisor:.2f}{suffix}"
    return f"{value:.0f}"
