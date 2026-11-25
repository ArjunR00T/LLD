
from .in_memory_store import InMemoryStore

store = InMemoryStore()

store.put("key1", "value1")
store.put("key2", "value2")
store.put("key3", "value3")

print("Initial store state:")
print(store._store,"\n")

print("Saving store state...\n")
store.save()
print("State saved. Now simulating a crash and reload...\n")

store = InMemoryStore()
store.load()

print("State Reloaded and store contains \n")    
print(store._store,"\n")

print("Adding more keys to the store after reload...\n")
store.put("key4", "value4")
store.put("key5", "value5")

print("Crashing here, snapshot not saved, but WAL has been updated with key4 and key5\n")

store = InMemoryStore()
store.load()

print("State Reloaded and store contains\n")
print(store._store)