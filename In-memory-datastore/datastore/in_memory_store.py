
import os
import pickle
import threading
import time
from pathlib import Path

from .wal import WAL
from .lru import LRU, Node

class Store:
    value: any
    timestamp: float
    Node: Node

class InMemoryStore:

    def __init__(
        self,
        snapshot_path="data/snapshots/data.pkl",
        wal_path="data/wal.log",
    ):

        self._store: dict[str, Store] = {}
        self._lru = LRU()
        self._lock = threading.RLock()
        self._snapshot_path = Path(snapshot_path)
        self.wal = WAL(wal_path)

        self.MAX_CAPACITY = 20
        self.default_ttl = 60

    def get(self, key):
        with self._lock:
            data = self._store.get(key)
            if data is None:
                return None

            if time.monotonic() > data["timestamp"]:
                self._delete_without_lock(key)
                return None

            self._lru.update(data["Node"])
            return data["value"]

    def put(self, key, value, ttl=None):
        with self._lock:
            expiry = time.monotonic() + (ttl if ttl is not None else self.default_ttl)
            self.wal.append(key, value, expiry, "put")
            self._apply_put_without_wal(key, value, expiry)

    def _apply_put_without_wal(self, key, value, expiry):
        if key in self._store:
            node = self._store[key]["Node"]
            self._lru.update(node)
            self._store[key]["value"] = value
            self._store[key]["timestamp"] = expiry
            return

        if len(self._store) >= self.MAX_CAPACITY:
            evicted_node = self._lru.evict()
            if evicted_node is not None:
                del self._store[evicted_node.value]

        node: Node = self._lru.add(key)
        self._store[key] = {
            "value": value,
            "timestamp": expiry,
            "Node": node,
        }

    def delete(self, key):
        with self._lock:
            self.wal.append(key, None, 0, "delete")
            self._delete_without_lock(key)

    def _delete_without_lock(self, key):
        data = self._store.get(key)
        if data is None:
            return

        self._lru.delete(data["Node"])
        del self._store[key]
    

    def save(self):
        with self._lock:
            now = time.monotonic()
            snapshot_store = {
                "version": 1,
                "lru": self._lru.get_list(),
                "wal_offset": self.wal.get_offset(),
                "store": {
                    key: {
                        "value": data["value"],
                        "remaining_ttl": data["timestamp"] - now,
                    }
                    for key, data in self._store.items()
                },
            }

            self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = self._snapshot_path.with_suffix(
                self._snapshot_path.suffix + ".tmp"
            )
            with temporary_path.open("wb") as file:
                pickle.dump(snapshot_store, file)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary_path, self._snapshot_path)

            print(f"Snapshot saved to {self._snapshot_path} with {len(self._store)} entries at offset {self.wal.get_offset()}")


    def load(self):
        with self._lock:
            offset = 0
            if self._snapshot_path.exists():
                with self._snapshot_path.open("rb") as file:
                    snapshot = pickle.load(file)

                now = time.monotonic()
                loaded_store = {}
                loaded_lru = LRU()
                offset = snapshot.get("wal_offset", 0)

                # add() inserts at the head, so restore the saved head-to-tail
                # order in reverse.
                for key in reversed(snapshot["lru"]):
                    entry = snapshot["store"].get(key)
                    if entry is None or entry["remaining_ttl"] <= 0:
                        continue

                    node = loaded_lru.add(key)
                    loaded_store[key] = {
                        "value": entry["value"],
                        "timestamp": now + entry["remaining_ttl"],
                        "Node": node,
                    }

                self._store = loaded_store
                self._lru = loaded_lru

            for task in self.wal.replay(after_offset=offset):
                print(f"Replaying WAL task: {task} with offset {task['offset']}")
                if task["operation"] == "put":
                    self._apply_put_without_wal(
                        task["key"], task["value"], task["expiry"]
                    )
                elif task["operation"] == "delete":
                    self._delete_without_lock(task["key"])
                else:
                    raise ValueError(
                        f"Unknown WAL operation: {task['operation']}"
                    )
        

    
