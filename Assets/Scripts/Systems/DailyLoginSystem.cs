using System;
using UnityEngine;
using CarpetEmpire.Core;
using CarpetEmpire.Data;

namespace CarpetEmpire.Systems
{
    /// <summary>
    /// Detects new-day logins, increments / resets streak, awards reward.
    /// Reward curve: day N gives min(5 * 2^(N-1), 100) gems.
    /// </summary>
    public class DailyLoginSystem : MonoBehaviour
    {
        public event Action<int, int> OnLoginReward;

        private void Start()
        {
            var state = GameManager.Instance.Save.State;
            if (state == null) return;

            var nowUtc = DateTime.UtcNow.Date;
            DateTime lastDate = state.lastDailyLoginUtc == 0
                ? DateTime.MinValue
                : DateTime.FromBinary(state.lastDailyLoginUtc).Date;

            if (nowUtc == lastDate) return;

            int daysGap = lastDate == DateTime.MinValue
                ? 1
                : (int)(nowUtc - lastDate).TotalDays;

            state.dailyLoginStreak = daysGap == 1 ? state.dailyLoginStreak + 1 : 1;
            state.lastDailyLoginUtc = nowUtc.ToBinary();

            int reward = CalcReward(state.dailyLoginStreak);
            GameManager.Instance.Economy.Add(CurrencyType.Gem, reward);
            GameManager.Instance.Save.Save();

            OnLoginReward?.Invoke(state.dailyLoginStreak, reward);
            Debug.Log($"[DailyLogin] Day {state.dailyLoginStreak}, +{reward} gems");
        }

        private static int CalcReward(int streakDay)
        {
            int raw = 5 * (int)Math.Pow(2, Math.Min(streakDay - 1, 5));
            return Math.Min(raw, 100);
        }
    }
}
