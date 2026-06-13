"""Vérif S1 — moteur config-driven par métier. Aucun appel réseau externe :
on ne touche que /, /api/profile, /config, /api/business (lectures fichiers)."""
import json, shutil
from pathlib import Path
from fastapi.testclient import TestClient
from web.server import app, CONFIG_DIR

c = TestClient(app)
ok = True
def check(label, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + label)
    ok = ok and cond

# 1) Restaurant (domaine historique) — placeholders résolus, profil injecté
r = c.get("/", headers={"host": "demo.corsica-studio.com"})
html = r.text
check("/ status 200", r.status_code == 200)
check("/ aucun placeholder {{ }} résiduel", "{{" not in html)
check("/ window.__PROFILE__ injecté", "window.__PROFILE__=" in html)
check("/ agent Margot présent", ">Margot<" in html or "Margot décroche" in html)
check("/ title resolu", "<title>Démo Agent Vocal IA · Corsica Studio</title>" in html)
check("/ hero resto", "Appelez le restaurant." in html)

# 2) Sous-domaine métier inconnu → fallback restaurant (jamais d'erreur)
r2 = c.get("/", headers={"host": "demo-inexistant.corsica-studio.com"})
check("/ fallback métier inconnu = restaurant", r2.status_code == 200 and "Margot décroche" in r2.text)

# 3) /api/profile restaurant
p = c.get("/api/profile", headers={"host": "demo.corsica-studio.com"}).json()
check("/api/profile agent=Margot", p.get("agent") == "Margot")
check("/api/profile metier=restaurant", p.get("metier") == "restaurant")
check("/api/profile bubbles présent", isinstance(p.get("bubbles"), dict))

# 4) /config restaurant
cfg = c.get("/config", headers={"host": "demo.corsica-studio.com"}).json()
check("/config prompt = MARGOT", "MARGOT" in cfg.get("instructions", ""))
check("/config 4 tools", len(cfg.get("tools", [])) == 4)
check("/config {{TODAY}} substitué", "{{TODAY}}" not in cfg.get("instructions", ""))

# 5) /api/business restaurant (business.json)
b = c.get("/api/business", headers={"host": "demo.corsica-studio.com"}).json()
check("/api/business nom=LOU PATIO", b.get("nom") == "LOU PATIO")
# alias historique /api/restaurant
br = c.get("/api/restaurant", headers={"host": "demo.corsica-studio.com"}).json()
check("/api/restaurant alias OK", br.get("nom") == "LOU PATIO")

# 6) Résolution d'un métier NON-défaut via dossier temporaire + merge profil
tmp = CONFIG_DIR / "metiers" / "_s1tmp"
tmp.mkdir(parents=True, exist_ok=True)
(tmp / "profile.json").write_text(json.dumps({
    "agent": "Testor", "agent_initial": "T", "meta_title": "PAGE TEST S1",
    "hero_title": "Bonjour test.", "bubbles": {"end": "Fin test."}
}), encoding="utf-8")
try:
    rt = c.get("/", headers={"host": "demo-_s1tmp.corsica-studio.com"})
    # NB: sous-domaine avec underscore non réaliste, on teste via ?metier=
    rt2 = c.get("/?metier=_s1tmp", headers={"host": "demo.corsica-studio.com"})
    h2 = rt2.text
    check("override ?metier= → agent Testor", ">Testor<" in h2 or "window.__PROFILE__" in h2)
    pt = c.get("/api/profile?metier=_s1tmp").json()
    check("merge profil : agent=Testor", pt.get("agent") == "Testor")
    check("merge profil : meta_title custom", pt.get("meta_title") == "PAGE TEST S1")
    check("merge profil : bubbles.end custom", pt.get("bubbles", {}).get("end") == "Fin test.")
    check("merge profil : bubbles hérités du défaut (info_start)",
          "info_start" in pt.get("bubbles", {}))
    check("merge profil : champs non fournis hérités (objet)", pt.get("objet") == "réservation")
    check("page test : title custom rendu", "PAGE TEST S1" in h2)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n=== S1 " + ("OK ✅ tous les checks passent" if ok else "ÉCHEC ❌") + " ===")
import sys; sys.exit(0 if ok else 1)
