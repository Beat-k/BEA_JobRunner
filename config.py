# Copyright (c) 2026 Jeremy Frank Jackson dba BEATEK
# Licensed under the MIT License.
"""Configuration: one JSON file decides what may run. Paths in it are relative to the file, '~' is expanded, and "@system" means the python running the runner."""
import copy
import json
import os
import sys

DEFAULTS = {
    "root": ".",                       # scripts must live inside this folder
    "inbox": "jobs/inbox", "outbox": "jobs/outbox",
    "audit": "jobs/audit.jsonl", "trust_file": "jobs/trusted.json",
    "envs": {"system": "@system"},     # name -> python interpreter a job may ask for
    "builtins": {},                    # name -> fixed argv list (read-only diagnostics you define; jobs cannot add arguments)
    "mode": "ask",                     # ask: prompt for every job | trusted: prompt only for new/changed scripts | auto: never prompt for auto_scripts
    "auto_scripts": [],                # globs (relative to root) that mode=auto may run without asking
    "max_timeout": 600, "max_output": 200000, "countdown": 3,
    "noise_prefixes": ["W0000", "I0000", "INFO:", "WARNING: Logging", "MIOpen(", "warning: xnack"],
}
MODES = ("ask", "trusted", "auto")


def _expand(p, base):
    if p == "@system":
        return sys.executable
    p = os.path.expanduser(p)
    return p if os.path.isabs(p) else os.path.realpath(os.path.join(base, p)) if os.sep in p or p.startswith(".") else p


def load_config(path=None, overrides=None):
    cfg = copy.deepcopy(DEFAULTS)
    base = os.getcwd()
    if path:
        base = os.path.dirname(os.path.realpath(path))
        with open(path) as f:
            user = json.load(f)
        unknown = set(user) - set(DEFAULTS)
        if unknown:
            raise ValueError("unknown config keys: %s" % sorted(unknown))
        cfg.update(user)
    cfg.update({k: v for k, v in (overrides or {}).items() if v is not None})
    if cfg["mode"] not in MODES:
        raise ValueError("mode must be one of %s" % (MODES,))
    cfg["root"] = os.path.realpath(os.path.join(base, os.path.expanduser(cfg["root"])))
    for k in ("inbox", "outbox", "audit", "trust_file"):
        cfg[k] = os.path.realpath(os.path.join(cfg["root"], cfg[k]))
    cfg["envs"] = {k: _expand(v, base) for k, v in cfg["envs"].items()}
    cfg["builtins"] = {k: [_expand(x, base) if i == 0 else x for i, x in enumerate(v)] for k, v in cfg["builtins"].items()}
    return cfg
