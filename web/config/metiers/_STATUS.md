# État des packs métier — socle « agent vocal par métier »

MAJ 2026-06-13. Voir l'archi dans `../../CLAUDE.md` (section Multi-métier).

Chaque métier vit dans `web/config/metiers/<metier>/` :
`profile.json` + `system_prompt.txt` + `tools.json` (+ `business.json` à ajouter).

| Métier | Agent | Fondations (profil+prompt+tools) | `business.json` | Champs établissement à remplir | Déployable |
|---|---|---|---|---|---|
| restaurant | Margot | ✅ (réf.) | ✅ Lou Patio | — | ✅ (prod) |
| hotel | Chloé | ✅ | ⏳ | home_name, home_tag, call_header, og_image, calendar_id | après business.json |
| medical | Léa | ✅ | ⏳ | idem | après business.json |
| immobilier | Clara | ✅ | ⏳ | idem | après business.json |
| artisan | Paul | ✅ | ⏳ | idem | après business.json |
| coach | Hugo | ✅ | ⏳ | idem | après business.json |
| beaute | Inès | ✅ | ⏳ | idem | après business.json |

## Pour finaliser un métier (quand Vannina donne le vrai établissement)
1. Récupérer les infos sur le site de l'établissement (comme `restaurant/business.json`)
   et écrire `metiers/<metier>/business.json` : champs adaptés au métier + une clé
   `showcase` = liste de `{ "titre": "...", "items": ["Libellé — prix", ...] }`
   pour la fiche du téléphone droit (puisque `showcase_kind` = `fiche`).
2. Remplir dans `profile.json` : `home_name`, `home_tag`, `call_header`,
   `calendar_id` (calendrier Google partagé « Démo Agent Vocal »), `og_image` si dispo.
3. Optionnel : enrichir `greeting_instruction` avec le nom de l'établissement
   (ex. « [Nom], bonjour, Chloé à votre écoute. »).
4. Tester : `METIER=<metier> uvicorn web.server:app --port 8000` puis ouvrir la page.

## Notes techniques
- Tous les prompts sont **agnostiques de l'établissement** : l'agent récupère
  toutes les données précises via `get_business_info`. R1 (ne jamais inventer) /
  R2 (réserver dès les infos réunies) conservés partout. Vouvoiement systématique.
- Outils homogènes : `get_business_info`, `check_availability`, `book_reservation`,
  `end_call`. `party_size` présent pour restaurant/hotel/coach (groupes possibles),
  absent pour medical/immobilier/artisan/beaute (1 personne par créneau).
- Médical : sécurité renforcée (orientation 15, zéro avis médical, confidentialité).
- Médical → angle « sans abonnement Doctolib » ; beauté → « sans abonnement Planity »
  (copie marketing du profil, factuel, pas dénigrant).
- Zéro tiret cadratin dans les prompts (nettoyés le 2026-06-13).

## ⚠️ Env local
Le venv `.venv` est cassé (cible Homebrew `python@3.12` disparue). Pour relancer
uvicorn en local, recréer le venv (`python3 -m venv .venv && .venv/bin/pip install -r
requirements.txt`) ou pointer un python valide. Sans impact sur le VPS (env distinct).
