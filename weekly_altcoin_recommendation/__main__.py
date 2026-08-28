import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import Settings
from .providers import CoinGeckoProvider, DefiLlamaProvider
from .portfolio import allocate_basket
from .report import render_report, send_email
from .scoring import rank_coins


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Haftalık 100 USD altcoin sepeti üretir")
    parser.add_argument("--dry-run", action="store_true", help="E-posta gönderme, raporu dosyaya yaz")
    parser.add_argument("--output", default="reports/latest.html", help="HTML çıktı yolu")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = Settings.from_env()
    coins = CoinGeckoProvider(settings.coingecko_api_key, settings.coingecko_plan).fetch_universe(
        settings.universe_size, settings.exclude_meme_coins
    )
    try:
        chains, protocols, dexes = DefiLlamaProvider().fetch()
        DefiLlamaProvider().enrich(coins, chains, protocols, dexes)
    except Exception as exc:
        for coin in coins:
            coin.data_notes.append(f"DeFiLlama alınamadı: {exc}")
    ranked = rank_coins(coins, settings.min_market_cap_usd, settings.min_volume_usd)
    now = datetime.now(ZoneInfo(settings.report_timezone))
    plain, html = render_report(ranked, now, settings.top_n, settings.basket_budget_usd)
    if args.dry_run:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(html, encoding="utf-8")
        print(f"Rapor oluşturuldu: {output.resolve()}")
        for index, (item, amount) in enumerate(
            allocate_basket(ranked, settings.basket_budget_usd, settings.top_n), 1
        ):
            print(f"{index}. {item.metrics.name} ({item.metrics.symbol}): ${amount:.2f}, puan {item.score:.1f}")
    else:
        subject = f"Haftalık ${settings.basket_budget_usd:.0f} Altcoin Sepeti — {now:%d.%m.%Y}"
        send_email(settings, subject, plain, html)
        print(f"Rapor {settings.smtp_to} adresine gönderildi")


if __name__ == "__main__":
    main()
