using System;
using UnityEngine;
using CarpetEmpire.Data;

namespace CarpetEmpire.Core
{
    public enum CurrencyType { Coin, Gem, Star, MotifToken }

    /// <summary>
    /// Owns currency state and broadcasts changes.
    /// Stations/UI subscribe via OnBalanceChanged.
    /// </summary>
    public class EconomyManager : MonoBehaviour
    {
        public event Action<CurrencyType, double> OnBalanceChanged;

        private GameState state;

        public void Initialize(GameState gameState)
        {
            state = gameState;
            BroadcastAll();
        }

        public double Get(CurrencyType type) => type switch
        {
            CurrencyType.Coin => state.coin,
            CurrencyType.Gem => state.gem,
            CurrencyType.Star => state.star,
            CurrencyType.MotifToken => state.motifToken,
            _ => 0
        };

        public void Add(CurrencyType type, double amount)
        {
            if (amount <= 0) return;
            ApplyDelta(type, amount);
        }

        public bool TrySpend(CurrencyType type, double amount)
        {
            if (amount <= 0) return true;
            if (Get(type) < amount) return false;
            ApplyDelta(type, -amount);
            return true;
        }

        private void ApplyDelta(CurrencyType type, double delta)
        {
            switch (type)
            {
                case CurrencyType.Coin: state.coin += delta; break;
                case CurrencyType.Gem: state.gem += delta; break;
                case CurrencyType.Star: state.star += delta; break;
                case CurrencyType.MotifToken: state.motifToken += delta; break;
            }
            OnBalanceChanged?.Invoke(type, Get(type));
        }

        private void BroadcastAll()
        {
            OnBalanceChanged?.Invoke(CurrencyType.Coin, state.coin);
            OnBalanceChanged?.Invoke(CurrencyType.Gem, state.gem);
            OnBalanceChanged?.Invoke(CurrencyType.Star, state.star);
            OnBalanceChanged?.Invoke(CurrencyType.MotifToken, state.motifToken);
        }

        public double PrestigeMultiplier => 1.0 + state.star * 0.02;
    }
}
