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
