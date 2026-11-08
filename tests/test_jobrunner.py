import io, json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import pytest
from BEA_JobRunner.config import load_config
from BEA_JobRunner.policy import JobError, validate
from BEA_JobRunner.runner import JobRunner
from BEA_JobRunner.audit import AuditLog
from BEA_JobRunner.trust import TrustStore


@pytest.fixture
def env(tmp_path):
    (tmp_path / "ok.py").write_text("print('hello'); print('INFO: noise')\n")
    (tmp_path / "slow.py").write_text("import time; time.sleep(30)\n")
    (tmp_path / "bea_jobrunner.json").write_text(json.dumps({"countdown": 0, "builtins": {"echo": [sys.executable, "-c", "print('b')"]}}))
    cfg = load_config(str(tmp_path / "bea_jobrunner.json"))
    return tmp_path, cfg


def job(cfg, name, **j):
    os.makedirs(cfg["inbox"], exist_ok=True)
    p = os.path.join(cfg["inbox"], name + ".json")
    json.dump(j, open(p, "w")); return p


def runner(cfg, answers):
    it = iter(answers)
    return JobRunner(cfg, prompt=lambda _: next(it), out=io.StringIO(), sleep=lambda s: None)


def outbox(cfg, jid):
    return json.load(open(os.path.join(cfg["outbox"], jid + ".json")))


def test_valid_plan(env):
    d, cfg = env
    p = validate({"script": "ok.py", "env": "system"}, cfg, "a")
    assert p.rel == "ok.py" and len(p.sha) == 64


@pytest.mark.parametrize("bad", [
    {"script": "../x.py", "env": "system"}, {"script": "/etc/passwd.py", "env": "system"},
    {"script": "ok.txt", "env": "system"}, {"script": "ok.py", "env": "nope"},
    {"script": "ok.py", "env": "system", "args": [["x"]]}, {"script": "ok.py", "env": "system", "timeout": -1},
    {"builtin": "rm"}, {"script": "missing.py", "env": "system"}])
def test_rejects(env, bad):
    with pytest.raises(JobError):
        validate(bad, env[1], "a")


def test_bad_id(env):
    with pytest.raises(JobError):
        validate({"builtin": "echo"}, env[1], "a/b")


def test_symlink_escape(env, tmp_path_factory):
    d, cfg = env
    outside = tmp_path_factory.mktemp("out"); (outside / "evil.py").write_text("print(1)")
    os.symlink(outside / "evil.py", d / "link.py")
    with pytest.raises(JobError):
        validate({"script": "link.py", "env": "system"}, cfg, "a")


def test_timeout_capped(env):
    assert validate({"builtin": "echo", "timeout": 99999}, env[1], "a").timeout == 600


def test_ask_declined_and_approved(env):
    d, cfg = env
    r = runner(cfg, ["n", "y"])
    r.process(job(cfg, "j1", script="ok.py", env="system"))
    assert outbox(cfg, "j1")["status"] == "declined"
    r.process(job(cfg, "j2", script="ok.py", env="system"))
    o = outbox(cfg, "j2"); assert o["status"] == "done" and o["exit_code"] == 0
    log = open(os.path.join(cfg["outbox"], "j2.log")).read()
    assert "hello" in log
    assert os.path.exists(os.path.join(cfg["inbox"], "j2.json.done"))


def test_trusted_mode_and_change_detection(env):
    d, cfg = env; cfg["mode"] = "trusted"
    r = runner(cfg, ["a"])
    r.process(job(cfg, "t1", script="ok.py", env="system"))
    r.process(job(cfg, "t2", script="ok.py", env="system"))      # no prompt: would StopIteration
    assert outbox(cfg, "t2")["status"] == "done"
    (d / "ok.py").write_text("print('changed')\n")
    r2 = runner(cfg, ["n"])
    r2.process(job(cfg, "t3", script="ok.py", env="system"))     # changed -> asks again
    assert outbox(cfg, "t3")["status"] == "declined"


def test_auto_only_for_listed(env):
    d, cfg = env; cfg["mode"] = "auto"; cfg["auto_scripts"] = ["ok.py"]
    r = runner(cfg, ["n"])
    r.process(job(cfg, "a1", script="ok.py", env="system"))
    assert outbox(cfg, "a1")["status"] == "done"
    r.process(job(cfg, "a2", script="slow.py", env="system"))    # not listed -> asks, answered n
    assert outbox(cfg, "a2")["status"] == "declined"


def test_builtin_never_takes_args(env):
    d, cfg = env; cfg["mode"] = "trusted"
    r = runner(cfg, [])
    r.process(job(cfg, "b1", builtin="echo", args=["; rm -rf /"]))
    assert outbox(cfg, "b1")["exit_code"] == 0


def test_timeout_kills(env):
    d, cfg = env
    r = runner(cfg, ["y"])
    t = time.time()
    r.process(job(cfg, "s1", script="slow.py", env="system", timeout=1))
    assert outbox(cfg, "s1")["exit_code"] == -9 and time.time() - t < 10


def test_rejected_job_gets_outbox(env):
    d, cfg = env
    runner(cfg, []).process(job(cfg, "r1", script="../nope.py", env="system"))
    assert outbox(cfg, "r1")["status"] == "rejected"


def test_noise_filtered_on_screen_not_in_log(env):
    d, cfg = env
    r = runner(cfg, ["y"]); r.process(job(cfg, "n1", script="ok.py", env="system"))
    assert "INFO: noise" not in r.out.getvalue()
    assert "INFO: noise" in open(os.path.join(cfg["outbox"], "n1.log")).read()


def test_audit_chain_and_tamper(env):
    d, cfg = env
    r = runner(cfg, ["y"]); r.process(job(cfg, "c1", script="ok.py", env="system"))
    a = AuditLog(cfg["audit"]); ok, n, _ = a.verify(); assert ok and n == 2
    lines = open(cfg["audit"]).read().splitlines()
    lines[0] = lines[0].replace("approved", "xxxxxxxx")
    open(cfg["audit"], "w").write("\n".join(lines) + "\n")
    ok, _, bad = a.verify(); assert not ok and bad is not None


def test_trust_roundtrip(env):
    d, cfg = env
    p = validate({"script": "ok.py", "env": "system"}, cfg, "a")
    t = TrustStore(cfg["trust_file"]); t.add(p)
    assert TrustStore(cfg["trust_file"]).has(p)
    t.clear(); assert not TrustStore(cfg["trust_file"]).has(p)


def test_unknown_config_key(tmp_path):
    (tmp_path / "c.json").write_text('{"bogus": 1}')
    with pytest.raises(ValueError):
        load_config(str(tmp_path / "c.json"))
