# Agent IA Vocal — by Le Club IA VIP

Démo d'un agent vocal en temps réel propulsé par **Grok Voice Think Fast 1.0** (xAI).
Tu parles dans ton micro, l'agent te répond en streaming, appelle des outils, et peut
même réserver une table dans ton Google Calendar.

L'agent par défaut s'appelle **Margot**, hôtesse vocale du *Petit Bistro* (Paris).

👉 **Communauté :** <https://skool.com/le-club-ia-vip>

---

## ✅ Pré-requis

- **Python 3.11+** ([télécharger](https://www.python.org/downloads/))
- Une **clé API xAI** — essai gratuit : <https://console.x.ai/>
- *(Optionnel)* un compte **Composio** si tu veux tester la réservation Google
  Calendar : <https://composio.dev>

---

## 🚀 Démarrage rapide (3 minutes)

### 1. Installer les dépendances

Ouvre un terminal dans le dossier du projet.

**Windows (PowerShell) :**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Mac / Linux :**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Ajouter ta clé xAI

```powershell
copy .env.example .env       # Windows
# ou
cp .env.example .env         # Mac / Linux
```

Ouvre `.env` et colle ta clé :

```env
XAI_API_KEY=xai-xxxxxxxxxxxxxxxxxxx
```

### 3. Lancer le serveur

```bash
uvicorn web.server:app --port 8000 --reload
```

### 4. Ouvrir l'app

👉 **<http://localhost:8000>**

Clique **Démarrer la conversation**, autorise le micro, parle.
Margot t'accueille en français.

---

## ✏️ Personnaliser ton agent

Pas besoin de redémarrer le serveur — il relit la config à chaque nouvelle conversation.

| Quoi | Où |
|---|---|
| Personnalité / prompt système | [`web/config/system_prompt.txt`](web/config/system_prompt.txt) |
| Outils disponibles (envoyés à xAI) | [`web/config/tools.json`](web/config/tools.json) |
| Implémentation des outils (navigateur) | [`web/static/voice.js`](web/static/voice.js) — constante `FUNCTIONS` |

**Exemple** : pour transformer Margot en agent de garage, change le prompt système.
Pour ajouter un outil "demander un devis", édite `tools.json` puis ajoute son handler
dans `voice.js`. C'est tout.

> Astuce : dans `tools.json` tu peux référencer des variables d'environnement avec
> `${MA_VARIABLE}` — elles sont remplacées côté serveur, donc tes secrets restent
> hors du dépôt git.

---

## 📅 Brancher Google Calendar via Composio (optionnel)

Le projet utilise [Composio](https://composio.dev) pour parler à Google Calendar
sans gérer l'OAuth toi-même.

1. Crée un compte sur <https://composio.dev>.
2. Connecte un compte Google avec le toolkit **Google Calendar**.
3. Crée un **MCP server** Composio pour ce toolkit — récupère son URL et ta clé API.
4. Ajoute-les à ton `.env` :

   ```env
   COMPOSIO_API_KEY=xxxxxxxxxxxxxxxxxx
   COMPOSIO_MCP_URL=https://mcp.composio.dev/composio/server/xxxxxxxx
   ```

5. Relance le serveur. Demande à Margot :
   *"Je voudrais réserver une table pour 4 demain à 19h, mon nom est Eric,
   mon numéro 06 12 34 56 78."* → l'événement apparaît dans ton Google Calendar.

L'agent appelle d'abord `GOOGLECALENDAR_FIND_FREE_SLOTS` (via MCP) pour vérifier
la dispo, puis la **function tool** `book_reservation` qui passe par le endpoint
serveur `/api/calendar/book`. Le payload calendrier est construit côté serveur —
le modèle ne touche jamais directement aux champs Google.

---

## 🐳 Déploiement Docker sur un VPS

Pour faire tourner Margot 24/7 (et la brancher à un numéro Twilio), un VPS
Debian/Ubuntu + Docker + Nginx suffit. Le projet expose le container sur
**`127.0.0.1:8001` uniquement** pour qu'aucune autre app du VPS ne soit
gênée, et c'est Nginx qui s'occupe du HTTPS + des en-têtes WebSocket.

### 1. Cloner et configurer le projet

```bash
git clone https://github.com/Thomas-Berton/template-grok-voice-agent.git
cd template-grok-voice-agent
cp .env.example .env
nano .env          # colle XAI_API_KEY, COMPOSIO_*, TWILIO_*
```

### 2. Builder + démarrer

```bash
docker compose up -d --build
docker compose logs -f          # vérifie que uvicorn démarre
curl http://127.0.0.1:8001/config   # doit renvoyer du JSON
```

### 3. Configurer Nginx pour ton domaine

Pointe d'abord ton sous-domaine (ex. `margot.tondomaine.com`) sur l'IP du
VPS (enregistrement DNS `A`). Puis :

```bash
sudo cp deploy/nginx.conf.example /etc/nginx/sites-available/margot.conf
sudo nano /etc/nginx/sites-available/margot.conf   # remplace server_name
sudo ln -s /etc/nginx/sites-available/margot.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d margot.tondomaine.com      # HTTPS auto via Let's Encrypt
```

Une fois fini, **<https://margot.tondomaine.com>** sert l'app web. Tout est
prêt pour Twilio.

---

## 📞 Brancher un numéro de téléphone Twilio

Margot peut aussi répondre à un vrai numéro de téléphone via **Twilio Media
Streams**. Le serveur relaie l'audio (µ-law 8 kHz) entre Twilio et xAI sans
transcodage, et gère les tool calls côté serveur (réservation, raccrochage,
horaires).

### 1. Ajouter les credentials Twilio au `.env`

Récupère-les dans <https://console.twilio.com/> (Account SID + Auth Token
sur le dashboard) et colle-les dans `.env` :

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Puis redémarre le container : `docker compose restart`.

### 2. Configurer le numéro Twilio

Dans la console Twilio :

1. **Phone Numbers** → **Manage** → **Active numbers** → clique sur ton numéro.
2. Onglet **Configure**, section **Voice Configuration** :
   - **A call comes in** → `Webhook`
   - URL : `https://margot.tondomaine.com/twilio/voice`
   - Méthode : `HTTP POST`
3. **Save configuration** en bas de la page.

C'est tout. Aucune TwiML Bin à créer — le serveur génère la TwiML
dynamiquement avec l'URL WebSocket correcte.

### 3. Tester

Appelle ton numéro Twilio depuis ton portable. Margot devrait répondre en
français en quelques secondes. Suis les logs :

```bash
docker compose logs -f margot
```

Tu devrais voir :

```
[twilio] WS connected
[twilio] start streamSid=MZ… callSid=CA…
[tool] → book_reservation({...})
[tool] ← book_reservation → {'status': 'confirmed', …}
```

### 4. Comment ça marche (vue de l'oiseau)

```
PSTN ──▶ Twilio ──wss──▶ /twilio/stream ──wss──▶ api.x.ai/v1/realtime
                              │
                              └──▶ tool calls (book_reservation, end_call, …)
```

Twilio envoie l'audio µ-law en base64 dans des messages JSON ; on les
ré-enveloppe en `input_audio_buffer.append` pour xAI. Au retour, xAI nous
envoie du µ-law qu'on ré-enveloppe en `media` events pour Twilio. Quand
Margot appelle `end_call`, on patche le statut de l'appel via l'API REST
Twilio (`Status=completed`) pour vraiment raccrocher la ligne PSTN.

---

## 📖 Guide complet

Une fois le serveur lancé, ouvre **<http://localhost:8000/guide.html>** pour le guide
détaillé : comment écrire un bon prompt, les 5 types d'outils
(`function`, `web_search`, `x_search`, `file_search`, `mcp`), recette d'un agent
restaurant complet, débogage.

---

## 🛠️ Stack

- **xAI Voice Agent API** — `grok-voice-think-fast-1.0`
- **FastAPI** + **uvicorn** (serveur Python)
- **WebSocket realtime** vers `wss://api.x.ai/v1/realtime`
- **Web Audio API** côté navigateur (PCM16 24 kHz)
- **Twilio Media Streams** côté téléphone (µ-law 8 kHz)
- **Ephemeral tokens** xAI — la clé API ne quitte jamais le serveur
- **Composio MCP** pour Google Calendar (optionnel)
- **Docker** + **Nginx** + **certbot** pour le déploiement VPS

---

## 🆘 Problèmes courants

| Symptôme | Solution |
|---|---|
| `start failed: Permission denied` | Le navigateur a bloqué le micro. Clique sur l'icône cadenas dans la barre d'URL → autoriser le micro → recharge. |
| `XAI_API_KEY is not set` | Vérifie que `.env` existe à la racine du projet et contient bien `XAI_API_KEY=...` |
| L'agent ne dit rien | Ouvre la console DevTools (F12) → onglet Network → WS → regarde les events. Vérifie que `session.created` arrive bien. |
| Audio saccadé ou accéléré | Sample rate non assorti — garde **24000** partout dans `voice.js`. |
| `COMPOSIO_API_KEY not set` quand tu réserves | La function `book_reservation` ne peut pas créer l'événement. Ajoute les deux variables Composio à `.env` (voir section Google Calendar). |

---

## ⚠️ Sécurité

- Ta clé xAI reste dans `.env` côté serveur. Le navigateur reçoit uniquement un
  **ephemeral token** valide 5 minutes.
- `COMPOSIO_API_KEY` est lue côté serveur ; elle ne fuit pas vers le navigateur.
  Elle n'apparaît dans `tools.json` que via le placeholder `${COMPOSIO_API_KEY}`,
  remplacé à la volée par `/config`.

---

**Construit par Le Club IA VIP** · <https://skool.com/le-club-ia-vip>
