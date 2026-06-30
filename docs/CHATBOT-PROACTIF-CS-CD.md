# Chatbot proactif — Corsica Studio + Corsica Design

> Rédigé le 2026-07-01 (v1, à enrichir avec le benchmark marché en cours). Un chatbot
> qui **fait des propositions** (proactif), pas un FAQ passif. Même **cerveau** que les
> agents vocaux (persona + base de connaissances + tools), exposé en **texte** sur le
> site. Capture le lead, qualifie, prend RDV.

**Règle absolue : ne jamais fusionner /CS et /CD.** Deux chatbots, deux personas, deux
bases de connaissances, deux pages.

---

## 1. Objectif
- Convertir le trafic existant des sites en **leads qualifiés et RDV**.
- **Proactif** : déclenche une accroche ciblée selon le comportement, propose une valeur
  (exemple, estimation, RDV), ne se contente pas d'attendre une question.
- **Omnicanal** : le visiteur peut passer du chat à un appel vocal (même cerveau,
  continuité de contexte).

## 2. Architecture technique

```
Site Framer (CS ou CD)
  └─ Composant chat (code component Framer)  ← déclencheurs proactifs
        │  POST /chat  (session, page, message, contexte visiteur)
        ▼
  Backend  (FastAPI route /chat  OU  n8n webhook)
        │  Claude API (streaming) + function calling (tools)
        │  base de connaissances de l'entité (CS / CD)
        ▼
  Tools : book_appointment · qualify_lead · capture_contact · propose_case ·
          send_recap · handoff_human
        ▼
  Airtable (lead) + Telegram (alerte Vannina) + Resend (récap email) +
  Composio Google Calendar (RDV)
```

- **Frontend** : composant Framer (React) — bulle proactive + fenêtre de chat, branding
  CS/CD, responsive, accessible. Lit la page courante + signaux comportementaux.
- **Backend** : Claude API (le « cerveau »). Réutilise le **même persona + base de
  connaissances** que l'agent vocal de l'entité (1 source de vérité). Hébergé sur le
  VPS (route dédiée) ou orchestré par n8n.
- **Mémoire de session** : contexte conversation + page d'origine + lead partiel.

## 3. Proactivité (déclencheurs & accroches)
Déclencheurs (configurables, anti-intrusif : 1 accroche, pas de spam) :
- **Temps sur page** (> 20-30 s) sur une page clé.
- **Profondeur de scroll** (a lu l'offre).
- **Page à forte intention** : Tarifs, une offre précise, page service.
- **Intention de sortie** (exit intent souris).
- **Visiteur de retour** (déjà venu → accroche « on reprend ? »).

Accroches = **propositions de valeur**, pas « puis-je vous aider ? » :
- CS (Tarifs) : « Vous comparez les offres ? Dites-moi votre besoin, je vous dis en 30 s
  ce qui colle et combien ça coûte. »
- CS (page Automatisation) : « Quelle tâche vous fait perdre le plus de temps ? Je vous
  montre comment on l'automatise. »
- CD (page projets) : « Un projet d'aménagement en tête ? Je vous fais une première
  estimation et on cale une visite. »

## 4. Les deux personas

| | **Chatbot CS** | **Chatbot CD** |
|---|---|---|
| Domaine | digital, web, IA, automatisation | architecture d'intérieur |
| Ton | dynamique, concret, orienté ROI | esthétique, à l'écoute, rassurant |
| Propose | exemple/cas, audit, RDV 15 min, devis | estimation, visite, portfolio, RDV |
| Base de connaissances | offres CS, cas clients, process | prestations CD, réalisations, style |

## 5. Tools (function calling)
1. **`capture_contact`** — récupère nom + email/téléphone dès que pertinent (lead).
2. **`qualify_lead`** — besoin, secteur, budget indicatif, délai, canal préféré → Airtable.
3. **`book_appointment`** — RDV via Composio Google Calendar (CS / CD).
4. **`propose_case`** — pousse le cas client / l'offre la plus pertinente selon le besoin.
5. **`send_recap`** — email Resend de récap (proposition + lien RDV).
6. **`handoff_human`** — alerte Telegram à Vannina (lead chaud / question hors périmètre).

## 6. Lead capture & CRM
- Chaque conversation → ligne Airtable (lead) : entité, page, besoin, qualif, statut.
- Lead chaud → **Telegram temps réel** à Vannina.
- Relance possible (email Resend / re-ciblage).

## 7. UX & conformité
- Bulle discrète, 1 accroche proactive max par session, fermable.
- Branding CS (bleu nuit / corail) et CD (sa propre identité).
- RGPD : mention claire (IA + traitement des données), consentement avant capture de
  données personnelles, finalité, données minimales.
- Ne jamais inventer (réponses ancrées dans la base de connaissances).

## 8. Omnicanal (voix + chat, 1 cerveau)
- Le persona + la base de connaissances + les tools sont **partagés** avec l'agent
  vocal de l'entité.
- Argument commercial : cohérence totale, présence 24/7 sur 2 canaux. Vendable en combo.

## 9. Plan de réalisation
- **C1** — Backend chat (Claude API + tools `capture_contact`, `qualify_lead`,
  `book_appointment`) réutilisant la base de connaissances CS, branché Airtable + Telegram.
- **C2** — Composant Framer (widget) + déclencheurs proactifs + accroches CS.
- **C3** — Déclinaison **CD** (persona + base de connaissances + page).
- **C4** — `propose_case` + `send_recap` + affinage accroches + mesures (taux
  d'engagement, leads, RDV).
- **C5** — Continuité voix↔chat + offre combo.

## 10. À confirmer
1. Backend : route sur l'app FastAPI (VPS) ou orchestration n8n ?
2. Périmètre base de connaissances CD (réalisations, style, prestations) à fournir.
3. Niveau de proactivité (agressif vs discret) et pages prioritaires.
4. Widget : design custom Framer ou base d'un composant existant.
