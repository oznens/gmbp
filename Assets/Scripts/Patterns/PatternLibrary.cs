using System.Collections.Generic;
using UnityEngine;
using CarpetEmpire.Data;

namespace CarpetEmpire.Patterns
{
    /// <summary>
    /// Global registry of all PatternData assets shipped with the game.
    /// Point this at a single instance in the bootstrap scene; query by id.
    /// </summary>
    [CreateAssetMenu(menuName = "CarpetEmpire/Pattern Library", fileName = "PatternLibrary")]
    public class PatternLibrary : ScriptableObject
    {
        [SerializeField] private List<PatternData> patterns = new();

        private Dictionary<string, PatternData> byId;

        public IReadOnlyList<PatternData> All => patterns;

        public PatternData Get(string id)
        {
            EnsureIndex();
            return byId.TryGetValue(id, out var pattern) ? pattern : null;
        }

        public IEnumerable<PatternData> UnlockedFor(int playerLevel, ICollection<int> unlockedCities)
        {
            foreach (var p in patterns)
            {
                if (p.unlockAtPlayerLevel > playerLevel) continue;
                // City gate hook (string lookup is left for the city system).
                yield return p;
            }
        }

        private void EnsureIndex()
        {
            if (byId != null) return;
            byId = new Dictionary<string, PatternData>(patterns.Count);
            foreach (var p in patterns)
            {
                if (p != null && !string.IsNullOrEmpty(p.id))
                    byId[p.id] = p;
            }
        }

        private void OnEnable() => byId = null;
    }
}
