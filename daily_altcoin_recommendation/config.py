from dataclasses import dataclass
import os
from pathlib import Path


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Load a small, dependency-free .env file without overriding real env vars."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[0:1] == value[-1:] and value.startswith(("'", '"')):
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    coingecko_api_key: str = ""
    coingecko_plan: str = "demo"
    top_n: int = 5
    basket_budget_usd: float = 100.0
    universe_size: int = 120
    min_market_cap_usd: float = 50_000_000
    min_volume_usd: float = 5_000_000
    exclude_meme_coins: bool = True
    report_timezone: str = "Europe/Istanbul"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_to: str = ""
    smtp_starttls: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv()
        return cls(
            coingecko_api_key=os.getenv("COINGECKO_API_KEY", ""),
            coingecko_plan=os.getenv("COINGECKO_PLAN", "demo"),
            top_n=int(os.getenv("TOP_N", "5")),
            basket_budget_usd=float(os.getenv("BASKET_BUDGET_USD", "100")),
            universe_size=int(os.getenv("UNIVERSE_SIZE", "120")),
            min_market_cap_usd=float(os.getenv("MIN_MARKET_CAP_USD", "50000000")),
            min_volume_usd=float(os.getenv("MIN_VOLUME_USD", "5000000")),
            exclude_meme_coins=_as_bool(os.getenv("EXCLUDE_MEME_COINS", "true")),
            report_timezone=os.getenv("REPORT_TIMEZONE", "Europe/Istanbul"),
            smtp_host=os.getenv("SMTP_HOST", ""),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_from=os.getenv("SMTP_FROM", ""),
            smtp_to=os.getenv("SMTP_TO", ""),
            smtp_starttls=_as_bool(os.getenv("SMTP_STARTTLS", "true")),
        )
