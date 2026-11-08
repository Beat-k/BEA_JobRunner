# Copyright (c) 2026 Jeremy Frank Jackson dba BEATEK
# Licensed under the MIT License.
"""Tamper-evident audit log: one JSON line per event; each line carries the sha256 of the line before it, so editing or deleting history breaks the chain."""
import hashlib
import json
import os
import time


class AuditLog:
    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def _last_hash(self):
        if not os.path.exists(self.path):
            return "0" * 64
        last = b""
        with open(self.path, "rb") as f:
            for line in f:
                if line.strip():
                    last = line.rstrip(b"\n")
        return hashlib.sha256(last).hexdigest() if last else "0" * 64

    def append(self, event, **fields):
        rec = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "event": event, "prev": self._last_hash()}
        rec.update(fields)
        with open(self.path, "a") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")

    def verify(self):
        """Returns (ok, lines_checked, first_bad_line_number_or_None)."""
        prev, n = "0" * 64, 0
        if not os.path.exists(self.path):
            return True, 0, None
        with open(self.path, "rb") as f:
            for i, line in enumerate(f, 1):
                line = line.rstrip(b"\n")
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    return False, n, i
                if rec.get("prev") != prev:
                    return False, n, i
                prev, n = hashlib.sha256(line).hexdigest(), n + 1
        return True, n, None
