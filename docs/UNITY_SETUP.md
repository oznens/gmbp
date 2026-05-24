# Unity Setup — Sıfırdan Adım Adım

Hiç Unity kurulu değilse buradan başla. Tahmini süre: 30-60 dakika.

## 1. Unity Hub Kurulumu

Unity Hub, Unity Editor versiyonlarını ve projelerini yöneten "launcher"dır.

**İndir:** https://unity.com/download

- Windows: `.exe` installer
- macOS: `.dmg` installer (Apple Silicon için Universal)
- Linux: `.AppImage`

Kurulum sırasında Unity ID oluştur (ücretsiz, e-posta + şifre). Mobil oyun için **Personal license** yeter (gelirin < $200K/yıl olduğu sürece).

## 2. Unity Editor Versiyonu Kur

Unity Hub'ı aç → sol menü **Installs** → **Install Editor** → **Unity 6 LTS** seç (2025 itibariyle en yeni LTS).

⚠️ **6.0 olmayanı seçme!** 6.0.x LTS olmalı.

### Kurulum sırasında modülleri seç:

- ✅ **Android Build Support**
  - ✅ Android SDK & NDK Tools
  - ✅ OpenJDK
- ✅ **iOS Build Support** (Mac kullanıyorsan)
- ✅ **Documentation** (opsiyonel ama tavsiye)
- ✅ **Microsoft Visual Studio Community** (Windows) veya **Visual Studio for Mac** yerine **VS Code** + C# extension (önerilen)

⚠️ Disk alanı: ~12 GB. Kurulum 15-30 dk sürer.

## 3. Visual Studio Code Setup (önerilen)

Eğer VS Code seçtiysen:

```
1. https://code.visualstudio.com → indir
2. Extensions:
   - C# Dev Kit (Microsoft)
   - Unity (Unity Technologies)
3. Unity Editor → Edit → Preferences → External Tools
   - External Script Editor = Visual Studio Code
```

## 4. Proje Açma (bu repo)

Bu repo (`gmbp`) bir Unity projesi DEĞİL — sadece dokümanlar ve scriptler. İki seçenek:

### Seçenek A — Tavsiye edilen (temiz başlangıç)

```bash
# Bu repoyu local'de aç
cd /your/local/path
git clone <repo-url> gmbp
cd gmbp

# Unity Hub'ı aç
# New project → 3D Mobile template → Project name: gmbp-unity
# Location: /your/local/path (gmbp'nin DIŞINDA bir yere)
```

Unity proje oluşturduktan sonra **Assets/Scripts** ve **docs** klasörlerini repodan kopyala:

```bash
cp -r /your/local/path/gmbp/Assets/Scripts /your/local/path/gmbp-unity/Assets/
cp -r /your/local/path/gmbp/docs /your/local/path/gmbp-unity/
cp /your/local/path/gmbp/.gitignore /your/local/path/gmbp-unity/
```

Sonra `gmbp-unity` klasörünü git repo'su yap ve push'la.

### Seçenek B — Doğrudan bu klasörü Unity ile aç

Unity Hub → **Add** → klasör seç (`gmbp`) → Unity versiyon sor → 6 LTS seç.

Unity boş klasörde `Assets/`, `Library/`, `ProjectSettings/`, `Packages/` üretir. Mevcut `Assets/Scripts` + `docs/` dosyaları korunur.

## 5. Build Settings (Mobile)

Editor açıldıktan sonra:

```
File → Build Profiles (veya Build Settings)
→ Platform: Android  → "Switch Platform"
→ Player Settings:
   - Company Name: <senin adın>
   - Product Name: Carpet Empire Tycoon
   - Package Name: com.<senin>.carpetempire
   - Minimum API Level: 26 (Android 8.0)
   - Target API Level: Latest
   - Scripting Backend: IL2CPP
   - Target Architectures: ARM64 (✅), ARMv7 (❌)
```

iOS için aynı yerde **iOS** sekmesi.

## 6. Önerilen Paketler (Package Manager)

`Window → Package Manager → Unity Registry`:

- ✅ **TextMeshPro** (UI için zaten varsayılan)
- ✅ **Cinemachine** (kamera)
- ✅ **DOTween (Pro veya Free)** — Asset Store'dan, animation tween
- ✅ **Mobile Notifications** — push için
- ✅ **In App Purchasing** — IAP için
- ✅ **Analytics** (Unity Analytics)
- ✅ **Addressables** (asset yönetimi, opsiyonel ama tavsiye)

Reklam SDK'sı (sonra):
- **LevelPlay (IronSource)** veya **AppLovin MAX** — ayrı SDK indirilir

## 7. İlk Çalıştırma Testi

`File → New Scene → 3D Sample Scene` → bir küp koy → Play tuşuna bas. Çalışırsa kurulum tamamdır.

## 8. Sorun Giderme

**"Failed to install Editor"**
- Antivirüs / Defender'ı geçici durdur, tekrar dene
- Hub'ı yönetici (admin) olarak çalıştır

**"Android SDK location not found"**
- Edit → Preferences → External Tools
- Android SDK path: Unity Hub'ın `playbackengines/AndroidPlayer/SDK` klasörü

**Mac'te "Unity is damaged" hatası**
```bash
xattr -dr com.apple.quarantine /Applications/Unity\ Hub.app
```

**Build çok yavaş?**
- Library klasörü cache → SSD'de tut
- IL2CPP yerine ilk testlerde Mono kullan (sadece development)

## 9. Sonraki Adım

Kurulum bittiğinde:
1. Bana "Unity kuruldu" de
2. `Assets/Scripts/Core/GameManager.cs` aç → Console'da "GameManager Initialized" mesajını gör
3. Faz 1 işleri için `docs/ROADMAP.md`'ye geç
