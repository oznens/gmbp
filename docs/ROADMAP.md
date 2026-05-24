# Geliştirme Roadmap — 12 Hafta MVP → Soft Launch

Solo, full-time. Günde ~6-8 saat efektif kod/tasarım.

## Faz 1 — Foundation (Hafta 1-2)

**Hedef:** Çalışan boş Unity projesi, tek tıklanabilir istasyon, ekrana coin yazısı.

- [ ] Unity Hub + Unity 6 LTS kur
- [ ] Yeni 3D Mobile project oluştur (`/home/user/gmbp`'ye)
- [ ] Mobile Build Settings (Android/iOS) yapılandır
- [ ] Core scripts iskeleti (`GameManager`, `EconomyManager`, `SaveSystem`)
- [ ] İlk istasyon prefab'ı (placeholder cube + click)
- [ ] Coin counter UI (TextMeshPro)
- [ ] Save/load JSON (PlayerPrefs veya JsonUtility)

**Çıktı:** Tıkla → coin +5 → kaydet → kapat-aç → coin korunmuş.

## Faz 2 — Core Loop (Hafta 3-4)

**Hedef:** Yün → Boya → Dokuma → Müşteri → Satış döngüsü çalışıyor.

- [ ] Customer spawner + queue sistemi
- [ ] Müşteri AI (NavMesh): kapı → vitrin → çıkış
- [ ] Loom state machine (idle → weaving → ready)
- [ ] Dokuma progress bar + procedural pattern texture (her satır build oluyor)
- [ ] Halı "reveal" animasyonu (zıplama + particle + sayı pop)
- [ ] Vitrinde otomatik satış → akçe gain

**Çıktı:** Tek loom'lu atölye, dokuma → satış döngüsü işliyor, halı reveal satisfying hissettiriyor.

## Faz 3 — Upgrade & Scaling (Hafta 5-6)

**Hedef:** Idle math, upgrade UI, multi-station.

- [ ] UpgradeData ScriptableObject (hız, kalite, çarpan)
- [ ] Upgrade UI (her istasyona "+" butonu)
- [ ] Idle income hesaplama (offline + active)
- [ ] 4-5 istasyon kilidi (Kalite Kontrol, Vitrin, Premium Loom, Pattern Designer)
- [ ] Akçe formatlama (1.2K, 3.5M, 1.2B)
- [ ] Pattern unlock sistemi (3-4 desen başlangıçta)

**Çıktı:** 4-5 istasyonlu atölye, upgrade yap, idle income kazan, desen koleksiyonu başlasın.

## Faz 4 — Meta & Retention (Hafta 7-8)

**Hedef:** Prestige, daily login, push notification.

- [ ] Prestige sistemi (star calculation + reset)
- [ ] Daily login streak UI + reward
- [ ] Daily quest (3 görev random pool — "3 madalyon dok" tarzı)
- [ ] Push notification (Unity Mobile Notifications) — "Halın bitti!" / offline reward hazır
- [ ] İlk şehir açılışı (Hereke → Uşak progression UI)

**Çıktı:** İlk prestige test edilebilir, daily login çalışıyor.

## Faz 5 — Polish & Art (Hafta 9-10)

**Hedef:** Placeholder asset'leri profesyonel asset'lerle değiştir.

- [ ] Synty POLYGON Fantasy / Market satın al ($30)
- [ ] Halı texture atlas — Fiverr veya Substance Designer ile 30-50 desen ($200-500)
- [ ] Karakterler (üstad + 6 müşteri çeşidi: köylü, tüccar, turist, sanat tüccarı, müze, sultan)
- [ ] Loom 3D model + dokuma animasyon (procedural shader veya pre-baked)
- [ ] Animasyon (Mixamo + custom)
- [ ] SFX library — dokuma tıkırtısı, makas, kumaş hışırtısı
- [ ] Music — Suno AI ile Anadolu fusion (saz + lo-fi)
- [ ] UI/UX iyileştirme (juice: tween, particle, screen shake)
- [ ] Loading screen, splash

**Çıktı:** Görsel olarak yayınlanabilir kalitede MVP.

## Faz 6 — Monetization & SDKs (Hafta 11)

**Hedef:** Reklam + IAP + analytics entegre.

- [ ] Unity LevelPlay (IronSource) veya AppLovin MAX kur
- [ ] Rewarded video (2x boost, offline 4x, skip timer)
- [ ] Interstitial (prestige sonrası)
- [ ] IAP — Unity IAP veya RevenueCat
- [ ] Starter Pack flow
- [ ] Firebase Analytics + Crashlytics
- [ ] GameAnalytics (KPI tracking)

**Çıktı:** Monetize edilmiş build.

## Faz 7 — Soft Launch (Hafta 12+)

**Hedef:** TR + Filipinler'de pilot, KPI ölç.

- [ ] Google Play internal track + TestFlight
- [ ] TR/PH'da $50-100 UA bütçesiyle test (Facebook + Google)
- [ ] D1, D3, D7 retention ölç
- [ ] CPI ölç (FB + Google + Unity)
- [ ] **Karar noktası:**
    - KPI'lar **publisher seviyesinde** → Rollic/Voodoo/Supersonic'e başvur
    - KPI'lar orta → iterate (2-4 hafta polish)
    - KPI'lar düşük → pivot veya kill

## Risk Buffer'ları

- Her fazda %30 buffer (yani gerçekte 16 hafta = 4 ay)
- Asset gecikme riski → freelance'ı erken bul
- Performance sorunu (low-end Android) → her sprint sonu profile et

## Bütçe (gerçekçi)

| Kalem | Maliyet |
|-------|---------|
| Unity (Personal) | $0 |
| Asset Store (Synty + audio) | $50-150 |
| Freelance 3D / 2D | $300-800 |
| Google/Apple dev account | $25 + $99 |
| UA test bütçesi (soft launch) | $200-500 |
| **Toplam** | **$675-1.575** |

Publisher'la deal yaparsan UA'i onlar finanse eder.
