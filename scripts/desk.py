#!/usr/bin/env python3
"""TON Quant v3.0 — AI Smart-Money Desk runtime (spec §7).

Reads deterministic features (desk_features.build_features), runs two LLM agents
SEQUENTIALLY against a local OpenAI-compatible LLM server (Osaurus / Apple-MLX on
:1337 by default; Ollama :11434/v1 also works) — one model resident at a time,
agents never co-loaded (8 GB M1 Air) — writes data/desk/verdicts.json (schema §5).

Fault-tolerant by design: a failed LLM call falls back to the deterministic floor
verdict; the run NEVER crashes (like `xs_forward || true`). Deterministic floors
are the hard gate (wash-ban -> high); the LLM only synthesizes/raises and writes
the reason — it can never lower risk below the floor or copy a high-risk wallet.

Agent 1 (manipulation):  features            -> {manip_risk, flags, reason}
Agent 2 (vetting):       history + agent-1   -> {copy_ok, conviction, reason}
  copy_ok is forced False when manip_risk=high or the edge rests on a thin sample
  (positive edge on few names) — the imitation-penalty cure.

Config: data/desk/config.json {"model","wallet_limit"} (env DESK_MODEL / DESK_LIMIT
override). Run from repo root:  python3 scripts/desk.py
stdlib + urllib only (no requests dependency).
"""
import json, os, sys, time, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desk_features import build_features, load  # noqa: E402
import desk_factors  # noqa: E402

# OpenAI-compatible chat endpoint — works for Osaurus (:1337, MLX, default) AND
# Ollama (:11434/v1/chat/completions). Switch backend via DESK_ENDPOINT / config.
ENDPOINT = os.environ.get("DESK_ENDPOINT", "http://localhost:1337/v1/chat/completions")
RISK_ORD = {"low": 0, "med": 1, "high": 2}


# ---------- LLM client (OpenAI-compatible) ----------
def llm(model, system, user, timeout=120, retries=2):
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user + " /no_think"}],  # Qwen3: no thinking
        "response_format": {"type": "json_object"},
        "temperature": 0, "max_tokens": 300,
    }
    data = json.dumps(body).encode()
    last = None
    for _ in range(retries):
        try:
            req = urllib.request.Request(
                ENDPOINT, data=data, headers={"Content-Type": "application/json"})
            r = json.load(urllib.request.urlopen(req, timeout=timeout))
            return _extract_json(r["choices"][0]["message"]["content"])
        except Exception as e:                       # noqa: BLE001 — never crash the run
            last = e
    raise RuntimeError(f"llm failed: {last}")


def _extract_json(txt):
    """Robust to gemma3's chatter around the JSON."""
    txt = (txt or "").strip()
    try:
        return json.loads(txt)
    except Exception:
        i, j = txt.find("{"), txt.rfind("}")
        if i >= 0 and j > i:
            return json.loads(txt[i:j + 1])
        raise


# ---------- deterministic floor (the hard gate) ----------
def floor_risk(f):
    wash = f.get("wash", 0)
    va = f.get("vol_auth", 1)
    ce = f.get("co_entry", 0)
    cc = f.get("conc", 0)
    if wash >= 0.5:
        return "high", "wash"                         # banned by wash detector
    if ce >= 0.5 and va <= 0.4:
        return "high", "coordinated_inauth"
    if va <= 0.25 or cc >= 0.8:
        return "med", "thin_liquidity"
    return "low", None


def _compact(f, is_token):
    keys = ("wash", "vol_auth", "conc") if is_token else \
           ("wash", "co_entry", "vol_auth", "conc", "edge_dispersion")
    return {k: f.get(k) for k in keys}


# ---------- Agent 1: manipulation analyst ----------
A1_SYS = (
    "You are a crypto manipulation analyst. You receive normalized 0..1 features. "
    "Higher wash, higher co_entry, LOWER vol_auth, higher conc => higher manipulation "
    "risk. Mark high when wash is high AND co_entry is high AND vol_auth is low. "
    'Reply ONLY with JSON: {"manip_risk":"low|med|high","flags":["wash"|"bundler"|'
    '"conceal"|...],"reason":"<=2 sentence chain-of-thought"}.')


def agent1(model, f, is_token):
    floor, fflag = floor_risk(f)
    try:
        out = llm(model, A1_SYS, "features: " + json.dumps(_compact(f, is_token)))
        risk = str(out.get("manip_risk", "low")).lower()
        if risk not in RISK_ORD:
            risk = "low"
        flags = [str(x) for x in (out.get("flags") or [])][:5]
        reason = str(out.get("reason", "")).strip()[:300]
    except Exception as e:                            # noqa: BLE001
        risk, flags, reason = "low", [], f"llm_unavailable ({type(e).__name__}); floor"
    if RISK_ORD[floor] > RISK_ORD[risk]:              # never below the floor
        risk = floor
    if fflag and fflag not in flags:
        flags = [fflag] + flags
    if is_token and f.get("fields"):                  # active learned factors can only RAISE
        frisk, fflags = desk_factors.apply_active(f["fields"])
        if RISK_ORD[frisk] > RISK_ORD[risk]:
            risk = frisk
        flags = flags + [x for x in fflags if x not in flags]
    return {"manip_risk": risk, "flags": flags[:5], "reason": reason or "deterministic floor"}


# ---------- Agent 2: smart-money vetting ----------
A2_SYS = (
    "You are a smart-money vetting analyst deciding if a wallet is safe to copy-trade. "
    "Refuse (copy_ok=false) when manipulation risk is high, or the edge rests on a thin "
    "sample (positive edge from very few names), or conviction is weak. Reward consistent "
    "edge across many names. "
    'Reply ONLY with JSON: {"copy_ok":true|false,"conviction":0.0-1.0,'
    '"reason":"<=2 sentence chain-of-thought"}.')


def agent2(model, w, v1):
    hard_block = v1["manip_risk"] == "high"
    thin = (w.get("ne") or 0) <= 2 and (w.get("edge") or 0) > 0
    user = json.dumps({
        "conv": w.get("conv"), "edge": w.get("edge"), "win": w.get("win"),
        "ne": w.get("ne"), "edge_dispersion": w.get("edge_dispersion"),
        "manip_risk": v1["manip_risk"], "flags": v1["flags"],
    })
    try:
        out = llm(model, A2_SYS, user)
        copy_ok = bool(out.get("copy_ok", False))
        conv = max(0.0, min(1.0, float(out.get("conviction", 0) or 0)))
        reason = str(out.get("reason", "")).strip()[:300]
    except Exception as e:                            # noqa: BLE001
        copy_ok, conv, reason = False, 0.0, f"llm_unavailable ({type(e).__name__}); floor"
    if hard_block or thin:                            # hard gate: imitation-penalty cure
        copy_ok = False
        if hard_block:
            conv = min(conv, 0.1)
            reason = reason or "blocked: manip_risk=high"
        elif not reason:
            reason = "blocked: thin sample (high edge, few names)"
    return {"copy_ok": copy_ok, "conviction": round(conv, 3),
            "reason": reason or "no reason"}


# ---------- orchestration ----------
def main():
    global ENDPOINT
    cfg = load("data/desk/config.json", {}) or {}
    ENDPOINT = os.environ.get("DESK_ENDPOINT") or cfg.get("endpoint", ENDPOINT)
    model = os.environ.get("DESK_MODEL") or cfg.get("model", "qwen3-4b-4bit")
    lim = os.environ.get("DESK_LIMIT") or cfg.get("wallet_limit")
    lim = int(lim) if lim else None

    feats = build_features()
    wallets = feats["wallets"][:lim] if lim else feats["wallets"]
    tokens = feats["tokens"]
    print(f"desk: model={model} wallets={len(wallets)} tokens={len(tokens)} "
          f"date={feats['date']}", flush=True)

    wv = []
    for i, w in enumerate(wallets, 1):
        v1 = agent1(model, w, is_token=False)         # agents run sequentially per wallet
        v2 = agent2(model, w, v1)
        wv.append({"addr": w["addr"], "name": w.get("name"),
                   "manip_risk": v1["manip_risk"], "flags": v1["flags"],
                   "copy_ok": v2["copy_ok"], "conviction": v2["conviction"],
                   "reason": v2["reason"]})
        print(f"  [{i}/{len(wallets)}] {(w.get('name') or w['addr'][:12])}: "
              f"{v1['manip_risk']} copy_ok={v2['copy_ok']}", flush=True)

    tv = []
    for t in tokens:
        v1 = agent1(model, t, is_token=True)
        tv.append({"sym": t["sym"], "manip_risk": v1["manip_risk"],
                   "flags": v1["flags"], "reason": v1["reason"]})

    out = {"date": feats["date"], "model": model,
           "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "wallets": wv, "tokens": tv}
    os.makedirs("data/desk/verdicts", exist_ok=True)
    with open("data/desk/verdicts.json", "w") as f:           # latest (витрина reads this)
        json.dump(out, f, ensure_ascii=False, indent=2)
    jpath = f"data/desk/verdicts/{feats['date']}.json"        # dated journal (calibration)
    with open(jpath, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    chk = json.load(open(jpath))  # read-back the journal copy
    high = sum(1 for x in chk["wallets"] if x["manip_risk"] == "high")
    print(f"wrote data/desk/verdicts.json: {len(chk['wallets'])} wallets "
          f"({high} high-risk), {len(chk['tokens'])} tokens", flush=True)


if __name__ == "__main__":
    main()
