using System.Collections.Generic;
using UnityEngine;

namespace CarpetEmpire.Customers
{
    /// <summary>
    /// Timed customer spawner. Picks weighted archetype, manages queue.
    /// Visualization (NavMesh / prefab instantiation) is layered on top later.
    /// </summary>
    public class CustomerSpawner : MonoBehaviour
    {
        [SerializeField] private List<CustomerData> archetypes = new();
        [SerializeField] private float spawnInterval = 2f;
        [SerializeField] private int maxQueue = 8;

        private readonly Queue<Customer> queue = new();
        private float spawnTimer;

        public IReadOnlyCollection<Customer> Queue => queue;
        public int QueueCount => queue.Count;
        public event System.Action<Customer> OnCustomerSpawned;
        public event System.Action<Customer> OnCustomerLeft;

        private void Update()
        {
            spawnTimer += Time.deltaTime;
            if (spawnTimer >= spawnInterval && queue.Count < maxQueue)
            {
                spawnTimer = 0;
                Spawn();
            }

            foreach (var c in queue)
            {
                c.Tick(Time.deltaTime);
            }

            // Clean up customers who left angry.
            while (queue.Count > 0)
            {
                var front = queue.Peek();
                if (front.CurrentState == Customer.State.LeftHappy ||
                    front.CurrentState == Customer.State.LeftAngry)
                {
                    queue.Dequeue();
                    OnCustomerLeft?.Invoke(front);
                }
                else break;
            }
        }

        private void Spawn()
        {
            var archetype = PickWeighted();
            if (archetype == null) return;

            var customer = new Customer(archetype);
            customer.EnterQueue();
            queue.Enqueue(customer);
            OnCustomerSpawned?.Invoke(customer);
        }

        private CustomerData PickWeighted()
        {
            if (archetypes.Count == 0) return null;

            float total = 0;
            foreach (var a in archetypes) total += Mathf.Max(0, a.spawnWeight);
            if (total <= 0) return archetypes[0];

            float roll = Random.value * total;
            float cumulative = 0;
            foreach (var a in archetypes)
            {
                cumulative += Mathf.Max(0, a.spawnWeight);
                if (roll <= cumulative) return a;
            }
            return archetypes[archetypes.Count - 1];
        }

        public bool TryServeFrontCustomer(out Customer served)
        {
            served = null;
            if (queue.Count == 0) return false;
            served = queue.Peek();
            if (served.CurrentState != Customer.State.Waiting) return false;
            served.BeginPurchase();
            served.CompletePurchase();
            return true;
        }
    }
}
