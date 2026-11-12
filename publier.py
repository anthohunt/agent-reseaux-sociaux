#!/usr/bin/env python3
"""Publie les posts validés par Anthony (décision du 12/11 : « Je valide chaque post, LinkedIn compris »). Sans IA.
Pour chaque validations/<ID>.json = oui sans envoyes/<ID>.json : retrouve la proposition dans rapports/*/*.json et publie
son texte EXACT (et ses médias) par l'API du réseau (Mastodon, Bluesky, dev.to, YouTube) ou par le relais de la tour (X,
page LinkedIn). Écrit envoyes/<ID>.json (preuve) ou, en cas d'échec, envoyes/<ID>.echec (signalé une fois au manager).
Les clés sont lues dans ~/.config/secrets/ingevision et jamais affichées. Usage : publier.py [--essai]"""
import json, mimetypes, re, subprocess, sys, urllib.parse, urllib.request, uuid
from datetime import datetime, timezone
from pathlib import Path

R = Path(__file__).resolve().parent
S = Path("/home/claude/.config/secrets/ingevision")
ESSAI = "--essai" in sys.argv


def http(url, data=None, headers=None, methode=None):
    r = urllib.request.Request(url, data=data, headers={"User-Agent": "ingevision-publier/1.0", **(headers or {})}, method=methode)
    with urllib.request.urlopen(r, timeout=120) as f:
        b = f.read()
        return json.loads(b) if b else {}


def multipart(champs, fichiers):
    b = uuid.uuid4().hex; corps = b""
    for k, v in champs.items():
        corps += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    for k, p in fichiers.items():
        corps += (f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{p.name}\"\r\nContent-Type: "
                  f"{mimetypes.guess_type(p.name)[0] or 'application/octet-stream'}\r\n\r\n").encode() + p.read_bytes() + b"\r\n"
    return corps + f"--{b}--\r\n".encode(), f"multipart/form-data; boundary={b}"


def alt(m):
    j = m.with_suffix(".json")
    try: return json.loads(j.read_text()).get("texte_alt", "")[:1000]
    except Exception: return ""


def mastodon(p, medias):
    k = (S / "mastodon.key").read_text().strip(); H = {"Authorization": "Bearer " + k}; ids = []
    for m in medias[:4]:
        corps, ct = multipart({"description": alt(m)}, {"file": m})
        ids.append(http("https://mastodon.social/api/v2/media", corps, {**H, "Content-Type": ct})["id"])
    d = urllib.parse.urlencode([("status", p["texte"])] + [("media_ids[]", i) for i in ids]).encode()
    return http("https://mastodon.social/api/v1/statuses", d, H)["url"]


def bluesky(p, medias):
    c = json.loads((S / "bluesky.key").read_text())
    s = http("https://bsky.social/xrpc/com.atproto.server.createSession",
             json.dumps({"identifier": c["identifiant"], "password": c["mot_de_passe_app"]}).encode(), {"Content-Type": "application/json"})
    H = {"Authorization": "Bearer " + s["accessJwt"]}; t = p["texte"]; b = t.encode()
    facets = []
    for m in re.finditer(r"https?://[^\s)]+", t):
        debut = len(t[:m.start()].encode()); facets.append({"index": {"byteStart": debut, "byteEnd": debut + len(m.group(0).encode())},
                                                           "features": [{"$type": "app.bsky.richtext.facet#link", "uri": m.group(0)}]})
    rec = {"$type": "app.bsky.feed.post", "text": t, "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "facets": facets, "langs": ["fr"]}
    imgs = []
    for m in [x for x in medias if x.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")][:4]:
        bl = http("https://bsky.social/xrpc/com.atproto.repo.uploadBlob", m.read_bytes(), {**H, "Content-Type": mimetypes.guess_type(m.name)[0]})
        imgs.append({"alt": alt(m), "image": bl["blob"]})
    if imgs: rec["embed"] = {"$type": "app.bsky.embed.images", "images": imgs}
    r = http("https://bsky.social/xrpc/com.atproto.repo.createRecord", json.dumps({"repo": s["did"], "collection": "app.bsky.feed.post", "record": rec}).encode(),
             {**H, "Content-Type": "application/json"})
    return "https://bsky.app/profile/ingevision.bsky.social/post/" + r["uri"].rsplit("/", 1)[-1]


def devto(p, medias):
    k = (S / "devto.key").read_text().strip()
    a = {"article": {"title": p.get("titre") or p["texte"].splitlines()[0][:120], "body_markdown": p["texte"], "published": True,
                     "tags": [x for x in (p.get("etiquettes") or [])][:4]}}
    return http("https://dev.to/api/articles", json.dumps(a).encode(), {"api-key": k, "Content-Type": "application/json"})["url"]


def youtube(p, medias):
    v = [x for x in medias if x.suffix.lower() in (".mp4", ".mov", ".webm")]
    if not v: raise RuntimeError("aucune vidéo jointe")
    c = json.loads((S / "youtube.key").read_text())
    t = http(c.get("token_uri") or "https://oauth2.googleapis.com/token", urllib.parse.urlencode(
        {"client_id": c["client_id"], "client_secret": c["client_secret"], "refresh_token": c["refresh_token"], "grant_type": "refresh_token"}).encode())
    meta = json.dumps({"snippet": {"title": (p.get("titre") or "Ingevision")[:100], "description": p["texte"], "defaultLanguage": "fr"},
                       "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}).encode()
    b = uuid.uuid4().hex
    corps = (f"--{b}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n").encode() + meta + \
            (f"\r\n--{b}\r\nContent-Type: video/mp4\r\n\r\n").encode() + v[0].read_bytes() + f"\r\n--{b}--\r\n".encode()
    r = http("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=multipart&part=snippet,status", corps,
             {"Authorization": "Bearer " + t["access_token"], "Content-Type": f"multipart/related; boundary={b}"})
    return "https://www.youtube.com/watch?v=" + r["id"]


# réglages de l'installation (hors dépôt) : commande d'allumage de la machine relais, adresse d'administration de la page LinkedIn
REGLAGES = {}
_f = Path(__file__).resolve().parent / "reglages.local"
if _f.exists():
    for _l in _f.read_text().splitlines():
        if "=" in _l and not _l.lstrip().startswith("#"):
            _k, _v = _l.split("=", 1); REGLAGES[_k.strip()] = _v.strip()

def relais(p, medias, reseau):
    """X et page LinkedIn : pas d'API gratuite ; relais de la tour (choix d'Anthony), une consigne = une action."""
    distants = []
    if medias:   # la tour peut être éteinte : le relais sait l'allumer, alors on le réveille d'abord par une consigne vide
        if subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "tour", "mkdir -p relais-x/medias"], timeout=30).returncode:
            subprocess.run(REGLAGES.get("ALLUMER_TOUR", "true"), shell=True, capture_output=True, timeout=60)
            raise RuntimeError("tour éteinte : allumée, nouvel essai au prochain passage du programme (10 min)")
    for m in medias[:4]:
        subprocess.run(["scp", "-q", str(m), f"tour:relais-x/medias/{m.name}"], timeout=120, check=True); distants.append(f"~/relais-x/medias/{m.name}")
    ou = "sur X, compte @ingevisioncloud" if reseau == "x" else "sur la PAGE LinkedIn Ingevision (administration : " + REGLAGES.get("LINKEDIN_ADMIN", "page d'administration de la page") + "), jamais le profil personnel"
    consigne = (f"Publie {ou} le texte exact ci-dessous, sans en changer un caractère" + (f", avec ces images : {', '.join(distants)}" if distants else "")
                + f". Vérifie le post publié puis donne son lien seul sur la dernière ligne, après « LIEN : ».\n\nTEXTE :\n{p['texte']}")
    r = subprocess.run(["/home/claude/agents-site/relais-x.sh", consigne], capture_output=True, text=True, timeout=1800)
    m = re.findall(r"LIEN\s*:\s*(https?://\S+)", r.stdout)
    if not m: raise RuntimeError("le relais n'a pas rendu de lien (code %d)" % r.returncode)
    return m[-1]


CANAUX = {"mastodon": mastodon, "bluesky": bluesky, "devto": devto, "youtube": youtube,
          "x": lambda p, m: relais(p, m, "x"), "linkedin": lambda p, m: relais(p, m, "linkedin")}


def propositions():
    P = {}
    for f in sorted(R.glob("rapports/*/*.json")):
        try:
            for p in json.loads(f.read_text(encoding="utf-8")).get("propositions") or []:
                if p.get("id"): P[p["id"].upper()] = p
        except ValueError:
            pass
    return P


def main():
    P = propositions(); E = R / "envoyes"; E.mkdir(exist_ok=True)
    for v in sorted((R / "validations").glob("N*.json")):
        d = json.loads(v.read_text()); i = d["id"].upper()
        ech = E / f"{i}.echec"
        essais = len(ech.read_text().splitlines()) if ech.exists() else 0
        if d.get("decision") != "oui" or (E / f"{i}.json").exists() or essais >= 3:   # 3 essais au plus (10 min d'écart au moins)
            continue
        p = P.get(i)
        if not p:
            print(f"{i} : proposition introuvable"); continue
        res = (p.get("reseau") or "").lower()
        medias = [R / m for m in (p.get("medias") or [])]
        manque = [str(m) for m in medias if not m.exists()]
        if ESSAI:
            print(f"[essai] {i} → {res}, {len(p['texte'])} caractères, médias {len(medias)} (manquants : {manque or 'aucun'})"); continue
        try:
            if manque: raise RuntimeError("média absent : " + ", ".join(manque))
            if res not in CANAUX: raise RuntimeError(f"réseau non géré par le programme : {res}")
            lien = CANAUX[res](p, medias)
            (E / f"{i}.json").write_text(json.dumps({"id": i, "reseau": res, "quand": datetime.now().isoformat(timespec="minutes"), "preuve": lien,
                                                     "citation": d.get("citation", "")}, ensure_ascii=False))
            print(f"{i} publié : {lien}")
        except Exception as e:
            msg = f"{type(e).__name__} : {str(e)[:200]}"
            with ech.open("a") as h: h.write(datetime.now().isoformat(timespec="minutes") + " " + msg + "\n")
            print(f"{i} : échec — {msg}")
            if essais + 1 >= 3: subprocess.run(["/home/claude/bin/signaler-maintenance", f"Agent Réseaux : post {i} non publié", f"{res} : {msg}", "--source", "agent-reseaux"],
                           capture_output=True, timeout=30)


if __name__ == "__main__":
    main()
