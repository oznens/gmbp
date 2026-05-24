using UnityEngine;
using CarpetEmpire.Core;

namespace CarpetEmpire.Stations
{
    /// <summary>
    /// Config-less stand-in loom used until designers wire real StationConfig assets.
    /// Produces coins on a fixed cadence so the HUD shows life on Play.
    /// Remove from Bootstrap once real stations exist in scene.
    /// </summary>
    public class DemoLoom : MonoBehaviour
    {
        [SerializeField] private double payoutPerTick = 5;
        [SerializeField] private float tickInterval = 1f;

        private float timer;

        private void Update()
        {
            if (GameManager.Instance == null) return;

            timer += Time.deltaTime;
            if (timer < tickInterval) return;
            timer = 0;

            double prestige = GameManager.Instance.Economy.PrestigeMultiplier;
            GameManager.Instance.Economy.Add(CurrencyType.Coin, payoutPerTick * prestige);
        }
    }
}
