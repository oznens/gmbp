using System;
using System.Collections.Generic;

namespace CarpetEmpire.Data
{
    /// <summary>
    /// Serializable root of all persistent player state.
    /// Keep all fields JSON-friendly (no properties, no complex types).
    /// </summary>
    [Serializable]
    public class GameState
    {
        public int saveVersion = 1;
        public long lastSaveUtc;

        public double coin;
        public double gem;
        public double star;
        public double motifToken;

        public double lifetimeCoinEarned;
        public double passiveIncomePerSec;
        public double pendingOfflineReward;

        public int currentCityIndex;
        public List<int> unlockedCities = new List<int> { 0 };
        public List<string> unlockedPatterns = new List<string> { "simple_kilim" };
        public List<StationSaveData> stations = new List<StationSaveData>();

        public int dailyLoginStreak;
        public long lastDailyLoginUtc;
    }

    [Serializable]
    public class StationSaveData
    {
        public string stationId;
        public int level;
        public bool unlocked;
    }
}
