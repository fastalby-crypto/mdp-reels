#!/usr/bin/env python3
"""Cerca gli articoli italiani pubblicati negli ultimi 3 giorni e crea il reel per
quelli che non lo hanno ancora. I reel stanno in <site>/reels/<post_id>.mp4 e
vengono cancellati dopo 14 giorni (a quel punto sono gia' su Instagram).

Uso: python3 scan.py <cartella_site> [post_id forzato]
Scrive "changed=true" in $GITHUB_OUTPUT se ha aggiunto o tolto qualcosa.
"""
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.request

SITE = "https://ilmagazinedelparrucchiere.com"
HERE = os.path.dirname(os.path.abspath(__file__))
KEEP_DAYS = 14


def posts_recent():
    after = (dt.datetime.utcnow() - dt.timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%S")
    url = f"{SITE}/wp-json/wp/v2/posts?lang=it&status=publish&per_page=20&after={after}&_fields=id,date"
    req = urllib.request.Request(url, headers={"User-Agent": "MDP-Reel-Builder/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return [str(p["id"]) for p in json.loads(r.read())]


def main():
    site = sys.argv[1]
    forced = sys.argv[2].strip() if len(sys.argv) > 2 and sys.argv[2].strip() else None
    reels = os.path.join(site, "reels")
    os.makedirs(reels, exist_ok=True)
    mpath = os.path.join(site, "reels.json")
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    changed = False

    todo = [forced] if forced else [p for p in posts_recent() if p not in manifest]
    for pid in todo:
        try:
            subprocess.run([sys.executable, os.path.join(HERE, "build_reel.py"), pid, reels], check=True)
            manifest[pid] = dt.date.today().isoformat()
            changed = True
            print("reel creato", pid)
        except subprocess.CalledProcessError as e:
            print("reel NON creato", pid, e, file=sys.stderr)

    limit = (dt.date.today() - dt.timedelta(days=KEEP_DAYS)).isoformat()
    for pid, day in list(manifest.items()):
        if day < limit:
            for ext in ("mp4", "jpg"):
                f = os.path.join(reels, f"{pid}.{ext}")
                if os.path.exists(f):
                    os.remove(f)
            del manifest[pid]
            changed = True

    json.dump(manifest, open(mpath, "w"), indent=1, sort_keys=True)
    open(os.path.join(site, ".nojekyll"), "w").close()
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as fh:
            fh.write(f"changed={'true' if changed else 'false'}\n")


if __name__ == "__main__":
    main()
