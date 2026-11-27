import unittest

from SeenanaStore.datastore.lru import LRU


def forward_values(lru):
    """Return values from most recently used head to least recent tail."""
    values = []
    previous = None
    current = lru.head

    while current is not None:
        if current.prev is not previous:
            raise AssertionError("Previous/next links are inconsistent")
        values.append(current.value)
        previous = current
        current = current.next

    return values


def assert_list_integrity(test_case, lru, expected_values):
    """Check values and both directions of the doubly linked list."""
    test_case.assertEqual(forward_values(lru), expected_values)

    if lru.head is None:
        return

    nodes = []
    current = lru.head
    while current is not None:
        nodes.append(current)
        current = current.next

    test_case.assertIsNone(nodes[0].prev)
    test_case.assertIsNone(nodes[-1].next)

    current = nodes[-1]
    for expected in reversed(nodes[:-1]):
        current = current.prev
        test_case.assertIs(current, expected)


class LRUTest(unittest.TestCase):
    def setUp(self):
        self.lru = LRU()
        self.nodes = [self.lru.add(value) for value in ("a", "b", "c")]

    def test_add_prepends_new_entries_at_head(self):
        assert_list_integrity(self, self.lru, ["c", "b", "a"])

    def test_add_to_empty_cache_sets_head(self):
        lru = LRU()
        node = lru.add("a")

        self.assertIs(lru.head, node)
        self.assertIs(lru.tail, node)
        assert_list_integrity(self, lru, ["a"])

    def test_delete_head(self):
        returned_head = self.lru.delete(self.nodes[2])

        self.assertIs(returned_head, self.nodes[1])
        assert_list_integrity(self, self.lru, ["b", "a"])

    def test_delete_middle(self):
        self.lru.delete(self.nodes[1])

        assert_list_integrity(self, self.lru, ["c", "a"])

    def test_delete_tail(self):
        self.lru.delete(self.nodes[0])

        assert_list_integrity(self, self.lru, ["c", "b"])

    def test_delete_only_node(self):
        lru = LRU()
        node = lru.add("a")

        self.assertIsNone(lru.delete(node))
        assert_list_integrity(self, lru, [])

    def test_evict_removes_least_recent_entry(self):
        returned_head = self.lru.evict()

        self.assertIs(returned_head, self.nodes[0])
        assert_list_integrity(self, self.lru, ["c", "b"])

    def test_evict_empty_cache_returns_none(self):
        self.assertIsNone(LRU().evict())

    def test_update_moves_entry_to_head(self):
        returned_head = self.lru.update(self.nodes[0])

        self.assertIs(returned_head, self.nodes[0])
        assert_list_integrity(self, self.lru, ["a", "c", "b"])

    def test_update_middle_entry(self):
        self.lru.update(self.nodes[1])

        assert_list_integrity(self, self.lru, ["b", "c", "a"])

    def test_update_tail_entry_moves_to_head(self):
        returned_head = self.lru.update(self.nodes[2])

        self.assertIs(returned_head, self.nodes[2])
        assert_list_integrity(self, self.lru, ["c", "b", "a"])

    def test_invalid_delete_argument_raises_type_error(self):
        with self.assertRaises(TypeError):
            self.lru.delete("a")

    def test_invalid_update_argument_raises_type_error(self):
        with self.assertRaises(TypeError):
            self.lru.update("a")


if __name__ == "__main__":
    unittest.main()
