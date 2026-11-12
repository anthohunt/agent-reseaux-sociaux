#!/bin/bash
# Agent Réseaux sociaux d'Ingevision (agent permanent créé le 12/11/2026). Critère validé par Anthony (choix B) : chaque mois,
# plus d'abonnés sur les comptes Ingevision et plus de visites du site venues des réseaux. Ligne éditoriale (choix C) et
# formats : consigne-contenu.md (tenue par la session Site). Chaque post est validé un par un par Anthony (choix A, LinkedIn
# compris) ; c'est publier.py qui publie, jamais l'agent.
# Passages (heure de Paris) : matin 8 h, midi 12 h, apresmidi 17 h, soir 21 h (lot du jour, rapport du matin suivant) ;
# le samedi soir est un passage long (« samedi » : reel de la semaine, vidéo du mois). Claude tourne sur un poste IOMEGA
# prêté (perso-claude, sans trace) ; s'il n'y a pas de poste libre, le passage est retenté au cron suivant (toutes les
# 30 min pendant 2 h), une marque logs/<date>-<passage>.fait évite les doublons.
# Usage : lancer.sh matin|midi|apresmidi|soir   (FORCE=1 : hors heure ; ESSAI=1 : petit modèle, rien ne revient)
set -u
R=$(cd "$(dirname "$0")" && pwd)
P="${1:?passage}"; J=$(TZ=Europe/Paris date +%F); H=$(TZ=Europe/Paris date +%H)
case "$P" in matin) HP="08 09";; midi) HP="12 13";; apresmidi) HP="17 18";; soir) HP="21 22";; *) echo "passage inconnu : $P"; exit 2;; esac
[ "$P" = soir ] && [ "$(TZ=Europe/Paris date +%u)" = 6 ] && P=samedi
[ "${FORCE:-0}" = 1 ] || [[ " $HP " == *" $H "* ]] || exit 0
mkdir -p "$R/logs" "$R/rapports/$J" "$R/validations" "$R/envoyes" "$R/medias" "$R/w" "$R/verrous"; chmod 700 "$R/verrous"
[ "${FORCE:-0}" = 1 ] || [ ! -e "$R/logs/$J-$P.fait" ] || exit 0
exec 9>"$R/verrous/passage.lock"; flock -n 9 || exit 1
# Un seul poste prêté jusqu'au 15/11 (PARC) : on prend sa place dans la file des agents du site (même verrou, 1 h d'attente au plus)
exec 8>/tmp/agents-site.lock; flock -w 3600 8 || { echo "$(date -u +%FT%TZ) file des agents du site trop longue : nouvel essai au cron suivant" >> "$R/logs/$J-$P.log"; exit 6; }
# le soir, on ne démarre plus après 23 h (heure de Paris) : la nuit des agents du site passe d'abord
if { [ "$P" = soir ] || [ "$P" = samedi ]; } && [ "${FORCE:-0}" != 1 ] && [ "$(TZ=Europe/Paris date +%H)" -ge 23 ]; then
  echo "$(date -u +%FT%TZ) trop tard (après 23 h) : passage du soir sauté, la nuit passe d'abord" >> "$R/logs/$J-$P.log"; exit 0
fi
L="$R/logs/$J-$P.log"; log() { echo "$(date -u +%FT%TZ) $*" >> "$L"; }
log "début passage $P"
python3 "$R/mesurer.py" "$J" > /dev/null 2>> "$L" || log "mesures en échec"
D=/home/claude/agent-reseaux-passe/$P; rm -rf "$D"; mkdir -p "$D"   # copie de travail envoyée au poste (son nom sert au coût)
rsync -a "$R/rapports" "$R/mesures" "$R/validations" "$R/envoyes" "$R/medias" "$R/w" "$D/" >> "$L" 2>&1
[ -f "$R/memoire.md" ] && cp "$R/memoire.md" "$D/" || touch "$D/memoire.md"
mkdir -p "$D/rapports/$J"
mkdir -p "$D/.claude"; cp "$R/garde/settings.json" "$R/garde/garde-arret.py" "$D/.claude/"
# Sources en lecture seule, copiées ici : l'agent n'a AUCUN accès au VPS (ni clés, ni publier.py, ni shell)
mkdir -p "$D/sources/rapports-site" "$D/sources/code"
rsync -a --include='*/' --include='*.json' --include='*.md' --exclude='*' /home/claude/site-anthony-hunt/fiches/ "$D/sources/fiches-site/" >> "$L" 2>&1
for x in $(ls -d /home/claude/agents-site/rapports/20* 2>/dev/null | tail -4); do rsync -a --exclude='*.png' --exclude='*.jpg' "$x" "$D/sources/rapports-site/" >> "$L" 2>&1; done
cp -r /home/claude/skills-monorepo/stop-slop-fr "$D/sources/" 2>> "$L"
git -C "$R" archive HEAD | tar -x -C "$D/sources/code" 2>> "$L"
CPT=$(/usr/local/bin/compte-agents 2>/dev/null | tr -d "[:space:]"); CPT=${CPT:-$(cat /home/claude/maintenance/compte-actif)}
TOKF=/home/claude/.claude-tokens/account-$CPT.env; CFG=/home/claude/.claude-$CPT-iomega; mkdir -p "$CFG"
[ -s "$TOKF" ] || { log "compte $CPT sans jeton"; exit 1; }
jeton() { grep -oP '(?<=CLAUDE_CODE_OAUTH_TOKEN=).*' "$TOKF" | tr -d "\"'"; }
export DATE="$J" PASSAGE="$P" PREFIXE="N$(date -d "$J" +%d%m)"
export PLANCHER="$(python3 -c "import json;p=json.load(open('$R/effort.json'))['$P'];print(', '.join(f'{k} ≥ {v}' for k,v in p.items() if v))")"
CC="$R/consigne-contenu.md"; [ -s "$CC" ] || CC=/home/claude/agents-site/consigne-reseaux.md
{ cat "$R/consigne.md"; [ -s "$CC" ] && cat "$CC"; [ -s "$R/anonymiser.local.md" ] && cat "$R/anonymiser.local.md"; } > "$R/logs/$J-$P.brut.md"
python3 /home/claude/agents-site/iomega/composer.py "$R/logs/$J-$P.brut.md" /home/claude/agents-site/iomega/machine.md "$R/logs/$J-$P.machine.md" >> "$L" 2>&1 \
  || cp "$R/logs/$J-$P.brut.md" "$R/logs/$J-$P.machine.md"
perl -pe 's/\{\{(\w+)\}\}/$ENV{$1}/g' "$R/logs/$J-$P.machine.md" > "$R/logs/$J-$P.consigne.md"
SID=$(cat /proc/sys/kernel/random/uuid); echo "$SID" > "$R/logs/$J-$P.session"
SESSF="$CFG/projects/$(echo "$D" | sed 's#[/.]#-#g')/$SID.jsonl"
MOD=claude-opus-5-5; EFF=high; DUREE=80m; [ "$P" = samedi ] && DUREE=180m
[ "${ESSAI:-0}" = 1 ] && { MOD=claude-haiku-5-5; EFF=low; DUREE=15m; }
lance() {
  log "claude $MOD ($EFF) compte $CPT $2"
  ( cd "$D" && env -u ANTHROPIC_API_KEY -u CLAUDECODE CLAUDE_CONFIG_DIR="$CFG" CLAUDE_CODE_OAUTH_TOKEN="$(jeton)" \
      PERSO_NOM="reseaux-$P" PERSO_AVANT="npm install --no-audit --no-fund --silent --prefix w playwright@1.60.0" \
      PERSO_SANS_RETOUR="w/node_modules w/package.json w/package-lock.json sources" PERSO_ENV="NODE_PATH" NODE_PATH='{BASE}\w\node_modules' \
      timeout "$DUREE" /home/claude/perso-iomega/perso-claude -p "$(cat "$1")" --model "$MOD" --effort "$EFF" --dangerously-skip-permissions $2 $SID < /dev/null ) >> "$L" 2>&1
  RC=$?; log "claude fini : code $RC"
}
lance "$R/logs/$J-$P.consigne.md" --session-id
if [ "$RC" = 75 ]; then log "aucun poste IOMEGA libre : nouvel essai au cron suivant"; rm -rf "$D"; exit 6; fi
if [ "${ESSAI:-0}" != 1 ]; then
  for n in $(seq 1 "$(python3 -c "import json;print(json.load(open('$R/effort.json'))['reprises_max'])")"); do
    python3 "$R/compter-effort.py" "$P" "$J" "$SESSF" >> "$L" 2>&1 && break
    export MANQUE="$(cat "$R/logs/$J-$P.manque.txt" 2>/dev/null)"
    perl -pe 's/\{\{(\w+)\}\}/$ENV{$1}/g' "$R/consigne-reprise.md" > "$R/logs/$J-$P.reprise.md"
    log "reprise $n"
    for t in 1 2 3 4; do lance "$R/logs/$J-$P.reprise.md" --resume; [ "$RC" = 75 ] || break; log "reprise $n : aucun poste libre, essai $t/4"; sleep 120; done
  done
  # retour au VPS : rapport du passage (identifiants renumérotés), mémoire, médias, scripts
  if [ -s "$D/rapports/$J/$P.json" ]; then
    python3 "$R/renumeroter.py" "$D/rapports/$J/$P.json" "$PREFIXE" "$R/rapports" >> "$L" 2>&1 && cp "$D/rapports/$J/$P.json" "$R/rapports/$J/"
  else log "aucun rapport écrit"; fi
  cp "$D/memoire.md" "$R/memoire.md"; rsync -a "$D/medias/" "$R/medias/" >> "$L" 2>&1; rsync -a --delete --exclude node_modules "$D/w/" "$R/w/" >> "$L" 2>&1
  touch "$R/logs/$J-$P.fait"
  case "$P" in soir|samedi) python3 "$R/deposer.py" "$J" >> "$L" 2>&1 || log "dépôt dans le rapport du matin en échec";; esac
fi
rm -rf "$D"; log "fin passage $P"
