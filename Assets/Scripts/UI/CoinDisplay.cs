using TMPro;
using UnityEngine;
using CarpetEmpire.Core;
using CarpetEmpire.Utils;

namespace CarpetEmpire.UI
{
    /// <summary>
    /// Listens to EconomyManager and renders one currency's balance.
    /// </summary>
    public class CoinDisplay : MonoBehaviour
    {
        [SerializeField] private CurrencyType currency = CurrencyType.Coin;
        [SerializeField] private string prefix = "";
        [SerializeField] private TMP_Text label;

        private EconomyManager economy;

        private void Awake()
        {
            if (label == null) label = GetComponent<TMP_Text>();
        }

        private void OnEnable()
        {
            TrySubscribe();
        }

        private void Start()
        {
            TrySubscribe();
        }

        private void OnDisable()
        {
            if (economy != null) economy.OnBalanceChanged -= HandleBalanceChanged;
        }

        private void TrySubscribe()
        {
            if (economy != null || GameManager.Instance == null) return;
            economy = GameManager.Instance.Economy;
            if (economy == null) return;
            economy.OnBalanceChanged += HandleBalanceChanged;
            Render(economy.Get(currency));
        }

        private void HandleBalanceChanged(CurrencyType type, double value)
        {
            if (type == currency) Render(value);
        }

        private void Render(double value)
        {
            if (label != null) label.text = prefix + NumberFormatter.Format(value);
        }
    }
}
