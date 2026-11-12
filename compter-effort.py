#!/usr/bin/env python3
"""Compte l'effort d un passage de l agent Réseaux sociaux (comme les agents du site), dans sa session (décision d'Anthony du 09/11/2026).
Usage : compter-effort.py <agent> <date> <fichier-session.jsonl> ; code 0 = plancher tenu, 3 = il manque de l'effort
(le détail, pour la reprise, est écrit dans logs/<date>-<agent>.manque.txt)."""
import json, re, sys
from pathlib import Path
D = Path(__file__).resolve().parent
agent, date, sess = sys.argv[1], sys.argv[2], Path(sys.argv[3])
P = json.load(open(D / "effort.json"))[agent]
fichiers = [sess] + sorted((sess.parent / sess.stem / "subagents").glob("*.jsonl"))
actions, pages, recherches, stories, depots, vus = 0, set(), 0, set(), set(), set()
for f in fichiers:
    if not f.exists(): continue
    for l in f.open(errors="replace"):
        try: e = json.loads(l)
        except Exception: continue
        c = (e.get("message") or {}).get("content")
        if not isinstance(c, list): continue
        for b in c:
            if not isinstance(b, dict): continue
            if b.get("type") == "tool_use" and b.get("id") not in vus:
                vus.add(b.get("id")); actions += 1
                t = json.dumps(b.get("input"), ensure_ascii=False)
                if b.get("name") == "WebSearch" or re.search(r"duckduckgo\.com|bing\.com/search|google\.[a-z]+/search", t): recherches += 1
                pages |= {u.rstrip('\\",.)') for u in re.findall(r"https?://(?:www\.)?(?:[a-z0-9-]+\.)?ingevision\.cloud[^\s\"'\\`<>]*", t)}
                stories |= set(re.findall(r"US-\d+\.\d+", t))
                depots |= set(re.findall(r"anthohunt/([A-Za-z0-9_.-]+)", t))
            if b.get("type") == "text":
                stories |= set(re.findall(r"US-\d+\.\d+", b.get("text", "")))
# les stories de la passe se lisent aussi dans les réponses d'outils (fichier lu), donc on ne compte que celles citées par l'agent
mesure = {"actions": actions, "pages": len(pages), "recherches": recherches, "stories": len(stories), "depots": len(depots)}
manque = [f"- {k} : {mesure[k]} au lieu d'au moins {v}" for k, v in P.items() if mesure[k] < v]
print(f"effort {agent} {date} : " + ", ".join(f"{k} {mesure[k]}/{P[k]}" for k in mesure))
out = D / "logs" / f"{date}-{agent}.manque.txt"
if manque:
    out.write_text("\n".join(manque) + "\n"); sys.exit(3)
out.unlink(missing_ok=True)
