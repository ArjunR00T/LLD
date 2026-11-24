
import os
from pathlib import Path
import pickle
import threading
import time

from datastore.in_memory_store import InMemoryStore

class WAL:

    def __init__(self,path="data/wal.log"):
        self._path = Path(path)
        self._lock = threading.Lock()
        self.log = {}
        self.offset = 1
        self._store = InMemoryStore()


    def append(self,key,value,expiry,operation):

        task = {
            "operation" : operation,
            "key": key,
            "value": value,
            "expiry": expiry
        }

        self.log[self.offset] = task
        self.offset += 1

        _temp_path = self._path.with_suffix(".tmp")

        with open(_temp_path, "ab") as f:
            pickle.dump(task, f)
            f.flush()
            os.filesync(f.fileno())

        os.replace(_temp_path, self._path)

    def replay(self):

        if not self._path.exists():
            return

        with open(self._path, "rb") as f:
            events = pickle.load(f)

        for event in events:
            operation = event["operation"]
            key = event["key"]
            value = event["value"]
            expiry = event["expiry"]

            if operation == "put":
                self._store.put(key, value, expiry)
            elif operation == "delete":
                self._store.delete(key)
            

        


        
        

