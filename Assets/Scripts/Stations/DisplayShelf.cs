using UnityEngine;
using CarpetEmpire.Carpets;
using CarpetEmpire.Core;
using CarpetEmpire.Customers;

namespace CarpetEmpire.Stations
{
    /// <summary>
    /// Bridges CarpetInventory and CustomerSpawner: when both have stock
    /// and a customer, executes a sale and credits the economy.
    /// Applies customer preference + prestige multipliers at sale time.
    /// </summary>
    public class DisplayShelf : MonoBehaviour
    {
        [SerializeField] private CarpetInventory inventory;
        [SerializeField] private CustomerSpawner spawner;
        [SerializeField] private float salesPerSecond = 1f;

        private float saleCooldown;

        public event System.Action<CarpetItem, Customer, double> OnSaleCompleted;

        private void Update()
        {
            if (inventory == null || spawner == null || GameManager.Instance == null) return;

            saleCooldown -= Time.deltaTime;
            if (saleCooldown > 0) return;
            if (inventory.Count == 0 || spawner.QueueCount == 0) return;
            if (!spawner.TryServeFrontCustomer(out var customer)) return;

            inventory.TryTake(out var carpet);
            if (carpet == null) return;

            double price = CalculatePrice(carpet, customer);
            GameManager.Instance.Economy.Add(CurrencyType.Coin, price);
            saleCooldown = 1f / Mathf.Max(0.1f, salesPerSecond);

            OnSaleCompleted?.Invoke(carpet, customer, price);
        }

        private double CalculatePrice(CarpetItem carpet, Customer customer)
        {
            float preference = customer.PreferenceMultiplier(
                carpet.Pattern != null ? carpet.Pattern.id : "");
            double prestige = GameManager.Instance.Economy.PrestigeMultiplier;
            return carpet.SaleValue * preference * customer.Data.coinMultiplier * prestige;
        }
    }
}
