from datastore.lru import LRU, Node
data = ['a','b','c']

lrucache = LRU()
nodes = []
for d in data:
    node = lrucache.add(d)
    nodes.append(node)

lrucache.print()

lrucache.delete(nodes[1])
lrucache.print()
