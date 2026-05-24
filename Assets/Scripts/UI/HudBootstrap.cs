using TMPro;
using UnityEngine;
using UnityEngine.UI;
using CarpetEmpire.Core;

namespace CarpetEmpire.UI
{
    /// <summary>
    /// Builds a minimal HUD (currency labels) at runtime so a fresh project
    /// has visible feedback on Play without needing prefabs in the scene yet.
    /// Will be replaced by proper UGUI prefabs in Phase 5 polish.
    /// </summary>
    public static class HudBootstrap
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void Build()
        {
            if (Object.FindObjectOfType<Canvas>(true) != null) return;

            var canvasGo = new GameObject("[HUD Canvas]",
                typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            Object.DontDestroyOnLoad(canvasGo);

            var canvas = canvasGo.GetComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 100;

            var scaler = canvasGo.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1080, 1920);
            scaler.matchWidthOrHeight = 0.5f;

            CreateCurrencyLabel(canvasGo.transform, "CoinLabel", CurrencyType.Coin,
                new Vector2(20, -20), TextAnchor.UpperLeft, "🪙 ");
            CreateCurrencyLabel(canvasGo.transform, "GemLabel", CurrencyType.Gem,
                new Vector2(-20, -20), TextAnchor.UpperRight, "💎 ");
            CreateCurrencyLabel(canvasGo.transform, "StarLabel", CurrencyType.Star,
                new Vector2(-20, -80), TextAnchor.UpperRight, "⭐ ");
        }

        private static void CreateCurrencyLabel(
            Transform parent, string name, CurrencyType currency,
            Vector2 anchoredPos, TextAnchor anchor, string prefix)
        {
            var go = new GameObject(name, typeof(RectTransform));
            go.transform.SetParent(parent, false);

            var rect = go.GetComponent<RectTransform>();
            switch (anchor)
            {
                case TextAnchor.UpperLeft:
                    rect.anchorMin = rect.anchorMax = new Vector2(0, 1);
                    rect.pivot = new Vector2(0, 1);
                    break;
                case TextAnchor.UpperRight:
                    rect.anchorMin = rect.anchorMax = new Vector2(1, 1);
                    rect.pivot = new Vector2(1, 1);
                    break;
            }
            rect.anchoredPosition = anchoredPos;
            rect.sizeDelta = new Vector2(400, 60);

            var tmp = go.AddComponent<TextMeshProUGUI>();
            tmp.fontSize = 42;
            tmp.color = Color.white;
            tmp.alignment = anchor == TextAnchor.UpperRight
                ? TextAlignmentOptions.Right
                : TextAlignmentOptions.Left;
            tmp.text = prefix + "0";

            var display = go.AddComponent<CoinDisplay>();
            display.GetType()
                .GetField("currency",
                    System.Reflection.BindingFlags.Instance |
                    System.Reflection.BindingFlags.NonPublic)
                ?.SetValue(display, currency);
            display.GetType()
                .GetField("prefix",
                    System.Reflection.BindingFlags.Instance |
                    System.Reflection.BindingFlags.NonPublic)
                ?.SetValue(display, prefix);
            display.GetType()
                .GetField("label",
                    System.Reflection.BindingFlags.Instance |
                    System.Reflection.BindingFlags.NonPublic)
                ?.SetValue(display, tmp);
        }
    }
}
