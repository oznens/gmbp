using System;
using System.IO;
using UnityEngine;
using CarpetEmpire.Data;

namespace CarpetEmpire.Core
{
    /// <summary>
    /// JSON file save in Application.persistentDataPath.
    /// Calculates offline reward delta on load.
    /// </summary>
    public class SaveSystem : MonoBehaviour
    {
        private const string FileName = "save.json";
        private const int MaxOfflineSeconds = 4 * 60 * 60;

        public GameState State { get; private set; }

        private string Path => System.IO.Path.Combine(Application.persistentDataPath, FileName);

        public void Load()
        {
            if (File.Exists(Path))
            {
                try
                {
                    var json = File.ReadAllText(Path);
                    State = JsonUtility.FromJson<GameState>(json) ?? new GameState();
                }
                catch (Exception e)
                {
                    Debug.LogError($"[SaveSystem] Load failed: {e.Message}");
                    State = new GameState();
                }
            }
            else
            {
                State = new GameState();
            }

            ApplyOfflineProgress();
        }

        public void Save()
        {
            if (State == null) return;
            State.lastSaveUtc = DateTime.UtcNow.ToBinary();
            var json = JsonUtility.ToJson(State, true);
            File.WriteAllText(Path, json);
        }

        private void ApplyOfflineProgress()
        {
            if (State.lastSaveUtc == 0 || State.passiveIncomePerSec <= 0) return;

            var last = DateTime.FromBinary(State.lastSaveUtc);
            var elapsed = (DateTime.UtcNow - last).TotalSeconds;
            elapsed = Math.Min(elapsed, MaxOfflineSeconds);
            if (elapsed <= 0) return;

            double offlineReward = elapsed * State.passiveIncomePerSec;
            State.pendingOfflineReward += offlineReward;
            Debug.Log($"[SaveSystem] Offline {elapsed:F0}s → +{offlineReward:F0} coins pending");
        }
    }
}
