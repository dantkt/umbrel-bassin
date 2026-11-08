#!/usr/bin/env python3
"""Backend du dashboard : lit les stats de ckpool-solo, suit le best share du jour, sert index.html.
Variables : CKPOOL_LOGS (défaut /logs), PORT (8080), STATE_FILE (state.json), MEMPOOL_URL (https://mempool.space)"""
import base64, functools, glob, json, os, re, time, urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

LOGS = os.environ.get("CKPOOL_LOGS", "/logs")
PORT = int(os.environ.get("PORT", "8080"))
STATE_FILE = os.environ.get("STATE_FILE", "state.json")
MEMPOOL = os.environ.get("MEMPOOL_URL", "https://mempool.space")
BTC_HOST, BTC_PORT = os.environ.get("BTC_HOST"), os.environ.get("BTC_PORT", "8332")
BTC_USER, BTC_PASS = os.environ.get("BTC_USER", ""), os.environ.get("BTC_PASS", "")

def rpc(method):
    req = urllib.request.Request(f"http://{BTC_HOST}:{BTC_PORT}",
                                 json.dumps({"jsonrpc": "1.0", "id": "b", "method": method, "params": []}).encode(),
                                 {"Content-Type": "application/json"})
    req.add_header("Authorization", "Basic " + base64.b64encode(f"{BTC_USER}:{BTC_PASS}".encode()).decode())
    return json.load(urllib.request.urlopen(req, timeout=5))["result"]
UNITS = {"": 1, "K": 1e3, "M": 1e6, "G": 1e9, "T": 1e12, "P": 1e15, "E": 1e18}

def num(s):
    if isinstance(s, (int, float)):
        return float(s)
    m = re.match(r"\s*([\d.]+)\s*([KMGTPE]?)", str(s or ""))
    return float(m[1]) * UNITS[m[2]] if m else 0.0

def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}

def read_pool():
    pool = {}
    try:
        for line in open(os.path.join(LOGS, "pool", "pool.status")):
            if line.strip().startswith("{"):
                pool.update(json.loads(line))
    except Exception:
        pass
    return pool

state = read_json(STATE_FILE) or {}
state.setdefault("day", ""); state.setdefault("daily", {}); state.setdefault("seen", {}); state.setdefault("ever", {})
_net = {"t": 0, "ok": False, "v": {"hashrate": 958e18, "difficulty": 148e12, "height": 0}}

def network():
    if time.time() - _net["t"] > (10 if BTC_HOST else 60):
        try:
            if BTC_HOST:  # ton propre nœud : la difficulté suit chaque ajustement
                m = rpc("getmininginfo")
                _net["v"] = {"hashrate": m["networkhashps"], "difficulty": m["difficulty"], "height": m["blocks"]}
            else:
                get = lambda p: urllib.request.urlopen(MEMPOOL + p, timeout=5).read()
                h = json.loads(get("/api/v1/mining/hashrate/3d"))
                _net["v"] = {"hashrate": h["currentHashrate"], "difficulty": h["currentDifficulty"],
                             "height": int(get("/api/blocks/tip/height"))}
            _net["t"], _net["ok"] = time.time(), True
        except Exception:
            _net["t"], _net["ok"] = time.time() - 5, False  # réessaie bientôt
    return _net["v"]

def update():
    today = time.strftime("%Y-%m-%d")
    if state["day"] != today:
        state["day"], state["daily"] = today, {}
    workers = []
    for f in glob.glob(os.path.join(LOGS, "users", "*")):
        addr = os.path.basename(f)
        for w in read_json(f).get("worker", []):
            name = w.get("workername", addr)
            key = name
            best = num(w.get("bestshare"))
            ever = max(num(w.get("bestever")), best, state["ever"].get(key, 0))
            state["ever"][key] = ever
            last = state["seen"].get(key)
            # Le best share de ckpool est un maximum de session : on ne voit que les hausses.
            if last is not None and best != last and best > 0:
                state["daily"][key] = max(state["daily"].get(key, 0), best)
            state["seen"][key] = best
            workers.append({"name": name, "hashrate": num(w.get("hashrate1m")),
                            "best_day": state["daily"].get(key, 0), "best_ever": ever})
    return workers

def snapshot():
    workers = update()
    pool = read_pool()
    top = lambda k: max(workers, key=lambda w: w[k], default=None)
    bd, be = top("best_day"), top("best_ever")
    t = time.localtime()
    reset = time.mktime((t.tm_year, t.tm_mon, t.tm_mday + 1, 0, 0, 0, 0, 0, -1))
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)
    net = network()
    return {"demo": False, "workers": workers, "day_reset": reset, "network": net,
            "node": {"ok": _net["ok"] and bool(BTC_HOST)},
            "pool": {"hashrate": num(pool.get("hashrate1m")) or sum(w["hashrate"] for w in workers)},
            "best_day": {"value": bd["best_day"] if bd else 0, "worker": bd["name"] if bd and bd["best_day"] else ""},
            "best_ever": {"value": be["best_ever"] if be else 0, "worker": be["name"] if be else ""}}

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] == "/api/stats":
            body = json.dumps(snapshot()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), functools.partial(Handler, directory=here))
    print(f"Dashboard sur http://0.0.0.0:{PORT}  (logs ckpool : {LOGS})")
    srv.serve_forever()
