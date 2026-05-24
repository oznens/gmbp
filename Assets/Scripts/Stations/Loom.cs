using UnityEngine;
using CarpetEmpire.Core;

namespace CarpetEmpire.Stations
{
    /// <summary>
    /// The core loom. Weaves a carpet, then awards coins on completion.
    /// Hooks: OnWeavingStarted / OnWeavingCompleted for UI &amp; VFX.
    /// </summary>
    public class Loom : Station
    {
        public event System.Action OnWeavingStarted;
        public event System.Action<double> OnWeavingCompleted;

        protected override void OnProduce()
        {
            OnWeavingStarted?.Invoke();
            double payout = CurrentOutput * GameManager.Instance.Economy.PrestigeMultiplier;
            GameManager.Instance.Economy.Add(CurrencyType.Coin, payout);
            OnWeavingCompleted?.Invoke(payout);
        }
    }
}
