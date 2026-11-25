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
        self.wal_path = Path(self.temp_dir.name) / "nested" / "wal.log"
        self.addCleanup(self.temp_dir.cleanup)

    def new_store(self):
        return InMemoryStore(self.snapshot_path, self.wal_path)

    def test_save_and_load_restores_values(self):
        store = self.new_store()
        store.put("a", {"count": 1})
        store.put("b", [1, 2, 3])
        store.save()

        restored = self.new_store()
        restored.load()

        self.assertEqual(restored.get("a"), {"count": 1})
        self.assertEqual(restored.get("b"), [1, 2, 3])

    def test_save_and_load_preserves_lru_order(self):
        store = self.new_store()
        store.put("a", 1)
        store.put("b", 2)
        store.put("c", 3)
        store.get("a")
        expected_order = lru_keys(store)

        store.save()
        restored = self.new_store()
        restored.load()

        self.assertEqual(lru_keys(restored), expected_order)

    def test_load_restores_snapshot_and_replays_newer_wal_entries(self):
        source = self.new_store()
        source.put("saved", 1)
        source.save()

        restored = self.new_store()
        restored.put("unsaved", 2)
        restored.load()

        self.assertEqual(restored.get("saved"), 1)
        self.assertEqual(restored.get("unsaved"), 2)

    def test_expired_entries_are_not_restored(self):
        store = self.new_store()
        store.put("expired", "old", ttl=-1)
        store.save()

        restored = self.new_store()
        restored.load()

        self.assertIsNone(restored.get("expired"))
        self.assertIsNone(restored._lru.head)

    def test_load_missing_snapshot_is_noop(self):
        store = self.new_store()
        store.put("a", 1)

        store.load()

        self.assertEqual(store.get("a"), 1)

    def test_load_replays_only_wal_entries_after_snapshot_without_appending(self):
        source = self.new_store()
        source.put("snapshot-value", 1)
        source.save()
        source.put("wal-value", 2)
        expected_wal_offset = source.wal.get_offset()

        restored = self.new_store()
        restored.load()

        self.assertEqual(restored.get("snapshot-value"), 1)
        self.assertEqual(restored.get("wal-value"), 2)
        self.assertEqual(restored.wal.get_offset(), expected_wal_offset)

    def test_load_replays_wal_when_snapshot_is_missing(self):
        source = self.new_store()
        source.put("wal-value", 2)

        restored = self.new_store()
        restored.load()

        self.assertEqual(restored.get("wal-value"), 2)


if __name__ == "__main__":
    unittest.main()
