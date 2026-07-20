# Checklist maîtresse — Sprints agents IA Corsica Studio

> Source de vérité opérationnelle. Mise à jour à chaque avancée. `[x]` fait, `[ ]` à faire,
> `(V)` = action Vannina, `(C)` = action Claude. Détails dans les docs liés
> (PLAN-MAITRE, ARCHITECTURE-STANDARD, PROSPECTION-IA, CHATBOT-PROACTIF, OFFRES-PRICING,
> BENCHMARK, CATALOGUE). Rien ne doit être oublié.

Cap : modèle **hybride**, **CS d'abord**, niche n°1 **BTP/dépannage**, niche n°2 **hôtellerie
multilingue**, wedge **réveil de devis**, prospection **B2B only**, **pas d'aides corses**.

---

## ✅ Sprint 0 — Déjà fait (acquis)
- [x] (C) 7 pages démo + bouton d'appel live (voix testée OK)
- [x] (C) Démos sectorielles en ligne (resto, hôtel, médical, immo, artisan, coach, beauté)
- [x] (C) WF-06a cold email en prod (867 restaurateurs)
- [x] (C) Numéro Twilio démo 04 12 13 60 20 branché + coffre à jour
- [x] (C) Docs : benchmark, catalogue, offres/pricing, archi standard, chatbot, prospection, plan maître
- [x] (C) Skills Framer agent installés (`npx @framer/agent setup`)

## Sprint 1 — Déblocage & fondations *(à faire en premier)*
- [x] (V+C) **Auth API Framer** : projet `OjzOQVoVRE6fGasAiFsZ` autorisé le 2026-07-01 ✅
- [x] (V) **Opérateur mobile identifié le 2026-07-02 : Free Mobile** (renvoi via espace abonné ou `**61*`) ; activation du renvoi = dernière étape A.5, après recette
- [x] (C) **Transfert** : résolu par défaut A.3 = toggle `TRANSFER_ENABLED` (+ fallback Airtable Config) + Dial 20 s → reprise agent ; `TRANSFER_NUMBER` devra être une ligne SANS renvoi (2026-07-02)
- [x] (V) **Infos /CD** récupérées de corsicadesign.com le 2026-07-02 (services, process, positionnement) ; reste : horaires RDV préférés
- [ ] (V) Confirmer les 6 points §11 de ARCHITECTURE-STANDARD (agendas, horaires, voix, conteneur)
- [x] (C) Numéro standard = **+33 4 12 13 60 16** acheté (le 10 n'était pas chez Twilio) + webhook branché → standard.corsica-studio.com/twilio/voice — 2026-07-02
- [x] (C) Base Airtable standard — **fait 2026-07-02 (A.4)** : permission `create_base` refusée au MCP → tables « Standard — » dans « Campagne Agent Vocal » (`appZaFI40YcGBCn8D`) : Appels `tblF0Q3jchpNb8C97`, Contacts `tblHUXSuCWt8Tt1fn`, Config `tbljnAJI1n4jVZ5lK` (record `standard`, transfert off)

## Sprint 2 — L2 : Standard entrant CS + CD *(réutilise le moteur)*
- [x] (C) IVR `/twilio/voice` : annonce légale + Gather 1/2 — **fait 2026-07-02, commit d07a6a5, 26/26 checks**
- [x] (C) `/twilio/route` : route 1→cs / 2→cd → `<Connect><Stream entite=…>` — **fait 2026-07-02**
- [x] (C) Dossiers config `entites/cs|cd/` créés (squelettes ; personas = A.2 en cours) — **2026-07-02**
- [x] (C) Personas CS + CD (vraies infos corsicadesign.com, 8 sections, R1/R2) — **fait 2026-07-02, commit 38cdfd6, 54 checks** ; TODO restant : horaires RDV (V)
- [x] (C) Tools standard : identify_caller (pré-fetch nominatif), qualify_lead, request_callback, transfer_to_human (toggle + Dial 20s + reprise), webhook fin d'appel — **fait 2026-07-02, commit 2939e84, 51 checks** (book/check/get/message existaient)
- [x] (C) 2 agendas Google créés via Composio le 2026-07-02 (RDV Corsica Studio 45e70304…, RDV Corsica Design 5b609809…, tz Europe/Paris, visibles dans le compte contact.corsicastudio@gmail.com)
- [x] (C) calendar_id branchés en littéral dans `entites/cs|cd/profile.json` — 2026-07-02
- [x] (C) Accueil personnalisé (pré-fetch A.3) + base de connaissances CS enrichie du site (qualif 6 besoins × 7 professions, commit 463e6ff) — 2026-07-02
- [x] (C) Post-traitement → n8n (Airtable + Telegram) — **fait 2026-07-02 (A.4)** : WF-Standard-Reception `Dif4bdlL818IcUY7` (webhook `standard-fin-appel` → Appels + upsert Contacts + Telegram) et WF-Standard-Digest `afWCvDC016CrlNZU` (cron 21h, digest si ≥1 appel), **créés INACTIFS**, credentials existants auto-assignés ; activation + `STANDARD_WEBHOOK_URL` dans le `.env` = A.5. Resend confirmation RDV : reste à faire (⚠️ pas d'email collecté au téléphone → à remplacer par SMS Twilio de confirmation, à arbitrer)
- [x] (C) Déploiement VPS : service dédié `standard-voice` + Traefik + `.env` (STANDARD_*, ENABLE_CALLBACK_TOOL=1, TRANSFER_ENABLED=0) — 2026-07-02, IVR public testé 200
- [ ] (V+C) **Recette EN COURS** : appel test Vannina au 04 12 13 60 16 (IVR→agent→RDV→Telegram)
- [x] (V) Renvois Free ACTIFS 06 → 04 12 13 60 16 (2026-07-03) — standard EN PRODUCTION ; re-vérification finale par Vannina à venir

## Sprint 3 — L3 : « Secrétaire générale » CS sur le site
- [ ] (C) Config agent « secrétaire générale CS » (même cerveau que L2 côté Studio)
- [ ] (C) Page/section vocale sur corsica-studio.com (façon démos, via Framer + app)
- [ ] (C) Caller-ID/identification + capture lead → Airtable + Telegram
- [ ] (C) Transfert sur demande
- [ ] (V+C) Test + publication

## Sprint 4 — L4 : Pages « agents vocaux spécialisés » sur Framer *(vitrine de vente)*
- [x] (C) Démo BTP/dépannage : métier `depannage` (Marc, SOS Dépann' 2A, triage urgences) commit 2622065 + copy page complète (CS-framer 711d5aa) — 2026-07-02 ; reste intégration Framer + 5 validations Vannina
- [x] (C) Hôtellerie multilingue : métier `hotel-international` (Chloé 4 langues, whisper_language par profil, commit 28e96bd) DÉPLOYÉ + copy page (70a10a3) — 2026-07-02 ; reste intégration Framer
- [ ] (C) Décliner beauté / resto / santé (réutiliser démos existantes)
- [ ] (C) Intégrer les offres/pricing (packs) sur les pages
- [ ] (C) CTA démo + prise de contact (lead → Airtable)
- [ ] (C) **Menu/navbar** : ajouter les 3 pages agents vocaux au dropdown + footer + maillage interne
- [ ] (C) **SEO des 3 pages** comme toute page du site : title + meta description (copys §1), **image OG dédiée** (générateur og-image), **schema.org complet** (Service + FAQPage + BreadcrumbList + LocalBusiness + Offer, skill schema-markup, vérif SSR + Rich Results Test), sitemap, breakpoints mobile
- [ ] (V) Validation visuelle des 3 pages puis PUBLICATION

## Sprint 5 — Wedge « réveil de devis » *(produit d'appel, signe vite)*
- [ ] (C) Script agent de relance (devis sans suite / clients existants — consentement OK)
- [ ] (C) WF n8n : import base devis (Airtable) → appels/emails → log résultat
- [ ] (C) Offre packagée + page de vente « ROI 48 h »
- [ ] (V) Fournir une base de devis test pour démo

## Sprint 6 — L1 : Agent de prospection SDR IA (B2B) *(gros build, croissance)*
- [x] (C) Brique Twilio outbound : POST /outbound/call (token, horaires 9-12/14-18, contrôle opposition) + /twilio/voice-out + contexte prospect injecté — **fait 2026-07-03** (agent coupé par la limite de session, complété à la main, smoke 22/22)
- [ ] (C) WF-OUT n8n (liste Airtable + horaires ouvrés + déclencheur)
- [ ] (C) Sourcing/enrichissement (Apify/MCP) + WF-SCORING (Claude)
- [x] (C) Métier `prospection` : Léa, SDR pédagogue (présentation conforme + opt-out immédiat, pitch dépannage, RDV 30 min agenda CS) — **fait 2026-07-03**
- [x] (C) Tools : book_reservation (RDV Vannina) + marquer_opposition (Airtable Oppositions) + qualify_lead — **fait 2026-07-03**
- [x] (C) Cahier des charges conversationnel NORMATIF (`docs/CAHIER-DES-CHARGES-CONVERSATION.md`, 9 sections) — **fait 2026-07-06**
- [x] (C+V) **Léa v13 → v14.1 VALIDÉE par Vannina le 2026-07-20** : v13 (enchaînement 2,5 s ×2, au revoir + fenêtre 3 s, 9c24992) + v14 (mode information, plafond 2 RDV, cahier 6.9-6.11) + v14.1 (réponse dans le même souffle, 6.12) — simulateur 8 scénarios, déployée. Rappel : OUTBOUND_HOURS=8-22 (tests) à remettre 9-12,14-18 avant pilote
- [ ] (C) Séquence email B2B 4 touches (réutilise WF-06a) en pré-chauffe
- [ ] (C) Conformité B2B opt-out (mentions, opposition, secteurs exclus) — checklist légale
- [ ] (V+C) Test campagne pilote + KPIs (réponse, RDV, coût/lead)

## Sprint 7 — Chatbot proactif (CS puis CD)
- [ ] (C) Backend chat Claude (même cerveau) + tools (capture_contact, qualify_lead, book)
- [ ] (C) Widget Framer + déclencheurs par intention (non intrusif)
- [ ] (C) Accroches CS (page Tarifs / Automatisation) + capture lead
- [ ] (C) Déclinaison CD (qualifieur de projet)

## Sprint 8 — Corsica Design (croissance CD)
- [ ] (C) Chatbot **visu IA avant/après** (WaveSpeed/fal.ai) → consultation payante
- [ ] (C) Qualifieur de leads projet (budget, surface, délai, localisation)
- [ ] (C) Nurturing prescripteurs B2B (sans cold call)

## Transverse (tous sprints)
- [ ] (C) Standards : annonce IA + enregistrement, caller-ID, transfert, RGPD
- [ ] (C) Tout consigner + commit/push après chaque étape ; MAJ `.wolf` + cette checklist
- [ ] (C) Go-to-market : prescripteurs (comptables, chambre de métiers, fédé BTP)
- [ ] (C) Autorité/inbound : baromètre local « appels manqués TPE corses » + LinkedIn (WF-12)
- [ ] (C) Tester option pricing **garantie/perf** (0 appel manqué / paiement au RDV)

---

### Légende d'avancement
Je coche au fil de l'eau. Les blocages (V) sont en tête de chaque sprint : tant qu'ils ne
sont pas levés, le build de ce sprint attend. Aucun élément n'est perdu : tout vit ici +
dans les docs liés + la mémoire (`strategie-agents-ia-cs`).

## Sprint 9 — Vertical coiffeurs (France entière, hors Corse) *(lancé 2026-07-20 sur demande Vannina)*
- [x] (C) Démo coiffeur EN LIGNE : demo-coiffeur.corsica-studio.com (Salomé, L'Atelier Coiffure, Aix) — config 4 fichiers, smoke 22/22, Traefik + wildcard DNS OK — **fait 2026-07-20**
- [x] (C) Benchmark concurrents : docs/BENCHMARK-COIFFEURS-2026.md (Fresha ~95 €/mois, Tala 29-499 €/mois HT ; « Cecchi » introuvable) — **fait 2026-07-20**
- [x] (C) Léa : ancrage métier coiffeur (mains dans la couleur, complément Planity) + recette non-régression — **fait 2026-07-20**
- [x] (C) Copy page Framer : CS-framer-website/01-framer-site/pages-agents-vocaux/PAGE-COIFFEUR-COPY.md (slug /agent-vocal-coiffeur) — **fait 2026-07-20**
- [x] (C) Image OG og-agent-vocal-coiffeur.png (gabarit #24, générateur og-image/generate_agents_vocaux_og.py, Salomé) + gabarit HTML sauvegardé dans CS-framer-website/01-framer-site/pages-agents-vocaux/og/ — **fait 2026-07-20**
- [x] (V) « Cecchi » = erreur du correcteur (résolu 2026-07-20) : pas d'acteur de ce nom, benchmark = Fresha + Tala
- [x] (V) Page dupliquée depuis /agent-vocal-depannage + path /agent-vocal-coiffeur + title + description — **fait 2026-07-20**
- [ ] (V) Uploader og-agent-vocal-coiffeur.png dans les réglages de la page Framer (Social Image)
- [ ] (C) Injection du contenu dans la page (MCP Framer : variante coiffeur du template, H1, sections, pricing, FAQ, schema) + vérification
- [ ] (C) Menu/navbar + footer : ajouter la page coiffeur au dropdown offres + maillage
- [ ] (V) Validation visuelle (desktop + mobile) puis PUBLICATION
- [ ] (C) Sourcing salons de coiffure France (hors Corse) + cross-suppression + pilote Léa coiffeurs
