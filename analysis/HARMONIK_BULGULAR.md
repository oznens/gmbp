# Harmonik Pattern — Çok-TF Derin Analiz Bulguları

Öze dönüş: harmonik paternleri (Gartley/Bat/Butterfly/Crab/Shark/Cypher) +
Price Action onayı + puanlama sistemiyle hangi yapıların kârlı olduğunu çözdük.

## Yöntem
`analysis/harmonic_multitf.py` — ZigZag XABCD tespiti → PRZ dokunuşu →
PA onayı (engulfing/pin/sweep) → 0-100 güven puanı → limit-fill backtest
(fee+slip dahil, min-risk %0.30). 12 sembol, 1 yıl.

## Sonuçlar (TF karşılaştırması)

| TF | Sinyal | WR | NetR | En iyi eşik | Eşikli NetR | avgR |
|----|--------|-----|------|-------------|-------------|------|
| **1H** | 30 | 37% | **+7.49R** | **≥40** | **+9.26R** | **+0.386** ✅ |
| 15m | 54 | 30% | -17.37R | ≥50 | +1.28R | +0.091 |
| 4H | (çok nadir) | — | — | — | — | — |

→ **1H harmonik için tatlı nokta.** 15m gürültülü (harmonik temiz yapı ister),
4H çok seyrek (yılda ~6 sinyal).

## Pattern bazlı (1H)

| Pattern | n | WR | NetR | Karar |
|---------|---|-----|------|-------|
| **Gartley** | 10 | 50% | **+7.62R** | ✅ ana patern |
| **Butterfly** | 4 | 50% | +1.36R | ✅ |
| Shark | 14 | 29% | +0.74R | ⚠️ marjinal |
| **Bat** | 2 | 0% | **-2.23R** | ❌ **ele** |

## Güven puanı (1H)
- ≥30: 30 sinyal, +7.49R
- **≥40: 24 sinyal, +9.26R, avgR +0.386** ← optimal
- ≥50: 4 sinyal, -0.76R (aşırı sıkı, örneklem çöküyor)

## Canlı modele gömülenler (`HarmonicPAModel`)
1. **Bat paterni bloklandı** (`BLOCK_PATTERNS = {"Bat"}`)
2. **conf_score ≥ 40 kapısı** (`MIN_CONF_SCORE = 40`)
3. **min risk %0.30** (fee koruması)
4. **0-100 puanlama**: Fib kalitesi(35) + PA onayı(30) + trend hizası(15) + hacim(20)
5. Öneri TF: **1H**

## Özet
Harmonik öz **kârlı** — ama doğru TF (1H), doğru patern (Gartley/Butterfly) ve
puanlama kapısı (≥40) ile. Bot bu konfigle yılda ~24 sinyal, avgR +0.386R,
toplam +9.26R üretiyor (12 sembol, fee dahil).
