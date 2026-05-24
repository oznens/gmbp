# Faz 2 — Gerçek Dokuma Döngüsü Bağlama

Faz 1'de `DemoLoom` basit tick verdi, HUD'da rakam gördük. Faz 2'de **gerçek** üretim zinciri var:

```
LoomController ─→ CarpetInventory ─→ DisplayShelf ─→ CustomerSpawner
   (üretir)        (depo)            (eşleştirir)    (sıra)
                                         │
                                         └─→ EconomyManager (para gelir)
```

## Editor'da Sahneyi Kurma (Unity hazır olunca yapacaksın)

### 1. ScriptableObject Asset'ler Oluştur

`Assets/Resources/Patterns/` klasörü oluştur:

- **Sağ tık → Create → CarpetEmpire → Pattern**
- 4-5 desen oluştur:
  - `SimpleKilim` (id: `simple_kilim`, speedMul: 1.0, valueMul: 1.0, unlockLevel: 1)
  - `Star` (id: `star`, speedMul: 1.2, valueMul: 1.5, unlockLevel: 3)
  - `Medallion` (id: `medallion`, speedMul: 0.8, valueMul: 2.0, unlockLevel: 8)
  - `TreeOfLife` (id: `tree_of_life`, speedMul: 0.7, valueMul: 3.0, unlockLevel: 15)
  - `PersianMedallion` (id: `persian_medallion`, speedMul: 0.5, valueMul: 5.0, unlockLevel: 25)

`Assets/Resources/Customers/`:
- **Create → CarpetEmpire → Customer**
- 3 müşteri arketipi:
  - `Villager` (coinMul: 1, weight: 7, patience: 30, prefersPattern: simple_kilim)
  - `Tourist` (coinMul: 3, weight: 1, patience: 25, prefersPattern: star)
  - `ArtDealer` (coinMul: 5, weight: 0.5, patience: 20, prefersPattern: medallion)

`Assets/Resources/Stations/`:
- **Create → CarpetEmpire → Station Config**
- `BasicLoomConfig` (id: `basic_loom`, baseOutput: 10, baseCooldown: 5, baseUpgradeCost: 50)

### 2. Sahne Hiyerarşisi

Yeni boş sahne (`Assets/Scenes/Workshop.unity`) oluştur, içine:

```
Workshop (root)
├── [GameManager]  (Bootstrap zaten otomatik oluşturuyor, ama production için manuel koyabilirsin)
├── Production
│   ├── Inventory       → CarpetInventory component (maxCapacity: 12)
│   ├── Loom_01         → LoomController + (ref: Inventory, BasicLoomConfig, SimpleKilim pattern)
│   └── DisplayShelf    → DisplayShelf component + (ref: Inventory, Spawner)
├── Customers
│   └── Spawner         → CustomerSpawner + archetypes listesine 3 müşteri SO'sunu sürükle
├── Interaction
│   └── TapBooster      → TapBooster component
└── HUD
    └── (HudBootstrap otomatik oluşturuyor, gerekirse manuel Canvas + WeavingProgressBar)
```

### 3. Test Senaryosu

Play tuşu:

1. `LoomController` dokumaya başlar
2. ~5 saniye sonra ilk halı tamamlanır → `CarpetInventory.Count = 1`
3. ~2 saniye sonra `CustomerSpawner` ilk müşteriyi spawn eder
4. `DisplayShelf` boş değil + sıra boş değil → satış olur
5. Coin HUD'da `0 → 10 → 22 → ...` artar
6. Ekrana tıkla → `TapBooster` devreye girer, loom hızlanır

### 4. Konsol Doğrulama

`Debug.Log` eklemeden de görebileceğin:
- HUD'da `🪙` sayacı artıyor → satış çalışıyor
- HUD'da `💎 5` → daily login bonusu (ilk gün)
- HUD'da `⭐ 0` → henüz prestige yok (1M coin'e ulaşınca açılır)

### 5. DemoLoom'u Kapat

Gerçek loop çalışınca DemoLoom artık gereksiz. `Bootstrap.cs` içindeki şu satırı sil veya yorum yap:

```csharp
var demoLoomGo = new GameObject("DemoLoom");
demoLoomGo.transform.SetParent(root.transform);
demoLoomGo.AddComponent<DemoLoom>();
```

## Sıradaki: Faz 3 (Upgrade UI, Multi-Station, Save/Load Inventory)

Bu hafta sonu hedefi: 4-5 istasyonlu, upgrade UI'lı, persist eden bir prototype.
