using UnityEngine;

namespace CarpetEmpire.Customers
{
    /// <summary>
    /// Designer-tunable customer archetype.
    /// Create: Assets → Create → CarpetEmpire → Customer.
    /// </summary>
    [CreateAssetMenu(menuName = "CarpetEmpire/Customer", fileName = "Customer")]
    public class CustomerData : ScriptableObject
    {
        public string id;
        public string displayName;

        [Header("Economy")]
        public float coinMultiplier = 1f;
        public float spawnWeight = 1f;
        public int unlockAtPlayerLevel = 1;

        [Header("Behavior")]
        [Tooltip("Seconds before the customer leaves without buying.")]
        public float patience = 30f;

        [Tooltip("Pattern IDs this customer especially likes (gives bonus).")]
        public string[] preferredPatterns;
        public float preferenceBonus = 1.3f;

        [Header("Visual")]
        public GameObject prefab;
        public Sprite icon;
    }
}
