# SPEC : Agent avis Google (add-on #27, sollicitation d'avis après prestation)

> Rédigé le 2026-07-21. Statut : SPEC validable, AUCUN build engagé (moteur
> `web/server.py` GELÉ jusqu'à la fin du pilote de prospection).
> Méthode : spec écrite + critères d'acceptation testables AVANT toute ligne de code
> (directive du 2026-07-06). Références normatives : `CLAUDE.md` (architecture),
> `docs/CAHIER-DES-CHARGES-CONVERSATION.md` (option vocale),
> `docs/SPEC-BAROMETRE-APPELS-MANQUES.md` (format de spec),
> `docs/SPEC-AGENT-ANTI-NOSHOW.md` (briques partagées : lecture agenda, SMS),
> `docs/OFFRES-PRICING-AGENTS-IA-CS.md` (pricing).

---

## 0. Résumé exécutif

L'add-on avis Google sollicite un retour d'expérience auprès des clients dont
le RDV a été honoré la veille (détection via l'agenda, ou saisie du
commerçant), par SMS d'abord (moins intrusif), avec une option d'appel vocal
pour les clients sans smartphone. Le client note sa visite de 1 à 5 sur une
page dédiée ; son retour est transmis au commerçant, et **le lien vers la
fiche Google du commerce est proposé à TOUS les clients, quelle que soit la
note**. Les clients insatisfaits (1 à 3) génèrent en plus une alerte privée
immédiate au commerçant, qui peut rattraper la situation avant que l'avis
public ne tombe : on n'empêche jamais l'avis, on donne au commerçant une
longueur d'avance sur l'écoute.

Principe directeur tranché ici : **jamais de review gating.** Le filtrage
(lien Google réservé aux satisfaits) est explicitement interdit par les
règles Google et qualifiable de pratique commerciale trompeuse en France
(section 1). Le parcours retenu est conforme : même lien, pour tous, sans
condition ; seule la mise en page du parcours diffère selon la note (écoute
d'abord pour les insatisfaits, lien Google toujours présent).

---

## 1. Point tranché n°1 : conformité (parcours anti review gating)

### 1.1 Ce que disent les règles (sources)

- **Confirmé (règles Google)** : la politique « Fake engagement » et les
  règles des avis Google Business Profile interdisent de solliciter des avis
  de façon sélective auprès des seuls clients satisfaits (review gating) et
  d'offrir une contrepartie contre un avis. Google a mis à jour et durci
  cette documentation en février 2026 en visant explicitement la
  sollicitation ciblée des seuls clients satisfaits ; sanctions : suppression
  d'avis, avertissement public sur la fiche, blocage de la réception d'avis,
  suspension du profil. Sources :
  https://support.google.com/contributionpolicy/answer/7400114 (politique
  contenus, section fake engagement),
  https://www.threechaptermedia.com/blog/google-review-policy-2026 et
  https://searchlabdigital.com/blog/google-review-guidelines-2026-update/
  (mise à jour février 2026),
  https://www.localranker.fr/blog/review-gating et
  https://viewup.fr/blogs/infos/sollicitation-davis-google-en-2026-conformite-sanctions-et-strategies-de-survie
  (synthèses françaises 2026 : « même lien, pour tous, sans condition »).
- **Confirmé (droit français)** : le Code de la consommation qualifie de
  pratique commerciale trompeuse la manipulation d'avis de consommateurs
  (ordonnance n° 2021-1734 du 22 décembre 2021, articles L. 121-2 et
  suivants) ; la DGCCRF contrôle aussi la « modération biaisée » (ne laisser
  émerger que les avis positifs). Sanctions pénales jusqu'à deux ans
  d'emprisonnement et 300 000 € d'amende (montant pouvant être porté en
  proportion du chiffre d'affaires). Sources :
  https://www.economie.gouv.fr/dgccrf/actualites-dgccrf/comment-la-dgccrf-enquete-sur-les-faux-avis,
  https://www.economie.gouv.fr/dgccrf/les-fiches-pratiques/pratiques-commerciales-trompeuses-les-cles-pour-les-reconnaitre-et-sen-premunir.
- **Probable (qualification du gating en France)** : la DGCCRF n'a pas publié
  de décision nommant précisément le « review gating » à date de rédaction,
  mais un dispositif qui oriente les seuls satisfaits vers l'avis public
  s'expose à la qualification de pratique trompeuse par omission (image
  globale des avis faussée). On ne prend pas ce risque, ni pour CS ni pour
  ses clients.

### 1.2 Le parcours conforme retenu (tranché)

1. **Un seul message de sollicitation, envoyé à TOUS les clients éligibles**,
   sans présélection sur la satisfaction supposée.
2. Le message invite à noter l'expérience (1 à 5) sur une page dédiée de
   l'établissement. Cette étape est un **retour d'expérience privé**,
   présenté comme tel, jamais comme une condition d'accès à l'avis public.
3. **La page de retour affiche le lien vers la fiche Google du commerce dans
   TOUS les cas**, quelle que soit la note, et même sans note. Seul l'ORDRE
   d'affichage varie :
   - note 4 ou 5 : remerciement + lien Google mis en avant ;
   - note 1 à 3 : message d'écoute + champ de commentaire libre (transmis en
     privé au commerçant) affichés d'abord, PUIS le lien Google, toujours
     visible sur la même page, sans clic supplémentaire ni condition. Aucune
     formulation dissuasive (« plutôt que de laisser un avis... » interdit).
4. **Aucune contrepartie**, jamais : pas de remise, pas de jeu-concours, pas
   de « avis contre avantage » (interdit règles Google + qualifiable de faux
   avis induit).
5. **Aucune dictée de contenu** : on ne suggère ni mots-clés, ni note, ni
   mention du personnel. Le texte se limite à « partagez votre expérience ».
6. **Volume lissé** : les sollicitations partent au fil de l'eau (J+1 de
   chaque prestation), jamais en rafale rétroactive sur le fichier clients
   (les pics soudains d'avis font partie des signaux sanctionnés par Google
   depuis février 2026). À l'activation de l'add-on, interdiction de
   solliciter l'historique : seuls les RDV postérieurs à l'activation sont
   éligibles.

### 1.3 Cadrage du canal SMS (prospection ou service ?)

- **Probable (prudence retenue)** : la sollicitation d'avis auprès d'un
  client récent peut être rattachée à l'exception « produits ou services
  analogues fournis par la même entreprise » de l'article L. 34-5 du CPCE
  (prospection vers clients existants sans consentement préalable, avec
  droit d'opposition). Par prudence, le dispositif applique le régime
  complet de la prospection SMS : mention STOP dans chaque message,
  exclusion immédiate et définitive sur STOP, envois entre 10h et 20h,
  jamais le dimanche ni les jours fériés.
- **Anti-pression (tranché)** : un même numéro n'est jamais sollicité plus
  d'une fois par période glissante de 90 jours par établissement, même s'il
  revient chaque semaine. Une sollicitation = un SMS, zéro relance.
- **RGPD** : CS sous-traitant du commerçant (DPA, comme l'add-on anti
  no-show) ; données minimales (numéro, date de prestation, note,
  commentaire) ; conservation des retours 12 mois, des journaux 30 jours ;
  le commerçant informe ses clients de l'usage du numéro pour le suivi
  qualité.

---

## 2. Point tranché n°2 : parcours complet

### 2.1 Déclencheur (RDV honoré la veille)

- **Source primaire : l'agenda.** Le workflow n8n quotidien (WF-AVIS, même
  mécanique de lecture Composio que WF-NOSHOW, brique partagée) liste les
  événements de la VEILLE du calendrier de l'établissement et retient ceux
  qui ne portent pas `[ANNULE]` ni `[?]` non résolu. Un RDV passé non annulé
  est réputé honoré (approximation assumée, corrigeable par le commerçant,
  voir ci-dessous).
- **Source secondaire : saisie du commerçant.** Le récap quotidien (email
  existant de l'add-on anti no-show, ou email dédié si l'add-on avis est
  vendu seul) liste les clients éligibles du jour avec, par ligne, un lien
  « ne pas solliciter » (client mécontent connu, prestation ratée, cas
  sensible). Fenêtre de retrait : jusqu'à l'heure d'envoi (11h par défaut).
  Pour un établissement sans agenda branché, la saisie manuelle devient la
  source primaire : le commerçant envoie les numéros du jour via le
  formulaire du récap.
- **Filtres d'entrée** : numéro absent ou invalide, numéro en liste STOP,
  numéro déjà sollicité dans les 90 jours, RDV créé et annulé le même jour,
  numéro du commerçant lui-même.

### 2.2 Le SMS (canal principal)

- Envoi à J+1 de la prestation, à 11h par défaut (paramétrable 10h à 20h,
  jamais dimanche ni férié ; si J+1 est exclu, glissement au premier jour
  autorisé).
- Gabarit (par métier, personnalisé établissement) : « [Établissement] :
  merci de votre visite ! Comment ça s'est passé ? Dites-le nous en
  30 secondes : [lien court]. STOP pour ne plus recevoir ces messages. »
  Aucune mention de note attendue, aucune contrepartie.
- **Réponse par lien, pas par SMS entrant (tranché)** : la notation se fait
  sur une page hébergée par le conteneur demo-voice
  (`GET /avis/<token>`), pas par réponse SMS. Raison : les numéros actuels
  (+33 4 12 13 60 xx) sont des fixes virtuels dont la réception SMS n'est
  pas garantie (probable, à vérifier au build) ; le lien fonctionne quel que
  soit l'expéditeur et permet la page conforme (lien Google pour tous).
  Le token est unique par sollicitation, à durée de vie 30 jours, non
  rejouable après soumission de la note.

### 2.3 La page de notation (`/avis/<token>`)

- Page mobile-first aux couleurs de l'établissement (nom, pas de branding CS
  envahissant), servie par le conteneur demo-voice (résolution par token,
  pas par Host).
- Étape 1 : « Comment s'est passée votre visite ? » : 5 étoiles ou boutons
  1 à 5.
- Étape 2, note 4 ou 5 : remerciement + bouton « Partager votre expérience
  sur Google » (lien direct `g.page/r/.../review` de l'établissement).
- Étape 2, note 1 à 3 : « Merci de votre franchise, qu'est-ce qu'on aurait
  pu mieux faire ? » + champ libre + envoi ; sous le champ, TOUJOURS
  visible sans action supplémentaire : « Vous pouvez aussi partager votre
  expérience sur Google : [même lien] ». Même lien, même page, aucune
  condition (section 1.2).
- La note et le commentaire sont écrits en base locale (SQLite ou JSONL par
  établissement) et poussés à n8n (webhook `AVIS_WEBHOOK_URL`, best-effort
  httpx comme `_demo_webhook`, jamais bloquant).

### 2.4 Alerte privée et récap

- **Note 1 à 3** : alerte PRIVÉE au commerçant en moins de 5 minutes
  (email Resend ou SMS, au choix) : note, commentaire, date de la
  prestation, numéro du client, suggestion d'action (« rappelez-le
  aujourd'hui »). C'est la valeur cachée de l'add-on : rattraper avant
  l'avis public, sans jamais l'empêcher.
- **Récap hebdomadaire** au commerçant : sollicitations envoyées, taux de
  réponse, répartition des notes, commentaires privés reçus, clics vers
  Google. (Le nombre d'avis Google effectivement déposés n'est pas mesurable
  individuellement : indicateur global via le comptage public de la fiche,
  relevé manuel ou scraping léger hebdomadaire, statut probable.)

### 2.5 Option appel vocal (clients sans smartphone)

- Activable par établissement, pour les numéros FIXES uniquement (préfixes
  01 à 05 : un SMS n'y arrivera pas ; les mobiles restent en SMS).
- Appel court (moins de 60 s), mode outbound tours pilotés, prompt dédié :
  identité + IA + enregistrement en une phrase, « comment s'est passée votre
  visite de hier ? », écoute de la réponse, remerciement.
  - Retour positif : « si vous souhaitez partager votre expérience sur
    Google, votre avis compte beaucoup pour [établissement] ». Aucune
    instruction de note, aucune contrepartie, pas de lien possible à
    l'oral : simple invitation, identique pour tous.
  - Retour négatif : écoute (une question de relance maximum), « je
    transmets à [établissement], merci de votre franchise », même invitation
    Google formulée à l'identique, alerte privée commerçant.
- Toutes les règles du cahier des charges conversation s'appliquent (au
  revoir explicite, fenêtre de politesse, raccrochage serveur, répondeur :
  AUCUN message, on raccroche au verdict AMD, une sollicitation d'avis sur
  répondeur n'a aucun sens et dérange).
- Un seul appel, jamais de retentative, mêmes fenêtres horaires que le SMS.

---

## 3. Point tranché n°3 : architecture (extension, pas de nouveau moteur)

### 3.1 Réutilisé (confirmé, existant ou spécifié ailleurs)

- Lecture agenda Composio quotidienne : brique WF partagée avec l'add-on
  anti no-show (`SPEC-AGENT-ANTI-NOSHOW.md` section 2.1), construite une
  seule fois.
- Envoi SMS Twilio : brique N3 de l'anti no-show, partagée (gabarits et
  garde-fous horaires communs).
- Mode outbound tours pilotés + AMD (option vocale) ; `marquer_opposition`
  (registre par établissement) pour le STOP vocal.
- Resend (alertes, récaps), n8n (orchestration), `usage.jsonl` + `/usage`.
- Conteneur demo-voice pour servir la page `/avis/<token>` (même serveur
  FastAPI, endpoint statique + petit handler POST).

### 3.2 À construire (nouveau)

| Brique | Description | Effort |
|---|---|---|
| A1 | Page `/avis/<token>` (GET rendu + POST note/commentaire, tokens signés, anti-rejeu, stockage local, webhook n8n) | 1 à 1,5 j |
| A2 | Gabarits SMS avis + config par établissement (`lien_avis_google`, heure d'envoi, option vocale on/off) dans `web/config/metiers/<m>/avis.json` bind-monté | 0,5 j |
| A3 | WF-AVIS n8n : éligibilité (agenda veille ou saisie), filtres (STOP, 90 jours), envoi lissé, collecte webhook, alerte insatisfait, récap hebdo | 1 à 1,5 j |
| A4 | Option vocale : prompt avis + routage fixes/mobiles (réutilise le mode outbound ; comptée seulement si l'option est vendue) | 1 à 1,5 j |
| Recette | Jeu de tokens, mocks Twilio/Resend, simulateur pour l'option vocale, vérification anti-gating automatisée (section 4) | 1 j |
| **Total** | | **3,5 à 5,5 jours sans option vocale ; 4,5 à 7 jours avec** (cible réaliste : 5,5 j avec option) |

Si l'add-on anti no-show n'est pas construit avant, ajouter la brique de
lecture agenda et l'envoi SMS (environ +1,5 à 2 j) : les deux specs partagent
volontairement ces fondations.

---

## 4. Point tranché n°4 : prix de l'add-on (HT, fourchettes)

Positionnement : add-on des Packs 1 et 2 du catalogue, vendable seul (mode
saisie manuelle) mais pensé en bundle avec l'anti no-show (fondations
communes, argument « la même assistante confirme vos RDV et fait grandir
votre fiche Google »).

- **Frais de mise en place HT : 250 à 550 €** (page de notation aux couleurs
  de l'établissement, lien Google vérifié, gabarits, DPA, recette).
- **Abonnement mensuel HT : 50 à 110 €/mois** en add-on d'un pack existant ;
  70 à 140 €/mois vendu seul (sans pack porteur, le socle support est à
  couvrir).
- **Usage** : forfait de 100 à 200 SMS/mois inclus ; au-delà 0,08 à 0,12 €
  HT par segment ; option vocale : minutes au tarif catalogue (0,35 à
  0,45 €/min HT).
- **Bundle anti no-show + avis** : remise de 10 à 15 % sur l'abonnement
  cumulé des deux add-ons (cohérent avec la règle de remise du catalogue :
  la base mutualisée, lecture agenda et SMS, coûte moins cher à produire).
- Argument de valeur : passer de 15 à 50 avis avec une note défendue change
  le classement local et la conversion de la fiche ; un seul client rattrapé
  avant un avis à une étoile vaut l'abonnement du trimestre.

---

## 5. Point tranché n°5 : KPIs et coûts

### 5.1 KPIs (récap hebdo commerçant + suivi CS)

| Métrique | Définition | Cible indicative |
|---|---|---|
| Taux de réponse | notes déposées / SMS délivrés | 15 à 35 % |
| Taux de clic Google | clics lien Google / notes déposées | 30 à 60 % |
| Avis déposés (proxy) | delta du compteur public de la fiche / sollicitations | 3 à 10 % (probable, mesure indirecte) |
| Délai d'alerte insatisfait | envoi alerte moins soumission note | inférieur à 5 minutes |
| Taux de STOP | STOP / SMS envoyés | inférieur à 2 %, sinon revoir gabarit ou fréquence |
| Note moyenne privée vs publique | comparaison mensuelle | suivi (écart important = problème d'expérience, pas de sollicitation) |

### 5.2 Coûts unitaires (fourchettes prudentes)

- SMS de sollicitation : **0,08 à 0,12 € HT** par segment (1 segment visé).
- Page de notation : négligeable (infra existante).
- Appel vocal optionnel (moins de 60 s) : **0,05 à 0,20 € HT** (fixe FR
  0,015 à 0,02 €/min + voix xAI ; répondeur : environ 0 €, on raccroche au
  verdict).
- Coût complet par client sollicité : **0,08 à 0,30 € HT**, soit 8 à 30 €
  HT pour 100 sollicitations : très en dessous de l'abonnement, la marge
  porte le support et la page.

---

## 6. Point tranché n°6 : critères d'acceptation TESTABLES

Vérifiables par curl, mocks (Twilio, Resend, Composio à zéro effet de bord),
inspection de données, ou simulateur pour l'option vocale. Vannina valide sur
produit vert uniquement.

**Anti-gating (bloquants, vérifiés automatiquement)**
1. Rendu HTML de `/avis/<token>` après une note de 1 : le lien Google de
   l'établissement est présent dans la page (grep de l'URL `g.page` ou
   `google.com/maps` dans le HTML rendu), sans clic ni action préalable.
2. Idem pour les notes 2, 3, 4, 5 ET pour la page avant toute note : le
   lien Google est présent dans les 6 états (boucle de test sur les 6
   rendus).
3. Le HTML des 6 états ne contient aucune formulation dissuasive : grep
   négatif sur une liste bloquante (« plutôt que », « avant de laisser un
   avis », « au lieu de », « ne laissez pas ») et aucune mention d'une
   contrepartie (« remise », « offert », « gagner », « jeu »).
4. Les gabarits SMS ne contiennent ni promesse de contrepartie ni
   instruction de note (grep négatif : « 5 étoiles », « bonne note »,
   « avis positif », liste extensible en config de recette).
5. Le transcript simulé de l'option vocale après un retour NÉGATIF contient
   l'invitation Google avec la même formulation exacte que le scénario
   positif (comparaison de chaînes par le simulateur : formulation
   déterministe, règle 8.3 du cahier conversation).
6. À l'activation d'un établissement de test avec 500 clients historiques en
   base, zéro SMS n'est émis pour des prestations antérieures à la date
   d'activation (mock Twilio à zéro envoi ; seuls les RDV postérieurs
   déclenchent).

**Canal SMS et cadence**
7. WF-AVIS exécuté un dimanche (horloge mockée) → zéro envoi, sollicitations
   glissées au premier jour autorisé (inspection de la file).
8. Heure d'envoi paramétrée 21h → écrêtée à 20h (inspection de la
   planification).
9. Chaque SMS rendu contient le nom de l'établissement, le lien court, la
   mention STOP, aucun tiret cadratin, et tient en 1 segment GSM-7 pour le
   gabarit par défaut (comptage automatisé).
10. Un numéro sollicité il y a 30 jours (base de test) → exclu de la tournée ;
    sollicité il y a 91 jours → inclus (test des deux bords de la fenêtre de
    90 jours).
11. STOP reçu (webhook mocké ou saisie via agent entrant) → numéro en liste
    d'exclusion, zéro SMS pour ses RDV futurs (rejeu du critère 10).
12. Le lien « ne pas solliciter » du récap, cliqué avant 11h sur un client de
    test → ce numéro est retiré de la tournée du jour (zéro envoi pour lui,
    les autres partent).

**Page de notation**
13. Token inconnu ou expiré (31 jours, horloge mockée) → page neutre « lien
    expiré » sans nom de client, HTTP 410, aucune écriture.
14. Double soumission du même token → la seconde est refusée (HTTP 409),
    une seule note en base.
15. POST d'une note 2 avec commentaire → ligne en base locale avec
    établissement, note, commentaire, ts ; webhook n8n mocké reçu avec les
    mêmes champs ; la réponse HTTP n'expose aucune donnée d'un autre client.
16. Le webhook n8n en panne (mock 500) → la note reste écrite en base locale
    et la page répond normalement au client (best-effort, jamais bloquant).

**Alertes et récap**
17. Note 1 à 3 soumise → alerte privée commerçant (mock Resend ou SMS) émise
    en moins de 5 minutes, contenant note, commentaire, date de prestation,
    numéro ; note 4 ou 5 → AUCUNE alerte (les deux cas testés).
18. Récap hebdo sur un jeu de 20 sollicitations de test : compte les envois,
    réponses, répartition des notes, clics Google (compteur de redirection
    `/avis/<token>/google` : le clic est mesuré par redirection serveur,
    pas par pixel) ; rendu réel relu via l'API Resend et archivé ; aucun
    tiret cadratin.

**Option vocale**
19. Routage : un numéro 06/07 dans la tournée vocale de test → SMS et pas
    d'appel ; un 04 → appel et pas de SMS (deux assertions).
20. Verdict AMD `machine_*` pendant un appel avis → raccrochage immédiat,
    zéro frame audio de message (vérifié par le simulateur), zéro SMS de
    substitution vers un fixe.
21. Transcript simulé : première réplique avec identité + établissement +
    mention IA + mention enregistrement ; une seule question de relance
    maximum après un retour négatif ; au revoir explicite avant tout
    raccrochage (verdicts automatiques existants du simulateur).
22. `curl POST /outbound/call` en mode avis sans `X-Outbound-Token` →
    HTTP 403, zéro appel.

**Non-régression**
23. Le smoke test existant (`_s1_test.py`) passe inchangé.
24. Les endpoints existants (`/token`, `/config`, `/api/calendar/book`)
    répondent à l'identique après l'ajout de `/avis/*` (diff de réponses sur
    le jeu de test).

---

## 7. Hors périmètre (explicitement)

- Aucune réponse automatique aux avis Google publics (V2 possible, API
  Business Profile, chantier distinct).
- Pas de sollicitation multi-plateformes (Tripadvisor, Pages Jaunes) dans
  cette version : Google uniquement.
- Pas d'achat ni d'incitation d'avis, jamais, en aucune V.
- Pas de tableau de bord web commerçant (le récap email suffit ; dashboard =
  chantier séparé).
- Le moteur `web/server.py` reste gelé : rien ne se construit avant la fin
  du pilote de prospection.

---

## 8. Ordre de build proposé (après validation de cette spec et fin du gel)

1. A1 (page `/avis/<token>`) + critères 1 à 3 et 13 à 16 : testable seule
   par curl, zéro dépendance.
2. A2 (gabarits + config) + critère 4 et 9.
3. A3 (WF-AVIS) + critères 6 à 12, 17, 18 (réutilise la lecture agenda et le
   SMS de l'anti no-show s'ils existent, sinon les construit ici).
4. A4 (option vocale) + critères 5, 19 à 22, uniquement si vendue.
5. Auto-recette complète (24 critères verts, preuves archivées), PUIS
   présentation à Vannina sur un établissement de test interne.

---

*Spec rédigée le 2026-07-21. Toute révision issue d'un retour de Vannina doit
ajouter l'exigence ici ET son critère testable en section 6.*
