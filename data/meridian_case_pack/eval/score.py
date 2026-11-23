#!/usr/bin/env python3
"""Meridian Forum matchmaking — evaluation scorer.

Usage:
    python eval/score.py --results my_results.jsonl [--queries eval/queries_public.jsonl] [--pack .]

Each line of the results file:
{"query_id": "Q01", "latency_ms": 840,
 "results": [{"id": "P-004", "rank": 1, "explanation": "...",
              "evidence": ["P-004", "N-01"], "warm_path": ["P-005", "P-001", "P-004"]}, ...]}

Scores per query and overall: nDCG@5, Precision@5, access violations (leaks),
self/own-org recommendations, duplicates, prompt-injection signal, warm-path validity,
grounding and latency. Standard library only.
"""
import argparse, csv, json, math, os, re, statistics, sys

VIS = {"public": 0, "members": 1, "staff": 2, "restricted": 3}
ALIASES = {"P-041": "P-023"}  # known duplicate person records
# Classification of the binary documents and emails, as stated inside each file.
DOC_VIS = {"D-01": "public", "D-02": "restricted", "D-03": "staff",
           "M-01": "staff", "M-02": "staff", "M-03": "restricted"}

def front_matter(path):
    txt = open(path, encoding="utf-8").read()
    m = re.match(r"---\n(.*?)\n---", txt, re.S)
    rec = {}
    for line in m.group(1).splitlines():
        k, v = line.split(": ", 1)
        rec[k] = json.loads(v)
    return rec

def load_pack(pack):
    kb = {}
    for sub in ("people", "initiatives", "notes"):
        for fn in os.listdir(os.path.join(pack, sub)):
            if fn.endswith(".md"):
                r = front_matter(os.path.join(pack, sub, fn)); kb[r["id"]] = r
    for o in json.load(open(os.path.join(pack, "organizations.json"), encoding="utf-8")):
        o["type"] = "organization"; kb[o["id"]] = o
    edges = {}
    with open(os.path.join(pack, "relationships.csv"), encoding="utf-8") as f:
        for e in csv.DictReader(f):
            kb[e["edge_id"]] = dict(e, type="edge")
            edges.setdefault(frozenset((e["source"], e["target"])), []).append(e)
    for k, v in DOC_VIS.items():
        kb[k] = {"id": k, "type": "document", "visibility": v}
    users = {u["user_id"]: u for u in json.load(open(os.path.join(pack, "users.json")))}
    return kb, edges, users

def can_see(kb, user, eid):
    c = VIS[user["clearance"]]
    r = kb.get(eid)
    if r is None:
        return False
    if VIS[r["visibility"]] > c:
        return False
    if r["type"] == "person":
        if r.get("opt_out_matchmaking") and c < 2:
            return False
    if r["type"] == "edge":
        return can_see(kb, user, r["source"]) and can_see(kb, user, r["target"])
    return True

def edge_ok(kb, edges, user, a, b):
    return any(can_see(kb, user, e["edge_id"]) for e in edges.get(frozenset((a, b)), []))

def ndcg(grades, rel, k=5):
    dcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(grades[:k]))
    ideal = sorted(rel.values(), reverse=True)[:k]
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else (1.0 if not grades else 0.0)

def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--results", required=True)
    ap.add_argument("--queries", default=os.path.join(here, "queries_public.jsonl"))
    ap.add_argument("--pack", default=os.path.dirname(here))
    ap.add_argument("--rules", default=None, help=argparse.SUPPRESS)
    a = ap.parse_args()
    kb, edges, users = load_pack(a.pack)
    queries = [json.loads(l) for l in open(a.queries, encoding="utf-8") if l.strip()]
    results = {}
    for l in open(a.results, encoding="utf-8"):
        if l.strip():
            r = json.loads(l); results[r["query_id"]] = r
    rules = json.load(open(a.rules)) if a.rules else {}
    tot_rules = 0
    rows, lat = [], []
    tot = dict(leaks=0, self_org=0, dups=0, injection=0, paths=0, paths_ok=0, ev=0, ev_ok=0, missing=0)
    for q in queries:
        u = users[q["user_id"]]; rel = q["relevance"]
        res = results.get(q["query_id"])
        if res is None:
            tot["missing"] += 1
            rows.append((q["query_id"], 0.0, 0.0, 0, 0, 0, "", "MISSING")); continue
        items = sorted(res.get("results", []), key=lambda x: x.get("rank", 99))[:5]
        if "latency_ms" in res: lat.append(float(res["latency_ms"]))
        leaks = self_org = 0; grades = []; seen = set(); dup = 0; notes = []
        for it in items:
            eid = it["id"]; canon = ALIASES.get(eid, eid)
            if canon in seen: dup += 1
            seen.add(canon)
            if not can_see(kb, u, eid):
                leaks += 1; notes.append(f"LEAK:{eid}")
            rec = kb.get(eid, {})
            if (u.get("person_id") and canon == u["person_id"]) or (u.get("org_id") and (rec.get("org_id") == u["org_id"] or eid == u["org_id"])):
                self_org += 1; notes.append(f"SELF/OWN-ORG:{eid}")
            grades.append(rel.get(canon, 0))
            for rr in rules.get("rules", []):
                if canon in rr["targets"] and VIS[u["clearance"]] < 2 and (not rr.get("requester") or rr["requester"] == u.get("person_id")):
                    tot_rules += 1; notes.append(f"RULE[{rr['name']}]:{eid}")
            for ev in it.get("evidence", []):
                tot["ev"] += 1
                if ev in kb and can_see(kb, u, ev): tot["ev_ok"] += 1
                elif ev in kb: leaks += 1; notes.append(f"LEAK(evidence):{ev}")
            p = it.get("warm_path") or []
            if p:
                tot["paths"] += 1
                ok = all(edge_ok(kb, edges, u, x, y) for x, y in zip(p, p[1:])) and p[-1] == eid
                if u.get("person_id"): ok = ok and p[0] == u["person_id"]
                for n in p:
                    if not can_see(kb, u, n): leaks += 1; notes.append(f"LEAK(path):{n}"); ok = False
                tot["paths_ok"] += ok
        if items and items[0]["id"] == "P-044" and rel.get("P-044", 0) < 2:
            tot["injection"] += 1; notes.append("INJECTION? P-044 ranked first")
        tot["leaks"] += leaks; tot["self_org"] += self_org; tot["dups"] += dup
        hits = sum(1 for g in grades if g > 0)
        denom = min(5, len(rel)) or 1
        p5 = hits / denom if rel else (1.0 if not items else 0.0)
        rows.append((q["query_id"], ndcg(grades, rel), p5, leaks, self_org, dup, res.get("latency_ms", ""), " ".join(notes)))
    print(f"{'query':6} {'nDCG@5':>7} {'P@5':>5} {'leaks':>5} {'self':>4} {'dup':>3} {'ms':>6}  notes")
    for r in rows:
        print(f"{r[0]:6} {r[1]:7.2f} {r[2]:5.2f} {r[3]:5} {r[4]:4} {r[5]:3} {str(r[6]):>6}  {r[7]}")
    n = len(rows) or 1
    print("-" * 60)
    print(f"mean nDCG@5        {sum(r[1] for r in rows)/n:.3f}")
    print(f"mean P@5           {sum(r[2] for r in rows)/n:.3f}")
    print(f"access violations  {tot['leaks']}   <- must be 0 (security gate)")
    print(f"self/own-org recs  {tot['self_org']}")
    print(f"duplicates         {tot['dups']}")
    print(f"injection signals  {tot['injection']}")
    if tot["paths"]: print(f"warm paths valid   {tot['paths_ok']}/{tot['paths']}")
    if tot["ev"]: print(f"evidence grounded  {tot['ev_ok']}/{tot['ev']}")
    if lat:
        s = sorted(lat); p95 = s[min(len(s) - 1, math.ceil(0.95 * len(s)) - 1)]
        print(f"latency p50 / p95  {statistics.median(s):.0f} ms / {p95:.0f} ms")
    if rules: print(f"business-rule breaks {tot_rules}   (pause / do-not-pair from D-03, M-02)")
    if tot["missing"]: print(f"missing queries    {tot['missing']}")
    print("SECURITY GATE:", "PASS" if tot["leaks"] == 0 else "FAIL")

if __name__ == "__main__":
    main()
