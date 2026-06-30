# Architecture — Standard téléphonique IA bi-marque (Corsica Studio + Corsica Design)

> Rédigé le 2026-07-01. Objectif : quand Vannina ne décroche pas son mobile, un agent
> vocal IA prend l'appel, route vers la bonne entité (Studio ou Design), renseigne,
> prend des rendez-vous, qualifie le prospect, prend un message, et notifie Vannina.
> Réutilise au maximum l'app `template-grok-voice-agent` déjà en prod sur le VPS.

**Règle absolue : ne jamais fusionner /CS et /CD.** Deux personas, deux contextes, deux
agendas, deux bases de connaissances. L'IVR sépare dès le début.

**Règles légales (non négociables, à chaque appel) :** annoncer que l'appel est
enregistré + l'agent déclare qu'il est une IA.

---

## 1. Vue d'ensemble du flux d'appel

```
Appelant
   │  compose le 06 51 00 30 49 (numéro public, mobile Vannina)
   ▼
Mobile Vannina
   │  renvoi conditionnel (non-réponse / occupé / injoignable)
   ▼
Numéro Twilio FR  04 12 13 60 10
   │  webhook "A call comes in"
   ▼
App  POST /twilio/voice   (VPS)
   │  1) annonce légale (enregistrement + IA)
   │  2) <Gather DTMF> : « tapez 1 pour Studio, 2 pour Design »
   ▼
App  POST /twilio/route?choix=1|2
   │  <Connect><Stream> avec Parameter entite=cs|cd + from=<numéro>
   ▼
App  WS /twilio/stream
   │  charge le persona + tools + agenda de l'entité choisie
   │  relais audio ↔ xAI grok-voice (µ-law 8 kHz, FR)
   │  exécute les tools server-side (RDV, message, qualif…)
   ▼
Fin d'appel (end_call / auto-hangup)
   │  post-traitement
   ▼
n8n / Airtable / Resend / Telegram  (log + notif + confirmations)
```

---

## 2. Téléphonie & renvoi d'appel

### 2.1 Renvoi depuis le mobile (côté opérateur)
Twilio ne peut pas intercepter les appels de l'opérateur mobile : il faut un **renvoi
d'appel conditionnel** configuré sur la ligne 06 51 00 30 49 vers le **04 12 13 60 10**.

Codes GSM standard (à activer une fois depuis le mobile ; dépend de l'opérateur) :
- Non-réponse : `**61*0412136010#` (+ délai, ex. `**61*0412136010**20#` = 20 s)
- Occupé : `**67*0412136010#`
- Injoignable / éteint : `**62*0412136010#`
- Tout conditionnel d'un coup : `**004*0412136010#`

> **À confirmer (Vannina)** : opérateur mobile exact (Orange/SFR/Bouygues/Free) → les
> codes/délais peuvent varier ; certains se règlent dans l'app opérateur plutôt qu'en
> code. Décision : renvoi **toujours sur non-réponse** (24/7) ou **seulement hors
> horaires** ? (un renvoi inconditionnel `**21*` enverrait TOUT directement à l'IA).

### 2.2 Configuration Twilio du 04 12 13 60 10
- Phone Numbers → ce numéro → Voice → "A call comes in" → Webhook
  `https://standard.corsica-studio.com/twilio/voice` (HTTP POST).
- Account SID + Auth Token déjà dans le coffre (voir mémoire `acces-twilio`).
- Numéro masqué : l'app gère déjà le sentinel `anonymous` (From masqué) → l'agent
  demande explicitement le numéro pour le rappel.

---

## 3. App / runtime (réutilisation de l'existant)

L'app `template-grok-voice-agent` fait **déjà** : `/twilio/voice` (TwiML), `/twilio/stream`
(relais Twilio↔xAI), tools server-side via `_server_tool_call`, résolution multi-métier
par Host, booking Composio Google Calendar, auto-hangup. On **étend** ce socle.

### 3.1 Nouveau : IVR à 2 branches
- **`POST /twilio/voice`** (réécrit pour ce numéro) renvoie un TwiML :
  ```xml
  <Response>
    <Say language="fr-FR">Bonjour, vous êtes en relation avec l'assistant vocal de
      Vannina Michelosi. Cet appel est enregistré et vous parlez à une intelligence
      artificielle.</Say>
    <Gather input="dtmf" numDigits="1" timeout="6" action="/twilio/route" method="POST">
      <Say language="fr-FR">Pour Corsica Studio, le digital et l'intelligence
        artificielle, tapez 1. Pour Corsica Design, l'architecture d'intérieur, tapez 2.</Say>
    </Gather>
    <Redirect>/twilio/voice</Redirect>  <!-- repose la question si rien -->
  </Response>
  ```
- **`POST /twilio/route`** lit `Digits` (1→`cs`, 2→`cd`) et renvoie :
  ```xml
  <Response><Connect>
    <Stream url="wss://standard.corsica-studio.com/twilio/stream">
      <Parameter name="entite" value="cs"/>
      <Parameter name="from" value="{From}"/>
    </Stream>
  </Connect></Response>
  ```
- **`WS /twilio/stream`** : déjà en place ; on lit `customParameters.entite` au `start`
  (comme le métier aujourd'hui) → choisit le `system_prompt`, les `tools`, l'`agenda`.

### 3.2 Configuration par entité (même pattern que `web/config/metiers/<metier>/`)
Créer `web/config/entites/cs/` et `web/config/entites/cd/` avec :
- `system_prompt.txt` — persona (voir §4)
- `tools.json` — tools exposés à xAI
- `business.json` — infos (horaires, services, tarifs en fourchette, FAQ)
- `profile.json` — agenda (calendar_id), libellés, capacité, durée RDV

Résolution : `entite` (DTMF) au lieu du Host. Fallback `cs` si absent.

---

## 4. Les deux agents (personas)

| | **Agent Corsica Studio (cs)** | **Agent Corsica Design (cd)** |
|---|---|---|
| Domaine | Digital, web, IA, automatisation (Framer, n8n, Claude) | Architecture d'intérieur |
| Ton | Vouvoiement pro, dynamique, orienté solution | Vouvoiement feutré, esthétique, à l'écoute |
| Représente | Vannina / Corsica Studio | Vannina / Corsica Design |
| Ouverture | « Corsica Studio, l'assistant de Vannina. Comment puis-je vous aider ? » | « Corsica Design, l'assistant de Vannina. En quoi puis-je vous aider ? » |
| Sujets | sites, automatisations, agents IA, **formation**, audit, aides corses | projets déco/agencement, prise de besoin, visite, devis |

Structure de prompt commune (modèle OpenAI Realtime 8 sections, comme Margot) :
`Role · Personality & Tone · Unclear audio · Tools · Rules · Conversation Flow · Safety
& Escalation · Context`. Règles ABSOLUES R1 (ne jamais mentir sur un RDV → tool avant
toute confirmation) et R2 (déclencher `book_appointment` dès les champs collectés).

---

## 5. Fonctionnalités (tools server-side)

Chaque tool = handler dans `_server_tool_call` (chemin téléphone). Liste :

1. **`get_infos`** — renseignements depuis `business.json` de l'entité (services,
   horaires, zone, délais, fourchettes de prix, aides corses pour CS). Base de
   connaissances locale, pas d'hallucination.
2. **`book_appointment`** — crée un évènement Google Calendar via Composio.
   - Champs : nom, téléphone (rappel), date/heure, objet, entité.
   - Agenda : `RDV Corsica Studio` (cs) / `RDV Corsica Design` (cd) — voir §6.
   - Rejette les téléphones placeholder (`anonymous`…), comme aujourd'hui.
3. **`check_availability`** — créneaux libres (lecture agenda) avant de proposer.
4. **`take_message`** — si pas de RDV : enregistre nom + numéro + message → notif.
5. **`qualify_lead`** — capture structurée du besoin (secteur, projet, budget
   indicatif, urgence, canal de rappel préféré) → Airtable.
6. **`request_callback`** — programme un rappel (date souhaitée) → Airtable + Telegram.
7. **`get_formation_info`** (cs) — infos offres formation IA, oriente vers `/formation`.
8. **`end_call`** — raccrochage propre (auto-hangup filet de sécurité déjà présent).

> Tous les tools écrivent un évènement structuré qui alimente le post-traitement (§7).

---

## 6. Données & intégrations

### 6.1 Google Calendar (Composio)
**Décision à confirmer** : 2 agendas séparés (`RDV Corsica Studio`, `RDV Corsica
Design`) — recommandé pour la séparation /CS-/CD et des couleurs distinctes — **ou** 1
agenda partagé « Standard IA » avec préfixe `[CS]` / `[CD]`. Reco : **2 agendas**.
- `calendar_id` par entité dans `profile.json` (vide → défaut).
- Possibilité de relier l'agenda perso de Vannina pour éviter les doubles réservations
  (free/busy en lecture via `check_availability`).

### 6.2 Airtable — base « Standard IA » (CRM des appels)
Table `Appels` : `date`, `entite (CS/CD)`, `numero_appelant`, `nom`, `intention`
(infos / rdv / message / rappel / qualif), `besoin`, `budget`, `urgence`, `message`,
`rdv_pris` (date), `statut`, `enregistrement_url`, `transcript`.
Sert de tableau de bord + base de relance.

### 6.3 n8n (orchestration & notifications)
- **WF-Standard-Reception** : webhook appelé par l'app en fin d'appel → écrit la ligne
  Airtable + envoie une **alerte Telegram** nominative à Vannina
  (« 📞 [CD] Appel de +33… — RDV pris le 3 juil 14h » ou « message : … »).
- **WF-Standard-Confirmation** : si RDV → email **Resend** de confirmation à l'appelant
  (+ copie Vannina) + éventuel SMS Twilio.
- **WF-Standard-Digest** : récap quotidien (21h) des appels reçus, par entité.

### 6.4 Stack (figée Corsica) : Twilio · xAI grok-voice · Composio (calendar) · n8n ·
Claude · Airtable · Resend · Telegram. **Pas de Zapier/Make.**

---

## 7. Cycle de vie d'un appel (post-traitement)
1. Fin d'appel → l'app POST un payload récap vers n8n (`STANDARD_WEBHOOK_URL`).
2. n8n écrit Airtable + Telegram (temps réel).
3. Si RDV : Resend confirmation. Si message/rappel : Telegram + flag de relance.
4. Vannina voit tout dans Airtable + reçoit l'alerte sur Telegram.

---

## 8. Déploiement (VPS Hostinger 168.231.83.45)
- Réutilise le conteneur `demo-voice` **ou** un service dédié `standard-voice`
  (recommandé : service séparé pour isoler le standard pro de la démo commerciale).
- Sous-domaine **`standard.corsica-studio.com`** routé par Traefik (Host-based).
- `.env` (en plus de l'existant) : `STANDARD_WEBHOOK_URL`, `AIRTABLE_*`, `RESEND_*`,
  `TELEGRAM_*`, `CS_CALENDAR_ID`, `CD_CALENDAR_ID`.
- Déploiement par `rsync`/`scp` vers `/opt/standard-voice` puis `docker compose up -d
  --build`. Toute action VPS journalisée (`vps/JOURNAL.md`).

---

## 9. Sécurité, légal, qualité
- Annonce **enregistrement + IA** dès le décroché (avant l'IVR).
- RGPD : données minimales, finalité (prise de contact/RDV), conservation limitée,
  mention dispo. Pas de données sensibles.
- Whisper FR forcé (pas de dérive de langue), auto-hangup sur « au revoir ».
- Numéro masqué géré. Tests de bout en bout avant mise en prod.

---

## 10. Plan de réalisation (sprints)
- **S1 — Socle routage** : numéro Twilio + webhook + IVR 1/2 + résolution `entite` +
  2 dossiers `entites/cs|cd` (prompts + business + tools de base) + annonce légale.
- **S2 — RDV & agenda** : `book_appointment` + `check_availability` sur 2 agendas
  Composio + confirmation Resend.
- **S3 — CRM & notif** : Airtable base + WF n8n (reception, confirmation, digest) +
  Telegram + `qualify_lead` / `take_message` / `request_callback`.
- **S4 — Affinage** : personas (ton CS vs CD), base de connaissances `get_infos`,
  `get_formation_info`, gestion numéro masqué, tests réels, mise en prod VPS.
- **S5 — Renvoi mobile** : activer le renvoi conditionnel 06→04 12 13 60 10 + recette
  bout en bout (appel non décroché → IA → RDV → notif).

---

## 11. À confirmer avec Vannina (avant S1)
1. **Opérateur mobile** (codes de renvoi) + **quand renvoyer** (toujours sur
   non-réponse, ou seulement hors horaires d'ouverture ?).
2. **Agendas** : 2 séparés (reco) ou 1 partagé ? Relier l'agenda perso pour le free/busy ?
3. **Horaires** affichés/annoncés par l'agent (CS et CD).
4. **Voix** : même voix pour les 2 agents ou 2 voix distinctes (différencier les marques).
5. **Transfert “vrai”** : si Vannina redevient dispo, veut-elle un transfert d'appel
   possible, ou tout passe par message/rappel ? (par défaut : message/rappel).
6. **Conteneur** : service `standard-voice` dédié (reco) ou mutualisé avec `demo-voice`.

---

### Réutilisation directe de l'existant (gain de temps)
- Relais Twilio↔xAI, auto-hangup, gestion `From` masqué, Whisper FR : **déjà codés**.
- Pattern config par segment (`metiers/<x>/`) → transposé en `entites/<cs|cd>/`.
- Booking Composio Google Calendar : **déjà branché**, à dupliquer par agenda.
- Déploiement VPS + Traefik + `.env` + coffre : **process déjà rodé**.
