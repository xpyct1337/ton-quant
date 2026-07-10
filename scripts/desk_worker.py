#!/usr/bin/env python3
"""TON Quant v3.0 — 24/7 desk worker (KeepAlive daemon).

Continuous loop on the M1 Air: governor decides run-vs-sleep (AC-only heavy work,
back off when thermally throttled), picker selects the due task, committer batches
data/desk/ pushes to main. The LLM never idles: between the ~7-min daily run and the
deterministic calibration it does ensemble deep-vetting for higher-confidence verdicts.

Fault-tolerant: every task runs in try/except; the loop never dies (KeepAlive also
restarts on crash). Run: python3 scripts/desk_worker.py   (one pass: --once)
stdlib + urllib only.
"""
import json, os, sys, time, subprocess, datetime, glob, urllib.request  # noqa: F401

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_features import load, build_features  # noqa: E402
import desk                                     # noqa: E402
import desk_calibration                         # noqa: E402
import desk_researcher                          # noqa: E402
import desk_copytrade                            # noqa: E402
import desk_deployers                            # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = "data/desk/worker_state.json"
COMMIT_EVERY = 12 * 3600     # batch background work twice daily; daily verdicts force-push
CALIB_EVERY = 6 * 3600       # recompute calibration at most this often
REVALIDATE_EVERY = 12 * 3600  # re-validate active factors at most this often
BASE_SLEEP = 20              # cooling pause between tasks when healthy


# ---------- governor ----------
def _pmset(arg):
    try:
        return subprocess.run(["pmset", "-g", arg], capture_output=True,
                              text=True, timeout=10).stdout
    except Exception:
        return ""


def power_state():
    """(on_ac, speed_limit%). Defaults to safe (AC, 100) if pmset unreadable."""
    batt = _pmset("batt")
    on_ac = ("AC Power" in batt) or (batt == "")
    speed = 100
    for line in _pmset("therm").splitlines():
        if "CPU_Speed_Limit" in line:
            try:
                speed = int(line.split("=")[1].strip())
            except Exception:
                pass
    return on_ac, speed


def thermal_decision(on_ac, speed_limit):
    if not on_ac:
        return {"run": False, "sleep": 300}          # on battery: idle, recheck in 5m
    if speed_limit < 80:
        return {"run": True, "sleep": 90}            # throttled: work but cool longer
    return {"run": True, "sleep": BASE_SLEEP}


def ensure_osaurus():
    """Start Osaurus if the LLM server isn't responding. The daemon is long-lived
    (unlike the old cron-based desk_run.sh, which re-checked on every fresh
    invocation) — Osaurus can crash or a cold boot can arrive with it not running,
    so every iteration re-checks rather than assuming it stays up forever."""
    try:
        urllib.request.urlopen("http://localhost:1337/v1/models", timeout=3)
        return True
    except Exception:                                 # noqa: BLE001
        pass
    try:
        subprocess.Popen(["osaurus", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:                                 # noqa: BLE001
        return False
    for _ in range(15):
        time.sleep(2)
        try:
            urllib.request.urlopen("http://localhost:1337/v1/models", timeout=3)
            return True
        except Exception:                             # noqa: BLE001
            continue
    return False


# ---------- state ----------
def get_state():
    return load(STATE, {"deep_cursor": 0, "last_calib": 0, "last_commit": 0,
                        "last_research_date": ""})


def put_state(s):
    os.makedirs("data/desk", exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(s, f, indent=2)


def today():
    return datetime.date.today().isoformat()


def data_date():
    """Date of the latest data the desk actually has (wallets.json's own date),
    NOT the system clock. If the cloud collector lags or fails for a day, the
    system date and the data date diverge — checking against today() would make
    'today_done' never become true, re-running the full LLM pass every single
    iteration forever until the cloud catches up (observed live: 59 full reruns
    in one stalled day). Falls back to today() only if wallets.json is unreadable."""
    return load("data/wallets.json", {}).get("date") or today()


# ---------- picker ----------
def pick_task(today_done, calib_stale, deep_pending, revalidate_due=False, research_due=False):
    if not today_done:
        return "daily_verdicts"
    if calib_stale:
        return "calibrate"
    if revalidate_due:
        return "revalidate"
    if deep_pending > 0:
        return "deep_vetting"
    return "research" if research_due else "idle"


# ---------- task runners (each tolerant; return short status) ----------
def run_daily_verdicts():
    desk.main()                                       # writes latest + journal
    return "daily_verdicts done"


def run_calibrate(state):
    desk_calibration.main()
    desk_copytrade.main()                  # deterministic analytics, same cadence
    desk_deployers.main()                  # deployer repeat-offender registry
    state["last_calib"] = int(time.time())
    return "calibrate+copytrade+deployers done"


def run_revalidate(state):
    state["last_revalidate"] = int(time.time())
    return desk_researcher.revalidate()


def run_research(state):
    # ponytail: one pre-registered candidate per new data date; point-in-time
    # verdicts still accumulate, but the LLM cannot burn hundreds of trials overnight.
    state["last_research_date"] = data_date()
    return desk_researcher.research_once()


def run_deep_vetting(state):
    """One entity per call (duty-cycle): ensemble re-vet, raise verdict confidence.

    Runs agent1 3x and keeps the worst (max) risk + records vote stability into the
    latest verdicts.json. Cursor walks the token list, then wraps."""
    v = load("data/desk/verdicts.json", None)
    if not v or not v.get("tokens"):
        return "deep_vetting: no verdicts yet"
    feats = {t["sym"]: t for t in build_features()["tokens"]}
    toks = v["tokens"]
    i = state.get("deep_cursor", 0) % len(toks)
    t = toks[i]
    f = feats.get(t["sym"])
    if f:
        order = {"low": 0, "med": 1, "high": 2}
        votes = [desk.agent1(v.get("model", "qwen3-4b-4bit"), f, is_token=True)
                 for _ in range(3)]
        worst = max(votes, key=lambda x: order[x["manip_risk"]])
        risks = [x["manip_risk"] for x in votes]
        t.update(manip_risk=worst["manip_risk"], flags=worst["flags"],
                 reason=worst["reason"],
                 ensemble={"votes": risks, "stable": len(set(risks)) == 1})
        for path in ("data/desk/verdicts.json",
                     f"data/desk/verdicts/{v.get('date', today())}.json"):
            with open(path, "w") as fo:
                json.dump(v, fo, ensure_ascii=False, indent=2)
    state["deep_cursor"] = i + 1
    return f"deep_vetting {t['sym']} ({i + 1}/{len(toks)})"


# ---------- committer ----------
def maybe_commit(state, force=False):
    if not force and time.time() - state.get("last_commit", 0) < COMMIT_EVERY:
        return
    if not subprocess.run(["git", "status", "--porcelain", "data/desk"],
                          capture_output=True, text=True).stdout.strip():
        return
    for _ in range(3):                                 # retry on concurrent-push reject
        subprocess.run(["git", "pull", "--rebase", "--autostash", "origin", "main"])
        subprocess.run(["git", "add", "data/desk"])    # scoped: never touch app/ or root
        subprocess.run(["git", "commit", "-m", f"worker: {today()} update"])
        if subprocess.run(["git", "push", "origin", "main"]).returncode == 0:
            break
    state["last_commit"] = int(time.time())


# ---------- loop ----------
def iterate():
    """One full iteration. Returns the sleep (seconds) the caller should honor."""
    os.chdir(REPO)
    on_ac, speed = power_state()
    dec = thermal_decision(on_ac, speed)
    if not dec["run"]:
        print(f"governor: idle (ac={on_ac} speed={speed})", flush=True)
        return dec["sleep"]
    if not ensure_osaurus():
        print("osaurus unreachable and failed to start; skipping this cycle", flush=True)
        return dec["sleep"]
    state = get_state()
    today_done = os.path.exists(f"data/desk/verdicts/{data_date()}.json")
    calib_stale = time.time() - state.get("last_calib", 0) > CALIB_EVERY
    revalidate_due = time.time() - state.get("last_revalidate", 0) > REVALIDATE_EVERY
    v = load("data/desk/verdicts.json", {})           # un-vetted this cycle -> 0 lets research run
    deep_pending = sum(1 for t in v.get("tokens", []) if "ensemble" not in t) if today_done else 0
    research_due = state.get("last_research_date") != data_date()
    task = pick_task(today_done, calib_stale, deep_pending, revalidate_due, research_due)
    try:
        if task == "daily_verdicts":
            msg = run_daily_verdicts()
        elif task == "calibrate":
            msg = run_calibrate(state)
        elif task == "revalidate":
            msg = run_revalidate(state)
        elif task == "deep_vetting":
            msg = run_deep_vetting(state)
        elif task == "research":
            msg = run_research(state)
        else:
            msg = "idle: nothing due"
    except Exception as e:                             # noqa: BLE001 — never crash loop
        msg = f"task {task} errored (tolerated): {type(e).__name__}: {e}"
    print(f"{datetime.datetime.now().isoformat(timespec='seconds')} [{task}] {msg}",
          flush=True)
    maybe_commit(state, force=task == "daily_verdicts")
    put_state(state)
    return dec["sleep"]


def main():
    once = "--once" in sys.argv
    while True:
        s = iterate()
        if once:
            break
        time.sleep(s)


if __name__ == "__main__":
    main()
