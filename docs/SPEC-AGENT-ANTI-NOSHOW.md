# SPEC : Agent anti no-show (add-on #26, confirmation de RDV la veille)

> Rédigé le 2026-07-21. Statut : SPEC validable, AUCUN build engagé (moteur
> `web/server.py` GELÉ jusqu'à la fin du pilote de prospection).
> Méthode : spec écrite + critères d'acceptation testables AVANT toute ligne de code
> (directive du 2026-07-06). Références normatives : `CLAUDE.md` (architecture),
> `docs/CAHIER-DES-CHARGES-CONVERSATION.md` (conversation, règles 1.x, 4.x, 8.5),
> `docs/SPEC-BAROMETRE-APPELS-MANQUES.md` (format de spec, brique B2 partagée),
> `docs/OFFRES-PRICING-AGENTS-IA-CS.md` (pricing).

---

## 0. Résumé exécutif

L'add-on anti no-show confirme les rendez-vous du lendemain pour les clients de
Corsica Studio (salons, restaurants, cabinets, artisans). Chaque jour, un
workflow n8n lit l'agenda Google du commerçant (Composio, déjà branché), extrait
les RDV du lendemain, et pour chacun déclenche un appel vocal court à une heure
paramétrée par le commerçant : « Bonjour, c'est l'assistante de [établissement],
je confirme votre rendez-vous demain à 14h. Ça tient toujours ? » Trois issues :
le client confirme (statut écrit dans l'agenda), reporte (l'agent propose des
créneaux libres et réécrit l'agenda), ou annule (le créneau est libéré et le
commerçant est alerté immédiatement). Si le client ne décroche pas : un SMS de
repli, un seul, et jamais de deuxième appel. Le soir, le commerçant reçoit un
récapitulatif de tous les RDV du lendemain avec leur statut.

Principes directeurs tranchés ici : **un RDV = au maximum 1 appel + 1 SMS,
jamais plus** ; **l'agent ne supprime jamais un RDV sans parole explicite du
client** (pas de réponse = RDV maintenu, marqué « non confirmé ») ; ce n'est
**pas du démarchage** mais la gestion d'un contrat en cours, ce qui n'exonère
pas de cadrer horaires, fréquence et transparence IA (section 1).

---

## 1. Point tranché n°1 : conformité (ce n'est pas du démarchage, on cadre quand même)

### 1.1 Qualification juridique

- **Confirmé** : l'appel de confirmation d'un RDV déjà pris par le client
  relève de l'exécution du contrat en cours, pas de la prospection
  commerciale. La loi n° 2025-594 du 30 juin 2025 (régime d'opt-in du
  démarchage téléphonique B2C applicable au 11/08/2026) prévoit explicitement
  l'exception des sollicitations intervenant dans le cadre de l'exécution d'un
  contrat en cours (source : Légifrance, loi n° 2025-594,
  https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000051826425). L'appel
  anti no-show entre dans cette exception tant qu'il ne contient AUCUN message
  commercial (pas d'upsell, pas de promotion pendant l'appel : interdit dans le
  prompt et vérifié en recette).
- **Confirmé** : les deux règles maison non négociables s'appliquent comme à
  tout agent CS : annonce de l'enregistrement de l'appel et déclaration
  explicite que l'interlocuteur parle à une IA (transparence exigée par
  l'article 50 du règlement européen sur l'IA pour les systèmes
  conversationnels). Les deux tiennent en une phrase d'ouverture courte.
- **Confirmé (RGPD)** : Corsica Studio agit en sous-traitant du commerçant
  (article 28 RGPD) : un avenant de sous-traitance (DPA) est annexé au contrat
  de l'add-on ; les données traitées (nom, téléphone, RDV) restent limitées à
  la finalité de confirmation ; transcripts et journaux conservés 30 jours
  maximum puis purgés ; le commerçant informe ses clients (mention dans la
  confirmation de RDV initiale : « votre RDV pourra être confirmé la veille
  par notre assistante vocale »).
- **Probable (à valider avec le commerçant pilote)** : la base légale retenue
  est l'exécution du contrat, avec l'intérêt légitime en base subsidiaire ;
  un client final peut refuser ce canal (« ne me rappelez plus pour
  confirmer ») : ce refus est enregistré (liste d'exclusion par établissement)
  et vaut pour tous les RDV futurs.

### 1.2 Cadrage horaires et fréquence (non contournable, même hors démarchage)

1. **Fenêtre d'appel : 9h30 à 19h30, heure locale de l'établissement, jamais
   le dimanche ni les jours fériés.** L'heure de tir est paramétrable par le
   commerçant (défaut : 17h30 la veille) mais écrêtée à cette fenêtre. Les
   plages `OUTBOUND_HOURS` du serveur restent le garde-fou dur : un créneau
   commerçant hors plage serveur est écrêté au bord le plus proche, jamais
   élargi.
2. **Veille non ouvrée** : si la veille du RDV est un dimanche ou un férié,
   l'appel avance au dernier jour autorisé précédent (samedi pour un RDV du
   lundi), avec un message adapté (« votre rendez-vous de lundi »). Aucun
   appel du dimanche, aucun SMS le dimanche.
3. **Un RDV = 1 tentative d'appel maximum + 1 SMS de repli maximum.** Jamais
   de deuxième appel, quel que soit le résultat. Seule exception : un échec
   purement technique Twilio (`failed`) autorise UNE retentative dans les
   30 minutes ; un non-décroché ou un occupé n'est jamais retenté.
4. **Liste d'exclusion** : un client qui demande à ne plus être appelé est
   inscrit sur la liste d'exclusion de l'établissement (tool
   `marquer_opposition` réutilisé avec un registre par établissement) ; les
   RDV futurs de ce numéro basculent en SMS seul, ou en rien si le refus
   porte sur tout le canal.

### 1.3 Ce que l'appel ne fait jamais

- Aucune vente, aucune promotion, aucun rebond commercial : confirmation,
  report, annulation, au revoir. Durée visée : moins de 90 secondes.
- Aucune divulgation de motif médical ou sensible : l'agent dit « votre
  rendez-vous de demain à 14h chez [établissement] », jamais le motif de la
  consultation, même s'il figure dans l'agenda (règle bloquante pour les
  cabinets : le motif est expurgé du contexte passé au modèle).
- Jamais de message laissé chez un tiers : si la personne qui décroche dit ne
  pas être le client, l'agent s'excuse, ne cite ni le RDV ni l'établissement
  au-delà du strict nécessaire, et clôt ; le RDV passe en SMS de repli.

---

## 2. Point tranché n°2 : parcours complet

### 2.1 Lecture de l'agenda (nouveau, quotidien)

- Un workflow n8n (WF-NOSHOW) tourne chaque jour à heure fixe par
  établissement (l'heure de tir moins 15 minutes, fenêtre de lissage) et
  liste les événements du lendemain du calendrier du client via Composio
  (`GOOGLECALENDAR_EVENTS_LIST` sur le `calendar_id` de l'établissement,
  même mécanique d'appel REST server-side que `/api/calendar/book` : le
  modèle ne voit jamais le schéma brut Google).
- **Extraction du téléphone** : le numéro est lu depuis la description de
  l'événement, au format posé par l'agent de réservation existant. Un RDV
  sans numéro exploitable (absent, invalide, sentinelle `anonymous` et
  variantes déjà filtrées par `/api/calendar/book`) est exclu de la tournée
  et listé dans le récap commerçant (« à confirmer vous-même »).
- **Multi-RDV du même client** (tranché) : plusieurs RDV le même lendemain
  pour le même numéro chez le même établissement = UN SEUL appel qui liste
  les RDV (« vos deux rendez-vous demain, 10h et 15h »). Chaque RDV garde son
  statut propre (le client peut en confirmer un et reporter l'autre). Le même
  numéro chez deux établissements différents = appels séparés (marques
  distinctes, jamais mutualisés).
- **Filtres d'entrée** : événements déjà marqués `[ANNULE]`, événements créés
  moins de 24h avant le RDV (le client vient de réserver, inutile de
  confirmer), numéros en liste d'exclusion (SMS seul ou rien), événements
  hors gabarit (réunions internes du commerçant : filtre sur le
  `summary_label` métier existant de `_metier_ctx`).

### 2.2 L'appel de confirmation (mode outbound, tours pilotés)

- Réutilise le moteur outbound existant (`/outbound/call`, AMD asynchrone,
  tours pilotés par le serveur, TimeLimit) avec un nouveau mode
  `confirmation` et un prompt dédié par métier
  (`web/config/metiers/<metier>/confirmation_prompt.txt`, même mécanique de
  hot-reload que `system_prompt.txt`).
- Ouverture conforme en une phrase : identité de l'assistante + établissement
  + IA + enregistrement, puis la question de confirmation. Toutes les règles
  du cahier des charges conversation s'appliquent (1.1 à 1.5, 2.x, 3.x, 4.x :
  au revoir explicite, fenêtre de politesse, raccrochage garanti serveur).
- **Trois issues + une** :
  1. **Confirme** → l'agent remercie, clôt. Statut `confirme`.
  2. **Reporte** → l'agent interroge les disponibilités (MCP calendrier
     existant), propose 2 créneaux maximum par tour, déplace l'événement via
     un nouveau tool serveur `reschedule_rdv` (Composio
     `GOOGLECALENDAR_UPDATE_EVENT`), confirme oralement le nouveau créneau.
     Statut `reporte`. Si aucun créneau ne convient après 2 propositions :
     l'agent clôt sur « [établissement] vous rappellera pour trouver un
     créneau », statut `a_replanifier`, alerte commerçant.
  3. **Annule** → l'agent prend acte SANS chercher à retenir (une seule
     relance douce autorisée : « souhaitez-vous plutôt le déplacer ? », puis
     acceptation immédiate). Le créneau est libéré via `cancel_rdv`
     (événement marqué `[ANNULE]` dans le titre, jamais supprimé : le
     commerçant garde la trace). Statut `annule`, **alerte immédiate au
     commerçant** (le créneau redevient vendable aujourd'hui, c'est toute la
     valeur de l'add-on).
  4. **Répondeur (AMD)** → message court, 12 secondes maximum (règle 1.5) :
     qui appelle, le RDV concerné, « sauf contrordre on vous attend », le
     numéro à rappeler pour modifier. PUIS le SMS de repli part quand même
     (c'est lui qui porte le numéro cliquable). Un seul message répondeur,
     jamais deux.
- **Non-décroché / occupé** → aucun nouvel appel, SMS de repli seul.

### 2.3 SMS de repli (nouveau canal, Twilio SMS sortant)

- Un seul SMS, envoyé dans les 5 minutes suivant l'échec de l'appel :
  « [Établissement] : votre RDV de demain [heure] est maintenu sauf
  contrordre. Pour modifier ou annuler, appelez le [numéro de l'agent
  entrant]. STOP au [numéro court] pour ne plus recevoir ces messages. »
- Le numéro donné est celui de l'agent vocal ENTRANT de l'établissement
  (chemin Twilio entrant existant) : le client qui rappelle tombe sur le même
  agent, qui sait reporter ou annuler. Réutilisation directe, zéro brique
  neuve côté entrant.
- **Probable (à vérifier au build)** : les numéros actuels (+33 4 12 13 60 xx)
  sont des fixes virtuels ; l'envoi de SMS depuis un expéditeur
  alphanumérique ou un numéro mobile virtuel Twilio dédié est à valider
  (réception de STOP incluse). Si le SMS entrant STOP n'est pas disponible
  sur le numéro choisi, le STOP est remplacé par « dites-le simplement à
  l'assistante en rappelant », et l'exclusion se fait par l'agent entrant.
- Aucun SMS après 20h ni le dimanche ou un jour férié (recommandations
  déontologiques SMS transposées par prudence, même pour un message de
  service).

### 2.4 Statuts et récap commerçant

- **Statut écrit dans l'agenda** (tranché) : préfixe texte dans le titre de
  l'événement, visible par le commerçant sans aucun outil supplémentaire :
  `[OK]` confirmé, `[REPORTE]` déplacé, `[ANNULE]` annulé, `[?]` non joint
  (SMS envoyé, pas de retour). Aucune dépendance à des champs cachés.
- **Alerte immédiate** (annulation ou `a_replanifier`) : notification au
  commerçant dans les 5 minutes, canal au choix du commerçant : email
  (Resend) ou SMS. (Telegram réservé à l'usage interne CS, pas aux clients.)
- **Récap quotidien** : le soir de la tournée (vers 20h), un email Resend au
  commerçant : liste des RDV du lendemain, statut de chacun, RDV exclus
  faute de numéro, et le compteur du mois (RDV confirmés, annulations
  captées la veille). C'est la preuve de valeur récurrente de l'add-on.
- Journalisation : chaque tentative écrit une ligne `usage.jsonl`
  (`event=noshow_attempt`, `etablissement`, `rdv_id`, `resultat`,
  `duree_s`, `ts`) ; les résultats consolidés d'appel réutilisent la brique
  `/twilio/call-status` spécifiée dans le baromètre (B2) : **brique partagée,
  à construire une seule fois** (statut : spécifiée, non construite).

---

## 3. Point tranché n°3 : architecture (extension, pas de nouveau moteur)

### 3.1 Réutilisé tel quel (confirmé, existant)

- Moteur outbound : `/outbound/call`, garde-fous (token `X-Outbound-Token`,
  `OUTBOUND_HOURS`, numéro FR, registre d'opposition), AMD asynchrone,
  tours pilotés serveur, TimeLimit, raccrochage garanti via l'API REST
  Twilio.
- Config par métier `web/config/metiers/<metier>/` + `_metier_ctx`
  (calendar_id, duration, summary_label) ; hot-reload des prompts.
- Composio Google Calendar (création déjà branchée via
  `/api/calendar/book`) ; MCP disponibilités.
- Agent entrant par établissement (cible des rappels du SMS de repli).
- Resend (récap et alertes email), n8n (orchestration), `usage.jsonl`.

### 3.2 À construire (nouveau)

| Brique | Description | Effort |
|---|---|---|
| N1 | Mode `confirmation` sur `/outbound/call` (body étendu `{mode, rdv, etablissement, rdv_multi[]}`, rétro-compat totale sans `mode`) + prompt confirmation par métier (gabarit + déclinaisons) | 1,5 à 2 j |
| N2 | Tools serveur `reschedule_rdv` + `cancel_rdv` (Composio UPDATE_EVENT, marquage titre, erreurs en `{"status":"error"}` HTTP 200 comme `/api/calendar/book`) | 1 à 1,5 j |
| N3 | Envoi SMS (Twilio Messages API, gabarits par métier, garde-fous horaires, gestion STOP) | 0,5 à 1 j |
| N4 | `/twilio/call-status` + consolidation (brique B2 du baromètre, partagée ; comptée ici à 50 % si le baromètre est construit d'abord) | 0,5 à 1 j |
| WF-NOSHOW | n8n : lecture agenda J+1, filtres, file d'appels par établissement, collecte des résultats, marquage agenda, alertes, récap 20h | 1,5 à 2 j |
| Recette | Simulateur étendu (scénarios confirme / reporte / annule / répondeur / tiers / refus canal), mocks Twilio + Composio, verdicts automatiques | 1 à 1,5 j |
| **Total** | | **6 à 9 jours** (cible réaliste : 7,5 j) |

Aucune de ces briques ne modifie le comportement des chemins existants :
sans `mode`, `/outbound/call` reste octet pour octet identique (même exigence
de non-régression que l'AMD v5 et le baromètre).

---

## 4. Point tranché n°4 : prix de l'add-on (HT, fourchettes)

Positionnement : add-on des Packs 1 et 2 du catalogue
(`OFFRES-PRICING-AGENTS-IA-CS.md`). Prérequis : agenda branché (Pack 2) ou
branchement agenda vendu avec l'add-on.

- **Frais de mise en place HT : 300 à 700 €** (gabarit d'appel adapté au
  métier et à l'établissement, paramétrage horaires, DPA, recette sur RDV de
  test).
- **Abonnement mensuel HT : 60 à 140 €/mois** en add-on d'un pack existant
  (cohérent avec la règle d'upsell du catalogue : chaque palier ajoute 100 à
  300 €/mois, un add-on mono-fonction se place sous ce palier).
- **Usage** : minutes vocales au tarif catalogue (0,35 à 0,45 €/min HT) ;
  SMS 0,08 à 0,12 € HT par segment au-delà d'un forfait inclus de 100 à
  200 SMS/mois.
- Argument de valeur : un no-show évité vaut 20 à 60 € HT chez un coiffeur,
  200 à 300 € en restauration (panier table, chiffres du catalogue), souvent
  plus en cabinet. Deux à trois no-shows évités par mois remboursent
  l'abonnement ; le récap quotidien rend la preuve visible.

---

## 5. Point tranché n°5 : KPIs et coût unitaire

### 5.1 KPIs (suivis par établissement, agrégés dans le récap mensuel)

| Métrique | Définition | Cible indicative |
|---|---|---|
| Taux de joignabilité | appels décrochés humain / appels tentés | 50 à 70 % |
| Taux de statut connu | RDV `confirme`+`reporte`+`annule` / RDV traités | 70 à 90 % (appel + rappels entrants post-SMS) |
| Annulations captées la veille | `annule` la veille / annulations totales | suivi (la valeur : le créneau redevient vendable) |
| Réduction du no-show | no-show après / no-show baseline (déclaré par le commerçant au setup) | 30 à 60 % de réduction (probable, à mesurer au pilote) |
| Taux de refus canal | clients en liste d'exclusion / clients appelés | inférieur à 3 %, sinon revoir heure de tir ou ton |
| Coût par RDV traité | coût Twilio + SMS + voix / RDV traités | 0,15 à 0,45 € HT |

### 5.2 Coût unitaire (fourchettes prudentes, à recaler sur facture réelle)

- Appel décroché (45 à 90 s) : Twilio sortant FR (fixe 0,015 à 0,02 € HT/min,
  mobile 0,09 à 0,12 € HT/min) + AMD (environ 0,0075 € HT/appel) + voix xAI :
  **0,10 à 0,30 € HT**.
- Non-décroché : environ 0 € ; répondeur : moins de 1 minute.
- SMS de repli : **0,08 à 0,12 € HT** par segment.
- Total par RDV traité : **0,15 à 0,45 € HT**, marge confortable sous
  l'abonnement dès 100 à 300 RDV/mois.

---

## 6. Point tranché n°6 : critères d'acceptation TESTABLES

Vérifiables par simulateur (`tools/simulate_call.py` étendu), curl avec mocks
(Twilio, Composio, Resend à zéro effet de bord), ou inspection de données.
Vannina n'est jamais le banc de test : elle valide sur produit vert.

**Garde-fous et conformité**
1. `curl POST /outbound/call` avec `mode=confirmation` SANS `X-Outbound-Token`
   → HTTP 403, zéro `calls.create` (mock Twilio à zéro appel).
2. `mode=confirmation` un dimanche (horloge mockée) → HTTP 423
   `hors_horaires`, zéro appel, zéro SMS.
3. Heure de tir commerçant paramétrée 20h30 → le WF écrête à 19h30 (bord de
   fenêtre), jamais au-delà (inspection de la planification WF sur données de
   test).
4. Numéro en liste d'exclusion de l'établissement → aucun appel ; SMS seul si
   le refus porte sur la voix, rien si le refus porte sur tout le canal
   (deux cas de test distincts).
5. Body sans `mode` → réponse et comportement octet pour octet identiques à
   l'existant (non-régression, mêmes champs JSON).
6. Transcript simulé d'un appel décroché : la première réplique de l'agent
   contient l'identité, l'établissement, la mention IA et la mention
   enregistrement (regex du simulateur), et AUCUNE des répliques ne contient
   de vocabulaire commercial interdit (liste : « offre », « promotion »,
   « profitez », « réduction » ; grep négatif).
7. Événement agenda dont la description contient un motif médical (jeu de
   test « détartrage + implant ») : le motif n'apparaît NI dans le prompt
   envoyé au modèle NI dans aucun transcript (grep négatif sur les deux).
8. Scénario « tiers décroche » (l'interlocuteur dit ne pas être le client) :
   l'agent clôt poliment sans énoncer l'heure du RDV, et un SMS de repli est
   émis vers le numéro du client (mock SMS : 1 envoi).
9. Scénario « ne me rappelez plus pour confirmer » : `marquer_opposition`
   (registre établissement) appelé, confirmation orale, clôture avec au
   revoir ; le RDV de test suivant du même numéro ne génère aucun appel
   (critère 4 rejoué).

**Cadence : jamais deux**
10. Après un appel `no-answer`, aucune deuxième tentative n'est planifiée
    (inspection WF : zéro cron restant pour ce RDV) ; exactement 1 SMS émis.
11. Après un répondeur avec message laissé, le SMS part quand même : total
    pour ce RDV = 1 appel + 1 message vocal ≤ 12 s (durée mesurée sur l'audio
    simulé) + 1 SMS. Jamais rien de plus.
12. `CallStatus=failed` (échec technique) → une seule retentative dans les
    30 min ; si elle échoue aussi, statut `[?]` + SMS, et plus rien.
13. RDV du lundi (veille = dimanche) → l'appel est planifié le samedi dans la
    fenêtre autorisée, et le transcript simulé dit « lundi » et non
    « demain » (regex).

**Agenda : lecture et écriture**
14. WF-NOSHOW sur un agenda de test à 5 événements dont 1 `[ANNULE]`, 1 sans
    téléphone, 1 créé il y a moins de 24h → exactement 2 appels planifiés ;
    les exclus figurent dans le récap avec leur raison.
15. Deux RDV du même numéro le même lendemain → 1 seul appel planifié ; le
    transcript simulé mentionne les deux horaires ; après « je confirme le
    premier mais annulez le second », l'événement 1 porte `[OK]` et
    l'événement 2 porte `[ANNULE]` (lecture Composio mockée).
16. Scénario report : l'agent propose au maximum 2 créneaux par tour (verdict
    simulateur), `reschedule_rdv` est appelé avec le créneau accepté,
    l'événement mocké est déplacé et titré `[REPORTE]`, et la confirmation
    orale reprend le nouveau créneau exact.
17. Scénario annulation : une seule relance douce maximum avant acceptation
    (verdict simulateur : jamais deux tentatives de rétention), `cancel_rdv`
    appelé, événement titré `[ANNULE]` et non supprimé.
18. Échec Composio simulé (500) sur `reschedule_rdv` → l'agent le dit
    honnêtement (« je note, [établissement] vous confirmera le nouveau
    créneau »), statut `a_replanifier`, alerte commerçant émise ; jamais de
    confirmation orale d'un créneau non écrit (règle R1 : ne jamais mentir
    sur une écriture agenda).

**SMS**
19. Gabarit SMS rendu pour un RDV de test : contient l'établissement,
    l'heure, le numéro de l'agent entrant, la mention d'opposition ; 1 seul
    segment si possible et JAMAIS de tiret cadratin ; aucun envoi hors
    fenêtre horaire (test à 20h30 mocké → SMS différé au lendemain 9h30 SAUF
    si le RDV est le lendemain matin avant 10h, auquel cas envoi immédiat
    plafonné à 21h : cas limite tranché ici).
20. Réception d'un STOP (webhook SMS entrant mocké, si le canal le permet) →
    numéro ajouté à la liste d'exclusion, accusé unique, plus aucun SMS.

**Récap et alertes**
21. Annulation captée en simulation → alerte commerçant (mock Resend ou SMS)
    émise en moins de 5 minutes avec le créneau libéré.
22. Récap du soir sur le jeu de test du critère 14 : email Resend contenant
    chaque RDV avec son statut, la section « à confirmer vous-même », le
    compteur mensuel ; rendu réel relu via l'API Resend et archivé
    (directive mémoire) ; aucun tiret cadratin.
23. Chaque tentative produit sa ligne `usage.jsonl`
    (`event=noshow_attempt` avec `rdv_id`, `resultat`, `duree_s`) ;
    `/usage` agrège par établissement.

**Non-régression**
24. Le smoke test existant (`_s1_test.py`) passe inchangé.
25. Un appel de prospection standard (sans `mode`) rejoué au simulateur après
    les modifs → transcript conforme au cahier des charges conversation
    (verdicts existants tous verts).

---

## 7. Hors périmètre (explicitement)

- Aucun appel de rappel J-7 ou J-3 (un seul contact, la veille).
- Pas de prise d'acompte ni de lien de paiement anti no-show (V2 possible).
- Pas de confirmation par WhatsApp ou email côté client final (SMS seul).
- Pas de sur-réservation automatique des créneaux libérés (le commerçant
  décide, l'add-on alerte).
- Le moteur `web/server.py` reste gelé : rien de cette spec ne se construit
  avant la fin du pilote de prospection.

---

## 8. Ordre de build proposé (après validation de cette spec et fin du gel)

1. N4 si non déjà livrée par le baromètre (fondation de mesure commune).
2. N2 (tools agenda) : testable seule par curl + mocks Composio.
3. N1 (mode confirmation + prompt) + critères 1 à 13 au simulateur.
4. N3 (SMS) + critères 19 et 20.
5. WF-NOSHOW + récap + critères 14 à 18 et 21 à 23.
6. Auto-recette complète (25 critères verts, preuves archivées), PUIS
   présentation à Vannina sur l'agenda de test interne.

---

*Spec rédigée le 2026-07-21. Toute révision issue d'un retour de Vannina doit
ajouter l'exigence ici ET son critère testable en section 6.*
