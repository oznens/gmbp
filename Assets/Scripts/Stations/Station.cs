using UnityEngine;
using CarpetEmpire.Core;
using CarpetEmpire.Data;

namespace CarpetEmpire.Stations
{
    /// <summary>
    /// Base class for all production stations (yarn, dye, loom, display, ...).
    /// Subclasses override OnProduce to emit output.
    /// </summary>
    public abstract class Station : MonoBehaviour
    {
        [SerializeField] private StationConfig config;

        public StationConfig Config => config;
        public int Level { get; private set; } = 1;
        public bool IsUnlocked { get; private set; }

        protected float CooldownTimer;

        public double CurrentOutput => config.baseOutput * Mathf.Pow(config.outputGrowth, Level - 1);
        public float CurrentCooldown => config.baseCooldown / Mathf.Pow(config.speedGrowth, Level - 1);
        public double NextUpgradeCost => config.baseUpgradeCost * Mathf.Pow(config.costGrowth, Level - 1);

        protected virtual void Update()
        {
            if (!IsUnlocked) return;
            CooldownTimer += Time.deltaTime;
            if (CooldownTimer >= CurrentCooldown)
            {
                CooldownTimer = 0f;
                OnProduce();
            }
        }

        protected abstract void OnProduce();

        public bool TryUpgrade()
        {
            var economy = GameManager.Instance.Economy;
            if (!economy.TrySpend(CurrencyType.Coin, NextUpgradeCost)) return false;
            Level++;
            return true;
        }

        public void Unlock()
        {
            IsUnlocked = true;
        }

        public StationSaveData ToSaveData() => new StationSaveData
        {
            stationId = config.id,
            level = Level,
            unlocked = IsUnlocked
        };

        public void LoadFromSave(StationSaveData data)
        {
            Level = Mathf.Max(1, data.level);
            IsUnlocked = data.unlocked;
        }
    }
}
