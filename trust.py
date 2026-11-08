# Copyright (c) 2026 Jeremy Frank Jackson dba BEATEK
# Licensed under the MIT License.
"""Trust store: 'always run THIS exact version of this script'. Change one byte of the script and it asks again."""
import json
import os


class TrustStore:
    def __init__(self, path):
        self.path = path
        self.items = set()
        if os.path.exists(path):
            try:
                with open(path) as f:
                    self.items = set(json.load(f))
            except (OSError, ValueError):
                self.items = set()

    @staticmethod
    def key(plan):
        return "%s|%s|%s" % (plan.rel, plan.env, plan.sha)

    def has(self, plan):
        return bool(plan.script) and self.key(plan) in self.items

    def add(self, plan):
        self.items.add(self.key(plan)); self._save()

    def clear(self):
        self.items = set(); self._save()

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(sorted(self.items), f, indent=1)
        os.replace(tmp, self.path)
