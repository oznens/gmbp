using UnityEngine;
using CarpetEmpire.Systems;

namespace CarpetEmpire.Core
{
    /// <summary>
    /// Auto-spawns the GameManager hierarchy before the first scene loads,
    /// so a fresh project plays without any manual scene setup.
    /// Once the production scene is built, this can be removed or guarded.
    /// </summary>
    public static class Bootstrap
    {
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        private static void Initialize()
        {
            if (GameManager.Instance != null) return;

            var root = new GameObject("[GameManager]");

            var economyGo = new GameObject("EconomyManager");
            economyGo.transform.SetParent(root.transform);
            economyGo.AddComponent<EconomyManager>();

            var saveGo = new GameObject("SaveSystem");
            saveGo.transform.SetParent(root.transform);
            saveGo.AddComponent<SaveSystem>();

            var prestigeGo = new GameObject("PrestigeSystem");
            prestigeGo.transform.SetParent(root.transform);
            prestigeGo.AddComponent<PrestigeSystem>();

            var dailyLoginGo = new GameObject("DailyLoginSystem");
            dailyLoginGo.transform.SetParent(root.transform);
            dailyLoginGo.AddComponent<DailyLoginSystem>();

            root.AddComponent<GameManager>();
        }
    }
}
