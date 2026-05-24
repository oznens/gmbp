using UnityEngine;

namespace CarpetEmpire.Data
{
    /// <summary>
    /// Designer-tunable carpet pattern.
    /// Create: Assets → Create → CarpetEmpire → Pattern.
    /// </summary>
    [CreateAssetMenu(menuName = "CarpetEmpire/Pattern", fileName = "Pattern")]
    public class PatternData : ScriptableObject
    {
        public string id;
        public string displayName;

        [TextArea] public string description;

        [Header("Gameplay")]
        [Tooltip("Time to weave (relative). <1 = slower, >1 = faster.")]
        public float speedMultiplier = 1f;

        [Tooltip("Sale value multiplier. Premium patterns sell for more.")]
        public float valueMultiplier = 1f;

        [Header("Progression")]
        public int unlockAtPlayerLevel = 1;

        [Tooltip("If non-empty, also requires this city unlocked.")]
        public string requiresCityId;

        [Header("Visual")]
        public Sprite preview;
        public Color dominantColor = Color.white;
    }
}
