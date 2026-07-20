# Runbook d'installation : nouvel agent vocal client

> Pas à pas technique pour passer d'un questionnaire d'onboarding rempli à un agent
> en service, sur l'architecture existante (app `template-grok-voice-agent`, VPS
> Hostinger 168.231.83.45, Traefik, conteneur `demo-voice`).
> Rappel discipline : **toute action VPS est consignée et horodatée dans
> `vps/JOURNAL.md`**.

Durée réaliste totale : 1,5 à 3 jours de travail étalés sur 1 à 2 semaines
(le délai vient des allers-retours client et de la recette, pas de la technique).

---

## 0. Prérequis (avant de commencer)

- ☐ Questionnaire d'onboarding validé par écrit par le client (mail).
- ☐ Contrat + DPA signés, acompte de mise en place encaissé ou facturé.
- ☐ Choisir le **slug** du client : minuscules, sans accent, court
  (ex. `coiffure-marie`). Il sert partout : dossier config, sous-domaine, agenda.
- ☐ Environnement local qui tourne : `cd template-grok-voice-agent`,
  `source .venv/bin/activate`, `uvicorn web.server:app --port 8000 --reload`.

## 1. Créer la configuration client (local)

La config vit dans `web/config/metiers/<slug>/`, 4 fichiers, résolus par Host.
On ne code pas : on duplique le métier le plus proche.

```bash
cd template-grok-voice-agent
cp -r web/config/metiers/<metier-le-plus-proche> web/config/metiers/<slug>
```

Gabarits disponibles : `restaurant` (référence), `coiffeur`, `depannage`, `artisan`,
`hotel`, `medical`, `immobilier`, `beaute`, `coach`.

Puis adapter les 4 fichiers avec le questionnaire :

1. **`system_prompt.txt`** : persona (prénom, ton, tu/vous), établissement, règles.
   - Garder la structure 8 sections (Role, Personality & Tone, Unclear audio, Tools,
     Rules, Conversation Flow, Safety & Escalation, Context).
   - **Ne jamais retirer** : l'annonce IA + enregistrement au décroché, R1 (jamais
     confirmer un RDV sans appel d'outil), R2 (déclencher l'outil dès que les champs
     sont collectés).
   - Appliquer le cahier des charges conversation
     (`docs/CAHIER-DES-CHARGES-CONVERSATION.md`) : phrases courtes, un seul bonjour,
     une question à la fois, au revoir explicite avant tout raccrochage.
   - Intégrer les interdits du client (§2 questionnaire) et les cas d'escalade
     (§5 questionnaire).
2. **`business.json`** : prestations, prix annonçables, horaires, adresse, FAQ, zone.
   Ne mettre QUE des infos validées par écrit par le client.
3. **`tools.json`** : partir du gabarit ; retirer les tools non souscrits (ex. pas de
   `book_appointment` si mode message seul). Les placeholders `${ENV_VAR}` restent
   tels quels.
4. **`profile.json`** : libellés UI/SEO (`agent`, `cta_label`, `hero_*`, bulles),
   et surtout l'agenda : `calendar_id`, `capacity_per_slot`, `slot_duration_min`,
   `event_summary_label`. Aucun secret dans ce fichier.

Rappel architecture : tout nouveau tool `function` = handler à ajouter dans
`FUNCTIONS` (`web/static/voice.js`, chemin navigateur) ET dans `_server_tool_call`
(`web/server.py`, chemin Twilio). Si on reste sur les tools existants du gabarit,
rien à coder.

## 2. Agenda (si prise de RDV souscrite)

1. Créer un Google Calendar dédié « RDV IA : <Client> » (ou utiliser celui du client
   s'il est sur Google Calendar : demander le partage en écriture au compte Composio).
2. Récupérer l'ID du calendrier (paramètres du calendrier, champ « ID »).
3. Le renseigner dans `profile.json` → `calendar_id` (vide = calendrier de démo,
   interdit en prod client).
4. Régler `slot_duration_min` et `capacity_per_slot` selon le questionnaire §6.
5. Cas Planity / Doctolib : PAS d'écriture directe. Mode dégradé assumé : l'agent
   collecte nom + téléphone + créneau souhaité, message envoyé au client qui confirme.
   Le dire tel quel dans le prompt (jamais « votre RDV est confirmé »).

## 3. Test local complet

```bash
# Override métier en local, sans DNS :
open "http://localhost:8000/?metier=<slug>"
./.venv/bin/python _s1_test.py            # smoke test rendu/config (22 checks)
```

- ☐ La page affiche les libellés du client (pas ceux du restaurant = fallback,
  signe que le dossier ou le slug est faux).
- ☐ Conversation navigateur : annonce IA + enregistrement entendue.
- ☐ Prise de RDV : l'événement apparaît dans le BON calendrier.
- ☐ Prise de message : récap correct.

## 4. Déploiement VPS (sous-domaine + routage)

Le conteneur `demo-voice` sert tous les hôtes ; le métier/client est résolu par le
header `Host` (`_resolve_metier()` dans `server.py`). Trois actions :

1. **DNS** : créer l'enregistrement A `demo-<slug>.corsica-studio.com → 168.231.83.45`
   (zone corsica-studio.com, MCP Hostinger ou panel). TTL court (300) le temps de
   l'installation.
2. **Traefik** : sur le VPS, ajouter l'hôte à la règle du service `demo-voice` dans
   `/docker/docker-compose.yml` (label `traefik.http.routers...rule=Host(...)`),
   à la suite des 7 hôtes démo existants. Vérifier que le certificat Let's Encrypt
   est bien émis au premier accès HTTPS.
3. **Fichiers** : rsync de la config (pas de git sur le VPS) :

```bash
rsync -av web/config/metiers/<slug>/ root@168.231.83.45:/opt/demo-voice/web/config/metiers/<slug>/
```

- Changement **config seule** (`web/config/*`) : le bind mount la prend en compte à
  la conversation suivante, rien à redémarrer.
- Changement **code Python ou static** (`server.py`, `voice.js`) :

```bash
ssh root@168.231.83.45
cd /docker && docker compose up -d --build demo-voice
docker logs -f demo-voice
```

- ☐ `https://demo-<slug>.corsica-studio.com` répond avec le bon profil.
- ☐ Action consignée dans `vps/JOURNAL.md` (date, heure, quoi, pourquoi).

## 5. Téléphonie : brancher le vrai numéro

Deux options. Le défaut commercial est l'option B (renvoi sur non-réponse : le client
garde son numéro, l'agent n'est qu'un relais).

### Option A : numéro Twilio dédié

1. Console Twilio : acheter un numéro FR (prévoir les exigences réglementaires
   françaises : bundle d'identité + adresse, délai possible de quelques jours).
2. Configurer le numéro : Voice → « A call comes in » → Webhook
   `https://demo-<slug>.corsica-studio.com/twilio/voice` (POST).
   **Important : utiliser le sous-domaine DU CLIENT** dans l'URL : le chemin Twilio
   résout la config via le header Host du WebSocket. Un webhook pointé sur le mauvais
   hôte sert le mauvais agent.
3. Vérifier que `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` sont dans
   `/opt/demo-voice/.env` (nécessaires au raccrochage propre via l'API REST).
4. Synchroniser tout nouveau secret : `.env` ET coffre
   (`COFFRE-SECRETS.local.md` + re-chiffrement).

### Option B : renvoi d'appel depuis la ligne du client (défaut)

Le client renvoie ses appels **sur non-réponse** vers le numéro Twilio d'accueil
(numéro mutualisé ou dédié selon le pack). Codes usuels France, à composer sur le
téléphone du client puis touche appel :

**Mobiles (codes GSM standard : Orange, SFR, Bouygues, Free)**

| Action | Code |
|---|---|
| Renvoi si non-réponse vers le numéro N | `**61*N#` |
| Idem avec délai de sonnerie (ex. 20 s, pas de 5 s, 5 à 30) | `**61*N**20#` |
| Renvoi si injoignable (éteint, hors réseau) | `**62*N#` |
| Renvoi si occupé | `**67*N#` |
| Vérifier l'état du renvoi non-réponse | `*#61#` |
| Désactiver le renvoi non-réponse | `##61#` |
| Tout annuler (tous les renvois) | `##002#` |

Recommandation type : `**61*N**20#` + `**62*N#` + `**67*N#` (non-réponse 20 s,
injoignable, occupé), et noter les codes de désactivation sur la fiche remise au
client (c'est SA porte de sortie immédiate, argument de vente et clause 7.3 du
contrat).

**Lignes fixes sur box** (pas de codes fiables, passer par l'interface) :
- Orange / Livebox : espace client Orange ou interface Livebox, rubrique téléphone,
  « renvoi sur non-réponse ».
- Free / Freebox : espace abonné Free, Téléphonie, « Renvoi d'appel »
  (choisir « sur non-réponse » + délai).
- SFR box : espace client SFR, téléphonie fixe, renvois d'appel.
- Bouygues Bbox : espace client, ligne fixe, renvois d'appel.

**Standard / IPBX pro** : renvoi de débordement configuré par le mainteneur du
standard (le contact est demandé au questionnaire §7).

Toujours faire un appel de contrôle après activation : appeler la ligne du client,
laisser sonner, vérifier que l'agent décroche après le délai.

### Piège connu : numéro masqué

Quand l'appelant masque son numéro, Twilio envoie `From=anonymous` : le serveur
adapte déjà le prompt (l'agent demande le numéro à l'oral) et rejette les téléphones
placeholder à la réservation. Rien à faire, mais le tester en recette (appel en
`#31#`).

## 6. Tests internes (AVANT toute écoute par le client)

Processus imposé par le cahier des charges conversation (§9) : simulateur d'abord,
transcripts relus, ensuite seulement des appels réels.

1. **Simulateur** : `tools/simulate_call.py`, scénarios minimum : coopératif,
   transcription pourrie, pressé, refus, « c'est un robot ? », silencieux.
   Verdicts attendus : zéro méta, un seul bonjour, une question à la fois, RDV
   réellement écrit dans l'agenda, au revoir avant tout raccrochage.
2. **Appels téléphoniques réels (par Corsica Studio)**, checklist :
   - ☐ Annonce IA + enregistrement dès le décroché
   - ☐ Infos exactes (horaires, adresse, 2 ou 3 prestations, prix annonçables)
   - ☐ Prise de message complète + récap reçu (SMS/mail au bon destinataire)
   - ☐ Prise de RDV : bon calendrier, bonne durée, bon libellé
   - ☐ Cas d'urgence : consigne d'escalade respectée
   - ☐ Appel en numéro masqué (`#31#`) : l'agent demande le numéro
   - ☐ Raccrochage propre (pas de silence PSTN), vérifié dans
     `docker logs -f demo-voice` (`[tool] → end_call`, statut completed)
   - ☐ Hors sujet / démarcheur : message court, pas de RDV
3. Surveiller les logs pendant les tests : lignes `[caller]`, `[tool]`, `[xai]`.
   Symptômes connus : pas de `[tool] → book_...` alors que les champs sont donnés
   = R2 cassée dans le prompt ; caractères non latins dans `[caller]` = pin Whisper
   `language: "fr"` perdu.

## 7. Recette avec le client (30 min, ensemble)

1. Le client appelle lui-même 2 ou 3 fois (scénarios : demande d'info, prise de RDV
   ou message, cas d'urgence).
2. Corriger en direct ce qui relève de la config (bind mount : effet à la
   conversation suivante, pas de redéploiement).
3. Relire ensemble un récap d'appel reçu (format, destinataire).
4. Validation écrite : mail « recette validée le [DATE] » (déclenche la facturation
   du solde et le démarrage de l'abonnement, article 3.2 du contrat).

## 8. Mise en service

- ☐ Activer le renvoi d'appel sur la ligne du client (§5B) ou publier le numéro (§5A).
- ☐ Appel de contrôle immédiat depuis un autre téléphone.
- ☐ Remettre au client la **fiche de service** : numéro couvert, délai de sonnerie,
  codes de désactivation du renvoi, numéro de Vannina pour le support, rappel des
  horaires de support (jours ouvrés 9 h à 18 h).
- ☐ Vérifier les notifications (récap SMS/mail, alerte Telegram côté CS).
- ☐ Journal VPS + tracker à jour (checklist client, Airtable).

## 9. Suivi première semaine (inclus dans le setup)

- J+1 : relire TOUS les transcripts du premier jour (`docker logs` / usage), corriger
  les formulations qui accrochent. Prévenir le client qu'on l'a fait (effet waouh).
- J+2 à J+6 : relecture quotidienne rapide, ajustements config au fil de l'eau.
- J+7 : point téléphonique avec le client : volume d'appels pris, messages, RDV,
  2 ou 3 exemples concrets d'appels sauvés. C'est le moment de caler le rythme de
  croisière (digest, cycle d'ajustement mensuel) et de semer l'upsell (chatbot site,
  pack supérieur).
- Archiver la config finale dans le repo (commit géré par Vannina) : le VPS n'est
  pas un clone git, le repo local reste la source de vérité.
