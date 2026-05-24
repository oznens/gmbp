# Carpet Empire Tycoon

Mobil idle tycoon oyunu. Anadolu'nun binlerce yıllık halı dokuma kültürünü modern mobil oyun formatında dünyaya açan **blue-ocean** simülasyon.

**Status:** Pre-production. Tasarım dokümanları yazıldı, Unity projesi henüz oluşturulmadı.

**Platform:** iOS + Android (Unity 6 LTS)
**Tür:** Idle Tycoon Simulator (Hybrid-Casual)
**Hedef kitle:** 25-55, cozy/satisfying game hayranları, sanat severler, global + TR
**Monetizasyon:** Rewarded ads + IAP (gem pack, starter pack, VIP pass)
**USP:** Mobil pazarda HİÇ rakibi yok. Dokuma animasyonu ASMR/TikTok viral potansiyeli yüksek.

## Niye "Blue Ocean"?

- **Kebab/Restoran/Supermarket tycoon:** Onlarca rakip, doymuş pazar
- **Halı/Carpet tycoon:** Mobil app store'da **sıfır** rakip (Mayıs 2026)
- **TikTok ASMR:** Sıkma, sıralama, dokuma içerikleri viral
- **Kültürel exotic appeal:** Türk + Pers halısı dünyada premium "art object" olarak biliniyor
- **Görsel diferansiyasyon:** Renkli iplik + desen animasyonu screenshot'larda öne çıkar

## Hızlı Başlangıç

1. `docs/UNITY_SETUP.md` — Unity Hub + Unity 6 kurulumu, projeyi açma
2. `docs/GAME_DESIGN.md` — Oyun tasarım dokümanı (GDD)
3. `docs/ECONOMY.md` — Idle matematiği, currency, upgrade eğrileri
4. `docs/ROADMAP.md` — 12 haftalık geliştirme planı

## Klasör Yapısı

```
gmbp/
├── Assets/              # Unity asset klasörü
│   └── Scripts/         # C# kaynak kodu
│       ├── Core/        # GameManager, EconomyManager, SaveSystem
│       ├── Stations/    # Loom, Dye, Display istasyon kodları
│       ├── Customers/   # Müşteri AI, queue
│       └── UI/          # HUD, menüler
├── docs/                # Tasarım ve plan dokümanları
└── Packages/            # Unity package manifest
```

## Hedef KPI (Publisher submission için)

| Metrik | Min | İdeal |
|--------|-----|-------|
| D1 retention | ≥ 35% | ≥ 45% |
| D3 retention | ≥ 18% | ≥ 24% |
| D7 retention | ≥ 8%  | ≥ 12% |
| CPI (FB)     | ≤ $1.50 | ≤ $1.00 |
| Session/day  | ≥ 3 | ≥ 5 |

Bu KPI'lara ulaşırsak Rollic / Voodoo / Supersonic'e başvuru yapılabilir.
