from datetime import datetime
from email.message import EmailMessage
from html import escape
import smtplib
from typing import List, Tuple

from .config import Settings
from .models import RankedCoin
from .portfolio import allocate_basket


def render_report(
    ranked: List[RankedCoin],
    generated_at: datetime,
    top_n: int = 5,
    basket_budget_usd: float = 100.0,
) -> Tuple[str, str]:
    basket = allocate_basket(ranked, basket_budget_usd, top_n)
    picks = [item for item, _ in basket]
    catchup_picks = sorted(
        (
            item for item in ranked
            if "Catch-up/Mismatch" in item.component_scores
            and item.score >= 50
            and item.risk_penalty < 18
        ),
        key=lambda item: item.component_scores["Catch-up/Mismatch"],
        reverse=True,
    )[:top_n]
    date_text = generated_at.strftime("%d.%m.%Y %H:%M %Z")
    plain_lines = [
        f"Haftalık ${basket_budget_usd:.2f} Altcoin Sepeti — {date_text}",
        "",
        "Bu bir yatırım tavsiyesi değildir.",
        "",
    ]
    cards = []
    market_warning = ""
    if not picks or picks[0].score < 60:
        market_warning = "<div class='warning'><strong>Sepet uyarısı:</strong> Güçlü aday eşiği geçilemedi. Bu hafta tutarı azaltmak veya alımı ertelemek daha temkinli olabilir.</div>"
        plain_lines.extend(["SEPET UYARISI: Güçlü aday eşiği geçilemedi; tutarı azaltmayı veya alımı ertelemeyi değerlendirin.", ""])
    allocation_rows = []
    for index, (item, amount) in enumerate(basket, 1):
        coin = item.metrics
        plain_lines.extend([
            f"{index}. {coin.name} ({coin.symbol}) — ${amount:.2f} — {item.score:.1f}/100",
            *[f"  + {reason}" for reason in item.reasons],
            *[f"  ! {risk}" for risk in item.risks],
            f"  Veri kapsamı: {', '.join(item.coverage)}",
            "",
        ])
        component_rows = "".join(
            f"<span class='pill'>{escape(name)} {value:.0f}</span>" for name, value in item.component_scores.items()
        )
        risk_html = "".join(f"<li>{escape(risk)}</li>" for risk in item.risks) or "<li>Otomatik risk bayrağı yok</li>"
        reason_html = "".join(f"<li>{escape(reason)}</li>" for reason in item.reasons)
        allocation_rows.append(
            f"<tr><td>#{index} <strong>{escape(coin.name)}</strong> {escape(coin.symbol)}</td>"
            f"<td><strong>${amount:.2f}</strong></td><td>{item.score:.1f}</td></tr>"
        )
        cards.append(f"""
        <section class="card">
          <div class="rank">#{index}</div>
          <div><h2>{escape(coin.name)} <small>{escape(coin.symbol)}</small></h2>
          <div class="score">${amount:.2f} <span>puan {item.score:.1f}/100</span></div></div>
          <div class="components">{component_rows}</div>
          <h3>Neden listede?</h3><ul>{reason_html}</ul>
          <h3>Riskler</h3><ul class="risks">{risk_html}</ul>
          <p class="coverage">Veri kapsamı: {escape(', '.join(item.coverage))}</p>
        </section>""")
    if not picks:
        cards.append("<section class='card'><h2>Bu hafta uygun aday bulunamadı</h2><p>Filtreleri geçen yeterli veri yok.</p></section>")
        plain_lines.append("Bu hafta uygun aday bulunamadı.")
    catchup_html = ""
    if catchup_picks:
        plain_lines.extend(["CATCH-UP / MISMATCH İZLEME LİSTESİ", ""])
        rows = []
        for item in catchup_picks:
            value = item.component_scores["Catch-up/Mismatch"]
            plain_lines.append(f"- {item.metrics.name} ({item.metrics.symbol}): catch-up {value:.1f}, genel {item.score:.1f}")
            rows.append(
                f"<tr><td><strong>{escape(item.metrics.name)}</strong> {escape(item.metrics.symbol)}</td>"
                f"<td>{value:.1f}</td><td>{item.score:.1f}</td><td>{item.risk_penalty:.0f}</td></tr>"
            )
        catchup_html = f"""<section class="card"><h2>Catch-up / Mismatch İzleme Listesi</h2>
        <p class="muted">Fundamentali desteklenen, BTC/ETH'ye göre geride kalmış ve kısa vadeli toparlanma işareti gösteren adaylar.</p>
        <table><thead><tr><th>Coin</th><th>Catch-up</th><th>Genel</th><th>Risk cezası</th></tr></thead>
        <tbody>{''.join(rows)}</tbody></table></section>"""
    allocation_html = ""
    if allocation_rows:
        allocation_html = f"""<section class="card"><h2>Önerilen Dağılım</h2>
        <table><thead><tr><th>Coin</th><th>Tutar</th><th>Puan</th></tr></thead>
        <tbody>{''.join(allocation_rows)}</tbody></table></section>"""
    html = f"""<!doctype html><html lang="tr"><head><meta charset="utf-8"><style>
    body{{margin:0;background:#0b1020;color:#e8edf7;font:15px Arial,sans-serif}}main{{max-width:760px;margin:auto;padding:28px 16px}}
    .header{{padding:24px;background:linear-gradient(135deg,#172348,#102c2a);border-radius:18px;margin-bottom:16px}}
    h1{{margin:0 0 8px;font-size:26px}}.muted,.coverage{{color:#9ca9c2}}.card{{position:relative;background:#151d32;border:1px solid #26314e;border-radius:16px;padding:20px;margin:14px 0}}
    .rank{{position:absolute;right:18px;top:18px;color:#6ee7b7;font-size:22px;font-weight:bold}}h2{{margin:0 0 6px}}small{{color:#93a4c3}}.score{{font-size:32px;color:#6ee7b7;font-weight:bold}}.score span{{font-size:14px;color:#93a4c3}}
    .pill{{display:inline-block;background:#24304d;border-radius:99px;padding:7px 10px;margin:5px 5px 5px 0}}h3{{font-size:14px;margin:18px 0 6px;color:#bdc8dc}}li{{margin:5px 0}}.risks{{color:#f8c273}}.warning{{background:#4a3017;color:#ffe1a6;border:1px solid #845923;border-radius:12px;padding:14px;margin:14px 0}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:9px;border-bottom:1px solid #2b3652}}.footer{{font-size:12px;color:#8390aa;padding:12px}}
    </style></head><body><main><div class="header"><h1>${basket_budget_usd:.2f} Haftalık Altcoin Sepeti</h1><div class="muted">{escape(date_text)}</div><p>Son 7 gün öncelikli; uzun dönem güç, likidite, tokenomics ve DeFi verileriyle filtrelenen açıklanabilir dağılım.</p></div>
    {market_warning}{allocation_html}{''.join(cards)}{catchup_html}<div class="footer">Analiz her pazartesi yenilenir. BTC aday değil benchmark olarak kullanılır. Sepetin yarısı eşit, yarısı risk cezası düşülmüş puana orantılı dağıtılır. Catch-up puanı yalnızca ekosistem verisi bulunan projelerde fundamental büyüme ile fiyat performansı arasındaki ayrışmayı ölçer. Bu rapor yatırım tavsiyesi değildir ve yüksek piyasa riski içerebilir.</div></main></body></html>"""
    return "\n".join(plain_lines), html


def send_email(settings: Settings, subject: str, plain: str, html: str) -> None:
    required = [settings.smtp_host, settings.smtp_from, settings.smtp_to]
    if not all(required):
        raise ValueError("SMTP_HOST, SMTP_FROM ve SMTP_TO ayarlanmalıdır")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = settings.smtp_to
    message.set_content(plain)
    message.add_alternative(html, subtype="html")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)
