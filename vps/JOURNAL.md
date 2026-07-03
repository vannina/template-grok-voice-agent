# Journal VPS — demo-voice (Hostinger 168.231.83.45)

Toute action sur le VPS de prod est consignée ici, horodatée (date + heure).
Aucun secret en clair dans ce fichier.

---

## 2026-06-28 06:12 CEST — Branchement du numéro Twilio (chemin téléphone)

Contexte : Vannina a acheté un numéro Twilio FR **+33 4 12 13 60 20**
(`+33412136020`, SID `PN129f0378f12da4d52b0d71330b41c1fa`) pour que les prospects
appellent Margot en réel.

Actions :
1. Webhook voice du numéro configuré via l'API Twilio :
   `VoiceUrl = https://demo.corsica-studio.com/twilio/voice` (POST).
2. `TWILIO_AUTH_TOKEN` ajouté à `/opt/demo-voice/.env` (absent jusqu'ici ;
   nécessaire au raccrochage REST en fin d'appel). Backup `.env.bak.<ts>` créé
   avant modif. Le `TWILIO_ACCOUNT_SID` était déjà présent.
3. `cd /docker && docker compose up -d demo-voice` → conteneur recréé et redémarré
   (~10 s de coupure du service démo).

Vérifs :
- `docker exec demo-voice printenv TWILIO_AUTH_TOKEN` → présent.
- `POST https://demo.corsica-studio.com/twilio/voice` → HTTP 200, TwiML correct
  (`<Connect><Stream url="wss://demo.corsica-studio.com/twilio/stream">`).

Reste : test d'appel réel sur le numéro pour valider la voix de bout en bout
(audio + raccrochage auto après le « au revoir »).

## 2026-07-02 15:00 CEST — Standard bi-marque : Sprint A.1 codé (local, PAS déployé)

IVR CS/CD implémenté dans `web/server.py` (commit `d07a6a5`) : Host standard.corsica-studio.com
→ annonce légale + Gather 1/2 → /twilio/route → stream avec Parameter entite=cs|cd →
config `web/config/entites/<e>/`. Rétro-compatible démo (smoke S1 OK + 26 checks).
Rien touché sur le VPS. Déploiement prévu au Sprint A.5 (avec sous-domaine Traefik +
webhook Twilio 04 12 13 60 10). Renvoi Free Mobile : à activer en DERNIER, après recette.

## 2026-07-02 15:40 CEST — A.2 personas entites cs|cd (local)
Commit 38cdfd6. Personas 8 sections + business.json (CS : offres/fourchettes HT ; CD :
faits corsicadesign.com) + profile.json (RDV 30 min, capacite 1, greetings dedies).
Note deploiement : ENABLE_CALLBACK_TOOL=1 requis dans le .env standard (prendre_message).

## 2026-07-02 16:30 CEST — A.3 tools standard (local)
Commit 2939e84. identify_caller (pre-fetch Airtable, accueil nominatif), qualify_lead,
request_callback, transfer_to_human (TRANSFER_ENABLED + Dial 20s -> reprise agent),
webhook fin d'appel (STANDARD_WEBHOOK_URL). Wording Vannina final (agent vocal, pas
d'"enregistre", pas de nom de famille, IVR court, fluide). Nouvelles env documentees
archi §8. Requis avant deploiement : base Airtable Standard IA + ENABLE_CALLBACK_TOOL=1.

## 2026-07-02 17:10 CEST — A.4 donnees + notifications (aucune action VPS)
Commit 5fc7169. Airtable (base appZaFI40YcGBCn8D) : Standard — Appels tblF0Q3jchpNb8C97,
Contacts tblHUXSuCWt8Tt1fn, Config tbljnAJI1n4jVZ5lK. n8n INACTIFS :
WF-Standard-Reception Dif4bdlL818IcUY7 (webhook standard-fin-appel), WF-Standard-Digest
afWCvDC016CrlNZU (cron 21h). A.5 : activer WFs + STANDARD_WEBHOOK_URL + deploiement.

## 2026-07-02 17:45 CEST — Agendas RDV crees (Composio API, compte contact.corsicastudio@gmail.com)
RDV Corsica Studio = 45e70304b9d6927cfcceeae642c1e501caa76c79d7d7a1b409c932949533b13f@group.calendar.google.com
RDV Corsica Design = 5b609809397f5c8c83daabf9ed8b40705c17fdb6d640f4fe65f3743883f9c0e5@group.calendar.google.com
tz Europe/Paris, inseres dans la calendarList, branches en litteral dans entites/*/profile.json.
Note : 2 doublons orphelins possibles (1re tentative, ids perdus, absents de la calendarList, sans effet).
Le lien calendar.app.google fourni par Vannina = page de reservation (autre mecanisme, non utilise).

## 2026-07-02 18:00 CEST — Agenda CD remplace par celui de Vannina
CD utilise desormais son agenda « CORSICA DESIGN »
(bdd5ed3c996370d7571dff15fbd2e7696a1e36e73f30fbf8dd66202fde061dfd@group.calendar.google.com,
meme compte, tz Europe/Paris). Doublon « RDV Corsica Design » (5b609809…) supprime.
CS reste sur « RDV Corsica Studio » (45e70304…).

## 2026-07-02 18:30 CEST — Point d'etape standard bi-marque (fin de session build)
FAIT (local, commits ci-dessus) : A.1 IVR, A.2 personas (wording final Vannina), A.3 tools
(caller-ID prefetch, transfert toggle+Dial20s, qualif, rappel, webhook fin d'appel),
A.4 Airtable (Standard — Appels/Contacts/Config) + WF n8n INACTIFS (Reception
Dif4bdlL818IcUY7, Digest afWCvDC016CrlNZU) + agendas branches (CS=RDV Corsica Studio
45e70304…, CD=CORSICA DESIGN bdd5ed3c…, doublons supprimes). Filtrage demarchage/stages/
emploi. CD accessible (pas que haut de gamme). En cours : enrichissement base de
connaissances CS depuis corsica-studio.com (agent).
RESTE : A.5 = DNS+Traefik standard.corsica-studio.com, service Docker, .env (TRANSFER_*,
STANDARD_*, ENABLE_CALLBACK_TOOL=1, secrets->coffre), webhook Twilio 0412136010,
activer les 2 WF n8n, recette avec Vannina, PUIS renvoi Free Mobile (dernier).

## 2026-07-02 19:15 CEST — A.5 STANDARD EN SERVICE (VPS + Twilio + n8n)
- rsync repo -> /opt/standard-voice ; .env = copie demo + STANDARD_HOSTS, ENABLE_CALLBACK_TOOL=1,
  AIRTABLE (base appZaFI40YcGBCn8D, tables Standard — *), STANDARD_WEBHOOK_URL, TRANSFER_ENABLED=0.
- /docker/docker-compose.yml : service standard-voice ajoute (backup .bak horodate),
  Traefik Host standard.corsica-studio.com, build OK, conteneur Up.
- Tests publics : POST /twilio/voice -> 200 TwiML IVR exact ; /twilio/route Digits=1 -> Stream entite=cs.
- Le 04 12 13 60 10 N'EST PAS chez Twilio (autre operateur) -> decision Vannina : achat
  d'un numero Twilio. ACHETE : +33412136016 (PN PNfd445e527554f0ad1494cba4e9f12248,
  adresse ADae69576fc55fa72c50afb3841cbb97ea, bundle BUcb630734ade24f7951cb9f6f3a4e78e6),
  VoiceUrl deja branche sur le standard.
- WF n8n ACTIVES : Reception Dif4bdlL818IcUY7, Digest afWCvDC016CrlNZU.
RESTE : recette (appel reel Vannina au 04 12 13 60 16) puis renvoi Free Mobile 06 -> 0412136016.

## 2026-07-02 20:05 CEST — Demo depannage EN LIGNE (VPS)
rsync web/config/metiers/depannage -> /opt/demo-voice (bind mount, pas de rebuild).
Traefik : Host demo-depannage.corsica-studio.com ajoute au routeur demo-voice
(backup compose .bak), recreate ~6s. Test : HTTP 200, /api/profile = Marc/depannage.
8e demo metier en prod.

## 2026-07-02 20:40 CEST — Demo hotel-international EN LIGNE (VPS, rebuild)
rsync complet -> /opt/demo-voice (server.py+voice.js : whisper_language par profil,
goodbyes EN/IT/DE additifs) + Traefik Host demo-hotel-international + rebuild demo-voice
(~30 s). Tests : nouveau metier 200 (Chloe, whisper=auto), regression demo/demo-hotel/
demo-depannage/standard = 200. 9 hosts servis par demo-voice, standard-voice intact.

## 2026-07-02 21:20 CEST — Correctifs recette DEPLOYES (standard-voice rebuild)
Commit 50b6381 : voix IVR Polly.Lea-Neural (x3 Say), latence 1re parole reduite
(pre-fetch caller 300ms non bloquant + handshake xAI parallele au start Twilio),
personas CS/CD chaleureux et proactifs (suggestion services par profession/projet).
Test : TwiML Polly OK. Feu vert donne a Vannina pour le renvoi Free -> 0412136016.

## 2026-07-03 10:20 CEST — RENVOIS FREE ACTIFS : standard EN PRODUCTION
Vannina a active les renvois conditionnels 06 51 00 30 49 -> 04 12 13 60 16.
Tout appel manque tombe sur l'assistante bi-marque. Coffre re-chiffre (1b1ff23).
Re-verification finale par Vannina a venir. TRANSFER_ENABLED reste 0.

## 2026-07-03 11:00 CEST — Point : pages Framer agents vocaux (aucune action VPS)
Composant V2_Template_AgentVocal (FDm0ZK7) cree dans Framer, porte les 3 offres
(assistante/depannage/hotel) + page QA canvas. 3 pages dupliquees par Vannina,
swap du contenu FAIT par MCP (pages sources intactes). Reste : renommage des paths
par Vannina (limite MCP), menu+SEO+schema (agent en cours), OG images, validation
visuelle puis publication. Buglog CS-framer : duplicateNode ne supporte pas les Pages.
Standard en production (renvois Free actifs), monitoring logs 1h sans anomalie signalee.

## 2026-07-03 15:20 CEST — D.3 outbound + Lea COMMITE (local, PAS deploye)
Commit du jour : POST /outbound/call (X-Outbound-Token, horaires 9-12/14-18 lun-ven
Europe/Paris, refus opposition), /twilio/voice-out (Stream metier=prospection + contexte
prospect), tool marquer_opposition, metier prospection/ (Lea SDR, tools/business/profile
completes a la main apres coupure limite session de l'agent). Smoke 22/22.
En cours (agent) : tables Airtable Prospection + WF-OUT n8n (INACTIFS, 3 appels/15min
pilote) + WF retour. Prochain : deploiement outbound sur standard-voice + OUTBOUND_TOKEN
(env+coffre) + recette Lea sur le 06 de Vannina AVANT tout vrai prospect.
Pages Framer : Settings title/meta/OG toujours a saisir par Vannina (limite MCP).
