# BEA_JobRunner (Linux)

**A human-approved mailbox that lets an AI assistant run scripts on your machine, and nothing else.**

The assistant drops a small JSON "job" file in `jobs/inbox/`. The runner shows you exactly what it wants to run, you press **y** or **n**, and the output goes back to `jobs/outbox/` for the assistant to read. No open ports, no cloud access to your machine, no shell.

## Quick start
```
cd <your project>
PYTHONPATH=<folder containing BEA_JobRunner> python3 -m BEA_JobRunner init   # writes bea_jobrunner.json
# edit it: interpreters (envs) and read-only built-ins
python3 -m BEA_JobRunner run
```
Leave the window open. When a job arrives you see its script, a size+hash fingerprint, and a time limit. Answer `y` to run, anything else to skip. Ctrl-C stops a running job; Ctrl-C when idle quits.

## Job file (`jobs/inbox/<id>.json`)
```
{"id":"x","script":"devmesh/gpu_hand_probe.py","env":"gpu","args":["--n","50"],"timeout":120,"hint":"why this is being run"}
{"builtin":"gpu_status"}
```
Results: `jobs/outbox/<id>.json` (status, exit code, seconds) and `<id>.log` (full output). The job file is renamed `.done` afterwards.

## What a job can and cannot do
- Run a `.py` file that is **inside the root folder** (symlinks resolved; `..` and absolute paths rejected).
- Use only interpreters you named in `envs`. Pass only string/number arguments. No shell is ever involved.
- `builtins` are fixed commands you define; a job cannot add arguments to them.
- Time limit is capped by `max_timeout` (600 s); output capped by `max_output`.

## Modes
| mode | behaviour |
|---|---|
| `ask` (default) | prompts for every job |
| `trusted` | built-ins run silently; scripts prompt `y / a / n`. `a` = always run this exact version (stored as path+env+sha256). Edit one byte and it asks again. |
| `auto` | no prompt only for built-ins and scripts matching `auto_scripts` globs; everything else still prompts |

`python -m BEA_JobRunner trust-list` / `trust-clear` manage the trust store.

## Audit log
`jobs/audit.jsonl` records every job seen, decision, run and exit code. Each line includes the hash of the previous line, so edits or deletions are detectable: `python -m BEA_JobRunner verify-audit`. It is tamper-*evident*, not tamper-proof: someone with write access can rewrite the whole chain.

## Honest limits
- A job you approve runs with **your** user's permissions. The approval prompt is the safety feature; read what it shows. A script can do anything your user can.
- The fingerprint only helps if you compare it with what you expect; stale copies of a script are the usual cause of confusing results.
- The systemd unit is only sensible for `trusted`/`auto` with a narrow `auto_scripts` list; `ask` needs a terminal.

## Tests
`python3 -m pytest BEA_JobRunner/tests` (22 tests: path escape, symlinks, timeouts, trust change detection, audit tamper).

## Requirements
Linux, Python 3.8+, and no third-party dependencies (`pytest` only for the tests).

## Install
Copy or clone the `BEA_JobRunner` folder somewhere and put its **parent** folder on `PYTHONPATH`. There is nothing to build.

## Contributing
Issues and pull requests are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md). Report security problems privately, not in public issues.

## License
Released under the [MIT License](LICENSE).

Copyright (c) 2026 Jeremy Frank Jackson dba BEATEK.
