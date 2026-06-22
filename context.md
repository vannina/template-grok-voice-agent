# context.md — template-grok-voice-agent

- Rôle : développeur de l'application d'agent vocal IA temps réel (/CS).
- Contexte : démo d'un agent vocal ("Margot", hôtesse de restaurant) sur le modèle `grok-voice-think-fast-1.0` (xAI). Un serveur FastAPI émet des tokens éphémères et sert une SPA ; le navigateur ouvre un WebSocket vers `wss://api.x.ai/v1/realtime` (PCM16 24 kHz). Le même serveur relaie aussi Twilio Media Streams pour le téléphone. Multi-métier ; déployé sur VPS Hostinger 168.231.83.45 (`/opt/demo-voice`, Traefik, 7 sous-domaines), tracking démo `?lead=` opérationnel.
- Objectif : faire la démo (et au besoin la mise en production téléphone) d'un agent vocal adapté par métier, branché sur un agenda (Composio Google Calendar) et capable d'appeler des outils.
- Livrable : l'app elle-même (serveur FastAPI `web/server.py`, SPA `web/static/voice.js`, config hot-reload `web/config/`), déployable et personnalisable par client. Source de vérité technique : son `README.md` et son `CLAUDE.md`.
- Contraintes : seul secret requis = `XAI_API_KEY` dans `.env`. Ajouter un tool `function` = handler dans `voice.js` (navigateur) ET `_server_tool_call` dans `server.py` (Twilio). Deux règles légales par agent : annoncer l'enregistrement, indiquer que c'est une IA. Français par défaut. Règles prompt R1/R2 load-bearing (voir CLAUDE.md).
- Usage : démos prospects par site web (sans Twilio), branchement d'un numéro Twilio seulement si un prospect l'exige pour conclure ; chaque client a un `system_prompt.txt` adapté à son secteur.

---
*doc au 2026-06-22 · détail architecture : voir CLAUDE.md (source de vérité)*
