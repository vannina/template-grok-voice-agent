# PROSPECTION IA — Corsica Studio (/CS)

Agent et pipeline de prospection B2B pour Corsica Studio.
Conçu le 2026-07-01. Cadre légal de référence : loi n°2025-594 applicable au 11/08/2026.

> Périmètre strict : ce document couvre **/CS uniquement** (digital, web, IA, automatisation). La partie /CD (architecture intérieure) est traitée en section séparée 1.2 et ne se mélange jamais avec /CS.

---

## 0. Garde-fous légaux (à lire en premier)

La conception entière découle de ces règles. Aucune brique du pipeline ne doit les contourner.

| Canal | Régime au 11/08/2026 | Conséquence design |
|---|---|---|
| Appel téléphonique B2C | **opt-in** (interdit sans consentement préalable), Bloctel supprimé | **Jamais d'appel B2C.** L'agent vocal n'appelle que des numéros professionnels. |
| Appel téléphonique B2B | **opt-out** (intérêt légitime) si l'objet est lié à l'activité du pro + droit d'opposition immédiat | Appel autorisé vers un pro, sur sujet pro, avec opposition annoncée et respectée en direct. |
| Cold email B2B | Légal si identité émetteur + finalité + lien de désinscription | Réutilisation de WF-06a, déjà conforme. |

**Règles non négociables baked-in dans chaque brique :**

1. **B2B uniquement.** Cible = professionnels (artisans, commerçants, PME), sur des sujets liés à leur activité. Jamais de particulier.
2. **L'agent déclare être une IA** (réutilise R2 de l'app existante, déjà injecté par `_runtime_rules()`).
3. **Annonce d'enregistrement** si l'appel est enregistré (déjà injecté par `_runtime_rules()`).
4. **Droit d'opposition immédiat** annoncé en ouverture d'appel et exécuté sur-le-champ (raccrochage + marquage `ne_pas_contacter`).
5. **Secteurs interdits, exclus même avec consentement** : rénovation énergétique, panneaux solaires / photovoltaïque, adaptation du logement. Filtrés au sourcing (liste NACE/mots-clés d'exclusion) ET au scoring.
6. Pas de scraping massif de plateformes (LinkedIn, Maps). Sourcing via sources publiques / API autorisées, lignée (URL + date) conservée pour chaque contact.

---

## 1. Objectif & périmètre

### 1.1 /CS — cible commerciale active

**Objectif** : alimenter le pipeline commercial de Corsica Studio en RDV qualifiés, en automatisant le sourcing, le scoring, l'approche multicanal et la prise de RDV, sans intervention manuelle sauf décision critique.

**Cibles B2B /CS** : artisans, commerçants, hôteliers, PME — Corse, France, Europe.
**Offre vendue** : agents vocaux IA sur-mesure, automatisation n8n, sites Framer, IA appliquée.
**Signal d'achat prioritaire** : établissement qui rate des appels (horaires, affluence), pas de prise de RDV en ligne, site daté ou inexistant, avis clients mentionnant joignabilité.

**Disqualifiants** : secteurs interdits (cf. 0.5), pro déjà équipé d'un standard IA, opposition exprimée, hors zone, structure trop petite (auto-entrepreneur sans flux d'appels).

### 1.2 /CD — nurturing prescripteurs (séparé, pas de cold call)

**Objectif** : entretenir une relation longue avec les prescripteurs de Corsica Design.
**Cibles** : promoteurs, agences immobilières, architectes, prescripteurs.
**Motion** : nurturing relationnel (LinkedIn + email B2B sur intérêt légitime), **pas d'appel vocal de prospection à froid**. Rythme lent, contenu de référence, RDV qualitatif.
**Cloisonnement** : base Airtable distincte, séquences distinctes, expéditeur distinct. Aucune fusion avec le pipeline /CS.

---

## 2. Architecture du pipeline

```
                       PIPELINE PROSPECTION B2B /CS
  ┌──────────────────────────────────────────────────────────────────────┐
  │                                                                        │
  │  [1] SOURCING            [2] SCORING           [3] SÉQUENCE MULTICANAL │
  │  ┌───────────────┐      ┌──────────────┐      ┌──────────────────────┐│
  │  │ Apify / MCP   │      │ Claude scorer│      │ Email B2B (WF-06a)    ││
  │  │ prospecting   │ ───► │ firmo +      │ ───► │ LinkedIn (manuel/semi)││
  │  │ + sources pub │      │ intention    │      │ Appel vocal B2B       ││
  │  │ + exclusions  │      │ → Hot/Warm/  │      │   (WF-OUT, Twilio)    ││
  │  └───────┬───────┘      │   Cold/Skip  │      └──────────┬───────────┘│
  │          │              └──────┬───────┘                 │            │
  │          │                     │                         ▼            │
  │          │                     │              [4] QUALIFICATION       │
  │          ▼                     ▼              ┌──────────────────────┐│
  │  ┌─────────────────────────────────────┐     │ Agent vocal qualifie ││
  │  │            AIRTABLE CRM /CS          │◄────┤ besoin / budget /    ││
  │  │  base prospects + lignée + statut    │     │ décideur / timing    ││
  │  │  + demo_* + opposition + scoring     │     └──────────┬───────────┘│
  │  └─────────────────┬───────────────────┘                │            │
  │                    ▲                                     ▼            │
  │                    │                          [5] PRISE DE RDV       │
  │                    │                          ┌──────────────────────┐│
  │                    └──────────────────────────┤ Composio Google Cal  ││
  │                       (event_id, statut RDV)   │ (book_rdv)           ││
  │                                                └──────────────────────┘│
  └──────────────────────────────────────────────────────────────────────┘

  Boucle de relance : tant que ni RDV ni opposition → relance email/LinkedIn
  programmée par n8n, escalade vers appel vocal sur les leads Hot.
```

**Flux de décision (par prospect)**
```
SOURCING → enrichissement (SIRET, NAF, site, avis, tel pro)
  ↓
FILTRE EXCLUSION → secteur interdit ? hors B2B ? opposition connue ? → SKIP
  ↓
SCORING → firmographique (taille, secteur, zone) + intention (signaux) → Hot/Warm/Cold
  ↓
SÉQUENCE → email B2B (toutes cibles) ; LinkedIn (si décideur identifié) ;
           appel vocal réservé aux Hot avec tel pro vérifié
  ↓
QUALIFICATION → l'agent vocal ou la réponse email qualifie BANT léger
  ↓
RDV → Composio Calendar, sinon relance, sinon clôture/opposition
  ↓
CRM → tout est journalisé dans Airtable (lignée + statut + horodatage)
```

---

## 3. L'agent vocal de prospection B2B (WF-OUT)

Réutilise le moteur existant (relais Twilio ↔ xAI Grok Voice, `_server_tool_call`, Composio Calendar, R1/R2). La nouveauté est le **sens sortant** (outbound) et un prompt de qualification, pas un nouveau moteur.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AGENT — Prospecteur vocal B2B /CS
Type : Autonome court (1 appel = 1 objectif : qualifier + proposer RDV)
Modèle : grok-voice-think-fast-1.0 (xAI realtime), voix FR
Déclencheur : n8n WF-OUT (Twilio outbound API), pas d'auto-déclenchement par l'agent
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 3.1 Comment il appelle

- **Déclenchement** : n8n WF-OUT sélectionne un lead **Hot** avec `tel_pro` vérifié et `opposition = false`, puis lance un appel via l'**API Twilio outbound** (`POST /Calls`, `Url` pointant vers `/twilio/voice` de l'app demo-voice, paramètre `metier=prospection`). Le relais WS existant prend le relais.
- **Horaires autorisés** : appels uniquement en horaires ouvrés pro (lun–ven 9h30–12h30 / 14h–18h, Europe/Paris), gérés par le cron WF-OUT + un garde-fou serveur. Jamais le week-end, jamais hors plage.
- **Ouverture obligatoire (4 éléments en 1 phrase)** : identité (Corsica Studio), finalité (sujet lié à leur activité), **déclaration IA**, **droit d'opposition immédiat**. Exemple de tournure : « Bonjour, ici l'assistant IA de Corsica Studio. Je vous appelle au sujet de la prise de rendez-vous de votre établissement. Cet appel peut être enregistré, et si vous préférez ne pas être contacté, dites-le moi, je raccroche tout de suite. »
- **Opposition** : si le pro s'oppose, l'agent remercie, raccroche (`end_call`), et l'outil `marquer_opposition` écrit `opposition = true` + `ne_pas_contacter = true` dans Airtable. Aucune relance ultérieure, tous canaux.
- **Numéro masqué** : non applicable en sortant ; le CallerID est un numéro pro Corsica Studio identifiable.

### 3.2 Outils de l'agent (handlers à ajouter dans `voice.js` FUNCTIONS **et** `_server_tool_call`)

```
━━━ OUTIL 1 — get_offre_info ━━━
Rôle : renvoie le pitch /CS adapté au secteur du prospect (pas d'invention de prix fixe).
Retour : { secteur, douleur_type, preuve, fourchette_prix_HT }
Garde R1 : ne jamais inventer un tarif hors fourchette.

━━━ OUTIL 2 — qualifier_lead ━━━
Rôle : enregistre les réponses BANT (besoin, budget indicatif, décideur, timing).
Retour : { score_qualif, statut } écrit dans Airtable.

━━━ OUTIL 3 — check_availability (existant, réutilisé) ━━━
Rôle : créneaux RDV commercial sur le calendrier "Prospection /CS".

━━━ OUTIL 4 — book_rdv (variante de book_reservation) ━━━
Rôle : pose le RDV commercial via Composio GOOGLECALENDAR_CREATE_EVENT.
Payload construit côté serveur (garde anti-hallucination déjà en place).
Retour : { status: confirmed/error, event_id, start }

━━━ OUTIL 5 — marquer_opposition ━━━
Rôle : opt-out immédiat. Écrit opposition=true + ne_pas_contacter=true (Airtable via webhook n8n).
Déclenchement : dès que le pro refuse / demande à ne plus être contacté.

━━━ OUTIL 6 — end_call (existant) ━━━
Rôle : raccroche proprement (filet auto-hangup déjà présent).
```

> Règle de synchronisation app : chaque nouvel outil = handler dans `web/static/voice.js` (FUNCTIONS) **et** dans `web/server.py` (`_server_tool_call`) + bulles UI. Sans quoi le chemin Twilio échoue.

### 3.3 Script de qualification (trame)

1. Ouverture conforme (identité + finalité + IA + opposition).
2. Accroche sectorielle : une observation liée à leur activité (« beaucoup d'établissements comme le vôtre ratent des appels en plein service »).
3. Question de besoin : « Quand vous êtes en plein rush, qui répond au téléphone ? »
4. Qualification légère : besoin réel ? qui décide ? horizon ?
5. Bascule valeur : un agent vocal qui répond et prend les RDV 24/7.
6. Ask unique : proposer un créneau de démo/échange (book_rdv).

### 3.4 Gestion des objections

| Objection | Réponse cadrée |
|---|---|
| « C'est un robot ? » | « Oui, je suis l'assistant IA de Corsica Studio » (R2, obligatoire). |
| « Pas le temps » | « Une minute : je vous propose juste un créneau, vous voyez si ça vaut le coup. » |
| « On a déjà quelqu'un » | « Justement, l'agent prend le relais quand la ligne est occupée. » |
| « Pas intéressé » | Remercier → `end_call` (pas d'insistance). |
| « Ne me rappelez plus » | `marquer_opposition` immédiat → raccrochage. |

### 3.5 Passage de relais

- **RDV pris** → `book_rdv` confirme, l'agent récapitule date/heure, Airtable passe en `RDV pris`, notification Telegram à Vannina (WF-13 réutilisé/étendu).
- **Intéressé sans créneau** → statut `À recontacter`, déclenche un email de suivi (WF-06a, séquence dédiée).
- **Pas joignable / répondeur** → statut `Sans réponse`, replanification (max N tentatives), puis bascule email.

---

## 4. Séquences

### 4.1 Séquence email B2B — 4 touches (structure, pas le copy complet)

Réutilise WF-06a (moteur déterministe, conforme : identité + finalité + désinscription). Personnalisation par secteur via le gabarit existant.

| Touche | Jour | Objet (style sobre) | Structure | Angle |
|---|---|---|---|---|
| 1 | J0 | `appels manqués` | Observation sectorielle → problème → preuve → ask démo (lien `?lead=`) | Joignabilité |
| 2 | J3 | `réservations en ligne` | Nouvel angle : RDV/résa loupés hors horaires | Manque à gagner |
| 3 | J7 | `démo 2 min` | Lien démo personnalisé + une preuve chiffrée | Friction zéro |
| 4 | J12 | `je referme` | Email de clôture (breakup), porte laissée ouverte | Dernière touche |

- **Personnalisation par secteur** : variable `{secteur}` pilote douleur + preuve (restaurant = service, médical = standard saturé, salon = no-show, artisan = appels en chantier, immo = visites, auto-école = inscriptions, club sport = adhésions).
- **CTA unique** : lien démo `?lead={record_id}` → attribution automatique (usage.jsonl → WF-13 → Airtable `demo_*`).
- Désinscription en pied, expéditeur identifié (Resend + DNS OVH déjà configurés).

### 4.2 Trame d'appel B2B

Voir 3.3 (script) + 3.4 (objections). L'appel n'intervient que sur les **Hot** déjà touchés par email/LinkedIn (réchauffés), jamais en premier contact aveugle.

### 4.3 LinkedIn (semi-manuel, pas de scraping)

Touche de connexion + 1 message de relance sur les décideurs identifiés (Tier 1/2). Observation spécifique liée à un signal réel. Pas d'automatisation de masse (ToS).

---

## 5. Conformité — checklist B2B opt-out

- [ ] **B2B only** : tout lead a un SIRET / statut pro vérifié ; aucun particulier.
- [ ] **Secteurs interdits exclus** : rénovation énergétique, photovoltaïque/panneaux solaires, adaptation logement — filtrés au sourcing (codes NAF + mots-clés) et bloqués au scoring.
- [ ] **Objet lié à l'activité** du pro (intérêt légitime caractérisé).
- [ ] **Appel** : identité + finalité + déclaration IA + droit d'opposition annoncés en ouverture.
- [ ] **Opposition immédiate** respectée en direct → `marquer_opposition` → `ne_pas_contacter`, tous canaux.
- [ ] **Enregistrement** : annoncé si l'appel est enregistré (`_runtime_rules()`).
- [ ] **Horaires** : appels en plage ouvrée pro uniquement.
- [ ] **Email** : identité émetteur + finalité + lien de désinscription (WF-06a conforme).
- [ ] **RGPD** : base légale = intérêt légitime B2B ; lignée (source URL + date) conservée par contact ; registre des oppositions tenu dans Airtable ; durée de conservation définie ; mention info/contact DPO.
- [ ] **Pas de scraping massif** de plateformes ; sources publiques / API autorisées.

---

## 6. Intégration n8n

| Workflow | Statut | Rôle |
|---|---|---|
| **WF-06a** (`HlC0xKnEZjsrx2oH`) | Existant, réutilisé | Moteur cold email B2B, séquences sectorielles, lien `?lead=`. Ajout d'une séquence "prospection /CS" + "nurturing /CD" (bases distinctes). |
| **WF-06b** | Existant, réutilisé | Digest quotidien (envois, démos, RDV). Enrichi des KPIs prospection. |
| **WF-13** | Existant, étendu | Attribution démo → Airtable `demo_*` + Telegram. Étendu pour notifier RDV pris + opposition. |
| **WF-SCORING** (nouveau) | À construire | Reçoit le sourcing brut, applique filtre exclusion + scoring Claude (firmo + intention), écrit Hot/Warm/Cold/Skip dans Airtable. |
| **WF-OUT** (nouveau) | À construire | Sélectionne Hot + `tel_pro` + non-opposé, vérifie horaire ouvré, lance l'appel via Twilio outbound API vers `/twilio/voice?metier=prospection`, log dans `usage.jsonl`. |
| **WF-SOURCE** (nouveau) | À construire | Sourcing Apify / MCP prospecting + enrichissement (SIRET/NAF/site/avis/tel pro), dédoublonnage, lignée. |

**Données Airtable (base /CS, distincte de la base /CD)** — champs clés à ajouter au schéma prospect existant :
- Identité : `nom`, `secteur`, `naf`, `siret`, `zone`, `site`, `tel_pro`, `email_pro`, `linkedin_decideur`
- Sourcing/lignée : `source_url`, `date_source`, `confiance` (High/Medium/Low)
- Scoring : `score` (Hot/Warm/Cold/Skip), `signal_intention`, `score_qualif` (BANT)
- État séquence : `statut` (À contacter / Emailé / Démo lancée / Appelé / RDV pris / À recontacter / Sans réponse / Clos)
- Tracking (existant) : `demo_lancee`, `demo_date`, `demo_etape`, `demo_count`
- Conformité : `opposition` (bool), `ne_pas_contacter` (bool), `date_opposition`, `rdv_event_id`

---

## 7. KPIs & plan de réalisation

### 7.1 KPIs

| Métrique | Cible indicative |
|---|---|
| Taux de réponse email B2B | 3–8 % |
| Taux de clic démo (`?lead=`) | 5–12 % des ouvreurs |
| Taux de jointure appel (décroché) | 25–40 % des Hot appelés |
| Taux de qualification en appel | ≥ 40 % des décrochés |
| RDV pris / 100 leads Hot travaillés | 5–10 |
| Taux d'opposition | suivi (signal de ciblage à corriger si élevé) |
| Coût / lead qualifié | API voix + email + sourcing, suivi via `usage.jsonl` + digest WF-06b |

### 7.2 Plan par étapes

1. **Étape 1 — Base & conformité** : créer la base Airtable /CS (schéma §6), liste d'exclusion secteurs interdits, registre opposition. Cloisonner /CD.
2. **Étape 2 — Sourcing** : construire WF-SOURCE (Apify/MCP + enrichissement + dédoublonnage + lignée).
3. **Étape 3 — Scoring** : construire WF-SCORING (filtre exclusion + scorer Claude). Valider sur un échantillon.
4. **Étape 4 — Email** : brancher la séquence prospection /CS sur WF-06a (4 touches §4.1), tester rendu réel via Resend.
5. **Étape 5 — Agent vocal sortant** : ajouter `metier=prospection` (prompt + tools.json), coder les outils 1/2/5 dans `voice.js` ET `_server_tool_call`, calendrier "Prospection /CS".
6. **Étape 6 — WF-OUT** : Twilio outbound + garde-fou horaires + sélection Hot. Tests à blanc (numéro perso) avant prod.
7. **Étape 7 — Boucle & mesure** : relances automatiques, KPIs dans WF-06b, itération ciblage.

---

## 8. Réutilisation vs à construire

### Déjà en place (réutiliser)
- **WF-06a** cold email B2B (campagne 867 restaurateurs en prod) — moteur conforme, séquences sectorielles, lien `?lead=`.
- **WF-06b** digest quotidien ; **WF-13** attribution démo (Airtable `demo_*` + Telegram).
- **App relais Twilio ↔ xAI** : `/twilio/voice`, `/twilio/stream`, `_server_tool_call`, hot-reload config, R1/R2 (déclaration IA + enregistrement) déjà injectés.
- **Composio Google Calendar** : `check_availability` + `book_reservation` (à dériver en `book_rdv`).
- **Tracking** : `usage.jsonl`, attribution `?lead=`, agrégation `/usage`.
- **Déploiement** : VPS 168.231.83.45, conteneur `demo-voice` multi-sous-domaines via Traefik, déploiement rsync vers `/opt/demo-voice`.

### À construire
- **Twilio outbound** (WF-OUT) : sens sortant + garde-fou horaires + ouverture conforme + `marquer_opposition`.
- **WF-SCORING** : filtre exclusion secteurs interdits + scoring firmo/intention (Claude).
- **WF-SOURCE** : sourcing Apify/MCP + enrichissement + lignée.
- **Métier `prospection`** dans l'app : `system_prompt.txt` (script qualif §3.3), `tools.json`, outils `get_offre_info` / `qualifier_lead` / `marquer_opposition` / `book_rdv` dans les deux chemins.
- **Schéma Airtable /CS** étendu (§6) + base /CD séparée.

---

*Source de vérité technique : `template-grok-voice-agent/CLAUDE.md` et `docs/TRACKING-DEMO.md`. Ne pas re-dériver l'architecture moteur ici.*
