using System;

namespace CarpetEmpire.Utils
{
    /// <summary>
    /// Idle-game style abbreviation: 1,234 → "1.23K", 1.2e9 → "1.2B".
    /// Goes up to aa, ab, ac... after T (trillion) for late-game prestige scales.
    /// </summary>
    public static class NumberFormatter
    {
        private static readonly string[] Suffixes =
        {
            "", "K", "M", "B", "T",
            "aa", "ab", "ac", "ad", "ae",
            "af", "ag", "ah", "ai", "aj"
        };

        public static string Format(double value)
        {
            if (value < 1000) return value.ToString("F0");

            int tier = (int)Math.Floor(Math.Log10(Math.Abs(value)) / 3);
            tier = Math.Min(tier, Suffixes.Length - 1);

            double scaled = value / Math.Pow(10, tier * 3);
            string format = scaled < 10 ? "F2" : scaled < 100 ? "F1" : "F0";
            return scaled.ToString(format) + Suffixes[tier];
        }
    }
}
