
import os
from pathlib import Path
import pickle
import threading

class WAL:

    def __init__(self,path="data/wal.log"):
        self._path = Path(path)
        self._lock = threading.Lock()
        self.offset = 1
        self._offset_initialized = False

    def _ensure_offset(self):
        if self._offset_initialized:
            return

        if self._path.exists():
            with self._path.open("rb") as file:
                record_offset = 0
                while True:
                    try:
                        task = pickle.load(file)
                    except EOFError:
                        break

                    record_offset += 1
                    task_offset = task.get("offset", record_offset)
                    if not isinstance(task_offset, int) or task_offset < 1:
                        raise ValueError("WAL record has an invalid offset")
                    self.offset = max(self.offset, task_offset + 1)

        self._offset_initialized = True

    def append(self,key,value,expiry,operation):
        with self._lock:
            self._ensure_offset()
            task = {
                "offset": self.offset,
                "operation": operation,
                "key": key,
                "value": value,
                "expiry": expiry,
            }

            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("ab") as file:
                pickle.dump(task, file)
                file.flush()
                os.fsync(file.fileno())

            self.offset += 1

    def get_offset(self):
        with self._lock:
            self._ensure_offset()
            return self.offset - 1

    def replay(self, after_offset=0):
        with self._lock:
            self._ensure_offset()
            if not self._path.exists():
                return

            with self._path.open("rb") as file:
                record_offset = 0
                while True:
                    try:
                        task = pickle.load(file)
                    except EOFError:
                        break

                    record_offset += 1
                    task_offset = task.get("offset", record_offset)
                    if not isinstance(task_offset, int) or task_offset < 1:
                        raise ValueError("WAL record has an invalid offset")

                    self.offset = max(self.offset, task_offset + 1)
                    if task_offset > after_offset:
                        yield task
        
        

