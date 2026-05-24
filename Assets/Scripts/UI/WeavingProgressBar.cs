using UnityEngine;
using UnityEngine.UI;
using CarpetEmpire.Stations;

namespace CarpetEmpire.UI
{
    /// <summary>
    /// Drives a UGUI Image (filled type) from a LoomController's progress.
    /// </summary>
    [RequireComponent(typeof(Image))]
    public class WeavingProgressBar : MonoBehaviour
    {
        [SerializeField] private LoomController loom;
        [SerializeField] private Gradient colorOverProgress;

        private Image image;

        private void Awake()
        {
            image = GetComponent<Image>();
            if (image.type != Image.Type.Filled)
            {
                Debug.LogWarning("[WeavingProgressBar] Image.type should be Filled.");
            }
        }

        private void OnEnable()
        {
            if (loom != null) loom.OnProgressChanged += Apply;
        }

        private void OnDisable()
        {
            if (loom != null) loom.OnProgressChanged -= Apply;
        }

        private void Update()
        {
            if (loom == null) return;
            Apply(loom.Progress01);
        }

        private void Apply(float t)
        {
            image.fillAmount = t;
            if (colorOverProgress != null) image.color = colorOverProgress.Evaluate(t);
        }
    }
}
