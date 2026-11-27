class Node:
    def __init__(self, value: str):
        self.value = value
        self.next = None
        self.prev = None


class LRU:
    def __init__(self):
        self.head = None  # Most recently used node.
        self.tail = None  # Least recently used node.

    def add(self, key):
        node = Node(key)
        node.next = self.head

        if self.head is not None:
            self.head.prev = node
        else:
            self.tail = node

        self.head = node
        return node

    def delete(self, node: Node):
        if not isinstance(node, Node):
            raise TypeError("node must be an instance of Node")

        if node.prev is not None:
            node.prev.next = node.next
        else:
            self.head = node.next

        if node.next is not None:
            node.next.prev = node.prev
        else:
            self.tail = node.prev

        node.prev = None
        node.next = None
        return self.head

    def evict(self):
        if self.tail is None:
            return None

        node = self.tail
        self.delete(node)
        return node

    def update(self, node: Node):
        if not isinstance(node, Node):
            raise TypeError("node must be an instance of Node")

        if node == self.head:
            return self.head

        if node.prev is not None:
            node.prev.next = node.next
        if node.next is not None:
            node.next.prev = node.prev
        else:
            self.tail = node.prev

        node.prev = None
        node.next = self.head
        self.head.prev = node
        self.head = node
        return self.head

    def print(self):
        current = self.head
        while current:
            print(current.value, end=" -> ")
            current = current.next
        print("")

    def get_list(self):
        curr = self.head
        res = []

        while curr:
            res.append(curr.value)
            curr = curr.next
        return res

