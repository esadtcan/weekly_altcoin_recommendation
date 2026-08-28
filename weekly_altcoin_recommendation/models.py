from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CoinMetrics:
    coin_id: str
    name: str
    symbol: str
    market_cap: float
    volume_24h: float
    price_usd: float
    fully_diluted_valuation: Optional[float] = None
    usd_24h: Optional[float] = None
    usd_7d: Optional[float] = None
    usd_30d: Optional[float] = None
    usd_200d: Optional[float] = None
    usd_1y: Optional[float] = None
    btc_24h: Optional[float] = None
    btc_7d: Optional[float] = None
    btc_30d: Optional[float] = None
    btc_200d: Optional[float] = None
    btc_1y: Optional[float] = None
    eth_24h: Optional[float] = None
    eth_7d: Optional[float] = None
    eth_30d: Optional[float] = None
    eth_200d: Optional[float] = None
    eth_1y: Optional[float] = None
    tvl: Optional[float] = None
    tvl_change_1d: Optional[float] = None
    tvl_change_7d: Optional[float] = None
    tvl_change_1m: Optional[float] = None
    dex_volume_24h: Optional[float] = None
    dex_volume_7d: Optional[float] = None
    dex_volume_30d: Optional[float] = None
    dex_change_1d: Optional[float] = None
    dex_change_7d: Optional[float] = None
    dex_change_1m: Optional[float] = None
    defi_context: Optional[str] = None
    data_notes: List[str] = field(default_factory=list)


@dataclass
class RankedCoin:
    metrics: CoinMetrics
    score: float
    component_scores: Dict[str, float]
    risk_penalty: float
    reasons: List[str]
    risks: List[str]
    coverage: List[str]
