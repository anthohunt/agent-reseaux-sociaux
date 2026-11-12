#!/usr/bin/env python3
"""Agent Réseaux sociaux : relevé de l'audience (critère validé par Anthony le 12/11/2026, choix B : « chaque mois, plus
d'abonnés sur la page Ingevision et plus de visites du site venues des réseaux »). Sans IA, léger, sur le VPS.
  mesurer.py [AAAA-MM-JJ]  → mesures/<date>.json (dernier relevé du jour) + mesures/historique.csv (une ligne par relevé)
Abonnés : API publiques (Mastodon, Bluesky), API à clé (dev.to, YouTube) ; X et page LinkedIn sans API : null ici, relevés
par l'agent lui-même pendant ses passages et notés dans son rapport. Visites du site venues des réseaux : journal nginx du
site (8 derniers jours), par paramètre utm_source des liens des posts et par site d'origine (Referer). Aucune clé affichée."""
import os
import csv, datetime, json, re, subprocess, sys, urllib.parse, urllib.request
from collections import defaultdict
from pathlib import Path
# accès root au serveur (adresse privée hors dépôt)
VPS_ROOT = os.environ.get("VPS_ROOT") or open(os.path.expanduser("~/.config/agents/vps-root")).read().strip()

D = Path(__file__).resolve().parent
S = Path("/home/claude/.config/secrets/ingevision")
J = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()
RESEAUX = {"mastodon": r"mastodon\.|mstdn|fosstodon", "bluesky": r"bsky\.app|bsky\.social", "x": r"(^|\.)t\.co$|(^|\.)x\.com$|twitter\.com",
           "linkedin": r"linkedin\.com|lnkd\.in", "devto": r"(^|\.)dev\.to$", "youtube": r"youtube\.com|youtu\.be", "huggingface": r"huggingface\.co"}


def get(url, headers=None, data=None):
    r = urllib.request.Request(url, headers={"User-Agent": "ingevision-mesures/1.0", **(headers or {})}, data=data)
    with urllib.request.urlopen(r, timeout=30) as f:
        return json.load(f)


def abonnes():
    a, err = {}, {}
    def essai(nom, f):
        try: a[nom] = f()
        except Exception as e: a[nom] = None; err[nom] = type(e).__name__
    essai("mastodon", lambda: get("https://mastodon.social/api/v1/accounts/lookup?acct=ingevisioncloud")["followers_count"])
    essai("bluesky", lambda: get("https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor=ingevision.bsky.social")["followersCount"])
    def devto():
        k = (S / "devto.key").read_text().strip(); n, p = 0, 1
        while True:
            L = get(f"https://dev.to/api/followers/users?per_page=1000&page={p}", {"api-key": k}); n += len(L)
            if len(L) < 1000: return n
            p += 1
    essai("devto", devto)
    def youtube():
        c = json.loads((S / "youtube.key").read_text())
        t = get(c.get("token_uri") or "https://oauth2.googleapis.com/token", data=urllib.parse.urlencode(
            {"client_id": c["client_id"], "client_secret": c["client_secret"], "refresh_token": c["refresh_token"], "grant_type": "refresh_token"}).encode())
        r = get("https://www.googleapis.com/youtube/v3/channels?part=statistics&mine=true", {"Authorization": "Bearer " + t["access_token"]})
        return int(r["items"][0]["statistics"].get("subscriberCount", 0))
    essai("youtube", youtube)
    a["x"] = None; a["linkedin"] = None   # pas d'API gratuite : relevé par l'agent pendant son passage
    return a, err


LIGNE = re.compile(r'^(\S+) \S+ \S+ \[([^\]]+)\] "(?:GET|HEAD) (\S+)[^"]*" (\d{3}) \S+ "([^"]*)" "([^"]*)"(?: "([^"]*)")?')
ROBOT = re.compile(r"bot|crawl|spider|slurp|curl|wget|python|httpx|go-http|headless|playwright|monitor|uptime|preview|facebookexternalhit|scan", re.I)


def visites():
    log = subprocess.run(["ssh", "-o", "BatchMode=yes", VPS_ROOT, "docker logs --since 192h site-racine 2>&1"],
                         capture_output=True, text=True, timeout=120).stdout
    par = defaultdict(lambda: defaultdict(set))   # jour → réseau → visiteurs distincts
    for l in log.splitlines():
        m = LIGNE.match(l)
        if not m or m[4][0] not in "23" or ROBOT.search(m[6]) or re.search(r"\.(js|css|png|jpe?g|webp|svg|ico|mp4|woff2?|json|xml|txt)(\?|$)", m[3]):
            continue
        res = None
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(m[3]).query)
        src = (q.get("utm_source") or [""])[0].lower()
        if src:
            res = next((r for r in RESEAUX if r in src), src[:20])
        else:
            hote = (urllib.parse.urlsplit(m[5]).hostname or "").lower()
            res = next((r for r, rx in RESEAUX.items() if hote and re.search(rx, hote)), None)
        if res:
            jour = datetime.datetime.strptime(m[2].split()[0], "%d/%b/%Y:%H:%M:%S").date().isoformat()
            par[jour][res].add((m[7] or m[1]).split(",")[0].strip())   # adresse réelle (dernier champ, derrière le relais)
    return {j: {r: len(v) for r, v in d.items()} for j, d in sorted(par.items())}


def main():
    a, err = abonnes()
    try: v = visites()
    except Exception as e: v = None; err["visites"] = type(e).__name__
    out = {"date": J, "quand": datetime.datetime.now().isoformat(timespec="minutes"), "abonnes": a, "visites_depuis_reseaux": v, "erreurs": err}
    (D / "mesures").mkdir(exist_ok=True)
    (D / "mesures" / f"{J}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    h = D / "mesures" / "historique.csv"; neuf = not h.exists()
    with h.open("a", newline="") as f:
        w = csv.writer(f)
        if neuf: w.writerow(["quand", *sorted(a), "visites_7j"])
        w.writerow([out["quand"], *[a[k] if a[k] is not None else "" for k in sorted(a)],
                    sum(sum(d.values()) for d in (v or {}).values())])
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
