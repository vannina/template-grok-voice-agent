# Catalogue & architecture — Gamme d'agents vocaux IA Corsica Studio

> Rédigé le 2026-07-01. Objectif : structurer la **gamme d'agents vocaux vendables**
> par Corsica Studio et leur **architecture commune**, en réutilisant le socle
> `template-grok-voice-agent`. Complète l'architecture du standard perso de Vannina
> (`ARCHITECTURE-STANDARD-IA-CS-CD.md`).

Principe : **un seul moteur, des agents configurables par client/secteur.** Chaque
agent = un dossier de config (persona + base de connaissances + tools + agenda) sur le
même runtime. On vend de la **configuration + déploiement + suivi**, pas du dev à chaque
fois.

Stack figée : Twilio · xAI grok-voice · Composio (Google Calendar) · n8n · Claude ·
Airtable · Resend · Telegram. Pas de Zapier/Make. Déploiement VPS Hostinger + Traefik.

---

## 1. Socle technique commun (réutilisé par tous les agents)

- **Inbound (appel reçu)** : numéro Twilio → webhook `/twilio/voice` → (option IVR) →
  `/twilio/stream` → relais audio ↔ xAI grok-voice (µ-law 8 kHz, FR) → tools
  server-side. **Déjà en place.**
- **Config par agent** : dossier `web/config/<agent>/` (`system_prompt.txt`,
  `tools.json`, `business.json`, `profile.json`). Résolu par Host (sous-domaine) ou
  paramètre. **Pattern déjà en place (métiers).**
- **Identification appelant + accueil personnalisé** : capture `From=` (fait) + lookup
  Airtable `Contacts` → accueil nominatif. **Standard sur tous les agents** (voir règle
  11 mémoire UX + §5bis archi standard).
- **Prise de RDV** : Composio Google Calendar (`book_appointment`, `check_availability`).
- **CRM / log** : Airtable (appels, contacts, RDV, qualif, messages).
- **Notifications** : n8n → Telegram (temps réel) + Resend (email confirmation) +
  option SMS Twilio. Digest quotidien.
- **Canaux** : **voix** (téléphone) ET **chat** (même cerveau exposé en texte via Claude
  API → widget sur le site Framer). Offre combo.
- **Légal (tous)** : annonce enregistrement + l'agent déclare être une IA ; RGPD.

### Inbound vs Outbound
- **Inbound** (l'agent reçoit) : secrétariat, réservation, prise de commande, support,
  pré-qualif. Socle ci-dessus.
- **Outbound** (l'agent appelle) : relances/campagnes. Twilio **outbound** déclenché par
  n8n (liste Airtable) → l'app compose et déroule un script → log résultat. Brique en
  plus à construire (déclencheur n8n + endpoint d'appel sortant).

---

## 2. Catalogue des agents

### A. Secrétariat / Assistante IA (« standard qui ne rate plus un appel ») — INBOUND
- **Cible** : artisans, professions libérales, PME, commerces — toute structure qui rate
  des appels. **Le plus gros marché.**
- **Déclencheur** : renvoi du fixe/mobile vers le numéro Twilio sur non-réponse.
- **Fait** : décroche, identifie l'appelant, renseigne (horaires, services, adresse),
  prend RDV, prend message, qualifie le besoin, propose un rappel, notifie le pro.
- **Tools** : `identify_caller`, `get_infos`, `book_appointment`, `check_availability`,
  `take_message`, `qualify_lead`, `request_callback`, `end_call`.
- **KPI vendeur** : 0 appel manqué, RDV pris 24/7, +CA récupéré.

### B. Réservation / prise de RDV sectorielle — INBOUND
- **Cible** : resto, hôtel, médical/dentaire, immobilier, artisan, coach, beauté (les **7
  démos existantes**).
- **Fait** : réservation/RDV de vive voix, infos services, confirmation.
- **Tools** : `book_appointment`, `check_availability`, `get_infos`, `identify_caller`,
  `end_call`. Agenda Composio par client.
- **Statut** : démos déjà en ligne (`/demo-agent-vocal*`) — base de vente prête.

### C. Prise de commande — INBOUND
- **Cible** : restauration rapide, click & collect, pizzerias, traiteurs.
- **Fait** : prend la commande (menu = base de connaissances), calcule le total, propose
  les extras, fixe l'heure de retrait, enregistre + notifie la cuisine.
- **Tools** : `get_menu`, `add_item`, `summarize_order`, `schedule_pickup`,
  `identify_caller` (carnet d'habitués → « comme d'habitude ? »), `end_call`.
- **Intégrations** : Airtable commandes + ticket cuisine (impression/Telegram).
- **KPI** : commandes prises en heure de pointe sans mobiliser le personnel.

### D. Support N1 / FAQ vocale — INBOUND
- **Cible** : services clients TPE/PME, SAV, syndics, associations.
- **Fait** : répond aux questions courantes depuis une base de connaissances,
  qualifie/route, escalade en message si hors périmètre.
- **Tools** : `search_kb`, `take_message`, `qualify_lead`, `request_callback`,
  `identify_caller`, `end_call`.

### E. Pré-qualification de leads entrants — INBOUND
- **Cible** : agences, courtiers, prestataires B2B avec flux d'appels.
- **Fait** : qualifie (besoin, budget, délai, décideur), score, route les chauds,
  prend RDV avec le commercial.
- **Tools** : `qualify_lead`, `book_appointment`, `check_availability`,
  `identify_caller`, `end_call`. Écrit le scoring dans Airtable/CRM.

### F. Relances & campagnes sortantes — OUTBOUND
- **Cible** : tous secteurs (no-show, avis Google, paiements, rappels RDV, réactivation).
- **Fait** : appelle une liste, déroule un script, recueille la réponse, met à jour le
  CRM, reprogramme si besoin.
- **Brique** : Twilio outbound + déclencheur n8n (liste Airtable + horaires autorisés) +
  endpoint d'appel sortant dans l'app. **À construire** (nouveau vs inbound).
- **Légal** : respecter horaires d'appel, opposition (Bloctel), consentement.

### G. Chatbot site (canal texte, même cerveau) — OMNICANAL
- **Cible** : tous les clients ayant déjà un agent vocal (upsell) + le site CS/CD.
- **Fait** : le persona + base de connaissances + tools de l'agent vocal, exposés en
  **chat** sur le site (composant Framer → backend Claude API). Prend RDV, qualifie,
  répond.
- **Argument** : 1 cerveau, 2 canaux (voix + chat), cohérence totale.

---

## 3. Packaging / offre (à affiner dans le benchmark #9)
- **Modèle recommandé** : service productisé. **Frais de mise en place** (config +
  base de connaissances + déploiement + numéro) + **abonnement mensuel** (hébergement
  VPS + maintenance + suivi + minutes). Prix **toujours en fourchette, HT**.
- **Suivi client léger** : interface Airtable (appels, RDV, messages, contacts) — pas un
  SaaS à coder. SaaS seulement après ~10-15 clients (récolte de la config commune).
- **Aides corses** à intégrer aux devis : Chèque Numérique Corsica, CII, Impresa Sì/ADEC.
- **Combo** : agent vocal + chatbot site = package « présence 24/7 ».

---

## 4. Roadmap produit
- **P1** — Industrialiser le socle : générateur de config par client (dossier
  `<agent>/`), table `Contacts` + `identify_caller`, notifications n8n standard.
- **P2** — Décliner les agents inbound A→E depuis le socle (prompts + tools + KB types).
- **P3** — Brique **outbound** (F) : Twilio sortant + n8n + horaires/Bloctel.
- **P4** — **Chatbot site** (G) : composant Framer + backend Claude partagé.
- **P5** — Portail client (interface Airtable) + offres packagées + page de vente.

---

## 5. À confirmer avec Vannina
1. Priorité de mise sur le marché : Secrétariat (A) d'abord ? (reco : oui, plus gros
   marché + déjà 80% construit avec ton standard perso).
2. Outbound (F) maintenant ou phase 2 ? (légal Bloctel à cadrer).
3. Voix unique ou voix par secteur/marque.
4. Niveau de personnalisation de la base de connaissances par client (scraping site +
   menu + FAQ) inclus dans le setup ou en option.
5. Bornes de prix (setup + abonnement) à fixer avec le benchmark (#9).

---

### Lien avec l'existant
- Réutilise **intégralement** `template-grok-voice-agent` (relais Twilio, tools,
  config par segment, Composio, auto-hangup, numéro masqué, caller-ID).
- L'agent **Secrétariat (A)** = même brique que le **standard perso CS/CD** de Vannina
  (`ARCHITECTURE-STANDARD-IA-CS-CD.md`) → on construit une fois, on templatise.
- Démos sectorielles (B) déjà en ligne = vitrine de vente.
