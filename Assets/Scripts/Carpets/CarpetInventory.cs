using System;
using System.Collections.Generic;
using UnityEngine;

namespace CarpetEmpire.Carpets
{
    /// <summary>
    /// FIFO queue of finished carpets. Looms push, DisplayShelf pops.
    /// When full, looms stall (back-pressure keeps the economy honest).
    /// </summary>
    public class CarpetInventory : MonoBehaviour
    {
        [SerializeField] private int maxCapacity = 12;

        private readonly Queue<CarpetItem> stock = new();

        public int Count => stock.Count;
        public int MaxCapacity => maxCapacity;
        public bool IsFull => stock.Count >= maxCapacity;

        public event Action<CarpetItem> OnAdded;
        public event Action<CarpetItem> OnRemoved;

        public bool TryAdd(CarpetItem item)
        {
            if (item == null || IsFull) return false;
            stock.Enqueue(item);
            OnAdded?.Invoke(item);
            return true;
        }

        public bool TryTake(out CarpetItem item)
        {
            if (stock.Count == 0)
            {
                item = null;
                return false;
            }
            item = stock.Dequeue();
            OnRemoved?.Invoke(item);
            return true;
        }

        public CarpetItem Peek() => stock.Count == 0 ? null : stock.Peek();
    }
}
