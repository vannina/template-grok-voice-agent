# Mécanisme « demande de rappel » (escalade) — PRÉPARÉ, NON ACTIVÉ

État au 2026-06-15 : **codé et testé en dry-run, mais désactivé** (flag OFF) et **non déployé**
sur le VPS. La prod actuelle est inchangée. Ce document explique le mécanisme et comment
l'activer le jour voulu.

## Le problème résolu

Aujourd'hui, quand l'agent ne peut pas répondre à une question ou ne peut pas finaliser un
rendez-vous, le prompt lui dit de « prendre un message et qu'un humain rappelle ». Mais il
n'existait **aucun outil derrière** : l'agent récoltait nom + numéro à l'oral, promettait un
rappel, et l'info disparaissait à la fin de l'appel. Le pro ne recevait rien.

Ce mécanisme comble ce trou : l'agent capte la demande et la **transmet réellement** au pro.

## Ce que ça fait

Un outil **`prendre_message`** exposé à l'agent. Quand il l'appelle, le serveur envoie au pro :
1. **Telegram** (alerte temps réel) via le bot Corsica Studio.
2. **Copie email** (Resend).

Le message contient : établissement, nom, téléphone, motif (une phrase), **résumé structuré de
l'échange** (le contexte complet rédigé par l'agent), et l'horodatage. Exemple :

```
[RAPPEL] Salon X
Nom : Sophie Marchetti
Telephone : +33611223344
Motif : veut un balayage avec sa coloriste habituelle, pas de créneau

Demande detaillee :
Cliente fidèle, demande Marie (coloriste). Balayage + soin un samedi matin avant
le 28 juin. Samedis proposés complets. Préfère être rappelée en fin de journée.

Recu : lundi 15 juin 2026, 03:59
Demande captee par l'agent vocal : la personne attend un rappel.
```

## Pourquoi un résumé structuré (et pas la transcription brute)

Le résumé est rédigé par l'agent, qui a tout le contexte de la conversation. C'est plus lisible
et actionnable qu'une transcription brute (bruitée, longue), et ça marche identiquement au
téléphone (Twilio) et sur le web. La transcription brute reste une évolution possible (cf. plus bas).

## Où c'est dans le code

- `web/server.py`
  - Bloc config en tête : `NOTIFY_ENABLED` (flag), `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
    `RESEND_API_KEY`, `NOTIFY_EMAIL`, `NOTIFY_FROM`, et la constante `CALLBACK_TOOL`.
  - `_metier_ctx()` : résout `telegram_chat_id` et `notify_email` par métier (profil > env).
  - `_notify_callback(ctx, args, dry_run=False)` : formate + envoie (Telegram + Resend). `dry_run`
    formate sans rien envoyer (test).
  - `_server_tool_call()` : branche `prendre_message` (chemin téléphone/Twilio).
  - `_load_config()` : **n'injecte l'outil + la consigne prompt QUE si `NOTIFY_ENABLED`**.
  - Endpoint `POST /api/message` (chemin navigateur) + modèle `CallbackMessage`.
- `web/static/voice.js` : `FUNCTIONS.prendre_message` (fetch `/api/message`) + bulles
  `message_start` / `message_done`.

## Tant que le flag est OFF (état actuel)

`ENABLE_CALLBACK_TOOL` non défini (ou `0`) → l'outil **n'est pas** envoyé à l'agent et la consigne
n'est pas ajoutée. L'agent fonctionne exactement comme avant (4 outils). L'endpoint `/api/message`
existe mais n'est appelé par personne. **Aucun envoi possible.**

## Pour ACTIVER (le jour voulu)

1. Sur le VPS, dans le `.env` de `/opt/demo-voice` (déjà présent localement) :
   ```
   ENABLE_CALLBACK_TOOL=1
   TELEGRAM_BOT_TOKEN=...        # bot Corsica Studio (déjà dans le .env local)
   TELEGRAM_CHAT_ID=...          # destinataire par défaut (démos = Vannina)
   RESEND_API_KEY=...
   NOTIFY_EMAIL=contact@corsica-studio.com
   NOTIFY_FROM=Corsica Studio <noreply@corsica-studio.com>
   ```
2. `rsync` de `web/server.py` + `web/static/voice.js` vers `/opt/demo-voice` puis
   `cd /docker && docker compose up -d --build demo-voice` (source Python modifiée → rebuild).
3. **Test réel** : appeler une démo, demander un truc que l'agent ne sait pas, donner un faux nom +
   numéro → vérifier la réception du Telegram + de l'email. (Ou `POST /api/message` directement.)

## Test en dry-run (sans rien envoyer, déjà fait)

```bash
cd template-grok-voice-agent
./.venv/bin/python - <<'PY'
import os, asyncio, pathlib, sys
for l in pathlib.Path('.env').read_text().splitlines():
    if '=' in l and not l.startswith('#') and ' ' not in l.split('=',1)[0]:
        k,v=l.split('=',1); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
sys.path.insert(0,'.'); from web import server
ctx = server._metier_ctx('beaute')
print(asyncio.run(server._notify_callback(ctx, {'nom':'Test','telephone':'+33600000000','motif':'x','resume':'y'}, dry_run=True))['payload']['text'])
PY
```

## Routage par établissement (vrais clients)

Par défaut tout part vers le Telegram + l'email de Corsica Studio (bien pour les démos). Pour un
client déployé, renseigner dans son `web/config/metiers/<metier>/profile.json` :
```json
"telegram_chat_id": "<chat_id du client>",
"notify_email": "<email du client>"
```
Le client obtient son `chat_id` en faisant « /start » avec le bot Corsica Studio une fois.

## Évolutions possibles (non faites)

- **Transcription brute** de l'appel jointe en plus du résumé (accumuler les transcripts de la
  session côté serveur Twilio / envoyer l'historique du chat côté navigateur).
- **SMS** (via Twilio, quand le numéro FR sera validé) ou **WhatsApp** (WhatsApp Business API, lourd).
- Création d'un événement « À RAPPELER » dans le calendrier en plus de la notif.
