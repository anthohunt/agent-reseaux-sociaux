#!/usr/bin/env python3
"""Identifiants des propositions d'un passage : <PREFIXE>-n, à la suite de ceux déjà donnés ce jour-là (jamais deux fois le
même numéro). Usage : renumeroter.py <rapport.json> <PREFIXE> <dossier rapports du VPS>"""
import json, re, sys
from pathlib import Path
f, P, R = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
r = json.loads(f.read_text(encoding="utf-8"))
pris = set()
for g in R.glob("*/*.json"):
    if g.name == f.name and g.parent.name == f.parent.name:
        continue
    try:
        for p in json.loads(g.read_text(encoding="utf-8")).get("propositions") or []:
            pris.add(p.get("id"))
    except ValueError:
        pass
n = max([int(x.split("-")[1]) for x in pris if x and x.startswith(P + "-") and x.split("-")[1].isdigit()] or [0])
carte = {}
for p in r.get("propositions") or []:
    n += 1
    if p.get("id"): carte[p["id"]] = f"{P}-{n}"
    else: p["id"] = f"{P}-{n}"
t = json.dumps(r, ensure_ascii=False, indent=1)
if carte:   # un seul remplacement simultané : aucun numéro n'est remplacé deux fois
    t = re.sub(r"\b(%s)\b" % "|".join(re.escape(k) for k in sorted(carte, key=len, reverse=True)), lambda m: carte[m.group(1)], t)
json.loads(t); f.write_text(t, encoding="utf-8")
print("identifiants :", [p["id"] for p in json.loads(t).get("propositions") or []])
