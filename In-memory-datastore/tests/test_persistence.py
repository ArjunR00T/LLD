import tempfile
import unittest
from pathlib import Path

from datastore.in_memory_store import InMemoryStore


def lru_keys(store):
    keys = []
    current = store._lru.head
    while current is not None:
        keys.append(current.value)
        current = current.next
    return keys


class PersistenceTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.snapshot_path = Path(self.temp_dir.name) / "nested" / "snapshot.pkl"
        self.addCleanup(self.temp_dir.cleanup)

    def test_save_and_load_restores_values(self):
        store = InMemoryStore(self.snapshot_path)
        store.put("a", {"count": 1})
        store.put("b", [1, 2, 3])
        store.save()

        restored = InMemoryStore(self.snapshot_path)
        restored.load()

        self.assertEqual(restored.get("a"), {"count": 1})
        self.assertEqual(restored.get("b"), [1, 2, 3])

    def test_save_and_load_preserves_lru_order(self):
        store = InMemoryStore(self.snapshot_path)
        store.put("a", 1)
        store.put("b", 2)
        store.put("c", 3)
        store.get("a")
        expected_order = lru_keys(store)

        store.save()
        restored = InMemoryStore(self.snapshot_path)
        restored.load()

        self.assertEqual(lru_keys(restored), expected_order)

    def test_load_replaces_existing_state(self):
        source = InMemoryStore(self.snapshot_path)
        source.put("saved", 1)
        source.save()

        restored = InMemoryStore(self.snapshot_path)
        restored.put("unsaved", 2)
        restored.load()

        self.assertEqual(restored.get("saved"), 1)
        self.assertIsNone(restored.get("unsaved"))

    def test_expired_entries_are_not_restored(self):
        store = InMemoryStore(self.snapshot_path)
        store.put("expired", "old", ttl=-1)
        store.save()

        restored = InMemoryStore(self.snapshot_path)
        restored.load()

        self.assertIsNone(restored.get("expired"))
        self.assertIsNone(restored._lru.head)

    def test_load_missing_snapshot_is_noop(self):
        store = InMemoryStore(self.snapshot_path)
        store.put("a", 1)

        store.load()

        self.assertEqual(store.get("a"), 1)


if __name__ == "__main__":
    unittest.main()
