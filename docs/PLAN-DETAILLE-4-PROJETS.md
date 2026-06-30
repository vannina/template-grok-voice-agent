# Plan détaillé — les 4 projets agents IA Corsica Studio

> Plan opérationnel granulaire. Pour chaque projet : objectif, réutilisation, à construire,
> blocages (V), puis sprints avec **sous-items détaillés** (étape technique · qui · critère
> de validation). `(V)` Vannina, `(C)` Claude. Complète CHECKLIST-SPRINTS (vue cases) et
> PLAN-MAITRE (vue stratégie). Standards transverses : annonce IA + enregistrement,
> caller-ID + accueil perso, transfert sur demande, RGPD, commit après chaque étape.

**Ordre d'exécution conseillé : Projet A → B → C → D** (réutilisation max d'abord, gros
build outbound en dernier). Prépa menée de front.

---

# PROJET A — Standard entrant CS + CD
**Objectif** : sur non-réponse du 06 51 00 30 49, l'agent décroche (Twilio 04 12 13 60 10),
route Studio/Design selon le besoin, renseigne, prend RDV/message, transfère sur demande,
notifie Vannina.
**Réutilise** : moteur Twilio↔xAI, `_server_tool_call`, config par segment, Composio Calendar,
auto-hangup, gestion numéro masqué.
**À construire** : IVR 2 branches, dossiers `entites/cs|cd`, tools manquants, 2 agendas,
Airtable, WF n8n, déploiement.
**Blocages (V)** : opérateur/délai de renvoi · choix anti-boucle transfert · infos /CD · 6 points §11.

### Sprint A.1 — Téléphonie & routage
- [ ] (V) Donner opérateur mobile + délai de renvoi → **critère** : codes de renvoi connus.
- [ ] (C) Webhook Twilio 04 12 13 60 10 → `https://standard.corsica-studio.com/twilio/voice` (POST) — **critère** : appel test renvoie le TwiML.
- [ ] (C) `/twilio/voice` : `<Say>` annonce légale (IA + enregistrement) + `<Gather dtmf numDigits=1 action=/twilio/route>` « 1 Studio / 2 Design » + `<Redirect>` si rien — **critère** : DTMF capté.
- [ ] (C) `/twilio/route` : map `Digits` 1→cs / 2→cd → `<Connect><Stream entite=… from=…>` — **critère** : la bonne entité démarre.
- [ ] (C) `WS /twilio/stream` : lire `customParameters.entite` au `start` → charger prompt/tools/agenda — **critère** : persona correct selon la touche.

### Sprint A.2 — Personas & base de connaissances (2 entités)
- [ ] (C) Créer `web/config/entites/cs/` (system_prompt, tools.json, business.json, profile.json).
- [ ] (C) Créer `web/config/entites/cd/` idem — **ne jamais fusionner /CS et /CD**.
- [ ] (V) Fournir infos /CD (services, horaires, style, zone) — **critère** : business.json CD rempli.
- [ ] (C) Persona CS (digital/IA, vouvoiement pro) + persona CD (archi, ton feutré) — règles R1/R2 (ne pas mentir sur un RDV, déclencher le booking dès les champs collectés).
- [ ] (C) `business.json` : horaires, services, zone, délais, fourchettes de prix (FAQ) par entité.

### Sprint A.3 — Tools (server-side)
- [ ] (C) `identify_caller` : lookup `From` dans Airtable Contacts → accueil nominatif.
- [ ] (C) `get_infos` : réponses ancrées dans business.json (pas d'hallucination).
- [ ] (C) `check_availability` + `book_appointment` : Composio Google Calendar, rejet téléphones placeholder.
- [ ] (C) `take_message`, `qualify_lead`, `request_callback`.
- [ ] (C) `transfer_to_human` : `<Dial>` vers ligne Vannina **seulement si** dispo (toggle) — anti-boucle.
- [ ] (C) `end_call` (auto-hangup déjà là). — **critère** : chaque tool loggé + testé unitairement.

### Sprint A.4 — Agendas, CRM, notifications
- [ ] (C) 2 agendas Composio : « RDV Corsica Studio » / « RDV Corsica Design » → `calendar_id` dans profile.json.
- [ ] (C) Airtable base « Standard IA » : tables Appels + Contacts (schéma : entite, numero, nom, intention, besoin, message, rdv, statut).
- [ ] (C) WF-Standard-Reception (n8n) : webhook fin d'appel → écrit Appel + alerte Telegram nominative.
- [ ] (C) WF-Standard-Confirmation : RDV → email Resend (appelant + Vannina).
- [ ] (C) WF-Standard-Digest : récap quotidien 21h. — **critère** : un appel test génère ligne + Telegram + email.

### Sprint A.5 — Déploiement & recette
- [ ] (V) Choix conteneur : `standard-voice` dédié (reco) ou mutualisé `demo-voice`.
- [ ] (C) `.env` (TWILIO, XAI, COMPOSIO, AIRTABLE, RESEND, TELEGRAM, calendar ids) + coffre.
- [ ] (C) Déploiement VPS (rsync /opt/standard-voice + docker compose) + Traefik sous-domaine.
- [ ] (V+C) **Recette bout en bout** : appel non décroché → IA → IVR → RDV → notif → (transfert testé).
- [ ] (V) Activer le renvoi conditionnel 06 → 04 12 13 60 10.
**DoD Projet A** : un appel réel non décroché aboutit à un RDV (ou message) tracé, Vannina notifiée, transfert fonctionnel.

---

# PROJET B — « Secrétaire générale » CS sur le site
**Objectif** : un agent vocal embarqué sur corsica-studio.com (façon démos) qui représente
Corsica Studio : renseigne, oriente, prend RDV/message, capture le lead.
**Réutilise** : moteur navigateur (voice.js, /token, /config), persona CS du Projet A (même cerveau),
caller-ID/identification.
**À construire** : config « secrétaire générale CS », intégration page site, capture lead.
**Blocages (V)** : auth API Framer (Sprint 1 global).

### Sprint B.1 — Cerveau & config
- [ ] (C) Config agent « secrétaire générale CS » (réutilise persona CS, oriente vers les offres).
- [ ] (C) Tools : `get_infos`, `book_appointment`, `qualify_lead`, `take_message`, `transfer_to_human`.
- [ ] (C) Base de connaissances CS (offres, process, cas) — **critère** : répond juste sur les offres.

### Sprint B.2 — Intégration site
- [ ] (C) Section/page vocale sur corsica-studio.com (composant Framer + app, façon démos).
- [ ] (C) UX : bouton d'appel visible, barre fixe, récap fin d'appel (règles UX mémoire).
- [ ] (C) Capture lead → Airtable + alerte Telegram.
- [ ] (V+C) Test navigateur (desktop + mobile) + publication.
**DoD Projet B** : un visiteur parle à la secrétaire générale sur le site, obtient une réponse/RDV, lead capturé.

---

# PROJET C — Pages « agents vocaux spécialisés » sur Framer (offres + démos)
**Objectif** : vitrine de vente — décliner les métiers en pages offres + démos, BTP/dépannage
en tête, hôtellerie multilingue en n°2.
**Réutilise** : 7 démos existantes, pattern config métier, offres/pricing déjà rédigées.
**À construire** : pages Framer offres, démo BTP, démo hôtellerie multilingue, CTA lead.
**Blocages (V)** : auth API Framer.

### Sprint C.1 — Niche n°1 BTP/dépannage
- [ ] (C) Config agent démo « dépannage » (persona urgences, qualif urgence vs RDV, SMS pro).
- [ ] (C) Page Framer offre + démo BTP/dépannage (micro-site sans friction).
- [ ] (C) Intégrer le pack Secrétariat IA (setup/abo HT) + CTA démo/contact → Airtable.

### Sprint C.2 — Niche n°2 hôtellerie multilingue
- [ ] (C) Config agent hôtel **multilingue FR/IT/EN/DE** (Whisper multilingue, réponses par langue).
- [ ] (C) Page Framer offre hôtellerie multilingue (argument saison + international).

### Sprint C.3 — Autres métiers + offres
- [ ] (C) Décliner beauté / resto / santé (réutiliser démos) en pages offres.
- [ ] (C) Page « gamme agents vocaux » récap (catalogue) + bundles.
**DoD Projet C** : pages offres BTP + hôtellerie en ligne avec démo jouable + CTA lead.

---

# PROJET D — Agent de prospection SDR IA (B2B) — *flagship*
**Objectif** : appelle les entreprises, propose les services CS, valide les leads, prend RDV
avec Vannina, fait de la pédagogie. **B2B opt-out only** (loi 2025-594). Dogfooding : preuve vivante.
**Réutilise** : moteur Twilio↔xAI, `_server_tool_call`, Composio, WF-06a (email), tracking.
**À construire** : Twilio **outbound**, WF-OUT, sourcing/scoring, métier `prospection`, schéma Airtable.
**Blocages (V)** : valider cibles B2B + secteurs exclus + horaires d'appel.

### Sprint D.1 — Conformité & cadrage
- [ ] (C) Checklist légale B2B opt-out : mentions identité+finalité, **opposition immédiate**, registre, RGPD.
- [ ] (C) Exclure secteurs interdits (rénovation énergétique, photovoltaïque, adaptation logement).
- [ ] (V) Valider cible (artisans/commerçants/PME) + plage horaire d'appel.

### Sprint D.2 — Sourcing & scoring
- [ ] (C) WF-SOURCE : sourcing/enrichissement (Apify/MCP) → Airtable prospects.
- [ ] (C) WF-SCORING (Claude) : firmographique (fit) + intention → score, priorisation.

### Sprint D.3 — Brique vocale outbound
- [ ] (C) Endpoint d'appel sortant dans l'app + intégration Twilio outbound.
- [ ] (C) WF-OUT (n8n) : déclenche les appels depuis la liste scorée, horaires ouvrés.
- [ ] (C) Métier `prospection` : persona SDR (propose offres CS, **pédagogie** IA, table d'objections).
- [ ] (C) Tools : `book_appointment` (RDV Vannina), `qualify_lead`, `marquer_opposition` (opt-out immédiat), `send_followup`, `end_call`.

### Sprint D.4 — Multicanal & séquences
- [ ] (C) Séquence email B2B 4 touches (réutilise WF-06a) en **pré-chauffe** avant l'appel.
- [ ] (C) Orchestration email → appel → RDV (ou relance) ; log CRM Airtable.
- [ ] (V+C) **Campagne pilote** (petit lot) + KPIs (taux réponse, RDV pris, coût/lead).
**DoD Projet D** : une liste B2B est appelée par l'agent, des leads validés, des RDV pris dans ton agenda, conforme.

---

## Suivi global
- Avancement coché dans CHECKLIST-SPRINTS-AGENTS-IA-CS.md.
- Décisions/stratégie : mémoire `strategie-agents-ia-cs`.
- Chaque étape terminée → commit/push + MAJ de ces fichiers (rien d'oublié).
- Blocages (V) toujours listés en tête de projet : ils conditionnent le démarrage du sprint.
