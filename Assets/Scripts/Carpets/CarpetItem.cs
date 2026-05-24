using CarpetEmpire.Data;

namespace CarpetEmpire.Carpets
{
    /// <summary>
    /// A finished carpet sitting in inventory waiting to be sold.
    /// Pure runtime data; not persisted (inventory is transient gameplay state).
    /// </summary>
    public class CarpetItem
    {
        public PatternData Pattern { get; }
        public double BaseValue { get; }
        public float QualityMultiplier { get; }
        public int ColorCount { get; }

        public CarpetItem(PatternData pattern, double baseValue, float quality, int colorCount)
        {
            Pattern = pattern;
            BaseValue = baseValue;
            QualityMultiplier = quality;
            ColorCount = colorCount;
        }

        /// <summary>
        /// Sale value before customer preference and global prestige bonuses.
        /// Those are applied at the point of sale in DisplayShelf.
        /// </summary>
        public double SaleValue
        {
            get
            {
                float patternMul = Pattern != null ? Pattern.valueMultiplier : 1f;
                float colorBonus = 1f + ColorCount * 0.1f;
                return BaseValue * patternMul * QualityMultiplier * colorBonus;
            }
        }
    }
}
