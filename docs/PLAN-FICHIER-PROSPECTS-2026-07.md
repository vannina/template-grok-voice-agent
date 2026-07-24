# PLAN FICHIER PROSPECTS · Campagne prospection vocale Léa (/CS)

Rédigé le 2026-07-20 à 22:39 (Europe/Paris). Mission #22, phase PRÉPARATION : aucun appel ne part, rien n'a été créé ni modifié sur Airtable ni sur n8n.

Cibles :
- **A. Artisans du dépannage en Corse** par métier : clim/frigoriste, plombier, électricien en priorité ; maçon, peintre, couvreur en secondaire.
- **B. Salons de coiffure en France HORS Corse**, villes moyennes de préférence (là où Planity est moins hégémonique).

Cadre légal : B2B opt-out uniquement, règles du doc `PROSPECTION-IA-CS.md` §0 (déclaration IA, opposition immédiate, horaires ouvrés, secteurs interdits exclus, pas de scraping massif, lignée conservée).

---

## 1. Schéma EXACT attendu par WF-OUT et état des tables Airtable

### 1.1 Le workflow WF-OUT (confirmé, lu sur n8n le 2026-07-20)

- **Workflow** : `WF-OUT · Prospection sortante Léa · v1.0`, id `ScBlNVZaomyft6H9`, **INACTIF** (non modifié).
- **Cadence** : cron `0 */15 9-17 * * 1-5` (toutes les 15 min, 9h à 17h45, lundi-vendredi). Garde-fou fin d'horaires côté app (retour 423 `hors_horaires`).
- **Source** : base Airtable `Campagne Agent Vocal` (`appZaFI40YcGBCn8D`), table `Prospection — Prospects` (`tbl09KiO2lEk270J1`).
- **Sélection (formule Airtable dans le node "Prospects à appeler")** :
  - jamais 2 tentatives le même jour (`date_dernier_appel` different d'aujourd'hui) ;
  - ET statut parmi : `a_appeler` OU (`rappeler` avec `date_rappel` <= aujourd'hui) OU (`injoignable` avec `tentatives` < 3 et dernier appel il y a >= 2 jours) ;
  - tri : `rappeler` dus d'abord (engagement pris), puis `score` décroissant ; **max 3 appels par run** ; `tentatives` >= 3 = injoignable définitif (exclu par la formule).
- **Appel** : `POST https://standard.corsica-studio.com/outbound/call` (header `X-Outbound-Token`) avec le body :

```json
{
  "to": "<telephone>",
  "prospect": {
    "nom": "...", "entreprise": "...", "secteur": "...",
    "metier": "...", "ville": "...", "record_id": "rec..."
  }
}
```

  Le champ **`metier` pilote le discours de Léa** côté app. Retours routés : `lancé` (statut=appele, date_dernier_appel, tentatives+1), `hors_horaires` (423, retentera), `opposition` (403, statut=opposition), autre (note d'erreur best-effort). Résumé Telegram (chat 8518781262) si >= 1 appel lancé.

### 1.2 Champs de la table `Prospection — Prospects` (confirmé)

| Champ | Type | Rôle / valeurs |
|---|---|---|
| `nom` | texte (primaire) | Nom du contact ou de l'établissement |
| `entreprise` | texte | Raison sociale |
| `telephone` | texte | **Clé d'usage, format E.164 `+33...`** (envoyé dans `to`) |
| `secteur` | select | `depannage` · `btp` · `autre` |
| `metier` | select | `climaticien` · `plombier` · `electricien` · `serrurier` · `couvreur` · `macon` · `peintre` · `multi` · `autre` |
| `ville` | texte | Ville |
| `source` | texte | **Lignée sourcing (URL + date)**, obligatoire (RGPD) |
| `score` | nombre | Tri de priorité (desc) |
| `statut` | select | `a_appeler` · `appele` · `rdv_pris` · `pas_interesse` · `opposition` · `injoignable` · `rappeler` |
| `date_dernier_appel` | date | Écrit par WF-OUT |
| `tentatives` | nombre | Incrémenté par WF-OUT (vide = 0, max 3) |
| `date_rappel` | date | Rappel convenu (statut=rappeler), re-priorisé dès échéance |
| `notes` | texte long | Erreurs / notes libres |
| `record_demo` | texte | record_id du prospect dans la base cold email (attribution démo) |

**Exemple de ligne prête à appeler** (le seul record actuel est un test interne : `Test Interne / Corsica Studio / +33651003049 / depannage / multi / Ajaccio / score 100 / a_appeler`) :

```
nom: Jean Rossi | entreprise: Rossi Froid Clim | telephone: +33495XXXXXX
secteur: depannage | metier: climaticien | ville: Ajaccio
source: https://annuaire-entreprises.data.gouv.fr/entreprise/XXX + PagesJaunes, 2026-07-20
score: 80 | statut: a_appeler | tentatives: (vide) | record_demo: (vide)
```

### 1.3 État actuel des tables (confirmé au 2026-07-20)

| Table | Base | Contenu | Constat |
|---|---|---|---|
| `Prospection — Prospects` (`tbl09KiO2lEk270J1`) | Campagne Agent Vocal | **1 record** (test interne Vannina) | Prête, vide de vrais prospects |
| `Prospection — Oppositions` (`tbl8OQ60vJf5juyIZ`) | Campagne Agent Vocal | **0 record**. Champs : `telephone` (E.164), `date`, `source` (`appel`/`email`/`manuel`) | Prête, à requêter avant CHAQUE import |
| `Prospects` (`tblIbcAR8GucFkgyw`) | **Corsica Studio** (`app4mDcBvos5Fd5he`) | **869 records dont 821 avec téléphone** : la campagne cold email WF-06a (les « 867 restaurateurs » + quelques artisans : le select `metier` y contient déjà plombier, électricien, chauffagiste...) | **Nota : elle n'est PAS dans la même base** que la prospection vocale, contrairement à ce qu'on pouvait croire ; le lien se fait via `record_demo` |
| `Desinscriptions` (`tblRVUPQ82sG5DBI5`) | Corsica Studio | Désinscrits RGPD, champs `email` + `telephone` | À inclure dans la cross-suppression |
| `sirene` (`tblxrIKBmhI0t2aAU`) | Corsica Studio | Sociétés corses (Sirene + RNE) enrichies dirigeant, **sans téléphone** | Actif interne réutilisable pour la cible A |

### 1.4 Ce qui manque (à créer plus tard, avec validation Vannina : rien modifié)

1. **Option `coiffure` dans le select `secteur`** et **option `coiffeur` dans le select `metier`** : la cible B n'est pas représentable aujourd'hui. Côté app, le discours de Léa piloté par `metier` devra aussi couvrir `coiffeur` (prompt sectoriel à écrire).
2. Champs recommandés mais absents (vs `PROSPECTION-IA-CS.md` §6) : `siret`, `code_naf`, `email_pro`, `confiance` (High/Medium/Low). Pour le pilote, `siret` et `naf` peuvent vivre dans `notes` ou `source` ; pour l'industrialisation, les ajouter en vrais champs.
3. Registre d'opposition : prévoir d'y reporter aussi les oppositions exprimées par email (source `email`) et les désinscrits téléphone de `Desinscriptions`.

---

## 2. Sources de sourcing légales (B2B France)

Aucun achat de base sans validation Vannina. Aucun scraping massif (règle interne n°6). Pour chaque contact importé : `source` = URL + date.

### 2.1 recherche-entreprises.api.gouv.fr (registre public Sirene) : la colonne vertébrale

- **Statut : confirmé** (API publique gratuite, sans clé, limite 7 requêtes/s, testée ce jour).
- **Comment** : `GET https://recherche-entreprises.api.gouv.fr/search?activite_principale=<NAF>&departement=<dep>&etat_administratif=A` (JSON, pagination). Donne SIRET/SIREN, dénomination, adresse, commune, NAF, dirigeants, date de création. Fiche publique liée : `annuaire-entreprises.data.gouv.fr` (parfait pour la lignée).
- **Volumes réels comptés le 2026-07-20** (établissements actifs, Corse 2A+2B) :

| NAF | Métier | Corse (2A+2B) |
|---|---|---|
| 43.22B | Installation thermique et climatisation (clim/frigoriste/chauffagiste) | **341** |
| 43.22A | Eau et gaz (plombiers) | **828** |
| 43.21A | Installation électrique (électriciens) | **1 333** |
| 43.34Z | Peinture | 762 |
| 43.91B | Couverture | 90 |
| 43.99C | Maçonnerie générale | 2 992 |

  Coiffure `96.02A` : plafond d'affichage API atteint au national (> 10 000 ; l'INSEE en recense environ 85 000, ordre de grandeur, probable). Échantillons départements « villes moyennes » comptés ce jour : Nièvre 315, Charente 583, Tarn 695, Allier 546, Hautes-Pyrénées 390.
- **Qualité téléphone : nulle** (les coordonnées de contact ne sont pas diffusées par Sirene). Cette source fournit la **base légale B2B** (SIRET vérifié = pro confirmé), le filtre NAF anti-secteurs-interdits, et la population de référence ; le téléphone vient d'une source complémentaire.

### 2.2 Pages Jaunes (pagesjaunes.fr, Solocal) : la meilleure source de téléphones

- **Statut : confirmé pour la qualité, probable pour le détail des CGU** (les CGU Solocal interdisent l'extraction automatisée ; à respecter).
- **Comment** : recherche par métier + ville, **export manuel raisonnable** (copier les fiches une à une) : parfaitement tenable pour un pilote de 100 fiches (2 à 3 h de travail). Pas de robot.
- **Volume espéré** : quasi exhaustif sur les TPE artisans et salons ; la mention « dépannage » dans la fiche PJ est en plus un excellent signal de ciblage pour la cible A.
- **Qualité téléphone : excellente** (numéro pro affiché volontairement par l'entreprise, souvent mobile du gérant chez les artisans).

### 2.3 Google Places API (officielle, pas de scraping Maps)

- **Statut : confirmé pour l'existence et les champs, probable pour le pricing exact** (grille Google évolutive).
- **Comment** : Text Search puis Place Details avec le champ téléphone (`nationalPhoneNumber`). API officielle, donc conforme à la règle « pas de scraping de Maps ». Ordre de coût : environ 0,02 USD par fiche Details, soit ~2 à 4 USD pour le pilote, largement sous le crédit gratuit mensuel Google.
- **Contrainte ToS à respecter** : hors `place_id`, les données Places ne doivent pas être stockées durablement (cache 30 jours max). Usage recommandé : **vérification et croisement** (le numéro stocké dans Airtable vient de Pages Jaunes ou du site web de l'entreprise, Places sert à confirmer + capter les signaux).
- **Signaux bonus précieux** : note, nombre d'avis, horaires, site web, **présence ou absence d'un lien de réservation** (détection Planity pour la cible B) et avis mentionnant l'injoignabilité (signal d'achat n°1 du doc prospection).
- **Qualité téléphone : très bonne.**

### 2.4 Sources d'appoint

- **Table `sirene` interne** (base Corsica Studio) : sociétés corses déjà enrichies dirigeant + site + réseaux ; croiser avant de re-sourcer (confirmé, gratuit, déjà à nous).
- **Annuaires de fédérations** : CMA de Corse (répertoire des métiers), UNEC pour la coiffure (probable : pas d'API, export manuel au cas par cas).
- **planity.com et plateformes équivalentes** : consultation manuelle par ville pour la cible B, en **liste d'exclusion** (un salon déjà sur Planity est moins prioritaire) ; ne rien en extraire d'autre.
- **Apify (scrapers Maps/PJ)** : existe, mais contraire à la règle interne n°6 en usage massif ; pas pour le pilote. À rediscuter avec Vannina seulement si l'industrialisation le justifie.
- **Achat de fichier (Kompass, etc.)** : NON par défaut ; uniquement sur validation explicite de Vannina.

### 2.5 Recette de sourcing retenue par cible

- **Cible A (Corse dépannage)** : population via recherche-entreprises (NAF 43.22B / 43.22A / 43.21A, dép. 2A+2B) + croisement table `sirene` interne, téléphone + signal « dépannage » via Pages Jaunes (manuel), vérification + signaux via Places API. Gisement brut : ~2 500 établissements sur les 3 métiers prioritaires, largement assez.
- **Cible B (coiffeurs villes moyennes)** : villes du programme Action cœur de ville (222 villes moyennes, référentiel public) dans des départements type Nièvre/Charente/Tarn/Allier/Hautes-Pyrénées, population via recherche-entreprises (NAF 96.02A), exclusion des salons visibles sur Planity (vérif manuelle), téléphone via Pages Jaunes, signaux via Places API.

---

## 3. Cross-suppression OBLIGATOIRE avant tout passage en `a_appeler`

Ordre d'exécution, sur chaque lot, avant import (pilote : script local sur CSV ; ensuite : node Code n8n dans WF-SOURCE) :

1. **Normalisation E.164** de tous les numéros : retirer espaces/points/tirets, `0X...` devient `+33X...`, conserver les `+33` existants ; **rejeter** les numéros invalides, non français, et les `08` surtaxés. Le champ `telephone` est la clé d'usage partout (WF-OUT, Oppositions, garde-fou app) : un numéro mal normalisé casse toute la chaîne de suppression.
2. **Registre d'opposition** : exclure tout numéro présent dans `Prospection — Oppositions` (0 record aujourd'hui, mais la requête doit être systématique et re-jouée à chaque import).
3. **Désinscrits** : exclure tout match (téléphone normalisé OU email) avec la table `Desinscriptions` de la base Corsica Studio, y compris statut `Desinscrit` de la table `Prospects` cold email. Une désinscription email n'est pas juridiquement une opposition téléphonique, mais on l'applique par prudence et cohérence de marque.
4. **Campagne cold email (869 prospects, 821 téléphones)** : exclure tout match avec la table `Prospects` de la base Corsica Studio par **téléphone normalisé**, puis par **SIRET**, puis par **dénomination + ville normalisées** (le champ `dedup_key` existe déjà côté cold email). Attention : cette table contient déjà des artisans corses (plombiers, électriciens, chauffagistes), le recouvrement avec la cible A est réel. Règle pilote : un prospect déjà travaillé par email ne rentre pas dans le fichier d'appel (pas de double sollicitation non coordonnée) ; l'escalade email vers appel des leads chauds est un scénario ultérieur, à valider.
5. **Clients et contacts existants** : exclure les clients /CS, les leads ebooks (`Leads /CS`) et les contacts du standard (`Standard — Contacts`) par téléphone/email ; liste courte de clients à confirmer avec Vannina avant le premier lot.
6. **Déduplication interne du lot** par téléphone normalisé (garder la fiche la plus riche, fusionner la lignée dans `source`).
7. **Filtre secteurs interdits** (rénovation énergétique, photovoltaïque, adaptation logement) par NAF et mots-clés dans la dénomination : peu probable sur ces cibles, mais on exclut par prudence les entreprises dont l'activité affichée est pompe à chaleur / isolation / solaire.

Traçabilité : conserver le CSV rejeté avec la raison (opposition, doublon email, client, invalide) pour audit.

---

## 4. Plan de pilote : 2 lots de 50

Structure : **chaque lot = 50 prospects (25 cible A + 25 cible B)**. Le lot 2 n'est constitué qu'après analyse du lot 1 (ajustement métiers/villes/horaires). Rappel : rien ne part tant que WF-OUT est inactif, que le code outbound n'est pas déployé et que Vannina n'a pas donné le GO.

### 4.1 Composition du lot 1

- **25 artisans Corse** : 10 clim/frigoristes (NAF 43.22B), 10 plombiers (43.22A), 5 électriciens (43.21A) ; répartis Ajaccio / Bastia / Porto-Vecchio / Corte-Balagne ; `secteur=depannage`, `metier=climaticien|plombier|electricien`. Saison estivale = pic de dépannage clim : angle parfait pour Léa (« qui répond quand vous êtes sur une intervention ? »).
- **25 salons de coiffure** : 5 villes moyennes x 5 salons (proposition : Nevers, Angoulême, Albi, Montluçon, Tarbes), hors Corse ; nécessite d'abord la création des options `coiffure`/`coiffeur` (validation Vannina).

### 4.2 Critères de sélection d'une fiche (les deux cibles)

- Établissement **actif** (etat_administratif A, SIRET vérifié = base légale B2B) ;
- **téléphone pro vérifié** (présent sur PJ ET confirmé par Places ou le site) ;
- signes d'activité réelle : fiche Google avec avis (>= 5 avis) OU site web vivant ;
- **pas de prise de RDV en ligne** (cible B : absent de Planity ; cible A : pas de module de résa) : c'est le signal d'achat ;
- pas une structure mono-personne sans flux d'appels apparent (disqualifiant du doc prospection) ;
- passage complet de la cross-suppression §3.
- `score` initial manuel 0-100 : +30 avis mentionnant l'injoignabilité, +20 pas de site, +20 mobile direct du gérant, +10 note < 4, +20 volume d'avis élevé (établissement qui tourne).

### 4.3 KPIs à suivre (par lot et par cible A/B)

| KPI | Définition | Cible (repères doc §7) |
|---|---|---|
| Taux de décroché | appels `lancé` aboutissant à une conversation / appels lancés | 25 à 40 % |
| Conversations > 30 s | proxy d'écoute réelle (durée via `usage.jsonl` / logs app) | >= 50 % des décrochés |
| RDV posés | statut `rdv_pris` (+ event_id calendrier) | 2 à 5 par lot de 50 (5-10 %) |
| Oppositions | statut `opposition` / appels aboutis | < 5 % ; > 10 % = stop et revoir ciblage |
| Injoignables définitifs | `tentatives` = 3 sans contact | à surveiller (qualité du fichier) |
| Coût / RDV | (coût Twilio sortant + coût xAI du lot) / RDV posés, via `usage.jsonl` | ordre de grandeur visé < 25 EUR HT / RDV, à calibrer au lot 1 |

Mesure : statuts Airtable (source de vérité) + `usage.jsonl` côté app + résumés Telegram WF-OUT ; comparer systématiquement cible A vs cible B (décision go/no-go par cible pour le lot 2).

---

## 5. Automatisable ensuite vs à la main pour le pilote

### À la main pour le pilote (volontairement)

- Constitution des 2 x 50 fiches : requêtes API de comptage/listing, relevé Pages Jaunes manuel, vérification Planity, scoring initial ;
- cross-suppression via script local (CSV) avec revue humaine du fichier final ;
- import Airtable en `a_appeler` **seulement après validation du fichier par Vannina** ;
- écoute/lecture des premiers appels et qualification des retours (calibrage du prompt de Léa par métier).

### Automatisable ensuite (dans l'ordre)

1. **WF-SOURCE** : recherche-entreprises (NAF + départements) vers table brute Airtable avec lignée automatique ; croisement table `sirene` interne.
2. **Enrichissement** : Places API (vérif téléphone, note, avis, site, détection résa en ligne) + fetch du site web ; écriture du `score` de contactabilité.
3. **Normalisation E.164 + cross-suppression** en node Code n8n (oppositions, désinscrits, cold email, clients) rejouée à chaque import : c'est la brique la plus rentable à fiabiliser.
4. **WF-SCORING** : filtre secteurs interdits + scorer Claude (firmographique + intention) vers Hot/Warm/Cold/Skip, alimente `score` et le tri de WF-OUT.
5. KPIs automatiques dans le digest quotidien (extension WF-06b) + report des oppositions dans le registre.

### Jamais sans validation Vannina

Achat de base, scraping automatisé (Apify PJ/Maps), activation de WF-OUT, extension à de nouveaux métiers/zones.

---

## 6. Lot 1 chargé (2026-07-21, 12h34 Europe/Paris)

Mission #22, phase EXÉCUTION lot 1. **42 prospects chargés** dans `Prospection — Prospects` (`tbl09KiO2lEk270J1`), tous en statut `a_appeler`, par lots de 10 via MCP Airtable (`create_records_for_table`). La table contient 43 records (42 + le test interne). WF-OUT reste INACTIF : aucun appel ne peut partir.

### 6.1 Décompte

| Étape | Volume |
|---|---|
| Population Sirene interrogée (API recherche-entreprises, curl) | 1 800 établissements actifs (341 clim 43.22B Corse + 828 plombiers 43.22A Corse + 631 coiffeurs 96.02A sur 7 villes) |
| Candidats présélectionnés (zones cibles, filtre mots-clés rénovation énergétique/photovoltaïque, pré-suppression par nom+ville vs cold email) | 81 fiches enquêtées |
| Téléphone vérifié trouvé (E.164 `+33...`) | 42 retenus |
| Écartés pendant l'enquête | ~39 : téléphone introuvable ou masqué (JMC Plomberie, Cassitta, Bonelli, Bettini, MBT, Zen Coiff, Cut&Coiff, Allo SAV, Sud Froid, Génie Climatique Service...), établissement fermé (Casanova Plomberie : liquidation 2024 ; Paul Mondoloni : établissement 43.22A cessé), **fiche Sirene « Opposé au marketing direct » (Antoine Cubeddu, Bastia : exclu par prudence RGPD)**, SIRET invérifiable (AGPlomberie & Co) |
| Cross-suppression finale (téléphone E.164 + nom+ville vs `Prospects` cold email 869/821 tel, `Desinscriptions`, `Prospection — Oppositions`) | **0 doublon** sur les 42 (recouvrement déjà éliminé en amont par la pré-suppression nom+ville ; `Desinscriptions` et `Oppositions` vérifiées = 0 record chacune au 2026-07-21) |
| Doublons internes au lot (par téléphone) | 0 |

### 6.2 Répartition

**Cible A — 18 artisans dépannage Corse** (`secteur=depannage`) :
- 10 climaticiens/frigoristes : Ajaccio 3, Afa 1, Bastia 1, Biguglia 2, Porto-Vecchio 3
- 8 plombiers : Ajaccio 3, Borgo 2, Saint-Florent 1, Porto-Vecchio 2
- Scores 65-85 (clim > plombier ; bonus dépannage 24/7 affiché, mobile direct du gérant)

**Cible B — 24 salons de coiffure villes moyennes hors Corse** (`secteur=coiffure`, `metier=coiffeur`) :
- Allier : Montluçon 2, Moulins 3, Vichy 4 · Tarn : Albi 6, Castres 3 · Charente : Angoulême 4, Cognac 2
- Score 70 = pas de réservation en ligne détectée (absent des listes Planity de la ville) ; score 40 = présent sur Planity/Fresha ou résa en ligne sur son site (6 salons concernés : Ikxis, David SCE, Hair du Temps, Le Boudoir Castres, Aurélie Coiff)

### 6.3 Qualité téléphone et sources

- 42/42 numéros E.164 valides (`+33[1-9]XXXXXXXX`), 0 numéro 08 surtaxé, 0 particulier (tous adossés à un SIREN actif vérifié via recherche-entreprises ; SIREN cité dans le champ `source` de chaque record avec la date).
- Cible A : numéros issus des sites officiels des entreprises (8 cas) et d'annuaires en consultation (118000.fr, mappy, u-corsu, bottin, justacote, e-pro, monartisan, ou-plombier...). Pages Jaunes cité en recoupement quand la fiche existe (consultation, pas d'extraction automatisée).
- Cible B : colonne vertébrale = JSON-LD de coiffeur.annuairefrancais.fr (nom + SIRET + téléphone), croisé par SIRET avec la population Sirene. Les numéros y sont tronqués d'un chiffre : reconstruction par le chiffre de zone du département (0470 Allier, 0563 Tarn, 0545 Charente), **validée sur 3 échantillons recoupés indépendamment** (Delarbre Montluçon, David SCE Albi, Aurélie Coiff Angoulême : exacts). Les numéros ambigus (préfixes 51/67/81 pouvant être mobiles) ont été écartés ou recoupés par une 2e source.
- Chaque record note sa lignée complète dans `source` (URL annuaire + fiche annuaire-entreprises + date).

### 6.4 Écarts vs plan

1. **Options selects** : `coiffure` (secteur) et `coiffeur` (metier) créées via `typecast` à l'insertion (le tool MCP `update_field` ne permet pas d'ajouter des choix de select). IDs créés : `selD4WTpjqDvzwo4l` (coiffure), `selF0psaSGQidcFSV` (coiffeur). Seule modification de schéma effectuée.
2. Électriciens (43.21A) non inclus au lot 1 : priorité clim/plombiers respectée, 18 fiches A de qualité plutôt que forcer à 25 (règle qualité avant quantité, WebSearch et annuaires rate-limités par moments).
3. C&P Réfrigération (Biguglia) : NAF 46.69B (négoce frigorifique) et non 43.22B ; frigoriste dépanneur réel, retenu avec note dans le record.
4. Table `Desinscriptions` : 0 record au moment du chargement (le plan en attendait ; vérifiée quand même, à re-vérifier avant tout lot 2).
5. Villes cible B : Nevers et Tarbes remplacées par Moulins/Vichy/Castres/Cognac (mêmes départements retenus au plan : Allier, Tarn, Charente).

Prochaine étape (hors périmètre lot 1) : validation du fichier par Vannina, prompt Léa `coiffeur`, puis GO/NO-GO avant toute activation de WF-OUT.

---

*Sources : n8n workflow `ScBlNVZaomyft6H9` (lu le 2026-07-20) ; Airtable bases `appZaFI40YcGBCn8D` et `app4mDcBvos5Fd5he` (lues le 2026-07-20) ; recherche-entreprises.api.gouv.fr (comptages du 2026-07-20) ; `docs/PROSPECTION-IA-CS.md` (2026-07-01). Statuts marqués confirmé/probable dans le texte.*

---

## 7. Correction tutoiement hôteliers (2026-07-24)

Rédigé le 2026-07-24. Base `app4mDcBvos5Fd5he`, table `Prospects` (`tblIbcAR8GucFkgyw`), champ `tutoiement_autorise` (`fldIf6aQO6yeiz0uO`).

### 7.1 Déclencheur

Le 23/07, un hôtelier (Le Kallisté) s'est plaint d'avoir reçu un email tutoyé. Règle /CS : tutoiement pour les artisans et commerçants, **vouvoiement obligatoire** pour les hôteliers, l'hébergement et les professions libérales.

### 7.2 Périmètre et méthode

- **868 records** examinés (tous ceux avec `tutoiement_autorise = TRUE`).
- Balayage complet des 868 `denomination` en 3 pages, puis contre-vérification par requêtes ciblées `contains` sur : `otel`, `ôtel`, `uberge`, `amping`, `îte`, `sidence`, `hambre`, `elais`, `illa`, `efuge`, `omaine`, `ostellerie`, `esort`, `ension de fam`.
- Contrôle professions libérales : filtre `metier` sur les options hotel / avocat / expert_comptable / medecin / dentiste / architecte / agence_immo / autre → **0 record**, plus requêtes `contains` sur `abinet`, `octeur`, `vocat`, `omptable`, `otaire`, `entiste`, `rchitect`, `linique`, `harmacie`, `érinaire`, `inésith` → **0 record**. Le lot TRUE ne contenait que des métiers de la restauration/hébergement.

### 7.3 Résultat

**61 records corrigés** : `tutoiement_autorise` passé à FALSE + note horodatée ajoutée en append dans `notes_internes` (`fldSomwRlHurMQWGE`), contenu existant préservé :
`2026-07-24 : vouvoiement force (regle CS : hoteliers et professions liberales = vouvoiement).`

Aucun autre champ modifié, aucune suppression. Restaurants, pizzerias, bars et brasseries non touchés.

**Hôtels (21)** : Hôtel L'Ondine · Hôtel Restaurant U Paradisu · Hôtel Restaurant La Caravelle · Hôtel Restaurant La Bergerie · Santa Vittoria Hôtel de la Plage · Hôtel Restaurant · Hôtel Restaurant du Fango · Hôtel U Paesolu · Hôtel le Royal · Hôtel Farera · Hôtel Restaurant l'Europe · Hôtel Des Roches · Hôtel Restaurant de La Jetée · Hôtel-Restaurant La Lagune · Cors'Hôtel · Hôtel Restaurant U Marinaru · Hôtel Marina di Lava · Hotel Lilium Maris · Hotel-Restaurant Des Deux Sorru · Sofitel Golfe d'Ajaccio Sea and Spa · Paesotel E Caselle

**Auberges et fermes-auberges (31)** : FERME AUBERGE PERIDUNDELLU · Auberge U San Martinu · L 'AUBERGE DU PECHEUR · Auberge du Cheval Blanc · AUBERGE U SIRENU · AUBERGE DU PECHEUR · Auberge D'Alata · L'Auberge Corse · Ferme auberge d Alzitone · Auberge Montana · AUBERGE DE LICETTO · AUBERGE TAFANI MARIE FRANCE · Auberge U Sirenu · Auberge du Prunelli · Auberge u Pasturellu · Auberge Casa Mathea · Auberge du pêcheur / Agula Marina · AUBERGE DE LA FORET · AUBERGE A FILETTA · Auberge du Coucou · Auberge de la Restonica · AUBERGE DU SANGLIER · Ferme Auberge Pozzo di Mastri · L'AUBERGE · AUBERGE CHEZ FLORA · CAMPING AUBERGE BUNGALOW CAVALLO MORTO · Auberge Acquella · Auberge du col de Bavella · Auberge Napoléon · FERME AUBERGE L'AGHIALLE · Auberge la Ferme

**Campings (2, hors camping-auberge déjà cité)** : Camping Ras L'Bol · CAMPING OLVA SAS

**Gîtes (2)** : Gîte Du Chalet Pietri · Gîte A Funtana

**Chambres d'hôtes (1)** : Restaurant - Chambres d'Hôtes TERRA BELLA

**Relais (2)** : Le Relais Campagnard · Le Relais

**Villa (1)** : Villa les Orangers

**Refuge (1)** : Refuge d'Ortu di u Piobbu

### 7.4 Cas ambigus tranchés

Le risque étant asymétrique (vouvoyer un artisan ne vexe personne, tutoyer un hôtelier fait perdre le prospect), le doute a systématiquement tranché vers le **vouvoiement**.

- **« Hôtel Restaurant … » (9 fiches)** → hôteliers, vouvoiement, même si le métier Airtable dit « Restaurant ».
- **« Auberge … » sans mention d'hébergement (20+ fiches)** → beaucoup ne sont peut-être que des restaurants, mais impossible de trancher sur le seul nom : vouvoiement par défaut.
- **Fermes-auberges (3)** → hébergement rural fréquent : vouvoiement.
- **Le Relais / Le Relais Campagnard** → « relais » relève du vocabulaire hôtelier : vouvoiement.
- **Villa les Orangers** → « villa » en contexte touristique corse = hébergement : vouvoiement.
- **Refuge d'Ortu di u Piobbu** → refuge de montagne du GR20, hébergement avéré : vouvoiement (fiche déjà signalée email erroné le 21/07, note préservée).
- **Paesotel E Caselle** → village-hôtel : vouvoiement.
- **Sofitel Golfe d'Ajaccio Sea and Spa** → marque hôtelière, aucun mot-clé « hôtel » dans le nom : détecté au balayage manuel.
- **Restaurant - Chambres d'Hôtes TERRA BELLA** → métier Airtable « Pizzeria », mais chambres d'hôtes : vouvoiement.

**Faux positifs volontairement laissés en tutoiement :**
- *BRASSERIE GRILL DE L'HOTEL DE VILLE* → « hôtel de ville » = mairie, pas un hébergement.
- *U Bistrotellu* → collision de sous-chaîne sur « otel ».
- *Restaurant Le Refuge* et *Le Refuge* → nommés explicitement restaurant / restaurants connus, pas des refuges de montagne.
- *La Bergerie*, *LA FERME A STADDA*, *Restaurant la ferme*, *Le Lodge* → noms de restaurants sans indice d'hébergement.

### 7.5 Vérification finale (prouvée)

Requêtes de contrôle exécutées après correction :

| Contrôle | Avant | Après |
|---|---|---|
| `tutoiement_autorise = TRUE` (total) | 868 | **807** (soit 868 − 61) |
| TRUE + `contains "ôtel"` | 17 | **0** |
| TRUE + `contains "uberge"` | 31 | **0** |
| TRUE + `contains "amping"` | 3 | **0** |
| TRUE + `contains "îte"` | 2 | **0** |
| TRUE + `contains "hambre"` | 1 | **0** |
| TRUE + `contains "elais"` | 2 | **0** |
| TRUE + `contains "otel"` | 5 | **2** (les 2 faux positifs assumés ci-dessus) |

Plus aucun hébergement identifiable ne reste en `tutoiement_autorise = TRUE`.
