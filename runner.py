# Copyright (c) 2026 Jeremy Frank Jackson dba BEATEK
# Licensed under the MIT License.
"""The runner: watches the inbox, asks the human (unless policy says otherwise), runs the job, streams its output, writes the outbox and the audit log."""
import json
import os
import subprocess
import sys
import threading
import time

from .audit import AuditLog
from .policy import JobError, validate
from .trust import TrustStore
import fnmatch


def run_plan(plan, cfg, out=sys.stdout):
    """Runs one validated plan. Output streams to `out` (noise filtered) and everything is returned for the log."""
    t0, lines, killed = time.time(), [], [False]
    p = subprocess.Popen(plan.argv, cwd=cfg["root"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace", bufsize=1)

    def watchdog():
        while p.poll() is None:
            if time.time() - t0 > plan.timeout:
                killed[0] = True; p.kill(); return
            time.sleep(0.2)
    threading.Thread(target=watchdog, daemon=True).start()
    noise = tuple(cfg["noise_prefixes"])
    try:
        for line in p.stdout:
            lines.append(line)
            if not line.startswith(noise):
                out.write("   | " + line); out.flush()
        p.wait()
        code = -9 if killed[0] else p.returncode
        if killed[0]:
            lines.append("TIMEOUT after %.0f s\n" % plan.timeout)
    except KeyboardInterrupt:
        p.kill(); p.wait(); code = -2; lines.append("INTERRUPTED by the human at the runner terminal\n")
        out.write("\n   job stopped (Ctrl-C)\n")
    text, cap = "".join(lines), cfg["max_output"]
    if len(text) > cap:
        text = text[:cap // 2] + "\n...[truncated]...\n" + text[-cap // 2:]
    return code, text, time.time() - t0


class JobRunner:
    def __init__(self, cfg, prompt=input, out=sys.stdout, sleep=time.sleep):
        self.cfg, self.prompt, self.out, self.sleep = cfg, prompt, out, sleep
        self.trust, self.audit = TrustStore(cfg["trust_file"]), AuditLog(cfg["audit"])
        for d in (cfg["inbox"], cfg["outbox"]):
            os.makedirs(d, exist_ok=True)

    def say(self, s=""):
        self.out.write(s + "\n"); self.out.flush()

    def _ask(self, text):
        try:
            return self.prompt(text).strip().lower()
        except EOFError:
            return ""

    def decide(self, plan):
        """Returns (run: bool, how: str). The human's answer is the real gate; policy only decides when we may skip asking."""
        mode = self.cfg["mode"]
        if mode == "auto":
            if plan.builtin or any(fnmatch.fnmatch(plan.rel, g) for g in self.cfg["auto_scripts"]):
                return True, "auto"
        elif mode == "trusted":
            if plan.builtin or self.trust.has(plan):
                return True, "trusted"
        opts = "[y = run once, a = always run THIS version, anything else = skip]  " if mode == "trusted" and plan.script else "[y = run, anything else = skip]  "
        ans = self._ask("   run it?  " + opts)
        if ans == "a" and mode == "trusted" and plan.script:
            self.trust.add(plan)
            return True, "approved-and-trusted"
        return ans in ("y", "a"), "approved" if ans in ("y", "a") else "declined"

    def _write(self, jid, res, log_text=None):
        if log_text is not None:
            with open(os.path.join(self.cfg["outbox"], jid + ".log"), "w") as f:
                f.write(log_text)
        with open(os.path.join(self.cfg["outbox"], jid + ".json"), "w") as f:
            json.dump(res, f)

    def process(self, path):
        jid = os.path.splitext(os.path.basename(path))[0]
        try:
            with open(path) as f:
                job = json.load(f)
            plan = validate(job, self.cfg, jid)
        except (JobError, OSError, ValueError) as e:
            self.say("\n\a[rejected] %s: %s" % (jid, e))
            self.audit.append("rejected", job=jid, reason=str(e))
            self._write(jid, {"id": jid, "status": "rejected", "reason": str(e)})
            os.replace(path, path + ".done")
            return
        self.say("\n\a" + "=" * 70 + "\nNEW JOB  %s\n   runs: %s\n   %s   (time limit %.0f s)   mode: %s" % (jid, " ".join(plan.argv), plan.fingerprint(), plan.timeout, self.cfg["mode"]))
        if plan.hint:
            self.say("   note: %s" % plan.hint)
        ok, how = self.decide(plan)
        base = dict(job=jid, argv=plan.argv, script=plan.rel, sha=plan.sha, decision=how)
        if not ok:
            self.say("   skipped.")
            self.audit.append("declined", **base)
            self._write(jid, {"id": jid, "status": "declined"})
        else:
            if how in ("auto", "trusted"):
                self.say("   (%s by policy)" % how)
            for i in range(int(self.cfg["countdown"]), 0, -1):
                self.out.write("   starting in %d ...   \r" % i); self.out.flush(); self.sleep(1)
            self.audit.append("run", **base)
            self.say("   running ...")
            code, text, dt = run_plan(plan, self.cfg, self.out)
            self.audit.append("done", job=jid, exit_code=code, seconds=round(dt, 1))
            self._write(jid, {"id": jid, "status": "done", "exit_code": code, "seconds": round(dt, 1), "log": jid + ".log", "script": plan.fingerprint()}, text)
            self.say("   finished: exit %s in %.1f s. The output is saved for the assistant." % (code, dt))
        os.replace(path, path + ".done")

    @staticmethod
    def _stable(path, wait=0.6):
        try:
            a = os.path.getsize(path); time.sleep(wait)
            return a > 0 and a == os.path.getsize(path)
        except OSError:
            return False

    def poll_once(self):
        n = 0
        for name in sorted(f for f in os.listdir(self.cfg["inbox"]) if f.endswith(".json")):
            full = os.path.join(self.cfg["inbox"], name)
            if self._stable(full):
                self.process(full); n += 1
        return n

    def serve(self):
        self.say("BEA_JobRunner. Watching: %s\nMode: %s. Leave this window open; it only acts when your assistant sends a job. Ctrl-C to quit." % (self.cfg["inbox"], self.cfg["mode"]))
        done, spin, t_start = 0, "|/-\\", time.time()
        self.audit.append("start", mode=self.cfg["mode"], root=self.cfg["root"])
        try:
            while True:
                n = self.poll_once(); done += n
                if not n:
                    self.out.write("\r  idle, waiting for jobs %s  (up %d min, %d handled)   " % (spin[int(time.time() * 2) % 4], (time.time() - t_start) // 60, done)); self.out.flush()
                    self.sleep(0.5)
        except KeyboardInterrupt:
            self.say("\nstopped"); self.audit.append("stop", handled=done)
