# daily_altcoin_recommendation

Her gün piyasa ve DeFi verilerini toplayıp açıklanabilir biçimde en güçlü 5 coin adayını sıralayan, HTML e-posta raporu üreten karar destek sistemi.

BTC sıralamaya girmez; altcoinler için piyasa ve relatif performans benchmark'ı olarak kullanılır.

> Bu yazılım yatırım tavsiyesi vermez ve getiri garantisi sunmaz. İlk sürüm gerçek emir göndermez.

## Neleri ölçer?

- Her gün yenilenen 24 saat/7 gün kısa vadeli teyit
- USD, BTC ve ETH karşısında 30 gün, 200 gün ve 1 yıllık uzun vadeli güç
- 24 saatlik hacim, piyasa değeri ve hacim/piyasa değeri oranı
- DeFiLlama protokol/zincir TVL'si ile 1 gün, 7 gün ve 1 aylık değişim
- Eşleşebilen DEX'lerde 24 saat, 7 gün ve 30 günlük hacim
- Fundamental büyüme ile fiyat performansı arasındaki `Catch-up/Mismatch`
- Market cap / FDV üzerinden gelecekteki arz baskısı
- Aşırı günlük/aylık yükseliş, TVL düşüşü ve olağandışı hacim için risk cezaları
- Varsayılan olarak stablecoin ve CoinGecko `meme-token` kategorisini dışlama
- Her aday için puan kırılımı, gerekçeler ve veri kapsamı
- Genel ilk 5'ten ayrı bir `Catch-up/Mismatch` izleme listesi

Haberler ile X/Reddit ölçümleri henüz puana dahil değildir. Rapor bu eksikliği açıkça gösterir; eksik veri yerine tahmin üretmez.

## Yerel kurulum

Python 3.9 veya üzeri yeterlidir; harici Python paketi gerekmez.

```bash
python3 -m unittest discover -s tests -v
python3 -m daily_altcoin_recommendation --dry-run
```

Oluşan rapor `reports/latest.html` dosyasına yazılır.

## E-posta ayarı

`.env.example` dosyasını `.env` adıyla kopyalayıp değerleri doldurun. Uygulama çalışma dizinindeki `.env` dosyasını otomatik okur; gerçek ortam değişkenleri varsa onlar önceliklidir. `.env` Git tarafından dışlanır ve repoya kaydedilmez.

Gmail kullanılıyorsa normal hesap parolası yerine iki aşamalı doğrulama ile oluşturulan bir uygulama parolası gerekir.

Gerekli değerler:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-address@gmail.com
SMTP_PASSWORD=app-password
SMTP_FROM=your-address@gmail.com
SMTP_TO=destination@example.com
SMTP_STARTTLS=true
```

Gönderim:

```bash
python3 -m daily_altcoin_recommendation
```

## Günlük zamanlama

macOS/Linux `cron` örneği, her gün İstanbul saatiyle 09:00 için (makinenin saat dilimi Europe/Istanbul ise):

```cron
0 9 * * * cd "/absolute/path/to/daily_altcoin_recommendation" && /usr/bin/python3 -m daily_altcoin_recommendation >> /tmp/daily_altcoin_recommendation.log 2>&1
```

Bilgisayar kapalı veya uykudaysa yerel zamanlayıcı çalışmayabilir. Sürekli çalışma için GitHub Actions, bir VPS veya sunucusuz zamanlayıcı kullanılmalıdır. E-posta ve API anahtarları repoya kaydedilmemelidir.

Repoda hazır gelen `.github/workflows/daily_altcoin_recommendation.yml`, her gün 09:05 İstanbul saatinde çalışır. GitHub deposunun `Settings → Secrets and variables → Actions` bölümüne `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TO` ve isteğe bağlı `COINGECKO_API_KEY` secret'larını ekleyin. İlk gönderimi `Actions → daily_altcoin_recommendation → Run workflow` ile elle deneyin.

## Tarihsel simülasyon

30 coinlik araştırma evrenini geçmiş bir günün kapanışında sıralayıp sonraki yedi günlük getiriyi ölçmek için:

```bash
python3 -m daily_altcoin_recommendation.backtest --as-of 2026-08-13 --top 5
```

Bir tarih aralığındaki her günün ayrı önerilerini görmek için:

```bash
python3 -m daily_altcoin_recommendation.backtest --as-of 2026-08-14 --daily-through 2026-08-20 --top 5
```

Simülasyon CoinGecko'nun tarihsel fiyat, market-cap ve hacmini; DefiLlama'nın tarihsel TVL'sini kullanır. Geçmiş DEX hacmi, haberler, sosyal veriler ve ücretsiz planda bulunmayan kesin tarihsel arz/unlock bilgileri dahil değildir. Geçmiş MC/FDV yaklaşık olarak güncel orandan türetilir; sonuç bu nedenle araştırma simülasyonudur, eksiksiz bir kurumsal backtest değildir.

## Puanlama notu

Puanlar yatırım getirisi olasılığı değildir. Analiz her gün çalışır ve uzun vadeli aday listesi de her gün yeni verilerle değişebilir. Coin'ler aynı günkü uygun evren içinde yüzdelik sıralamayla karşılaştırılır. Mevcut bileşen ağırlıkları:

- Kısa vadeli teyit (24 saat/7 gün): %10
- Uzun vadeli güç (30 gün/200 gün/1 yıl): %20
- Likidite: %15
- DeFi/Ekosistem: %25
- Tokenomics (MC/FDV): %15
- Catch-up/Mismatch: %15

Catch-up puanı; BTC/ETH'ye göre 7/30 günlük geride kalma, TVL/DEX büyümesinin 30 günlük fiyattan güçlü olması, TVL veya DEX hacminin market cap'e oranı ve son 24 saatte relatif toparlanma işaretlerini birlikte kullanır. DeFi/ekosistem verisi olmayan veya temeli zayıf coin yalnızca düştüğü için catch-up puanı alamaz.

Bir bileşenin verisi yoksa eksik alan 50/100 nötr kabul edilir; ağırlığı diğer güçlü bileşenlere dağıtılarak puanın yapay biçimde şişmesine izin verilmez. Eksiklik raporda ayrıca gösterilir.
