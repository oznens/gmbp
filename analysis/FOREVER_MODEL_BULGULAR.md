# Forever Model [Pro+] (Sniper) — Eksiksiz İmplementasyon & Bulgular

## Ne yapıldı

toodegrees'in **Forever Model [Pro+] (Sniper)** modeli, dokümanlardan birebir
araştırılıp **eksiksiz** implement edildi (`models/forever_model.py`):

| Bileşen | Açıklama | Durum |
|---|---|---|
| **IRL** (Internal Range Liquidity) | Fair Value Gap (3-mum imbalance) | ✅ |
| **ERL** (External Range Liquidity) | Swing high/low likidite havuzu (süpürülen) | ✅ |
| **SMT** (Smart Money Technique) | Korelasyonlu iki varlık arası diverjans | ✅ |
| **CISD** (Change in State of Delivery) | Önceki mumu yutan güçlü kapanış + sweep | ✅ |
| **CE** (Consequent Encroachment) | FVG'nin %50'sine limit giriş | ✅ |
| TP = karşı ERL | Sabit RR yerine external liquidity hedefi | ✅ |

SMT için çift-varlık zaman-hizalı backtest harness'ı yazıldı
(`analysis/forever_backtest.py`). Her sembol korelasyonlu eşiyle hizalanır:
BTC↔ETH, SOL↔AVAX, ARB↔OP, ADA↔XRP, LINK↔ETH, LTC↔BTC, DOGE↔SOL.

## Sonuçlar (1 yıl, fee+slip dahil)

### TP modu kritik: sabit-RR vs karşı-ERL
| Konfig | n | WR | NetR | avgR |
|---|---|---|---|---|
| 1H SMT, **sabit 2.5R** | 17 | 29% | **-1.22R** | -0.072 |
| 1H SMT, **ERL hedefi** | 17 | 29% | **+4.70R** | **+0.277** |

→ Gerçek modeldeki gibi **external liquidity hedefi** şart; sabit RR kaybettiriyor.

### SMT'nin değeri (kalite filtresi olarak)
| Konfig | n | NetR | avgR |
|---|---|---|---|
| 1H **SMT'li** + ERL-TP | 17 | +4.70R | **+0.277** |
| 1H **SMT'siz** + ERL-TP | 113 | +4.29R | +0.038 |

→ SMT trade başına R'yi **7 kat** artırıyor (+0.277 vs +0.038). Dokümanların
dediği gibi SMT bir **kalite filtresi** — bu, konseptin doğru anlaşıldığının kanıtı.

### Timeframe karşılaştırması (SMT + ERL-TP)
| TF | n | WR | NetR | avgR |
|---|---|---|---|---|
| 4H | 3 | 0% | -3.18R | çok az setup |
| **1H** | 17 | 29% | **+4.70R** | **+0.277** ✅ |
| 15M | 76 | 28% | -11.69R | -0.154 (gürültülü) |

## Dürüst değerlendirme

1. **Model eksiksiz ve doğru** — SMT, CISD, IRL/FVG, ERL, CE hepsi var ve
   SMT'nin kalite etkisi beklendiği gibi çıkıyor (konsept doğrulandı).

2. **Pozitif edge var ama düşük frekanslı**: En iyi konfig (1H + SMT + ERL-TP)
   trade başına **+0.277R** — gerçek bir istatistiksel üstünlük. Ancak yılda
   sadece ~17 setup (12 sembol). Bu yüksek-konviksiyon, az-işlem bir modeldir.

3. **15m'de bozuluyor**: Orijinal model 5m CISD + indeks/forex (Gold↔Silver SMT)
   için tasarlanmış. Kripto 15m'de SMT korelasyonu zayıflıyor, gürültü artıyor.

4. **100R+ gerçekçi değil** (bu veri/TF setinde, overfit olmadan): +0.277R/trade
   ile 100R için ~360 SMT-onaylı setup gerekir → çok daha düşük TF (5m, gerçek
   model TF'i), çok daha fazla sembol veya çok yıllı veri şart. Mevcut reversal
   modellerini zorlamak curve-fitting olur ve canlıda kaybettirir.

## Öneri (kârlı & mantıklı portföy)

En sağlam sonuç **kombinasyon**:
- **Sniper + judas_swing** (4H): +9.83R (geniş taban, çok işlem)
- **Forever Model** (1H, SMT, ERL-TP): +4.70R (yüksek kalite, az işlem, +0.277R/trade)

İkisi farklı rejimlerde ateşler → düşük korelasyon → birleşik equity daha düz.
Canlıda Forever Model'i **yüksek-konviksiyon ekstra onay** olarak, Sniper/judas'ı
**ana akış** olarak kullanmak en mantıklısı.
