# Tracking d'attribution des démos (lien `?lead=` → Telegram + Airtable)

État au 2026-06-22 : **codé, déployé et validé end-to-end en prod.** Le mécanisme
est actif sur le VPS (var `DEMO_WEBHOOK_URL` renseignée). Ce document explique la
chaîne complète, du lien dans le cold email jusqu'à l'alerte Telegram et aux champs
écrits sur le prospect Airtable.

## Le problème résolu

Le cold email (WF-06a) envoie aux restaurateurs un bouton vers la démo de l'agent
vocal. Jusqu'ici, quand un prospect cliquait et testait l'agent, **on ne savait pas
qui** : la démo était anonyme, impossible de relier une session à un prospect de la
base. Aucune relance ciblée possible.

Ce mécanisme comble ce trou : chaque lien de démo porte l'identité du prospect, et
le lancement d'une démo est **attribué nominativement** et remonté en temps réel.

## Ce que ça fait

Le bouton démo du cold email est personnalisé par prospect. Quand le prospect lance
la conversation :
1. Le serveur **logue** son `record_id` Airtable dans `usage.jsonl`.
2. Le serveur **notifie n8n (WF-13)**, qui écrit l'info sur le prospect Airtable et
   envoie une **alerte Telegram nominative** (ex. `🔥 [resto] teste Margot`).

## La chaîne complète

1. **Cold email (WF-06a)** pose le lien d'attribution :
   `https://demo.corsica-studio.com/?lead=${record_id}&utm_...`
   Le `record_id` est l'ID Airtable du prospect ; les `utm_*` servent au suivi.

2. **`web/static/voice.js`** lit `?lead=` dans l'URL (`URLSearchParams`) et le
   transmet dans le body du `POST /token` :
   ```js
   const _leadId = new URLSearchParams(location.search).get("lead") || "";
   // ... body: JSON.stringify({ lead: _leadId })
   ```

3. **`web/server.py`**, endpoint `/token` :
   - récupère le `lead` (tronqué à 40 car.) et résout le **métier** à partir de
     l'en-tête `Host` (un seul conteneur sert les 7 sous-domaines métier) ;
   - écrit l'événement dans `usage.jsonl` (avec le `lead` si présent) ;
   - si un `lead` est présent, appelle `_demo_webhook(lead, metier)` qui POST vers
     n8n **best-effort** (httpx, ne bloque **jamais** le mint du token).

4. **n8n WF-13** reçoit `{lead, metier, ts, source}` sur le webhook
   `https://n8n-cs.corsica-studio.com/webhook/demo-lancee` et :
   - écrit `demo_lancee`, `demo_date`, `demo_etape`, `demo_count` sur le prospect
     Airtable (`lead` = `record_id`) ;
   - envoie l'alerte Telegram nominative.

## Où c'est dans le code

- `web/static/voice.js`
  - Lecture de `?lead=` (`URLSearchParams`) et transmission dans le body du
    `POST /token`.
- `web/server.py`
  - `DEMO_WEBHOOK_URL` : variable d'env (endpoint n8n WF-13). Si vide, aucun webhook.
  - `_demo_webhook(lead, metier)` : POST best-effort vers n8n (httpx). Ne bloque
    jamais le mint de token.
  - `/token` : capture le `lead`, résout le métier par `Host`, écrit dans
    `usage.jsonl`, puis appelle `_demo_webhook` si `lead` présent.
  - `_aggregate_usage()` + endpoint `GET /usage` : agrègent `par_lead`,
    `par_metier`, `sessions_identifiees` à partir de `usage.jsonl`.

## L'endpoint `/usage`

`GET /usage` (`_aggregate_usage()`) lit `usage.jsonl` et renvoie notamment :
- `par_lead` : nombre de sessions par `record_id` prospect (trié décroissant) ;
- `par_metier` : nombre de sessions par secteur ;
- `sessions_identifiees` : total des sessions rattachées à un `lead`.

C'est le tableau de bord rapide pour voir quels prospects ont lancé une démo.

## Configuration (var d'env)

Dans le `.env` de `/opt/demo-voice` sur le VPS :
```
DEMO_WEBHOOK_URL=https://n8n-cs.corsica-studio.com/webhook/demo-lancee
```
Si la variable est absente ou vide, le serveur fonctionne normalement mais
n'émet aucun webhook (seul `usage.jsonl` reste alimenté).

## Déploiement

Voir `CLAUDE.md` (section *Production deployment*). Rappel : `/opt/demo-voice`
n'est **pas** un clone git, on déploie par `rsync`/`scp` puis
`cd /docker && docker compose up -d --build demo-voice` (source Python modifiée →
rebuild). Le conteneur `demo-voice` sert les 7 sous-domaines via Traefik (Host).

## Validation end-to-end (2026-06-22)

Test réussi avec le resto « Le Grand Bleu » (`rec6ox0jSlilUVI0K`) :
- lien `?lead=` confirmé dans le mail envoyé ;
- `/usage` : `par_lead` + `par_metier` remplis ;
- WF-13 : champs `demo_*` écrits sur le prospect + alerte Telegram reçue.

Les données de test ont été nettoyées ensuite.

## Commits

- `7537e53` : lead + webhook + `par_lead`.
- `a2eb78e` : `par_metier`.

(github.com/vannina/template-grok-voice-agent, branche `main`.)
