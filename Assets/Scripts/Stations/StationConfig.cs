using UnityEngine;

namespace CarpetEmpire.Stations
{
    /// <summary>
    /// Designer-tunable parameters for a station type.
    /// Create instances: Assets → Create → CarpetEmpire → Station Config.
    /// </summary>
    [CreateAssetMenu(menuName = "CarpetEmpire/Station Config", fileName = "StationConfig")]
    public class StationConfig : ScriptableObject
    {
        public string id;
        public string displayName;

        [Header("Output")]
        public double baseOutput = 5;
        public float outputGrowth = 1.07f;

        [Header("Timing")]
        public float baseCooldown = 3f;
        public float speedGrowth = 1.03f;

        [Header("Economy")]
        public double baseUpgradeCost = 50;
        public float costGrowth = 1.15f;

        [Header("Progression")]
        public int unlockAtPlayerLevel = 1;
    }
}
