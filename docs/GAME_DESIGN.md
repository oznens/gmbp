# Game Design Document — Carpet Empire Tycoon

## 1. Vision

Anadolu ve Pers halı kültürünü mobil idle tycoon formatına sokan ilk oyun. Pizza Ready / Idle Restaurant Empire'ın "halı" versiyonu — ama saf kopya değil, dokuma mekaniği oyuna **satisfying core** ekliyor.

**Tek cümle pitch:** *"Küçük bir köy tezgâhından başla, sultan saraylarına halı satan bir imparatorluk kur — iplik boya, desen doku, sat, prestij yap."*

**Stratejik diferansiyasyon:**
- Mobil pazarda direkt rakip yok (App Store araştırması — Mayıs 2026)
- Dokuma animasyonu TikTok/Reels'te organik viral potansiyeli yüksek (ASMR + reveal)
- Cultural premium feel — "exotic art" temasıyla global appeal

## 2. Core Loop (15-45 saniyelik döngü)

```
1. İplik temin et (yün gelir veya satın al)
2. Boya istasyonunda renk seç (kırmızı, mavi, lacivert, krem...)
3. Tezgâha kur (loom) → otomatik dokuma başlar
4. Dokuma ilerler (visible animation, sıra sıra desen oluşur)
5. Bitince halı "reveal" animasyonu (juice!)
6. Müşteri satın alır → para
7. Para → upgrade (hız, kalite, yeni desen, yeni tezgâh)
```

**Diferansiyatör mini-mekanik:** Oyuncu dokuma sırasında ekrana dokunup **"shuttle hızlandır"** yapabilir (tap-based mini boost). Block Blast tarzı satisfying tıklama hissi.

Idle income tier 5'ten sonra açılır. Offline dokuma 4 saate kadar (rewarded ad ile 24 saate).

## 3. Stations (İstasyonlar)

| İstasyon | Açılma | İşlev | Upgrade'ler |
|----------|--------|-------|-------------|
| Yün Tezgâhı | Başlangıç | Ham yün üretir | Hız, kapasite |
| Boya İstasyonu | Başlangıç | İpliği boyar (1 renk) | Renk çeşidi, hız |
| Tezgâh (Loom) | Başlangıç | Halı dokur (basit kilim) | Hız, boyut |
| Kalite Kontrol | Lv 5 | Hatalı düğüm fix, premium çarpan | Doğruluk, hız |
| Vitrin (Display) | Lv 8 | Müşterilere otomatik satar | Pazarlama çarpanı |
| Premium Loom (Hereke) | Lv 12 | İpek halı (5x fiyat) | Hız, ipek üretimi |
| Pattern Designer | Lv 18 | Özel desen kilidi açar | Yeni motifler |
| Export Office | Lv 25 | Uluslararası müşteri (10x) | Pazarlar açar |
| Royal Showroom | Lv 35 | VIP/koleksiyoner | Bid sistemi |

## 4. Halı Türleri / İlerleme Hattı

Şehir-bazlı progression (her şehir = yeni tarz):

1. **Hereke (Tutorial)** — Basit kilim, 3 renk
2. **Uşak** — Geometrik desen, 6 renk
3. **Isparta** — Çiçek motifleri, 10 renk
4. **Sivas** — İpek tanıtımı, premium
5. **İstanbul (Kapalıçarşı)** — Global müşteri, turist
6. **Tebriz (Pers genişlemesi)** — Persian medallion, knot density
7. **Kerman, Buhara** — Rakip stilleri "satın al"
8. **Berlin, NYC, Tokyo** — Modern design export, kültür fusion

Her şehir = yeni prestige round = kalıcı star multiplier.

## 5. Müşteri Tipleri

- **Köylü (Normal):** Standart kilim, 1x para — 70%
- **Tüccar:** Toplu sipariş, 2x — 15% (Lv 5+)
- **Turist:** Renkli/eğlenceli desen, 3x — 8% (Lv 10+)
- **Sanat Tüccarı:** Premium kalite ister, 5x — 5% (Lv 18+)
- **Müze Yetkilisi:** Tek seferlik mega sipariş, 15x — 1.5% (Lv 25+)
- **Sultan / Royalty:** Özel desen + ipek, 30x para + nadir gem — 0.5% (Lv 35+)
- **TikToker:** "Halı reveal" çeker → 30 sn müşteri patlaması (Lv 45+)

## 6. Currency

- **Akçe (🪙):** Ana para birimi, harcanabilir
- **Gem (💎):** Premium para — IAP veya rewarded ad
- **Star (⭐):** Prestige currency — kalıcı global multiplier
- **Motif Token (🎟):** Limited event ödülü, özel desenleri açar

## 7. Pattern System (Diferansiyatör Özellik)

Oyuncu **desen** seçer/keşfeder. Her desen farklı satış değeri ve süre:

| Desen | Hız | Çarpan | Açılma |
|-------|-----|--------|--------|
| Basit Kilim | 1x | 1x | Başlangıç |
| Yıldız | 1.2x | 1.5x | Lv 3 |
| Madalyon | 0.8x | 2x | Lv 8 |
| Hayat Ağacı | 0.7x | 3x | Lv 15 |
| Persian Medallion | 0.5x | 5x | Lv 25 (Tebriz) |
| Hereke İpek Saray | 0.3x | 10x | Lv 40 |

Daily quest: "5 madalyon dokuyun" tarzı görevler.

## 8. Monetization

### IAP
- **Starter Pack** ($2.99) — 2000 gem + 24h boost + golden loom skin
- **Gem Pack** ($1.99 - $99.99) — Standart paketler
- **VIP Pass** ($9.99/ay) — 2x para, no-ad, exclusive müşteri, özel desen
- **Pattern Pack** ($4.99) — Premium desen bundle

### Reklamlar
- **Rewarded Video:** 2x para (5dk), offline 4x (24h), free pattern reveal, skip dye timer
- **Interstitial:** Prestige sonrası, şehir geçişlerinde
- **Banner:** Asla

### ARPDAU hedefi: $0.20-0.40

## 9. Retention Hooks

| Mekanik | D1 | D3 | D7+ |
|---------|----|----|-----|
| Daily Login (Desen Serisi) | ✅ | ✅ | ✅ |
| Daily Quest (3 görev) | ✅ | ✅ | ✅ |
| Weekly Pattern Event | | ✅ | ✅ |
| Prestige (her 2-3 günde) | | | ✅ |
| Yeni şehir kilidi | | | ✅ |
| Push: "Halın bitti!" | ✅ | ✅ | ✅ |
| Sosyal: koleksiyoncu liderlik | | | ✅ |

## 10. Art Direction

- **Stil:** Stylized 3D, sıcak Anadolu paleti (kırmızı, terra, lacivert, altın)
- **Karakter:** Chibi proportions, üstada saçı bağlı, müşteriler kültürel kıyafet
- **Tezgâh:** Detaylı dokuma animasyonu — iplik sıra sıra örülüyor (PROCEDURAL veya pre-baked animation atlas)
- **Halı reveal:** Big juice — yere düşüyor, toz kalkıyor, renk patlaması particle
- **Referans:** Pizza Ready (juice), Sky: Children of the Light (renk), Townscaper (kültür hissi)
- **Asset stratejisi:** Synty POLYGON Fantasy + custom halı texture'ları (Substance/freelance)

## 11. Sound

- **Müzik:** Anadolu fusion (saz + lo-fi, ney + ambient) — Suno AI ile prototyping
- **SFX:** Dokuma "tık tık", makas, kumaş hışırtısı, müşteri "Maşallah!" sesleri
- **Voice:** "Ne güzel halı!" / "How much?" / "Çok teşekkür!"

## 12. TikTok / Marketing Açısı

**Viral hook'lar:**
- **Reveal compilation:** "10 saatte yapılan halı" reveal video
- **Color satisfaction:** Boya istasyonu renk patlaması ASMR
- **Pattern collecting:** "Hangi desen senin favorin?" engagement
- **Cultural pride:** Türk + global diaspora payda

## 13. Risk Analizi

| Risk | Olasılık | Etki | Önlem |
|------|----------|------|-------|
| Validate edilmemiş niş | Yüksek | Yüksek | Hafta 4'te erken prototype test (TikTok'a 30sn klip at, organic reaction ölç) |
| Halı görseli zor (texture) | Orta | Orta | Procedural pattern shader VEYA 30-50 önceden hazır halı texture atlas'ı |
| ASO "carpet" düşük volume | Orta | Orta | "Tycoon", "idle empire", "loom", "weaving" anahtar kelimeleri ekle |
| Kültürel olarak yabancılaşma | Düşük | Düşük | Berlin/Tokyo şehir açılışı global çapayı netleştirir |
| Solo dev burnout | Yüksek | Yüksek | 12 hafta MVP scope sınırı, freelance asset, asla feature creep |
| Publisher reddi | Orta | Orta | Self-publish backup, Steam port opsiyonu |
