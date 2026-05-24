using System;

namespace CarpetEmpire.Customers
{
    /// <summary>
    /// Runtime customer instance (data, not GameObject).
    /// Visualization is wired in Phase 5 via CustomerView.
    /// </summary>
    public class Customer
    {
        public enum State { Entering, Waiting, Buying, Leaving, LeftHappy, LeftAngry }

        public CustomerData Data { get; }
        public State CurrentState { get; private set; }
        public float WaitTimer { get; private set; }

        public event Action<Customer> OnStateChanged;

        public Customer(CustomerData data)
        {
            Data = data;
            CurrentState = State.Entering;
        }

        public void Tick(float deltaTime)
        {
            if (CurrentState != State.Waiting) return;
            WaitTimer += deltaTime;
            if (WaitTimer >= Data.patience)
            {
                SetState(State.LeftAngry);
            }
        }

        public void EnterQueue()
        {
            WaitTimer = 0;
            SetState(State.Waiting);
        }

        public void BeginPurchase()
        {
            SetState(State.Buying);
        }

        public void CompletePurchase()
        {
            SetState(State.LeftHappy);
        }

        private void SetState(State next)
        {
            if (CurrentState == next) return;
            CurrentState = next;
            OnStateChanged?.Invoke(this);
        }

        public float PreferenceMultiplier(string patternId)
        {
            if (Data.preferredPatterns == null) return 1f;
            foreach (var p in Data.preferredPatterns)
            {
                if (p == patternId) return Data.preferenceBonus;
            }
            return 1f;
        }
    }
}
