# Copyright (c) 2026 Jeremy Frank Jackson dba BEATEK
# Licensed under the MIT License.
"""Policy: decides whether a job file is allowed to run. Nothing here executes anything."""
import hashlib
import os
import re
from dataclasses import dataclass, field

ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class JobError(ValueError):
    pass


@dataclass
class Plan:
    id: str
    argv: list
    timeout: float
    env: str = ""
    script: str = ""              # absolute, resolved path (empty for builtins)
    rel: str = ""                 # path relative to root, as shown to the human
    sha: str = ""                 # sha256 of the script's contents at validation time
    size: int = 0
    builtin: str = ""
    hint: str = ""
    args: list = field(default_factory=list)

    def fingerprint(self):
        return "%d bytes, sha %s" % (self.size, self.sha[:8]) if self.script else "built-in command"


def validate(job, cfg, job_id):
    if not ID_RE.match(job_id or ""):
        raise JobError("bad job id (use letters, digits, _ . - only)")
    if not isinstance(job, dict):
        raise JobError("job must be a JSON object")
    try:
        timeout = min(float(job.get("timeout", 120)), float(cfg["max_timeout"]))
    except (TypeError, ValueError):
        raise JobError("timeout must be a number")
    if timeout <= 0:
        raise JobError("timeout must be positive")
    hint = str(job.get("hint", ""))[:300]
    if "builtin" in job:
        name = job["builtin"]
        if name not in cfg["builtins"]:
            raise JobError("unknown builtin %r" % (name,))
        return Plan(id=job_id, argv=list(cfg["builtins"][name]), timeout=timeout, builtin=name, hint=hint)
    env, script, args = job.get("env"), job.get("script"), job.get("args", [])
    if env not in cfg["envs"]:
        raise JobError("env must be one of %s" % sorted(cfg["envs"]))
    if not isinstance(script, str) or not script.endswith(".py") or os.path.isabs(script):
        raise JobError("script must be a relative .py path inside the root")
    root = cfg["root"]
    path = os.path.realpath(os.path.join(root, script))
    if os.path.commonpath([path, root]) != root or not os.path.isfile(path):
        raise JobError("script not found inside the root: %s" % script)
    interp = cfg["envs"][env]
    if not os.path.exists(interp) and not any(os.access(os.path.join(d, interp), os.X_OK) for d in os.environ.get("PATH", "").split(os.pathsep)):
        raise JobError("env %r has no interpreter at %s" % (env, interp))
    if not isinstance(args, list) or not all(isinstance(x, (str, int, float)) and not isinstance(x, bool) for x in args):
        raise JobError("args must be a list of strings or numbers")
    with open(path, "rb") as f:
        data = f.read()
    return Plan(id=job_id, argv=[interp, path] + [str(x) for x in args], timeout=timeout, env=env, script=path,
                rel=os.path.relpath(path, root), sha=hashlib.sha256(data).hexdigest(), size=len(data), hint=hint, args=[str(x) for x in args])
