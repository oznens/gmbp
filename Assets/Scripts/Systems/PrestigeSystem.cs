using System;
using UnityEngine;
using CarpetEmpire.Core;
using CarpetEmpire.Data;

namespace CarpetEmpire.Systems
{
    /// <summary>
    /// Prestige rules:
    ///   - Stars earned = floor(sqrt(lifetimeCoinEarned / threshold))
    ///   - Reset clears coins + station levels, keeps stars, cities, patterns.
    /// </summary>
    public class PrestigeSystem : MonoBehaviour
    {
        public const double PrestigeThreshold = 1_000_000;

        public event Action<double> OnPrestigeExecuted;

        public double PreviewStarsEarned()
        {
            var state = GameManager.Instance.Save.State;
            return CalcStars(state.lifetimeCoinEarned);
        }

        public bool CanPrestige()
        {
            return PreviewStarsEarned() >= 1;
        }

        public bool TryExecute()
        {
            if (!CanPrestige()) return false;

            var state = GameManager.Instance.Save.State;
            double stars = CalcStars(state.lifetimeCoinEarned);

            state.coin = 0;
            state.lifetimeCoinEarned = 0;
            state.passiveIncomePerSec = 0;
            state.pendingOfflineReward = 0;
            foreach (var station in state.stations)
            {
                station.level = 1;
            }

            var economy = GameManager.Instance.Economy;
            economy.Initialize(state);
            economy.Add(CurrencyType.Star, stars);

            GameManager.Instance.Save.Save();
            OnPrestigeExecuted?.Invoke(stars);
            return true;
        }

        private static double CalcStars(double lifetimeCoins)
        {
            if (lifetimeCoins < PrestigeThreshold) return 0;
            return Math.Floor(Math.Sqrt(lifetimeCoins / PrestigeThreshold));
        }
    }
}
