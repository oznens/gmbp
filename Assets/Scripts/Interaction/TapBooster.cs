using UnityEngine;
using CarpetEmpire.Stations;

namespace CarpetEmpire.Interaction
{
    /// <summary>
    /// Each tap on screen boosts every active LoomController for a short window.
    /// Tap stacking caps so spamming has diminishing returns (keeps it satisfying
    /// without breaking the economy).
    /// </summary>
    public class TapBooster : MonoBehaviour
    {
        [SerializeField] private float perTapBoost = 0.5f;
        [SerializeField] private float boostDuration = 1.5f;
        [SerializeField] private float maxBoostMultiplier = 3f;

        private float currentBoost = 1f;
        private float remaining;

        private void Update()
        {
            if (remaining > 0)
            {
                remaining -= Time.deltaTime;
                if (remaining <= 0) currentBoost = 1f;
            }

            if (DetectTap())
            {
                currentBoost = Mathf.Min(currentBoost + perTapBoost, maxBoostMultiplier);
                remaining = boostDuration;
                ApplyToLooms(currentBoost, boostDuration);
            }
        }

        private static bool DetectTap()
        {
#if ENABLE_INPUT_SYSTEM
            var mouse = UnityEngine.InputSystem.Mouse.current;
            if (mouse != null && mouse.leftButton.wasPressedThisFrame) return true;
            var touch = UnityEngine.InputSystem.Touchscreen.current;
            if (touch != null && touch.primaryTouch.press.wasPressedThisFrame) return true;
            return false;
#else
            if (Input.GetMouseButtonDown(0)) return true;
            for (int i = 0; i < Input.touchCount; i++)
            {
                if (Input.GetTouch(i).phase == TouchPhase.Began) return true;
            }
            return false;
#endif
        }

        private static void ApplyToLooms(float mult, float duration)
        {
            var looms = FindObjectsByType<LoomController>(FindObjectsSortMode.None);
            foreach (var loom in looms)
            {
                loom.ApplyTapBoost(mult, duration);
            }
        }
    }
}
