#!/usr/bin/env python3
"""Partie « Réseaux sociaux » du rapport du matin : passages du jour (analyse, suggestions, mesures) et le lot du soir à
valider post par post en session (decider N<jjmm>-n oui|non). Usage : deposer.py <date des passages> [--apercu]"""
import datetime, json, subprocess, sys
from pathlib import Path
R = Path(__file__).resolve().parent
J = sys.argv[1]
rap = {}
for p in ("matin", "midi", "apresmidi", "soir", "samedi"):
    f = R / "rapports" / J / f"{p}.json"
    if f.exists():
        try: rap[p] = json.loads(f.read_text(encoding="utf-8"))
        except ValueError: rap[p] = {"resume": "rapport illisible"}
NOMS = {"matin": "8 h", "midi": "12 h", "apresmidi": "17 h", "soir": "21 h", "samedi": "samedi soir"}
mes = {}
try: mes = json.loads((R / "mesures" / f"{J}.json").read_text())
except Exception: pass
L = [f"Passages du {J[8:10]}/{J[5:7]} : " + (", ".join(NOMS[p] for p in rap) or "aucun") + f" (sur 4 prévus).", ""]
ab = mes.get("abonnes") or {}
if ab:
    L.append("Abonnés : " + ", ".join(f"{k} {v if v is not None else '?'}" for k, v in ab.items()))
v = mes.get("visites_depuis_reseaux")
if v is not None:
    L.append("Visites du site venues des réseaux (7 jours) : " + str(sum(sum(d.values()) for d in v.values())))
for p, r in rap.items():
    L += ["", f"— Passage de {NOMS[p]} : {r.get('resume', '')}"]
    L += [f"  • {x}" for x in (r.get("analyse") or [])]
    L += [f"  • Suggestion : {x}" for x in (r.get("suggestions") or [])]
    L += [f"  • Signalé : {x.get('quoi')} — {x.get('pourquoi', '')}" for x in (r.get("signale") or [])]
props = [x for r in rap.values() for x in (r.get("propositions") or [])]
if props:
    L += ["", f"À VALIDER, post par post ({len(props)}) — en session : « oui N…-n » ou « non N…-n » ; publié seulement après ton oui, texte inchangé :"]
    for x in props:
        L += ["", f"[{x.get('id')}] {x.get('reseau')} · {x.get('format')} · {x.get('titre', '')}", x.get("texte", "")]
        if x.get("medias"): L.append("Médias : " + ", ".join("/home/claude/agent-reseaux/" + m for m in x["medias"]))
        L.append(f"Pourquoi : {x.get('pourquoi', '')} — Mesure : {x.get('mesure', '')}")
else:
    L += ["", "Aucun post à valider aujourd'hui."]
texte = "\n".join(L)
sujet = f"Réseaux sociaux : {len(props)} post(s) à valider" if props else "Réseaux sociaux : rien à valider"
if "--apercu" in sys.argv:
    print(sujet + "\n\n" + texte); sys.exit()
lendemain = (datetime.date.fromisoformat(J) + datetime.timedelta(days=1)).isoformat()
t = R / "logs" / f"{J}-depot.txt"; t.write_text(texte, encoding="utf-8")
sys.exit(subprocess.run(["/home/claude/mail-du-matin/deposer.py", "reseaux", "--date", lendemain, "--sujet", sujet, "--text-file", str(t)]).returncode)
