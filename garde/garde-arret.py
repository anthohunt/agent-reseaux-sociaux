#!/usr/bin/env python3
"""Crochet PreToolUse de l'agent Réseaux (poste IOMEGA) :
- refuse tout arrêt de programmes par leur nom (pkill, killall, taskkill /IM, Stop-Process -Name), y compris par ssh ;
- refuse toute publication et tout accès aux clés : c'est publier.py, lancé après le oui d'Anthony, qui publie,
  jamais l'agent (publier.py, relais-x.sh, dossiers de secrets, fichiers de jetons)."""
import json, re, sys

try:
    e = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
i = e.get("tool_input") or {}
c = " ".join(str(i[k]) for k in ("command", "file_path", "path", "pattern") if i.get(k))
if re.search(r"""(^|[\s;&|(`"'])(pkill|killall|pidof\s.*\|\s*xargs\s+kill)\b|taskkill\b[^\n]*/im\b|stop-process\b[^\n]*-name\b""", c, re.I):
    print("Bloqué : jamais d'arrêt de programmes par leur nom. Arrête par numéro de processus (kill <PID>) "
          "après avoir vérifié que c'est bien le tien.", file=sys.stderr)
    sys.exit(2)
if re.search(r"publier\.py|relais-x|secrets?/|\.claude-tokens|compte-secret|oauth_token|\.key\b", c, re.I):
    print("Bloqué : tu ne publies rien et tu ne lis aucune clé. Tes posts vont au rapport ; "
          "publier.py les envoie après le oui d'Anthony.", file=sys.stderr)
    sys.exit(2)
sys.exit(0)
