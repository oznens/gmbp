using UnityEngine;

namespace CarpetEmpire.Core
{
    /// <summary>
    /// Top-level singleton. Boots subsystems and survives scene loads.
    /// </summary>
    [DefaultExecutionOrder(-1000)]
    public class GameManager : MonoBehaviour
    {
        public static GameManager Instance { get; private set; }

        [Header("Subsystems")]
        [SerializeField] private EconomyManager economy;
        [SerializeField] private SaveSystem saveSystem;

        public EconomyManager Economy => economy;
        public SaveSystem Save => saveSystem;

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
            DontDestroyOnLoad(gameObject);

            if (economy == null) economy = GetComponentInChildren<EconomyManager>();
            if (saveSystem == null) saveSystem = GetComponentInChildren<SaveSystem>();

            Debug.Log("[GameManager] Initialized");
        }

        private void Start()
        {
            saveSystem.Load();
            economy.Initialize(saveSystem.State);
        }

        private void OnApplicationPause(bool paused)
        {
            if (paused) saveSystem.Save();
        }

        private void OnApplicationQuit()
        {
            saveSystem.Save();
        }
    }
}
