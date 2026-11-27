from datastore import InMemoryStore

class StoreHandler:
    def get_value(self, store:InMemoryStore , key: str):
        val = store.get(key)
        print(val)
        return val

    def put_value(self, store:InMemoryStore, key: str, value: str, expiry: int | None = None):
        store.put(key, value, ttl=expiry)

    def delete_value(self, store:InMemoryStore, key: str):
        store.delete(key)
