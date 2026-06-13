"""Vérif S2 — structure des 6 packs métier + dump du rédactionnel visible."""
import json
from pathlib import Path

BASE = Path("web/config/metiers")
METIERS = ["hotel", "medical", "immobilier", "artisan", "coach", "beaute"]
TOOL_OK = {"get_business_info", "check_availability", "book_reservation", "end_call"}
PROFILE_KEYS = ["agent","agent_initial","agent_role","secteur","objet","cta_label",
    "hero_title","hero_accent","hero_sub","chip_1","chip_2","chip_3","card1_title",
    "card1_bullets","conversion_title","conversion_text","mailto_subject","bubbles",
    "info_label","recap_title","event_summary_label","calendar_note","greeting_instruction"]

print("==== STRUCTURE ====")
for m in METIERS:
    d = BASE / m
    issues = []
    # profile.json
    try:
        prof = json.loads((d / "profile.json").read_text(encoding="utf-8"))
        miss = [k for k in PROFILE_KEYS if k not in prof]
        if miss: issues.append(f"profile manque: {miss}")
        for f in ("home_name","home_tag","call_header","calendar_id"):
            if prof.get(f) not in ("", None): issues.append(f"{f} non vide: {prof.get(f)!r}")
        if not isinstance(prof.get("bubbles"), dict): issues.append("bubbles pas dict")
    except Exception as e:
        issues.append(f"profile.json INVALIDE: {e}"); prof = {}
    # tools.json
    try:
        tools = json.loads((d / "tools.json").read_text(encoding="utf-8"))
        names = {t.get("name") for t in tools}
        if not names <= TOOL_OK: issues.append(f"noms d'outils hors liste: {names - TOOL_OK}")
        if "book_reservation" not in names: issues.append("book_reservation absent")
    except Exception as e:
        issues.append(f"tools.json INVALIDE: {e}")
    # system_prompt.txt
    try:
        sp = (d / "system_prompt.txt").read_text(encoding="utf-8")
        if "—" in sp: issues.append(f"TIRET CADRATIN présent ({sp.count(chr(8212))}x)")
        if "{{TODAY}}" not in sp: issues.append("{{TODAY}} absent")
        if "get_business_info" not in sp: issues.append("get_business_info non cité")
        if "R1" not in sp or "R2" not in sp: issues.append("R1/R2 absent")
        if "end_call" not in sp: issues.append("end_call absent")
        if m == "medical" and "15" not in sp: issues.append("médical: orientation 15 absente")
    except Exception as e:
        issues.append(f"system_prompt INVALIDE: {e}")
    # cadratin dans profile (valeurs str)
    if prof:
        cad = [k for k,v in prof.items() if isinstance(v,str) and "—" in v]
        if cad: issues.append(f"cadratin dans profile: {cad}")
    print(f"\n[{m}] " + ("OK ✅" if not issues else "⚠️  " + " | ".join(issues)))

print("\n\n==== RÉDACTIONNEL VISIBLE (à relire) ====")
for m in METIERS:
    try:
        p = json.loads((BASE / m / "profile.json").read_text(encoding="utf-8"))
    except Exception:
        continue
    print(f"\n----- {m.upper()} ({p.get('agent')}) -----")
    print(f"  hero      : {p.get('hero_title')}  /  {p.get('hero_accent')}")
    print(f"  hero_sub  : {p.get('hero_sub')}")
    print(f"  cta       : {p.get('cta_label')}   |  home_btn2: {p.get('home_btn_secondary')}")
    print(f"  chips     : 1){p.get('chip_1')}  2){p.get('chip_2')}  3){p.get('chip_3')}")
    print(f"  card1     : {p.get('card1_title')}")
    print(f"     bullets: {p.get('card1_bullets')}")
    print(f"  conv_titre: {p.get('conversion_title')}")
    print(f"  conv_texte: {p.get('conversion_text')}")
    print(f"  showcase  : {p.get('showcase_title')} / {p.get('showcase_sub')}")
    print(f"  recap     : {p.get('recap_title')} | unit={p.get('recap_unit')!r} | {p.get('recap_note')}")
    print(f"  greeting  : {p.get('greeting_instruction')}")
    print(f"  meta_title: {p.get('meta_title')}")
    print(f"  meta_desc : {p.get('meta_description')}")
