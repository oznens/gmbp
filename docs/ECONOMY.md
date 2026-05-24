# Economy & Idle Math — Carpet Empire Tycoon

## 1. Para Birimleri

| Sembol | Ad | Kazanım | Harcanma |
|--------|------|---------|----------|
| 🪙 | Akçe (Coin) | Halı satışı, idle income | Upgrade, yeni istasyon |
| 💎 | Gem | IAP, rewarded ad, daily quest | Hızlandırma, premium upgrade, prestige skip |
| ⭐ | Star (Prestige) | Atölyeyi sıfırla (prestige) | Kalıcı global multiplier |
| 🎟 | Motif Token | Limited event görevleri | Özel desen / nadir motif |

## 2. Akçe Üretimi

### Aktif (tap-based)
```
income_per_sale = base_carpet_value
                * pattern_multiplier
                * quality_multiplier
                * customer_type_multiplier
                * prestige_multiplier
```

### Pasif (idle)
- Lvl 5'te açılır
- Saniyede üretim: `passive_per_sec = sum(loom.output_per_sec)`
- Offline cap: 4 saat (rewarded ad ile 24 saate)

## 3. Upgrade Eğrileri

```
cost(n) = base_cost * 1.15^n
```

| İstasyon | Base Cost | Output | Cooldown |
|----------|-----------|--------|----------|
| Yün Tezgâhı | 50 | 5 yün | 3 sn |
| Boya İstasyonu | 200 | 1 boyalı iplik | 2 sn |
| Basit Loom | 500 | 1 kilim (50 akçe) | 15 sn |
| Kalite Kontrol | 5,000 | +20% değer | — |
| Vitrin | 25,000 | Auto-sell | — |
| Premium Loom (İpek) | 250,000 | 1 ipek halı (5000 akçe) | 60 sn |
| Pattern Designer | 1M | Yeni desen unlock | — |
| Export Office | 10M | Uluslararası 10x | — |
| Royal Showroom | 100M | VIP bid sistemi | — |

## 4. Halı Değer Hesabı (Sanat Eseri Modeli)

Bu oyunun **diferansiyatörü**: Her halı tek tek değer hesabı ile satılır.

```
carpet_value = base_loom_value
             * pattern_complexity_multiplier  // 1x - 10x
             * color_count_bonus              // 1x + (n_colors * 0.1)
             * quality_bonus                  // 1x - 2x (kalite kontrol upgrade'i)
             * customer_match_bonus           // 1x - 1.5x (turist Persian sever, vb.)
```

**Örnek:** Basit Loom (50) × Madalyon (2x) × 5 renk (1.5x) × Premium kalite (1.8x) × Sanat Tüccarı (1.3x) = 351 akçe.

## 5. Prestige System

**Tetik:** İlk prestige 1M akçe, sonrakiler 10x katlanır.

**Formül (Star kazancı):**
```
stars_earned = floor(sqrt(total_lifetime_coins / 1_000_000))
```

**Star multiplier:**
```
global_multiplier = 1 + (stars_owned * 0.02)
```

**Prestige reset'i:**
- Akçe sıfırlanır
- İstasyon levelleri sıfırlanır
- Stars kalır
- Açılmış şehirler kalır (kalıcı)
- Açılmış desenler kalır

## 6. Pattern Economy (Özel Sistem)

Desenler **koleksiyon** sistemiyle açılır:

| Desen | Açılma yolu | Çarpan |
|-------|-------------|--------|
| Basit Kilim | Başlangıç | 1x |
| Yıldız | Lv 3 | 1.5x |
| Madalyon | Lv 8 + 5 madalyon dokuma görevi | 2x |
| Hayat Ağacı | Lv 15 + event | 3x |
| Persian Medallion | Tebriz şehir kilidi | 5x |
| Hereke İpek | Lv 40 + ipek loom | 10x |
| Custom (User-designed) | VIP Pass | Çarpan değişken |

Daily quest örneği: "3 Madalyon halısı dok" → 50 gem ödül.

## 7. Müşteri Ekonomisi

| Tip | Sabır (sn) | Akçe Çarpanı | Pattern Tercih | Olasılık |
|-----|-----------|--------------|----------------|----------|
| Köylü | 30 | 1x | Basit Kilim | 70% |
| Tüccar | 25 | 2x | Yıldız | 15% (Lv 5+) |
| Turist | 25 | 3x | Renkli, Yıldız | 8% (Lv 10+) |
| Sanat Tüccarı | 20 | 5x | Madalyon, ipek | 5% (Lv 18+) |
| Müze | 15 | 15x | Premium, Hayat Ağacı | 1.5% (Lv 25+) |
| Royalty | 10 | 30x | İpek, Custom | 0.5% (Lv 35+) |
| TikToker | 8 | 5x + boom | Renkli | 0.1% (Lv 45+) |

**Müşteri spawn rate:** sn'de 0.5 (lvl 1) → 3 (lvl 50). Vitrin upgrade'i ile artar.

## 8. Boost'lar

Rewarded ad ile aktive edilir:

| Boost | Etki | Süre | Cooldown |
|-------|------|------|----------|
| 2x Akçe | Tüm satış 2x | 5 dk | 15 dk |
| Speed Loom | Tüm istasyonlar 2x | 5 dk | 30 dk |
| Offline 4x | Offline kazanç 4x | 24 saat | 24 saat |
| Free Pattern Reveal | Random desen %50 kilit aç | tek seferlik | 30 dk |

## 9. Gem Ekonomisi

**Kazanım:**
- Daily login (5-50 gem, streak'e bağlı, 7 günde max)
- Daily quest (3 görev × 5-10 gem)
- Achievement (one-time, 50-500 gem)
- Royalty müşteri tip (5 gem her satış)
- Event reward (50-200 gem)

**Harcama:**
- Hızlandırma (1 saat upgrade = 10 gem)
- Premium upgrade (gold tier her istasyonun)
- Prestige skip (100 gem)
- Continue (müşteri kaçtıysa, 5 gem)
- Pattern unlock skip (50-300 gem)

**IAP fiyatlandırma:**
| Paket | Gem | Fiyat | Bonus |
|-------|-----|-------|-------|
| Starter | 2000 | $2.99 | İlk teklif, +golden loom skin |
| Small | 500 | $1.99 | — |
| Medium | 1200 | $4.99 | +10% |
| Large | 3500 | $14.99 | +25% |
| XL | 8000 | $29.99 | +40% |
| Mega | 30000 | $99.99 | +60%, VIP rütbe + sultan outfit |

## 10. Balancing Hedefi

**F2P oyuncu yolculuğu:**
- Day 1: Lvl 5 (idle açılır), basic loom
- Day 3: Lvl 12 (Premium loom, ipek tanışma)
- Day 7: İlk prestige, ~10 star
- Day 14: Tebriz şehri (Persian unlock)
- Day 30: Lvl 50, 3 şehir, 50+ star

**Paying oyuncu (whale):**
- Day 1: Lvl 30, 3 şehir
- Day 7: Lvl 60, multi-prestige
- Day 14: Tüm şehirler, Sultan müşteri

**ARPDAU hedef:** $0.25 (premium hissetmesi gereken oyun, slightly higher ARPDAU)
