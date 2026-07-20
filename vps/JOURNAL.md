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

## 2026-07-05 ~13h CEST — Point contexte (recette Lea en cours d'iteration)
PAGES FRAMER : CLOS. 3 pages en ligne (title/meta/OG persos verifies), menu+footer+schema,
H1 depannage "sur une clim" publie (module V2_Template_AgentVocal verifie dans le bundle).
LEA : v5 DEPLOYEE (AMD async, script squelette, barge-in global, 12 mots). Mesure : serveur
351 ms ; delai restant = TTFB generation xAI (~2 s) -> v6 EN COURS (interrompue limite session,
reset 15h) : opener audio instantane voix ara ("Allo, bonjour !" via <Play>) + pitch commercial
direct langage artisan ("Les clients qui vous appellent pendant que vous etes occupe, j'ai une
solution pour ne plus les perdre"). Verdicts Vannina v3-v5 integres (pas d'hypothetique, pas de
secretariat, prospection assertive). OUTBOUND_HOURS temporairement 8-22 pour tests internes
(REMETTRE 9-12,14-18 avant pilote). Personnalisation confirmee 3 niveaux (metier/ville/identite).
RESTE : relancer v6 a 15h -> deploy -> appel test -> si OK : token credential n8n + verif
credentials UI + sourcing artisans (classes par metier) + cross-suppression + activation WF
(go Vannina) + page /qui-vous-appelle a integrer + transfert + SMS confirmations.

## 2026-07-05 soir — Recette Lea v7/v8 (contexte sauvegarde)
v6 DEPLOYEE : opener "Allo, bonjour !" voix ara reelle (web/static/opener-prospection.mp3,
1,05s, <Play> avant Connect, OUTBOUND_OPENER dans .env standard). v7 hot-deploy : pitch
court ("Vingt secondes ?"), solution concrete mots Vannina ("Elle note les coordonnees du
client, ou prend le rendez-vous directement dans votre agenda"), closing demonstration.
TEST-PILOTE-8 : diagnostic logs = barge-in TROP agressif (chaque "Allo ?" annulait la
reponse en vol -> fragments+silences) + relance watchdog 20s trop lente + bug table
"Oppositions" (403, vraie table = "Prospection — Oppositions").
v8 EN COURS (agent) : barge-in seuil 900ms (BARGE_IN_MIN_MS), relances 7s/8s
(WD_RELANCE_S/WD_CLOSE_S), defaut table oppositions corrige. Apres v8 : deploy rebuild
standard-voice -> appel test -> si OK sourcing artisans par metier + pilote.
RAPPEL : OUTBOUND_HOURS=8-22 (tests) a remettre 9-12,14-18 avant pilote.

## 2026-07-20 17h40 — Déploiement Léa v13 (standard-voice)
Recette AVANT déploiement (nouvelle méthode : spec = CAHIER-DES-CHARGES-CONVERSATION.md) :
smoke 22/22, mocks 24/24, simulateur 6/7 PASS (coop/meta/presse/refus/robot/opposition ;
"silencieux" = limite harnais xAI idle-timeout, logique silences couverte par les mocks).
Déployé : rsync web/server.py (commit 9c24992) -> /opt/standard-voice ; cd /docker &&
docker compose up -d --build standard-voice. Démarrage sain (opener chargé, uvicorn up).
v13 = enchaînement silences 2,5 s plafonné à 2 (3e silence -> clôture), au revoir jamais
coupé (drain calculé + filet 8 s armé APRÈS le drain), fenêtre de politesse 3 s après
l'au revoir (parole -> reprise ; "au revoir" seul -> raccrochage 2 s), hangup REST garanti.
RAPPEL : OUTBOUND_HOURS=8-22 (tests) à remettre 9-12,14-18 avant pilote.
Suite : appel de validation Vannina (+33651003049).

## 2026-07-20 21h20 — Léa v14 : mode information (retours Vannina recette v13)
Retours : boucle « je vous propose un rendez-vous » quand le client demande des infos ;
elle attendait une validation avant d'expliquer. Méthode appliquée : exigences 6.9/6.10/6.11
ajoutées au CAHIER-DES-CHARGES (v2) -> prompt corrigé (mode information : réponses réelles
2 phrases max, plafond 2 propositions de RDV, explication proactive sans demande de
permission, clôture service « à disposition » + numéro démo + rappel optionnel) ->
scénario simulateur « curieux » + 3 verdicts (mode_info, no_rdv_loop, disposition).
Recette : curieux 7/7 PASS + non-régression 6/6 PASS (coop, refus, opposition, presse,
robot, meta). Déployé par rsync du prompt seul (bind mount, hot reload, pas de rebuild).
Aussi : OUTBOUND_HOURS avait sauté du .env au rebuild v13 (refus hors_horaires 20h53) ->
ré-ajouté à 8-22 (tests), conteneur recréé 21h0x. À REMETTRE 9-12,14-18 avant pilote.
Backlog : vertical coiffeurs HORS Corse (tâche #20) + prospection France entière actée.

## 2026-07-20 21h55 — Léa v14.1 : réponse dans le même souffle (VALIDATION Vannina v14)
Vannina VALIDE la v14 (« on peut partir comme ça ») avec un dernier point : annonce
(« je vais vous donner des infos ») + latence avant l'explication. Cause : parole +
appel get_business_info + 2e réponse = un aller-retour de trop. Fix : exigence 6.12 au
cahier (réponse dans le même souffle, jamais d'annonce, tool réservé aux prix — les
questions courantes se répondent sans outil), prompt corrigé, verdict annonce_avant_
réponse ajouté au simulateur. Recette : curieux 7/7 PASS. Déploiement : rsync prompt
seul (hot reload). Chantier coiffeurs lancé (config démo + benchmark « Cecchi »).

## 2026-07-20 22h30 — Démo coiffeur EN LIGNE (vertical #4)
Config web/config/metiers/coiffeur/ (Salomé, L'Atelier Coiffure, Aix-en-Provence,
fictif, France entière — zéro référence corse) créée et validée (smoke 22/22, profil
46 clés complet). Déploiement : rsync config -> /opt/demo-voice/web/config/metiers/ ;
ajout Host(demo-coiffeur.corsica-studio.com) à la règle Traefik demo-voice dans
/docker/docker-compose.yml (backup .bak-coiffeur) ; docker compose up -d demo-voice.
DNS : wildcard *.corsica-studio.com -> 168.231.83.45 déjà en place chez OVH, rien à
faire. Certificat Let's Encrypt émis, vérif : HTTPS 200 + /api/profile agent=Salomé.
Benchmark concurrents : docs/BENCHMARK-COIFFEURS-2026.md (« Cecchi » introuvable sous
ce nom — demander la source à Vannina ; confirmés : Fresha AI Concierge ~95 EUR/mois,
Tala 29-499 EUR/mois HT ; positionnement retenu : relais non-réponse agnostique
plateforme). Léa : ancrage métier coiffeur ajouté au prompt (recette en cours).

## 2026-07-20 22h50 CEST — Mission #31 Ops : monitoring VPS agents vocaux EN PLACE
Objectif : plus jamais de crash silencieux de demo-voice / standard-voice.
1) WF-Monitor n8n CRÉÉ + ACTIF (ID C90fMNDFNjG1PONZ) : webhook POST
/webhook/monitor-alerte -> Telegram Vannina (credential Telegram existant de
l'instance, même chat_id 8518781262 que WF-13/WF-06b, AUCUN nouveau bot).
Testé : POST prod « [test] monitoring en place » -> réponse OK + exécution 3224
success (message Telegram parti).
2) /opt/monitoring/check.sh (cron */5 min) : conteneurs running + HTTPS 200 sur
demo. et standard.corsica-studio.com + seuil 5 lignes error/traceback/failed
sur 5 min de logs (exclusions bénignes). Anti-spam : fichiers d'état
/opt/monitoring/state, 1 alerte/h max par problème, message 🟢 au rétablissement.
Fallback si n8n injoignable : Telegram direct (token sourcé du .env standard,
jamais affiché). Testé à la main : sain, 0 alerte ; chemin webhook OK ; fallback
direct ok:true. Premier passage cron vérifié dans syslog.
3) FIX au passage : /opt/{demo,standard}-voice/data chown 1000:1000 (les
conteneurs tournent en uid 1000 « app » ; standard-voice loggait
« [usage] write failed: Permission denied » -> usage.jsonl du standard jamais
écrit, et celui de la démo root-owned donc appends KO depuis le 22/06).
Le tracking usage se remplit à nouveau à partir de maintenant.
4) /opt/monitoring/couts.sh (cron 21h50 UTC = 23h50 Paris été) : append dans
/opt/monitoring/couts.csv (date,app,sessions,minutes) — sessions/jour par app
depuis data/usage.jsonl (event=start) + appels/minutes Twilio du jour via l'API
(curl -u $TWILIO_ACCOUNT_SID:$TWILIO_AUTH_TOKEN
https://api.twilio.com/2010-04-01/Accounts/$SID/Calls.json?StartTime=YYYY-MM-DD,
somme des duration ; credentials sourcés du .env standard, jamais affichés).
Testé en réel : ligne « 2026-07-20,twilio,13,14 » (13 appels, 14 min ce jour).
5) /opt/monitoring/backup-hebdo.sh (cron dimanche 02h30 UTC) :
/root/backups/config-vps-DATE.tar.gz (chmod 600, dossier 700) avec les .env
demo+standard, /opt/monitoring (hors logs/state) et /docker/docker-compose.yml,
rétention 8 semaines. Testé : archive créée, contenu vérifié par tar tzf,
aucun contenu de .env affiché. Complète backup.sh quotidien existant (14 j +
off-site Drive chiffré) qui ne couvrait PAS le .env de standard-voice.
6) Recette hebdo Léa : /opt/monitoring/recette-hebdo.sh (cron lundi 05h30 UTC
= 07h30 Paris été). Pas de venv sur l'hôte -> docker cp de
tools/simulate_call.py dans le conteneur standard-voice (python3+websockets+
dotenv+XAI_API_KEY dans l'image) puis docker exec, scénarios coop + curieux,
verdict POSTé « [recette hebdo] Léa PASS/FAIL » sur monitor-alerte, transcripts
dans /opt/standard-voice/data/recette/. simulate_call.py du VPS remis à niveau
(rsync commit d087dae : ajoute le scénario curieux, v12 -> v14.1). UNE exécution
réelle AVANT le cron : PASS (coop 5/5 verdicts, curieux 7/7).
7) Snapshot Hostinger : créé via MCP (VM 1575715, snapshot 20/07 20:41 UTC)
MAIS constat : chez Hostinger le snapshot EXPIRE EN 24 H et il n'y a qu'un seul
slot (toute création écrase le précédent) -> inutilisable comme point hebdo, pas
de cron. La couverture réelle : backups automatiques Hostinger (4 points, dernier
20/07 14:12 UTC, restauration ~45 min, MCP VPS_getBackupsV1/VPS_restoreBackupV1)
+ backup.sh quotidien local + off-site Drive + archive config hebdo (5).
Procédure avant intervention risquée : MCP hostinger VPS_createSnapshotV1
(virtualMachineId 1575715) — ATTENTION, écrase le snapshot existant.
Crontab root posée (VPS en UTC) :
  */5 * * * *  check.sh · 50 21 * * * couts.sh · 30 2 * * 0 backup-hebdo.sh ·
  30 5 * * 1  recette-hebdo.sh
Scripts versionnés dans le repo : vps/monitoring/ (aucun secret dedans).
TODO mineur : sessions=0 ce 20/07 dans couts.csv (normal, usage.jsonl standard
inexistant avant le fix perms) ; ajuster le seuil logs (5/5 min) si faux positifs.
