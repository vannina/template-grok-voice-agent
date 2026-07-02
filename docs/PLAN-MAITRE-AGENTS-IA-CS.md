# Plan maître — Agents IA Corsica Studio (source de vérité ordonnée)

> Rédigé le 2026-07-01. Consolide tous les docs et **ordonne** le chantier. Mené **de
> front sur 3 axes**. Décisions Vannina intégrées : modèle **hybride**, **CS d'abord**,
> wedge **« réveil de devis »**, **niche n°1 = BTP/dépannage**, **niche n°2 = hôtellerie
> multilingue** ; prospection **B2B only** ; pas d'aides corses ; prix HT en fourchette.

Docs liés : `BENCHMARK-MARCHE-AGENTS-IA-2026` · `CATALOGUE-AGENTS-VOCAUX-CS` ·
`OFFRES-PRICING-AGENTS-IA-CS` · `ARCHITECTURE-STANDARD-IA-CS-CD` · `CHATBOT-PROACTIF-CS-CD`
· `PROSPECTION-IA-CS`. Mémoire : `strategie-agents-ia-cs`.

---

## 0. Cap stratégique
- **Vendre le système, pas le bot** (le bot nu = commodité à 89 €). Bundle site +
  automatisation + agent + prospection + confiance locale + démo micro-site.
- **Hybride** : premium sur-mesure (marge) + produit d'appel standardisé (volume).
- **CS d'abord** ; CS finance CD ensuite.
- **Standards transverses tous agents** : annonce IA + enregistrement ; identification
  appelant + accueil personnalisé ; **transfert vers Vannina sur demande** ; multilingue
  là où c'est pertinent.

## 1. Les 3 axes (de front)
- **Axe A — Agents vocaux (inbound)** : ton standard perso CS+CD **+** la gamme vendable
  (Secrétariat IA en tête), décliné par niche.
- **Axe B — Chatbot proactif** (CS puis CD) : même cerveau que la voix, sur le site.
- **Axe C — Prospection IA B2B (Corsica Studio UNIQUEMENT)** : email-first (WF-06a
  généralisé) + scoring + voix outbound B2B conforme. + wedge **« réveil de devis »**.
  Corsica Design n'est **jamais prospecté** (uniquement joignable via le standard entrant).

## 2. Séquencement ordonné (phases)

### P0 — Déjà fait
- 7 pages démo agent vocal + bouton d'appel live (voix testée OK).
- Démos sectorielles en ligne (resto, hôtel, médical, immo, artisan, coach, beauté).
- WF-06a cold email en prod (867 restaurateurs).
- Benchmark, catalogue, offres/pricing, archi standard, chatbot, prospection : **documentés**.

### P1 — Demain
- **Auth API Framer** (`npx @framer/agent project auth`) — fluidifier les modifs de site.

### P2 — Fondation NICHE n°1 (BTP/dépannage) — *priorité haute*
- Décliner l'agent **« Standard / Secrétariat IA dépannage »** depuis le moteur (config
  secteur) : persona urgences, qualification urgence vs RDV, prise de coordonnées, SMS au
  pro. + `identify_caller` + `transfer_to_human`.
- **Démo micro-site dépannage** (sans friction) pour la vente.
- Page de vente + offre packagée Secrétariat IA (setup 600-1 200 € / abo 130-220 €/mois HT).

### P3 — Wedge « réveil de devis » — *signe vite*
- Agent qui relance la **base de devis sans suite / clients existants** (consentement OK,
  légal). n8n + Airtable + script. **Démo ROI 48 h** = produit d'appel pour ouvrir la porte.

### P4 — Ton standard perso CS+CD
- IVR 1/2 (Studio/Design), renvoi 06 51 00 30 49 → Twilio 04 12 13 60 10, RDV Composio,
  caller-ID, transfert sur demande, notif. **Après tes 6 confirmations** (§11 archi standard).
- L'agent Secrétariat (P2) = la même brique → on construit une fois, on templatise.

### P5 — Chatbot proactif CS (puis CD)
- Backend Claude (même cerveau) + widget Framer, déclencheurs par intention (non intrusif),
  capture lead + RDV. Puis déclinaison CD (qualifieur de projet).

### P6 — Prospection IA B2B
- **Email-first** : généraliser WF-06a à d'autres secteurs (au-delà resto) + scoring.
- **Voix outbound B2B** conforme (Twilio outbound + WF-OUT, horaires, opposition immédiate,
  déclaration IA) — secteurs interdits exclus. Jamais de B2C.

### P7 — Corsica Design
- **Visu IA avant/après** (WaveSpeed/fal.ai) en chatbot → consultation payante.
- Qualifieur de leads projet + nurturing prescripteurs (B2B, sans cold call).
- CD = vitrine revendable au vertical « métiers de la déco ».

## 3. Niches (ordre d'attaque)
1. **BTP / dépannage** (confirmé) — cycle court, douleur forte, références rapides.
2. **Hôtellerie multilingue** (FR/IT/EN/DE) — fossé vs concurrents franco-centrés ;
   abonnement saison ; attaquer en **pré-saison (fév-avr)**.
3. **Beauté/bien-être** — ferme vite, accumule des cas clients.
4. **Restauration/traiteurs** (emporter), **santé véto/dentaire** (2e vague, RGPD).

## 4. Go-to-market
- **Wedge** : « réveil de devis » (ROI immédiat) → ouvre, puis upsell Secrétariat IA + bundle.
- **Canal** : direct (démo micro-site) **+ prescripteurs** (comptables, chambre de métiers,
  fédérations BTP) en revenu partagé.
- **Autorité/inbound** : baromètre local « appels manqués des TPE corses » (data de tes
  agents) → presse/backlinks ; contenu LinkedIn (WF-12).
- **Prix** : entre AirAgent (89 €) et VOKAI (299 €), justifié par le sur-mesure. Option
  **garantie/perf** pour lever le risque TPE.

## 5. Réutilisation vs à construire
- **Réutilise** : moteur Twilio↔xAI, `_server_tool_call`, config par segment, Composio
  Calendar, auto-hangup, caller-ID, WF-06a, tracking `?lead=`/usage.jsonl, VPS+Traefik.
- **À construire** : configs niche (dépannage…), `transfer_to_human`, `identify_caller`,
  table Airtable Contacts/Appels, WF n8n (réception, confirmation, digest, scoring, outbound),
  Twilio outbound, backend chat + widget Framer, visu IA CD.

## 6. Décisions encore ouvertes (à trancher)
1. Standard perso : les **6 points §11** de `ARCHITECTURE-STANDARD-IA-CS-CD` (opérateur/renvoi,
   agendas, horaires, voix, transfert, conteneur).
2. **Transfert** : numéro dédié sans renvoi vs toggle « dispo » vs Dial-timeout (anti-boucle).
3. Niche n°1 : valider le **sous-segment** d'attaque (plombier ? serrurier ? multi ?).
4. Bornes de prix finales + test offre garantie/perf.

## 6bis. Programme d'exécution validé (Vannina, 2026-07-01) — « gère tout ça »
Quatre livrables à mener, je pilote :
- **L1 — Agent de prospection SDR IA** (outbound B2B) : appelle les entreprises, propose
  les services CS, valide les leads, prend RDV avec Vannina, fait de la pédagogie.
- **L2 — Standard entrant CS + CD** : sur non-réponse du 06, l'agent route selon le besoin
  (Studio/Design), renseigne, prend RDV/message, transfert sur demande.
- **L3 — « Secrétaire générale » agent vocal sur le site CS** (widget vocal embarqué, façon
  démos, qui représente Corsica Studio : renseigne, oriente, prend RDV/message).
- **L4 — Pages « agents vocaux spécialisés » sur le site Framer** : décliner les métiers
  (BTP/dépannage en tête) en pages offres + démos vendables.

Ordre recommandé (réutilisation max + déblocage) :
1. **L2 standard entrant** (réutilise le moteur ; débloqué par 6 confirmations §11 archi).
2. **L3 secrétaire générale site** (même cerveau que L2, exposé sur le site).
3. **L4 pages spécialisées Framer** (vitrine de vente ; nécessite l'auth API Framer).
4. **L1 prospection SDR** (brique Twilio outbound nouvelle ; gros build, moteur de croissance).
Mené **de front** côté prépa (configs + specs), build séquencé pour la mise en prod.

Inputs minimaux pour démarrer (le reste = défauts intelligents, ajustables) :
- Opérateur mobile + délai de renvoi du 06 → 04 12 13 60 10.
- Transfert : numéro dédié sans renvoi **ou** toggle « dispo » (anti-boucle).
- Infos /CD (services, horaires, style) pour le persona Design.

## 7. Backlog ordonné (todo)
Voir la todo de session (tâches #7, #8, #11, #12, #13, #14✓, #15, #16). Ordre conseillé :
API Framer → niche BTP (agent + démo + offre) → réveil de devis → standard perso →
chatbot proactif → prospection B2B → CD.
