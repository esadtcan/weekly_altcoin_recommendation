# weekly_altcoin_recommendation

An explainable decision-support system that builds a diversified **$100 weekly basket of five altcoins** and delivers the result as an HTML email every Monday.

Bitcoin is not eligible for the basket. It is used as a market and relative-performance benchmark alongside Ethereum.

> This software is for research and decision support only. It does not provide financial advice, guarantee returns, or place real orders.

## What it analyzes

- Seven-day price action, BTC/ETH-relative strength, and ecosystem confirmation as the primary weekly signals
- Longer-term strength over 30 days, 200 days, and one year in USD, BTC, and ETH terms
- 24-hour volume, market capitalization, and volume-to-market-cap ratios
- DeFiLlama protocol and chain TVL, including one-day, seven-day, and one-month changes
- DEX volume over 24 hours, seven days, and 30 days where a reliable match is available
- Fundamental-growth versus price-performance divergence through the `Catch-up/Mismatch` component
- Future supply pressure using market-cap-to-FDV ratios
- Risk penalties for excessive short-term rallies, TVL deterioration, unusual volume, and weak data coverage
- Stablecoin and CoinGecko `meme-token` category exclusions by default
- A transparent score breakdown, selection reasons, risks, and data coverage for every candidate
- An exact-dollar allocation that always reconciles to the configured weekly budget
- A separate `Catch-up/Mismatch` watchlist in addition to the overall top five

News and X/Reddit metrics are not yet included in the score. The report states this limitation instead of inventing missing data.

## Requirements

- Python 3.9 or newer
- No third-party Python packages
- Network access to CoinGecko and DeFiLlama
- SMTP credentials for email delivery

## Local setup

```bash
git clone https://github.com/esadtcan/weekly_altcoin_recommendation.git
cd weekly_altcoin_recommendation
python3 -m unittest discover -s tests -v
```

Generate a report without sending email:

```bash
python3 -m weekly_altcoin_recommendation --dry-run
```

The report is written to `reports/latest.html` by default. Use `--output` to choose another path:

```bash
python3 -m weekly_altcoin_recommendation --dry-run --output reports/example.html
```

## Configuration

Copy `.env.example` to `.env` and edit the values. The application loads `.env` from the current working directory without overriding environment variables that are already set. `.env` is excluded from Git.

Analysis settings:

```text
COINGECKO_API_KEY=
COINGECKO_PLAN=demo
TOP_N=5
BASKET_BUDGET_USD=100
UNIVERSE_SIZE=120
MIN_MARKET_CAP_USD=50000000
MIN_VOLUME_USD=5000000
EXCLUDE_MEME_COINS=true
REPORT_TIMEZONE=Europe/Istanbul
```

Email settings:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-address@gmail.com
SMTP_PASSWORD=app-password
SMTP_FROM=your-address@gmail.com
SMTP_TO=destination@example.com
SMTP_STARTTLS=true
```

Gmail accounts should use an app password created after enabling two-factor authentication, not the normal account password.

Send the report immediately:

```bash
python3 -m weekly_altcoin_recommendation
```

## Weekly GitHub Actions schedule

The included `.github/workflows/weekly_altcoin_recommendation.yml` workflow runs every Monday at **09:05 Europe/Istanbul**. GitHub Actions cron expressions use UTC, so the workflow uses `06:05 UTC`; Istanbul remains UTC+3 year-round.

Add these repository secrets under **Settings → Secrets and variables → Actions**:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`
- `SMTP_TO`
- `COINGECKO_API_KEY` (optional)

Test the first delivery manually from **Actions → weekly_altcoin_recommendation → Run workflow**.

## Local scheduling

On a machine configured for the `Europe/Istanbul` time zone, this cron entry runs every Monday at 09:05:

```cron
5 9 * * 1 cd "/absolute/path/to/weekly_altcoin_recommendation" && /usr/bin/python3 -m weekly_altcoin_recommendation >> /tmp/weekly_altcoin_recommendation.log 2>&1
```

A local schedule will not run while the computer is powered off or asleep. GitHub Actions, a VPS, or another hosted scheduler is preferable for unattended delivery.

## Historical simulation

Rank the research universe at a historical close and calculate the following seven-day return:

```bash
python3 -m weekly_altcoin_recommendation.backtest --as-of 2026-08-13 --top 5
```

Generate a separate recommendation for every day in a historical interval:

```bash
python3 -m weekly_altcoin_recommendation.backtest --as-of 2026-08-14 --daily-through 2026-08-20 --top 5
```

The simulation uses historical CoinGecko price, market-cap, and volume data together with historical DeFiLlama TVL. It does not include historical DEX volume, news, social data, or precise historical unlock data unavailable on the free plan. Historical market-cap-to-FDV is approximated from the current ratio, so this is a research simulation rather than an institutional-grade backtest.

## Scoring model

Scores are relative rankings within the eligible weekly universe, not probabilities of future returns.

| Component | Weight |
| --- | ---: |
| Seven-day confirmation, with 24-hour data as a secondary signal | 30% |
| Long-term strength over 30 days, 200 days, and one year | 15% |
| Liquidity | 15% |
| DeFi and ecosystem strength, prioritizing seven-day changes | 20% |
| Tokenomics using market cap / FDV | 10% |
| Catch-up / mismatch | 10% |

Half of the weekly basket is equally allocated. The other half is distributed in proportion to risk-adjusted conviction above a score of 40.

The catch-up score combines seven-day and 30-day BTC/ETH-relative underperformance, TVL or DEX growth that exceeds 30-day price performance, TVL or DEX volume relative to market capitalization, and signs of 24-hour relative recovery. A coin cannot receive a strong catch-up score merely because its price has fallen; supporting ecosystem data is required.

When a component is unavailable, it receives a neutral 50/100 value and its weight is redistributed without allowing missing data to inflate the total score. Missing coverage is also disclosed in the report.

## Risk notice

Cryptocurrency markets are highly volatile. Review the generated evidence, liquidity, tokenomics, and risk flags independently before making any investment decision.
