import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from datastore.in_memory_store import InMemoryStore


def lru_keys(store):
    keys = []
    current = store._lru.head
    while current is not None:
        keys.append(current.value)
        current = current.next
    return keys


class InMemoryStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        wal_path = Path(self.temp_dir.name) / "wal.log"
        self.store = InMemoryStore(wal_path=wal_path)

    def test_get_returns_value_after_put(self):
        self.store.put("a", 1)

        self.assertEqual(self.store.get("a"), 1)

    def test_get_missing_key_returns_none(self):
        self.assertIsNone(self.store.get("missing"))

    def test_put_existing_key_updates_value_without_duplicate_lru_node(self):
        self.store.put("a", 1)
        self.store.put("a", 2)

        self.assertEqual(self.store.get("a"), 2)
        self.assertEqual(lru_keys(self.store), ["a"])
        self.assertEqual(len(self.store._store), 1)

    def test_get_moves_existing_key_to_lru_head(self):
        self.store.put("a", 1)
        self.store.put("b", 2)

        self.assertEqual(lru_keys(self.store), ["b", "a"])
        self.assertEqual(self.store.get("b"), 2)
        self.assertEqual(lru_keys(self.store), ["b", "a"])

    def test_delete_removes_value_and_lru_node(self):
        self.store.put("a", 1)
        self.store.put("b", 2)

        self.store.delete("a")

        self.assertIsNone(self.store.get("a"))
        self.assertEqual(lru_keys(self.store), ["b"])
        self.assertNotIn("a", self.store._store)

    def test_delete_missing_key_is_noop(self):
        self.store.delete("missing")

        self.assertEqual(self.store._store, {})
        self.assertEqual(lru_keys(self.store), [])

    def test_expired_entry_is_deleted_and_returns_none(self):
        with patch("datastore.in_memory_store.time.monotonic", side_effect=[100, 100 + self.store.default_ttl + 1]):
            self.store.put("a", 1)
            self.assertIsNone(self.store.get("a"))

        self.assertNotIn("a", self.store._store)
        self.assertEqual(lru_keys(self.store), [])

    def test_get_of_unexpired_entry_returns_value(self):
        with patch("datastore.in_memory_store.time.monotonic", side_effect=[100, 100 + self.store.default_ttl - 1]):
            self.store.put("a", 1)
            self.assertEqual(self.store.get("a"), 1)

    def test_capacity_evicts_lru_head(self):
        self.store.MAX_CAPACITY = 2
        self.store.put("a", 1)
        self.store.put("b", 2)
        self.store.put("c", 3)

        self.assertIsNone(self.store.get("a"))
        self.assertEqual(self.store.get("b"), 2)
        self.assertEqual(self.store.get("c"), 3)
        # The reads above move b and then c to the LRU head.
        self.assertEqual(lru_keys(self.store), ["c", "b"])


if __name__ == "__main__":
    unittest.main()
