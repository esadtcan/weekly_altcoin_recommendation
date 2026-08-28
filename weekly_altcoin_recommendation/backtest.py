"""Point-in-time snapshot simulation for the curated 30-coin research universe."""

import argparse
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote

from .config import Settings
from .http import ApiError, get_json
from .models import CoinMetrics
from .providers import (
    CoinGeckoProvider,
    _best_match,
    _index_rows,
    _name_match,
    _relative_return,
)
from .scoring import rank_coins


RESEARCH_UNIVERSE = {
    "aave", "ondo-finance", "solana", "uniswap", "chainlink", "hyperliquid",
    "near", "bittensor", "morpho", "sui", "avalanche-2", "injective-protocol",
    "ethereum", "binancecoin", "ethena", "arbitrum", "ripple", "hedera-hashgraph",
    "internet-computer", "mantle", "tron", "stellar", "render-token", "cardano",
    "sky", "polkadot", "worldcoin-wld", "zcash", "monero",
}


def _timestamp(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())


def _daily_map(rows: Iterable[List[Any]]) -> Dict[date, float]:
    result: Dict[date, float] = {}
    for timestamp_ms, value in rows:
        if value is not None:
            result[datetime.fromtimestamp(float(timestamp_ms) / 1000, timezone.utc).date()] = float(value)
    return result


def _tvl_map(rows: Iterable[Dict[str, Any]]) -> Dict[date, float]:
    result: Dict[date, float] = {}
    for row in rows:
        value = row.get("tvl", row.get("totalLiquidityUSD"))
        if value is not None:
            result[datetime.fromtimestamp(float(row["date"]), timezone.utc).date()] = float(value)
    return result


def _on_or_before(values: Dict[date, float], day: date, tolerance: int = 3) -> Optional[float]:
    for offset in range(tolerance + 1):
        found = values.get(day - timedelta(days=offset))
        if found is not None:
            return found
    return None


def _return(values: Dict[date, float], end: date, days: int) -> Optional[float]:
    current = _on_or_before(values, end)
    previous = _on_or_before(values, end - timedelta(days=days))
    if current is None or previous in (None, 0):
        return None
    return (current / previous - 1) * 100


class HistoricalLoader:
    def __init__(self, settings: Settings, cache_dir: Path) -> None:
        self.settings = settings
        self.coingecko = CoinGeckoProvider(settings.coingecko_api_key, settings.coingecko_plan)
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_coingecko_call = 0.0

    def _wait_for_coingecko(self) -> None:
        remaining = 8.0 - (time.monotonic() - self._last_coingecko_call)
        if remaining > 0:
            time.sleep(remaining)
        self._last_coingecko_call = time.monotonic()

    def _cached(self, key: str, fetcher) -> Any:
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        last_error: Optional[Exception] = None
        for attempt in range(4):
            try:
                value = fetcher()
                path.write_text(json.dumps(value), encoding="utf-8")
                return value
            except ApiError as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(15 * (attempt + 1))
        raise RuntimeError(f"Historical data failed for {key}: {last_error}")

    def metadata(self) -> List[Dict[str, Any]]:
        ids = sorted(RESEARCH_UNIVERSE | {"bitcoin"})
        return self._cached(
            "research_universe_metadata",
            lambda: self._fetch_metadata(ids),
        )

    def _fetch_metadata(self, ids: List[str]) -> List[Dict[str, Any]]:
        self._wait_for_coingecko()
        return get_json(
            f"{self.coingecko.base_url}/coins/markets",
            params={"vs_currency": "usd", "ids": ",".join(ids), "per_page": len(ids), "page": 1, "sparkline": "false"},
            headers=self.coingecko.headers,
            retries=1,
        )

    def market_chart(self, coin_id: str, start: date, end: date) -> Dict[str, Any]:
        cache_key = f"market_{coin_id}_{start.isoformat()}_{end.isoformat()}"
        value = self._cached(
            cache_key,
            lambda: self._fetch_market_chart(coin_id, start, end),
        )
        return value

    def _fetch_market_chart(self, coin_id: str, start: date, end: date) -> Dict[str, Any]:
        self._wait_for_coingecko()
        return get_json(
            f"{self.coingecko.base_url}/coins/{quote(coin_id)}/market_chart/range",
            params={"vs_currency": "usd", "from": _timestamp(start), "to": _timestamp(end + timedelta(days=1))},
            headers=self.coingecko.headers,
            retries=1,
        )

    def tvl_history(self, coin: CoinMetrics, chains, protocols) -> Optional[Dict[date, float]]:
        chain = _name_match(coin, _index_rows(chains))
        if chain:
            chain_name = str(chain.get("name", coin.name))
            rows = self._cached(
                f"chain_tvl_{coin.coin_id}",
                lambda: get_json(f"https://api.llama.fi/v2/historicalChainTvl/{quote(chain_name)}"),
            )
            return _tvl_map(rows)
        protocol = _best_match(coin, _index_rows(protocols))
        if protocol:
            slug = str(protocol.get("slug") or protocol.get("name") or coin.coin_id)
            payload = self._cached(
                f"protocol_tvl_{coin.coin_id}",
                lambda: get_json(f"https://api.llama.fi/protocol/{quote(slug)}"),
            )
            return _tvl_map(payload.get("tvl", []))
        return None


def simulate(
    as_of: date,
    settings: Settings,
    data_start: Optional[date] = None,
    data_end: Optional[date] = None,
) -> Tuple[List[Any], Dict[str, float], Dict[str, Any]]:
    end = as_of + timedelta(days=7)
    start = data_start or as_of - timedelta(days=210)
    market_data_end = data_end or end
    loader = HistoricalLoader(settings, Path("data/backtest_cache"))
    metadata = {row["id"]: row for row in loader.metadata()}
    series: Dict[str, Dict[str, Dict[date, float]]] = {}
    for coin_id in sorted(RESEARCH_UNIVERSE | {"bitcoin"}):
        payload = loader.market_chart(coin_id, start, market_data_end)
        series[coin_id] = {
            "prices": _daily_map(payload.get("prices", [])),
            "market_caps": _daily_map(payload.get("market_caps", [])),
            "volumes": _daily_map(payload.get("total_volumes", [])),
        }

    benchmark_rows: Dict[str, Dict[str, Optional[float]]] = {}
    for benchmark in ("bitcoin", "ethereum"):
        prices = series[benchmark]["prices"]
        benchmark_rows[benchmark] = {
            f"price_change_percentage_{period}_in_currency": _return(prices, as_of, days)
            for period, days in (("24h", 1), ("7d", 7), ("30d", 30), ("200d", 200), ("1y", 365))
        }

    coins: List[CoinMetrics] = []
    for coin_id in sorted(RESEARCH_UNIVERSE):
        row = metadata.get(coin_id)
        if not row:
            continue
        coin_series = series[coin_id]
        prices = coin_series["prices"]
        historical_mc = _on_or_before(coin_series["market_caps"], as_of) or 0
        current_mc = float(row.get("market_cap") or 0)
        current_fdv = float(row.get("fully_diluted_valuation") or 0)
        estimated_fdv = historical_mc / (current_mc / current_fdv) if current_mc and current_fdv else None
        asset_returns = {
            f"price_change_percentage_{period}_in_currency": _return(prices, as_of, days)
            for period, days in (("24h", 1), ("7d", 7), ("30d", 30), ("200d", 200), ("1y", 365))
        }
        coins.append(CoinMetrics(
            coin_id=coin_id,
            name=str(row.get("name", coin_id)),
            symbol=str(row.get("symbol", "")).upper(),
            market_cap=historical_mc,
            volume_24h=_on_or_before(coin_series["volumes"], as_of) or 0,
            price_usd=_on_or_before(prices, as_of) or 0,
            fully_diluted_valuation=estimated_fdv,
            usd_24h=asset_returns["price_change_percentage_24h_in_currency"],
            usd_7d=asset_returns["price_change_percentage_7d_in_currency"],
            usd_30d=asset_returns["price_change_percentage_30d_in_currency"],
            usd_200d=asset_returns["price_change_percentage_200d_in_currency"],
            usd_1y=None,
            btc_24h=_relative_return(asset_returns, benchmark_rows["bitcoin"], "24h"),
            btc_7d=_relative_return(asset_returns, benchmark_rows["bitcoin"], "7d"),
            btc_30d=_relative_return(asset_returns, benchmark_rows["bitcoin"], "30d"),
            btc_200d=_relative_return(asset_returns, benchmark_rows["bitcoin"], "200d"),
            eth_24h=_relative_return(asset_returns, benchmark_rows["ethereum"], "24h"),
            eth_7d=_relative_return(asset_returns, benchmark_rows["ethereum"], "7d"),
            eth_30d=_relative_return(asset_returns, benchmark_rows["ethereum"], "30d"),
            eth_200d=_relative_return(asset_returns, benchmark_rows["ethereum"], "200d"),
        ))

    chains = loader._cached("defillama_chains", lambda: get_json("https://api.llama.fi/v2/chains"))
    protocols = loader._cached("defillama_protocols", lambda: get_json("https://api.llama.fi/protocols"))
    for coin in coins:
        try:
            tvl = loader.tvl_history(coin, chains, protocols)
        except Exception as exc:
            coin.data_notes.append(f"Tarihsel TVL alınamadı: {exc}")
            continue
        if tvl:
            coin.tvl = _on_or_before(tvl, as_of)
            coin.tvl_change_1d = _return(tvl, as_of, 1)
            coin.tvl_change_7d = _return(tvl, as_of, 7)
            coin.tvl_change_1m = _return(tvl, as_of, 30)
            coin.defi_context = "tarihsel zincir/protokol"

    ranked = rank_coins(coins, settings.min_market_cap_usd, settings.min_volume_usd)
    forward_returns = {
        coin_id: _return(values["prices"], end, 7)
        for coin_id, values in series.items()
    }
    limitations = {
        "as_of": as_of.isoformat(),
        "end": end.isoformat(),
        "universe": len(ranked),
        "price_history_days": 200,
        "fdv": "Current MC/FDV ratio applied to historical market cap",
        "missing": ["historical DEX volumes", "news", "X/Reddit", "exact historical supply/unlocks"],
    }
    return ranked, forward_returns, limitations


def main() -> None:
    parser = argparse.ArgumentParser(description="Bir tarih için noktasal coin sıralaması simülasyonu")
    parser.add_argument("--as-of", required=True, help="YYYY-MM-DD; sonraki 7 gün ölçülür")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--daily-through", help="YYYY-MM-DD; --as-of gününden bu güne kadar her günün önerilerini yazdır")
    args = parser.parse_args()
    as_of = date.fromisoformat(args.as_of)
    settings = Settings.from_env()
    if args.daily_through:
        through = date.fromisoformat(args.daily_through)
        if through < as_of:
            parser.error("--daily-through, --as-of tarihinden önce olamaz")
        shared_start = as_of - timedelta(days=211)
        current = as_of
        while current <= through:
            ranked, _, limitations = simulate(current, settings, shared_start, through)
            picks = ranked[:args.top]
            print(f"DATE {current.isoformat()} ELIGIBLE {limitations['universe']}")
            for index, item in enumerate(picks, 1):
                catchup = item.component_scores.get("Catch-up/Mismatch")
                catchup_text = f" catchup={catchup:.1f}" if catchup is not None else ""
                print(f"{index}. {item.metrics.name} ({item.metrics.symbol}) score={item.score:.1f}{catchup_text}")
            sui = next(((index, item) for index, item in enumerate(ranked, 1) if item.metrics.coin_id == "sui"), None)
            if sui:
                catchup = sui[1].component_scores.get("Catch-up/Mismatch")
                catchup_text = f" catchup={catchup:.1f}" if catchup is not None else ""
                print(f"SUI rank={sui[0]}/{len(ranked)} score={sui[1].score:.1f}{catchup_text}")
            current += timedelta(days=1)
        return
    ranked, forward, limitations = simulate(as_of, settings)
    picks = ranked[:args.top]
    print(f"SIMULATION {limitations['as_of']} -> {limitations['end']}")
    print(f"ELIGIBLE {limitations['universe']}")
    returns: List[float] = []
    for index, item in enumerate(picks, 1):
        realized = forward.get(item.metrics.coin_id)
        if realized is not None:
            returns.append(realized)
        realized_text = f"{realized:+.2f}%" if realized is not None else "N/A"
        print(f"{index}. {item.metrics.name} ({item.metrics.symbol}) score={item.score:.1f} next7d={realized_text}")
    if returns:
        print(f"EQUAL_WEIGHT_RETURN {sum(returns) / len(returns):+.2f}%")
    for benchmark in ("bitcoin", "ethereum"):
        value = forward.get(benchmark)
        if value is not None:
            print(f"BENCHMARK {benchmark.upper()} {value:+.2f}%")
    sui = next(((index, item) for index, item in enumerate(ranked, 1) if item.metrics.coin_id == "sui"), None)
    if sui:
        value = forward.get("sui")
        print(f"SUI rank={sui[0]}/{len(ranked)} score={sui[1].score:.1f} next7d={value:+.2f}%")
    print("LIMITATIONS " + json.dumps(limitations, ensure_ascii=False))


if __name__ == "__main__":
    main()
