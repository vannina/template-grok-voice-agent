# SPEC : Baromètre appels manqués (lead magnet vague 2)

> Rédigé le 2026-07-21. Statut : SPEC validable, AUCUN build engagé.
> Méthode : spec écrite + critères d'acceptation testables AVANT toute ligne de code
> (directive du 2026-07-06). Références normatives : `CLAUDE.md` (architecture),
> `docs/PROSPECTION-IA-CS.md` (moteur outbound, garde-fous), 
> `docs/CAHIER-DES-CHARGES-CONVERSATION.md` (conversation, règles 1.5, 4.x, 8.5).

---

## 0. Résumé exécutif

Le baromètre mesure la joignabilité téléphonique réelle d'un commerce cible :
3 tentatives d'appel à des heures clés de son métier, réparties sur 2 à 3 jours
ouvrés. Chaque tentative produit un statut mesuré (décroché humain, répondeur,
sonnerie dans le vide, occupé) via les statuts Twilio et l'AMD asynchrone déjà en
place. Résultat : un rapport PDF personnalisé (« 2 appels sur 3 ont sonné dans le
vide, voici ce que ça peut coûter dans votre métier ») envoyé par email (Resend),
puis Léa rappelle avec cette douleur prouvée.

Principe directeur tranché ici : **le baromètre ne génère JAMAIS d'appel muet ni
d'appel de test déguisé.** Toute tentative qui aboutit à un humain EST un appel de
prospection B2B conforme (ouverture Léa complète : identité, finalité, IA,
opposition). Les échecs (non-décroché, répondeur, occupé) sont mesurés
passivement, sans déranger personne. La mesure est un sous-produit de la
prospection légitime, pas une activité de surveillance.

---

## 1. Point tranché n°1 : conformité et éthique de l'appel-test

### 1.1 Options examinées

| Option | Description | Verdict |
|---|---|---|
| (a) Raccrocher après N sonneries, silence si décroché | Mesure pure | **REJETÉE** |
| (b) Message honnête « test de joignabilité » si décroché | Transparence | **REJETÉE** |
| (c) Si décroché : Léa enchaîne en vrai pitch B2B conforme | Un seul dérangement | **RETENUE** (avec 4 renforts, voir 1.3) |

### 1.2 Analyse du cadre légal et argumentaire

**Cadre applicable (B2B, France, loi n°2025-594 applicable au 11/08/2026)** :
le démarchage téléphonique B2B reste en régime d'opposition (opt-out) quand
l'objet est lié à l'activité du professionnel, avec droit d'opposition immédiat.
C'est exactement le cadre déjà implémenté dans `/outbound/call` (garde-fous
horaires, registre d'opposition, numéro français, ouverture conforme de Léa).

**Pourquoi (a) est rejetée.** Un appel décroché suivi d'un silence puis d'un
raccrochage est un « appel sans interlocuteur », pratique assimilable au ping
call / spam vocal, sanctionnée par l'ARCEP et le 33700 côté fraude aux numéros,
et qualifiable de pratique commerciale agressive côté DGCCRF si répétée. Trois
appels muets le même numéro en trois jours, depuis un numéro identifiable
Corsica Studio, c'est en plus un suicide commercial : le prospect rappelle,
tombe sur notre numéro, et associe la marque à du harcèlement. Rejet total,
y compris en variante « on raccroche avant le décroché » : impossible de
garantir le raccrochage avant décroché (le décroché peut survenir à la
1ère sonnerie), donc le risque d'appel muet existe structurellement.

**Pourquoi (b) est rejetée.** Le message « c'est un test de joignabilité »
cumule les inconvénients : il dérange autant qu'un vrai appel, n'apporte aucune
valeur au prospect, grille la surprise du rapport, biaise les tentatives
suivantes (le prospect se met à décrocher parce qu'il se sait observé), et
donne une image de surveillance (« Corsica Studio me teste à mon insu »).
Juridiquement ce n'est même pas plus sûr : un appel de « mesure » sans intérêt
pour l'appelé se justifie MOINS bien au titre de l'intérêt légitime qu'un appel
de prospection assumé et conforme.

**Pourquoi (c) est retenue.** L'intuition de Vannina est confirmée, pour trois
raisons : (1) chaque appel a une finalité licite et assumée (prospection B2B
sur un sujet lié à l'activité), l'ouverture conforme de Léa est déjà codée et
recettée ; (2) le prospect n'est dérangé qu'une seule fois au maximum sur tout
le baromètre (dès qu'un humain décroche, le baromètre s'arrête, voir 1.3) ;
(3) les données du rapport sont des faits produits par des appels légitimes,
pas par un dispositif de test caché : on peut l'écrire noir sur blanc dans le
rapport (« lors de nos 3 tentatives de prise de contact »), ce qui est
inattaquable.

### 1.3 Renforts obligatoires sur l'option (c) (challenge de l'intuition)

L'intuition « (c) au décroché + comptabiliser les non-décrochés » est bonne
mais insuffisante seule. Quatre renforts sont exigés :

1. **Arrêt au premier humain.** Dès qu'une tentative aboutit à un décroché
   humain, les tentatives restantes sont ANNULÉES. L'appel devient un appel de
   prospection classique (pipeline WF-OUT standard) et le prospect ne reçoit
   pas de rapport baromètre : il n'y a plus de douleur à prouver, Léa a déjà
   pitché en direct. Le rapport n'est envoyé que si au moins 1 tentative
   effectuée a échoué ET qu'aucun humain n'a décroché.
2. **Un seul message répondeur sur tout le baromètre.** Si l'AMD conclut
   répondeur : message de Léa (12 s max, règle 1.5 du cahier des charges
   conversation) UNIQUEMENT à la première tentative qui tombe sur répondeur.
   Tentatives suivantes sur répondeur : raccrochage AVANT le bip (dès verdict
   `machine_*`), aucun message, aucun dérangement. Trois messages vocaux en
   trois jours seraient perçus comme de l'insistance.
3. **Jamais deux tentatives le même jour** (voir point n°2). Une tentative par
   jour ouvré maximum, jamais le week-end, toujours dans les plages
   `OUTBOUND_HOURS` du serveur (garde-fou non contournable déjà en place).
4. **Opposition = arrêt total.** Si le prospect exprime son opposition à
   n'importe quelle tentative : `marquer_opposition` (déjà codé), annulation
   des tentatives restantes ET du rapport email (l'opposition vaut tous
   canaux). Un prospect déjà au registre d'opposition n'entre jamais dans un
   baromètre (`/outbound/call` refuse déjà, statut 403 `opposition`).

Le numéro présenté est le numéro prospection dédié (+33 4 12 13 60 43), déjà
rappelable : un prospect qui rappelle tombe sur Léa via
`/twilio/voice-prospection` (mécanique existante, réutilisée telle quelle).

---

## 2. Point tranché n°2 : cadence des 3 tentatives

### 2.1 Règles de cadencement (non contournables)

- **3 tentatives maximum par baromètre, 1 par jour ouvré maximum.**
- Réparties sur **3 jours ouvrés consécutifs** (J1, J2, J3) ; si un jour saute
  (férié, hors plage, quota), la tentative glisse au jour ouvré suivant, avec
  un plafond de **10 jours calendaires** pour boucler le baromètre (au-delà,
  clôture avec les tentatives effectuées).
- Chaque tentative vise un **créneau différent** de la grille métier (2.2) :
  jamais deux fois la même heure, pour échantillonner la journée du prospect.
- Toutes les tentatives passent par `/outbound/call` : les garde-fous serveur
  (token, horaires `OUTBOUND_HOURS`, numéro FR, opposition) s'appliquent sans
  exception. La grille métier est un sous-ensemble de `OUTBOUND_HOURS` ; si un
  créneau métier sort des plages serveur, il est écrêté au bord de plage le
  plus proche (jamais élargi).
- `TimeLimit` Twilio inchangé (plafond dur existant) ; en mode baromètre, une
  tentative non décrochée coûte 0 minute facturée (l'appel n'aboutit pas), une
  tentative répondeur coûte moins de 1 minute (message 12 s ou raccrochage au
  verdict AMD).

### 2.2 Grille des créneaux par métier (heure Europe/Paris, jours ouvrés)

Objectif : appeler quand le métier a statistiquement les mains prises, c'est
la démonstration même du produit. Les 3 créneaux sont tirés dans l'ordre T1,
T2, T3 (un par jour).

| Métier | T1 (rush) | T2 (creux présumé) | T3 (fin de journée) |
|---|---|---|---|
| restaurant | 12h00 | 15h30 | 18h45 |
| artisan / dépannage | 9h45 | 14h30 | 17h30 |
| beauté / salon | 10h30 | 14h00 | 17h45 |
| médical / paramédical | 9h30 | 11h30 | 17h00 |
| hôtel | 10h00 | 15h00 | 18h00 |
| immobilier | 10h00 | 14h00 | 18h00 |
| auto-école / club sport | 10h30 | 14h30 | 17h30 |
| défaut (métier inconnu) | 10h00 | 14h30 | 17h00 |

Chaque tentative part dans une fenêtre de tir de plus ou moins 15 minutes
autour du créneau (lissage de charge WF côté n8n). La grille vit dans la
config du workflow n8n (pas en dur dans le serveur) pour être ajustable sans
redéploiement. Volume initial prudent : 10 baromètres actifs en parallèle
maximum (soit au plus 10 appels par créneau), relevable après recette.

### 2.3 Séquencement avec le cold email (vague 2)

Le baromètre s'insère APRÈS la touche email 1 (J0) et AVANT l'appel chaud :
J0 email, J2-J4 baromètre (3 tentatives), J5 envoi du rapport PDF par email,
J6-J7 rappel de Léa en s'appuyant sur le rapport (« je vous ai envoyé votre
baromètre de joignabilité hier »). Un prospect désinscrit de l'email ou opposé
au téléphone n'entre pas ou sort immédiatement du baromètre.

---

## 3. Point tranché n°3 : contenu exact du rapport PDF

### 3.1 Structure (1 page A4 portrait, branding /CS)

1. **En-tête** : logo Corsica Studio, titre « Baromètre de joignabilité »,
   nom de l'établissement, ville, date d'édition.
2. **Le verdict en une phrase** (gros, corail #FF6E44) : « X appel(s) sur N
   n'ont pas trouvé d'interlocuteur. » (N = tentatives effectuées, jamais
   « sur 3 » si seulement 2 tentatives ont eu lieu).
3. **Le détail mesuré** (tableau, uniquement des faits) :
   - date + heure de chaque tentative ;
   - résultat : « décroché », « répondeur », « sonnerie sans réponse »,
     « ligne occupée » ;
   - durée de sonnerie avant issue (secondes, depuis les statuts Twilio).
4. **Ce que ça peut représenter** (chiffrage PRUDENT, voir 3.2) : une
   fourchette de manque à gagner mensuel, formulée en hypothèse et jamais en
   certitude, avec la source de chaque chiffre externe en note de bas de page.
5. **La solution en 3 lignes** : une assistante vocale qui décroche quand
   vous ne pouvez pas, positionnement relais (règle 6.4 : « elle intervient
   seulement quand vous ne décrochez pas »).
6. **Double CTA** : « Testez-la maintenant : 04 12 13 60 20 » + lien démo
   personnalisé `https://demo<-metier>.corsica-studio.com/?lead={record_id}`
   (attribution WF-13 existante) + « ou réservez 15 minutes avec Vannina »
   (lien agenda).
7. **Pied de page** : mentions : coordonnées /CS, rappel que les tentatives
   étaient des appels de prise de contact B2B de Corsica Studio, contact pour
   exercer son droit d'opposition, aucune mention d'aide publique.

### 3.2 Règles de chiffrage (anti-bullshit, bloquantes)

- **Deux familles de chiffres, jamais mélangées** :
  (1) les MESURES du baromètre (faits, présentés comme tels) ;
  (2) les HYPOTHÈSES de chiffrage (paniers moyens métier, part d'appels
  entrants commerciaux), présentées comme hypothèses avec leur source.
- **Aucun chiffre externe sans source vérifiable** (étude nommée, année,
  éditeur) stockée dans le gabarit. Au moment du build, chaque valeur de la
  table `chiffrage_metiers` doit référencer sa source ; s'il n'existe pas de
  source solide pour un métier, le rapport bascule sur la formulation
  hypothétique pure : « si un seul de ces appels était un client à
  [fourchette panier moyen métier] HT, cela représente jusqu'à [calcul] HT
  par mois ». Le calcul n'utilise alors QUE le panier moyen (fourchette
  saisie par métier, validée par Vannina) et le taux mesuré du baromètre.
- **Toujours des fourchettes, toujours en HT, jamais un chiffre unique.**
  Borne basse systématiquement conservatrice (1 appel manqué converti sur 10).
- **Interdits** : « une étude montre que » sans référence ; extrapolation
  annuelle en gros titre (le mensuel suffit) ; toute promesse de gain.
- Table de chiffrage par métier (valeurs à sourcer au build, format imposé) :
  `{ metier, panier_moyen_ht: [min, max], appels_jour_estimes: [min, max],
  source: {titre, editeur, annee, url} | null }`.

### 3.3 Cas particuliers de contenu

- **1 seule tentative échouée sur 2 ou 3 effectuées** : ton mesuré
  (« votre joignabilité est bonne, mais le créneau de [heure] reste à
  risque »), le CTA reste.
- **3 échecs sur 3** : verdict fort mais factuel, jamais moqueur.
- **0 échec** : pas de rapport (voir 1.3.1, le baromètre s'est arrêté).
- Le PDF fait moins de 500 Ko (pièce jointe email), nom de fichier
  `barometre-joignabilite-{slug-etablissement}.pdf`.

### 3.4 Email porteur (Resend)

- Expéditeur identifié /CS, objet sobre : « votre baromètre de joignabilité »
  (minuscules, style campagne existante WF-06a).
- Corps court (5 lignes max) : le verdict en une phrase, le PDF en pièce
  jointe, le lien démo `?lead=`, le lien de désinscription (conformité
  WF-06a réutilisée).
- Envoi via Resend (DNS OVH déjà configurés), tracking ouverture/clic activé.
- Audit du rendu réel obligatoire avant mise en prod (directive mémoire :
  relire l'email envoyé via l'API Resend, template inclus).

---

## 4. Point tranché n°4 : architecture technique

### 4.1 Principe : extension, pas de nouveau moteur

Tout s'appuie sur le moteur outbound existant. Les nouveautés sont : un mode
`barometre` dans `/outbound/call`, la capture des statuts finaux Twilio
(StatusCallback, absente aujourd'hui), une brique de rendu PDF, un workflow
n8n orchestrateur (WF-BARO) et des champs Airtable `baro_*`.

### 4.2 Serveur `web/server.py` (conteneur demo-voice)

**B1. Mode baromètre sur `POST /outbound/call`** (effort : 1 à 1,5 jour)
- Body étendu : `{"to", "prospect", "mode": "barometre", "attempt": 1|2|3,
  "baro_id": "<id Airtable du baromètre>"}`. Sans `mode`, comportement
  strictement inchangé (rétro-compat totale, comme pour l'AMD v5).
- En mode baromètre, le serveur passe à `calls.create` :
  `StatusCallback=https://<host>/twilio/call-status?baro_id=...&attempt=...`
  avec `StatusCallbackEvent=initiated ringing answered completed`.
- Comportement conversationnel si décroché humain : IDENTIQUE au mode
  prospection (prompt Léa inchangé, ouverture conforme). Le mode baromètre ne
  change RIEN à ce que le prospect entend : il ne change que la télémétrie et
  la politique répondeur.
- Politique répondeur pilotée par un flag de contexte : `attempt` dont le
  baromètre a déjà laissé un message (info passée par n8n dans le body,
  `voicemail_deja_laisse: true|false`) ; si true et verdict AMD `machine_*`,
  raccrochage immédiat au verdict, sans message.

**B2. Endpoint `POST /twilio/call-status`** (effort : 0,5 à 1 jour)
- Reçoit les callbacks Twilio : `CallSid`, `CallStatus` (`completed`,
  `no-answer`, `busy`, `failed`, `canceled`), `CallDuration`,
  `Timestamp`. Croise avec le verdict AMD déjà stocké (`_AMD_RESULTS`) pour
  produire le **résultat consolidé** d'une tentative :
  - `CallStatus=no-answer` → `sonnerie_sans_reponse`
  - `CallStatus=busy` → `occupe`
  - `completed` + AMD `machine_*` ou `fax` → `repondeur`
  - `completed` + AMD `human` (ou parole humaine détectée par le pont WS) →
    `decroche_humain`
  - `failed`/`canceled` → `echec_technique` (exclu du rapport, retentée 1 fois)
- Journalise dans `usage.jsonl` (`{"event": "baro_attempt", "baro_id", 
  "attempt", "resultat", "duree_s", "ts"}`) ET pousse le résultat à n8n via
  webhook (`BARO_WEBHOOK_URL`, best-effort httpx comme `_demo_webhook`,
  jamais bloquant). Répond toujours 204 à Twilio.

**B3. Rendu PDF `POST /barometre/report`** (effort : 1 à 1,5 jour)
- Recommandation tranchée : **WeasyPrint dans le conteneur demo-voice**
  (HTML + CSS vers PDF, polices MuseoModerno / Source Sans 3 embarquées en
  fichiers locaux, zéro réseau au rendu, zéro Chrome). La recette Chrome
  headless (mémoire du 2026-06-13) reste la solution de secours si WeasyPrint
  pose problème dans l'image python:3.12-slim, mais Chrome alourdit l'image
  d'environ 400 Mo : WeasyPrint d'abord.
- Body : `{ baro_id, etablissement, ville, metier, tentatives: [{ts, creneau,
  resultat, duree_s}], record_id }`. Le serveur charge la table
  `chiffrage_metiers` (fichier `web/config/barometre/chiffrage.json`,
  bind-mounté donc éditable sans rebuild), calcule les fourchettes, rend le
  gabarit `web/config/barometre/rapport.html` et renvoie le PDF binaire
  (n8n le récupère et l'attache à l'email Resend).
- Protégé par le même header `X-Outbound-Token`.

### 4.3 n8n : WF-BARO (nouveau) (effort : 1 à 1,5 jour)

- **Entrée** : vue Airtable « à baromètrer » (statut `Emailé`, tel pro
  vérifié, `opposition=false`, `baro_statut` vide, métier dans la grille).
- **Planification** : crée l'enregistrement baromètre (`baro_statut=planifie`,
  créneaux T1/T2/T3 calculés depuis la grille métier stockée dans le WF),
  puis 1 exécution cron par créneau (fenêtre de tir 15 min, quota global
  10 baromètres actifs).
- **Tir** : POST `/outbound/call` avec `mode=barometre` ; gère les refus
  serveur (`hors_horaires` → replanifie au jour ouvré suivant, `opposition` →
  clôture immédiate du baromètre sans rapport).
- **Collecte** : webhook `BARO_WEBHOOK_URL` ; écrit `baro_tN_*` dans Airtable.
  Si `decroche_humain` → annule les crons restants, `baro_statut=decroche`
  (pas de rapport, pipeline prospection standard) ; si `echec_technique` →
  une seule re-tentative le jour ouvré suivant au même créneau.
- **Clôture** : après T3 (ou plafond 10 jours) : si au moins 1 échec mesuré,
  POST `/barometre/report`, envoi Resend (PDF joint + lien `?lead=`),
  `baro_statut=rapport_envoye`, alerte Telegram (extension WF-13). J+1 ou
  J+2 : injecte le prospect dans la file d'appels de Léa (WF-OUT) avec un
  contexte `barometre` dans la fiche prospect pour que Léa cite le rapport.

### 4.4 Airtable (base prospects /CS) (effort : 0,25 jour)

Champs à ajouter : `baro_statut` (planifie / en_cours / decroche /
rapport_envoye / oppose / abandonne), `baro_t1_ts`, `baro_t1_resultat`,
`baro_t1_duree`, idem t2/t3, `baro_score` (« 2/3 manqués »),
`baro_rapport_url` (pièce jointe), `baro_email_ouvert` (bool, webhook
Resend), `baro_email_clique` (bool).

### 4.5 Estimation d'effort récapitulative

| Brique | Effort |
|---|---|
| B1 mode baromètre `/outbound/call` + politique répondeur | 1 à 1,5 j |
| B2 `/twilio/call-status` + consolidation + webhook n8n | 0,5 à 1 j |
| B3 rendu PDF WeasyPrint + gabarit HTML + chiffrage.json | 1 à 1,5 j |
| WF-BARO n8n (planif, tir, collecte, clôture, quotas) | 1 à 1,5 j |
| Email Resend (gabarit + pièce jointe + tracking + audit rendu réel) | 0,5 à 1 j |
| Schéma Airtable + vue + extension WF-13 Telegram | 0,25 j |
| Auto-recette complète (simulateur, mocks Twilio, jeu de données) | 1 à 1,5 j |
| **Total** | **5,25 à 8,25 jours** (cible réaliste : 7 j) |

---

## 5. Point tranché n°5 : KPIs et coût unitaire

### 5.1 KPIs du baromètre (suivis dans le digest WF-06b)

| Métrique | Définition | Cible indicative |
|---|---|---|
| Taux de complétion | baromètres clos / baromètres lancés | supérieur à 90 % |
| Taux « douleur prouvée » | rapports envoyés / baromètres clos | 40 à 70 % (dépend du ciblage) |
| Taux d'ouverture email rapport | ouvertures Resend / rapports envoyés | 45 à 65 % (objet personnalisé + pièce jointe attendue) |
| Taux de clic (démo ou RDV) | clics / rapports envoyés | 8 à 15 % |
| Taux de rappel entrant | rappels sur +33 4 12 13 60 43 attribués / rapports | suivi (bonus) |
| Rappel Léa → conversation | décrochés / rappels Léa post-rapport | 30 à 50 % (numéro déjà vu 3 fois : attendu au-dessus des 25-40 % du froid) |
| Conversation → RDV | RDV pris / conversations post-rapport | 15 à 25 % |
| Taux d'opposition | oppositions / prospects baromètrés | inférieur à 5 %, sinon revoir ciblage ou cadence |

### 5.2 Coût unitaire par prospect baromètré (fourchettes prudentes, à recaler sur la première facture Twilio réelle)

- Tentative non décrochée (no-answer, busy) : environ 0 € (appel non abouti,
  non facturé ou facturation résiduelle négligeable).
- Tentative répondeur : moins de 1 min Twilio sortant FR (fixe environ
  0,015 à 0,02 € HT/min, mobile environ 0,09 à 0,12 € HT/min) + AMD (environ
  0,0075 € HT/appel analysé) + xAI voix pour 12 s de message.
- Tentative décrochée : appel de prospection normal, plafonné par
  `OUTBOUND_TIME_LIMIT` (coût du pipeline WF-OUT standard, pas un surcoût
  baromètre).
- Rendu PDF + email Resend : négligeable (infra existante).

**Fourchette retenue : 0,05 à 0,50 € HT par baromètre complet (3 tentatives)
hors cas décroché humain**, soit moins de 1 € HT par douleur prouvée. Un seul
RDV pris rembourse plusieurs milliers de baromètres : le coût n'est pas le
sujet, le goulot est le quota d'appels quotidien et la qualité du ciblage.

---

## 6. Point tranché n°6 : critères d'acceptation TESTABLES

Chaque critère est vérifiable par simulateur (`tools/simulate_call.py` étendu
ou mocks httpx), par curl, ou par inspection de données. Aucun critère validé
par une écoute de Vannina : elle est la validation finale sur produit vert.

**Garde-fous et conformité**
1. `curl POST /outbound/call` avec `mode=barometre` SANS header
   `X-Outbound-Token` → HTTP 403, aucun `calls.create` émis (mock Twilio à
   zéro appel).
2. `mode=barometre` hors plages `OUTBOUND_HOURS` (horloge mockée samedi 11h)
   → HTTP 423 `hors_horaires`, aucun appel.
3. `mode=barometre` vers un numéro présent au registre d'opposition → HTTP
   403 `opposition`, aucun appel, aucune écriture `baro_*`.
4. Numéro non français (`+1...`) → HTTP 400 `numero_invalide`.
5. Body sans `mode` → réponse et comportement OCTET pour OCTET identiques à
   l'existant (test de non-régression : mêmes champs JSON, pas de
   `StatusCallback` dans le `calls.create` mocké).
6. En mode baromètre, le `calls.create` mocké contient `StatusCallback`,
   `StatusCallbackEvent`, `MachineDetection=DetectMessageEnd`, `AsyncAmd=true`
   et le `TimeLimit` existant.
7. Simulation d'un décroché humain en mode baromètre : le transcript généré
   contient l'ouverture conforme complète (identité Corsica Studio, finalité,
   déclaration IA, proposition d'opposition) dans les 2 premières répliques
   de Léa (verdict automatique du simulateur, regex sur le transcript).
8. Simulation opposition (« ne me rappelez plus ») pendant une tentative
   baromètre : `marquer_opposition` appelé, appel clos poliment, ET le
   webhook de collecte porte `resultat=oppose` ; vérifier ensuite qu'un POST
   `/barometre/report` pour ce `baro_id` est refusé (HTTP 409 ou statut
   `oppose`) et qu'aucun email ne part (mock Resend à zéro envoi).

**Mesure et consolidation**
9. POST simulé Twilio sur `/twilio/call-status` avec `CallStatus=no-answer`
   → ligne `usage.jsonl` `event=baro_attempt, resultat=sonnerie_sans_reponse`,
   HTTP 204, webhook n8n mocké reçu avec `baro_id` et `attempt` corrects.
10. `CallStatus=busy` → `resultat=occupe` (même chaîne de vérification).
11. `CallStatus=completed` précédé d'un verdict AMD `machine_end_beep` sur le
    même `CallSid` → `resultat=repondeur`, `duree_s` = `CallDuration` Twilio.
12. `CallStatus=completed` avec AMD `human` → `resultat=decroche_humain`.
13. `CallStatus=failed` → `resultat=echec_technique`, ET le rapport rendu pour
    un baromètre contenant un `echec_technique` n'affiche PAS cette tentative
    dans le tableau des mesures (inspection du HTML rendu).
14. Callback `/twilio/call-status` avec un `CallSid` inconnu → HTTP 204,
    aucune exception dans les logs (grep `ERROR` vide).

**Politique répondeur (un seul message)**
15. Simulation : tentative 1 verdict `machine_end_beep`,
    `voicemail_deja_laisse=false` → le pont WS déclenche le message répondeur
    (12 s max, mesuré sur l'audio simulé) puis raccroche.
16. Simulation : tentative 2 verdict `machine_end_beep`,
    `voicemail_deja_laisse=true` → raccrochage sans AUCUN audio de message
    (zéro frame audio sortante après le verdict, vérifié par le simulateur).

**Orchestration WF-BARO (tests via exécutions n8n sur données de test)**
17. Un prospect de test « à baromètrer » génère exactement 3 crons aux
    créneaux de la grille de son métier, sur 3 jours ouvrés distincts, chaque
    créneau différent (inspection des données d'exécution WF).
18. Résultat `decroche_humain` à la tentative 1 → les crons T2/T3 sont
    annulés, `baro_statut=decroche`, aucun rapport généré, aucun email.
19. Trois échecs mesurés → POST `/barometre/report` appelé, email Resend
    envoyé avec PDF joint, `baro_statut=rapport_envoye`, alerte Telegram
    reçue (canal de test).
20. Plafond : avec 11 prospects éligibles et un quota de 10, le 11e n'est pas
    planifié tant qu'un baromètre actif n'est pas clos.

**Rapport PDF**
21. `curl POST /barometre/report` avec un jeu « 2 échecs sur 3 » → PDF
    valide (`pdfinfo` sans erreur), moins de 500 Ko, 1 page ; le texte extrait
    (`pdftotext`) contient « 2 » et « 3 » dans la phrase verdict, les 3
    lignes de mesure avec dates/heures, le numéro 04 12 13 60 20, le lien
    `?lead=` du prospect, et AUCUN tiret cadratin.
22. Jeu « 1 tentative effectuée, 1 échec » → le verdict dit « 1 appel sur
    1 », jamais « sur 3 » (regex sur le texte extrait).
23. Métier sans source de chiffrage (`source: null` dans `chiffrage.json`)
    → le PDF ne contient ni « étude » ni « % » externe : uniquement la
    formulation hypothétique avec la fourchette de panier moyen HT
    (regex : présence de « si », « HT », d'une fourchette « à » ; absence du
    mot « étude »).
24. Tout montant du PDF est suivi de « HT » et exprimé en fourchette
    (regex : aucun montant isolé sans borne min et max).
25. `POST /barometre/report` sans `X-Outbound-Token` → HTTP 403.

**Email**
26. L'email de rapport (envoyé sur une boîte de test) contient : expéditeur
    /CS identifié, objet « votre baromètre de joignabilité », le PDF joint,
    le lien `?lead=`, le lien de désinscription ; rendu réel relu via l'API
    Resend (template inclus) et archivé dans le dossier de recette.
27. L'ouverture de l'email de test déclenche l'écriture
    `baro_email_ouvert=true` sur le prospect Airtable de test (webhook
    Resend → n8n).

**Non-régression globale**
28. Le smoke test existant (`_s1_test.py`, 22 checks) passe inchangé après
    les modifications serveur.

---

## 7. Hors périmètre (explicitement)

- Aucun appel B2C, jamais (garde existante).
- Pas de baromètre multi-numéros (un seul numéro testé par établissement).
- Pas de page web publique « testez votre joignabilité » en libre-service
  (V2 possible : lead magnet auto-servi avec consentement explicite, à
  spécifier séparément).
- Pas de scoring d'intention dans cette spec (WF-SCORING est un chantier
  distinct, voir PROSPECTION-IA-CS §6).

---

## 8. Ordre de build proposé (après validation de cette spec)

1. B2 (`/twilio/call-status` + consolidation) : c'est la fondation de mesure,
   testable seule avec des curl.
2. B1 (mode baromètre) + critères 1-8, 15-16 au simulateur.
3. B3 (rapport PDF) + critères 21-25.
4. WF-BARO + Airtable + email + critères 9-14, 17-20, 26-27.
5. Auto-recette complète (les 28 critères verts, preuves archivées), PUIS
   présentation à Vannina sur 3 prospects de test internes.

---

*Spec rédigée le 2026-07-21. Toute révision issue d'un retour de Vannina doit
ajouter l'exigence ici ET son critère testable en section 6.*
