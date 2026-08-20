from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .http import get_json
from .models import CoinMetrics


STABLE_IDS = {
    "tether", "usd-coin", "dai", "first-digital-usd", "ethena-usde",
    "usds", "paypal-usd", "frax", "true-usd", "usdd", "usdb",
}
STABLE_SYMBOLS = {"usdt", "usdc", "dai", "fdusd", "usde", "usds", "pyusd", "tusd", "usdd"}

CHAIN_ALIASES = {
    "avalanche-2": "Avalanche",
    "binancecoin": "BSC",
    "hyperliquid": "Hyperliquid L1",
    "matic-network": "Polygon",
    "near": "Near",
}


class CoinGeckoProvider:
    def __init__(self, api_key: str = "", plan: str = "demo") -> None:
        self.api_key = api_key
        self.base_url = "https://pro-api.coingecko.com/api/v3" if plan == "pro" else "https://api.coingecko.com/api/v3"

    @property
    def headers(self) -> Dict[str, str]:
        if not self.api_key:
            return {}
        header = "x-cg-pro-api-key" if "pro-api" in self.base_url else "x-cg-demo-api-key"
        return {header: self.api_key}

    def _markets(self, currency: str, per_page: int, category: str = "") -> List[Dict[str, Any]]:
        params = {
            "vs_currency": currency,
            "order": "market_cap_desc",
            "per_page": min(per_page, 250),
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h,7d,30d,200d,1y",
        }
        if category:
            params["category"] = category
        return get_json(
            f"{self.base_url}/coins/markets",
            params=params,
            headers=self.headers,
        )

    def fetch_universe(self, size: int, exclude_meme_coins: bool = True) -> List[CoinMetrics]:
        usd = self._markets("usd", size)
        by_id = {row["id"]: row for row in usd}
        bitcoin = by_id.get("bitcoin", {})
        ethereum = by_id.get("ethereum", {})
        excluded_ids = set(STABLE_IDS)
        if exclude_meme_coins:
            excluded_ids.update(row["id"] for row in self._markets("usd", 250, "meme-token"))
        coins: List[CoinMetrics] = []
        for row in usd:
            symbol = str(row.get("symbol", "")).lower()
            if row.get("id") in excluded_ids or symbol in STABLE_SYMBOLS:
                continue
            coins.append(CoinMetrics(
                coin_id=row["id"],
                name=row.get("name", row["id"]),
                symbol=symbol.upper(),
                market_cap=float(row.get("market_cap") or 0),
                volume_24h=float(row.get("total_volume") or 0),
                price_usd=float(row.get("current_price") or 0),
                fully_diluted_valuation=_number(row.get("fully_diluted_valuation")),
                usd_24h=_number(row.get("price_change_percentage_24h_in_currency")),
                usd_7d=_number(row.get("price_change_percentage_7d_in_currency")),
                usd_30d=_number(row.get("price_change_percentage_30d_in_currency")),
                usd_200d=_number(row.get("price_change_percentage_200d_in_currency")),
                usd_1y=_number(row.get("price_change_percentage_1y_in_currency")),
                btc_24h=_relative_return(row, bitcoin, "24h"),
                btc_7d=_relative_return(row, bitcoin, "7d"),
                btc_30d=_relative_return(row, bitcoin, "30d"),
                btc_200d=_relative_return(row, bitcoin, "200d"),
                btc_1y=_relative_return(row, bitcoin, "1y"),
                eth_24h=_relative_return(row, ethereum, "24h"),
                eth_7d=_relative_return(row, ethereum, "7d"),
                eth_30d=_relative_return(row, ethereum, "30d"),
                eth_200d=_relative_return(row, ethereum, "200d"),
                eth_1y=_relative_return(row, ethereum, "1y"),
            ))
        return coins


class DefiLlamaProvider:
    def fetch(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        chains = get_json("https://api.llama.fi/v2/chains")
        protocols = get_json("https://api.llama.fi/protocols")
        dex = get_json(
            "https://api.llama.fi/overview/dexs",
            params={
                "excludeTotalDataChart": "true",
                "excludeTotalDataChartBreakdown": "true",
                "dataType": "dailyVolume",
            },
        )
        return chains, protocols, dex.get("protocols", []) if isinstance(dex, dict) else []

    def enrich(self, coins: Iterable[CoinMetrics], chains: List[Dict[str, Any]], protocols: List[Dict[str, Any]], dexes: List[Dict[str, Any]]) -> None:
        chain_index = _index_rows(chains)
        protocol_index = _index_rows(protocols)
        dex_index = _index_rows(dexes)
        for coin in coins:
            chain = _name_match(coin, chain_index)
            protocol = _best_match(coin, protocol_index)
            defi_row = chain or protocol
            if defi_row:
                coin.tvl = _number(defi_row.get("tvl"))
                coin.tvl_change_1d = _number(defi_row.get("change_1d"))
                coin.tvl_change_7d = _number(defi_row.get("change_7d"))
                coin.tvl_change_1m = _number(defi_row.get("change_1m"))
                coin.defi_context = "zincir" if chain else "protokol"
            dex = _best_match(coin, dex_index)
            if dex:
                coin.dex_volume_24h = _number(dex.get("total24h"))
                coin.dex_volume_7d = _number(dex.get("total7d"))
                coin.dex_volume_30d = _number(dex.get("total30d"))
                coin.dex_change_1d = _number(dex.get("change_1d"))
                coin.dex_change_7d = _number(dex.get("change_7d"))
                coin.dex_change_1m = _number(dex.get("change_1m"))
            if not defi_row and not dex:
                coin.data_notes.append("DeFiLlama eşleşmesi bulunamadı")


def _number(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _relative_return(asset: Dict[str, Any], benchmark: Dict[str, Any], period: str) -> Optional[float]:
    key = f"price_change_percentage_{period}_in_currency"
    asset_return = _number(asset.get(key))
    benchmark_return = _number(benchmark.get(key))
    if asset_return is None or benchmark_return is None or benchmark_return <= -100:
        return None
    return ((1 + asset_return / 100) / (1 + benchmark_return / 100) - 1) * 100


def _normal(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _index_rows(rows: Iterable[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    index: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for key in (row.get("name"), row.get("displayName"), row.get("symbol")):
            if key:
                index[_normal(str(key))].append(row)
    return index


def _best_match(coin: CoinMetrics, index: Dict[str, List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    # Exact name is safer than ticker-only matching; ticker collisions are common in crypto.
    exact_name = index.get(_normal(coin.name), [])
    if exact_name:
        return max(exact_name, key=lambda row: float(row.get("tvl") or row.get("total24h") or 0))
    symbol_rows = index.get(_normal(coin.symbol), [])
    if len(symbol_rows) == 1:
        return symbol_rows[0]
    return None


def _name_match(coin: CoinMetrics, index: Dict[str, List[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    alias = CHAIN_ALIASES.get(coin.coin_id)
    if alias:
        alias_rows = index.get(_normal(alias), [])
        if len(alias_rows) == 1:
            return alias_rows[0]
    rows = index.get(_normal(coin.name), [])
    return rows[0] if len(rows) == 1 else None
