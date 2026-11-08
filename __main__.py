# Copyright (c) 2026 Jeremy Frank Jackson dba BEATEK
# Licensed under the MIT License.
"""python -m BEA_JobRunner  run | init | verify-audit | trust-list | trust-clear | show-config"""
import argparse
import json
import os
import sys

from . import __version__
from .audit import AuditLog
from .config import DEFAULTS, load_config
from .runner import JobRunner
from .trust import TrustStore

EXAMPLE = {"root": ".", "envs": {"system": "@system", "gpu": "~/bea_gpu_env/bin/python"},
           "builtins": {"gpu_status": ["rocm-smi", "--showuse", "--showmemuse", "--showtemp"]},
           "mode": "ask", "auto_scripts": [], "countdown": 3}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="BEA_JobRunner", description=__doc__)
    ap.add_argument("cmd", choices=["run", "init", "verify-audit", "trust-list", "trust-clear", "show-config"], nargs="?", default="run")
    ap.add_argument("--config", default=None, help="path to bea_jobrunner.json (default: ./bea_jobrunner.json if present)")
    ap.add_argument("--mode", choices=["ask", "trusted", "auto"], default=None); ap.add_argument("--countdown", type=int, default=None)
    ap.add_argument("--version", action="version", version=__version__)
    a = ap.parse_args(argv)
    if a.cmd == "init":
        if os.path.exists("bea_jobrunner.json"):
            raise SystemExit("bea_jobrunner.json already exists; not overwriting")
        with open("bea_jobrunner.json", "w") as f:
            json.dump(EXAMPLE, f, indent=2)
        print("wrote bea_jobrunner.json; edit the interpreters and built-ins, then: python -m BEA_JobRunner run"); return 0
    path = a.config or ("bea_jobrunner.json" if os.path.exists("bea_jobrunner.json") else None)
    cfg = load_config(path, {"mode": a.mode, "countdown": a.countdown})
    if a.cmd == "show-config":
        print(json.dumps(cfg, indent=2)); return 0
    if a.cmd == "verify-audit":
        ok, n, bad = AuditLog(cfg["audit"]).verify()
        print("audit log OK: %d entries, chain intact" % n if ok else "AUDIT LOG BROKEN at line %s (after %d good entries)" % (bad, n)); return 0 if ok else 1
    if a.cmd == "trust-list":
        for k in sorted(TrustStore(cfg["trust_file"]).items):
            print(k)
        return 0
    if a.cmd == "trust-clear":
        TrustStore(cfg["trust_file"]).clear(); print("trust store cleared"); return 0
    JobRunner(cfg).serve(); return 0


if __name__ == "__main__":
    sys.exit(main())
