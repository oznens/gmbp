using System;
using UnityEngine;
using CarpetEmpire.Carpets;
using CarpetEmpire.Data;

namespace CarpetEmpire.Stations
{
    /// <summary>
    /// Production-grade loom: weaves a CarpetItem over time using the active
    /// pattern, then drops it into a CarpetInventory.
    ///
    /// State: Idle → Weaving → ReadyToDrop → (auto-drop) → Idle
    /// Stalls in ReadyToDrop when inventory is full (back-pressure).
    /// </summary>
    public class LoomController : MonoBehaviour
    {
        public enum LoomState { Idle, Weaving, ReadyToDrop }

        [SerializeField] private StationConfig config;
        [SerializeField] private CarpetInventory inventory;
        [SerializeField] private PatternData activePattern;
        [SerializeField, Range(0.5f, 2f)] private float qualityMin = 0.9f;
        [SerializeField, Range(0.5f, 2f)] private float qualityMax = 1.3f;

        private float progress;
        private float boostMultiplier = 1f;
        private float boostRemaining;
        private CarpetItem pending;

        public LoomState State { get; private set; } = LoomState.Idle;
        public float Progress01 => Mathf.Clamp01(progress);
        public PatternData ActivePattern => activePattern;
        public StationConfig Config => config;

        public event Action OnWeavingStarted;
        public event Action<float> OnProgressChanged;
        public event Action<CarpetItem> OnCarpetCompleted;

        public void SetPattern(PatternData pattern)
        {
            activePattern = pattern;
        }

        public void ApplyTapBoost(float multiplier, float duration)
        {
            boostMultiplier = Mathf.Max(boostMultiplier, multiplier);
            boostRemaining = Mathf.Max(boostRemaining, duration);
        }

        private void Update()
        {
            if (config == null || inventory == null) return;

            TickBoost(Time.deltaTime);

            switch (State)
            {
                case LoomState.Idle:
                    BeginWeaving();
                    break;
                case LoomState.Weaving:
                    AdvanceWeaving(Time.deltaTime);
                    break;
                case LoomState.ReadyToDrop:
                    TryDropToInventory();
                    break;
            }
        }

        private void TickBoost(float dt)
        {
            if (boostRemaining <= 0) { boostMultiplier = 1f; return; }
            boostRemaining -= dt;
            if (boostRemaining <= 0) boostMultiplier = 1f;
        }

        private void BeginWeaving()
        {
            progress = 0;
            State = LoomState.Weaving;
            OnWeavingStarted?.Invoke();
        }

        private void AdvanceWeaving(float dt)
        {
            float patternSpeed = activePattern != null ? activePattern.speedMultiplier : 1f;
            float cooldown = Mathf.Max(0.01f,
                config.baseCooldown / patternSpeed / boostMultiplier);

            progress += dt / cooldown;
            OnProgressChanged?.Invoke(Progress01);

            if (progress >= 1f)
            {
                pending = CraftCarpet();
                State = LoomState.ReadyToDrop;
            }
        }

        private void TryDropToInventory()
        {
            if (pending == null) { State = LoomState.Idle; return; }
            if (!inventory.TryAdd(pending)) return; // stall until space

            OnCarpetCompleted?.Invoke(pending);
            pending = null;
            State = LoomState.Idle;
        }

        private CarpetItem CraftCarpet()
        {
            float quality = UnityEngine.Random.Range(qualityMin, qualityMax);
            int colorCount = activePattern == null ? 1 : 3; // refined per pattern later
            return new CarpetItem(activePattern, config.baseOutput, quality, colorCount);
        }
    }
}
