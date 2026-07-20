# RGPD : registre de traitement + modèle de DPA (sous-traitance)

> **AVERTISSEMENT : modèle de travail.**
> À faire relire par un avocat (ou un conseil RGPD) avant première signature.
> Partie A : registre interne Corsica Studio (à tenir à jour, non contractuel).
> Partie B : modèle de DPA à signer avec chaque client (Annexe 3 du contrat type).

Version gabarit : 1.0 (2026-07-20)

---

# PARTIE A : Registre des activités de traitement (Corsica Studio, sous-traitant)

Article 30.2 du RGPD. Corsica Studio agit ici en **sous-traitant** pour le compte de
ses clients (les établissements équipés d'un agent vocal), chacun **responsable de
traitement** des données de ses propres appelants.

Sous-traitant : [RAISON SOCIALE], [SIREN], [ADRESSE, Ajaccio].
Contact données personnelles : contact@corsica-studio.com (pas de DPO désigné à ce
jour : structure unipersonnelle, à réévaluer si le volume ou la sensibilité augmente).

## A.1 Traitement n°1 : prise d'appels par agent vocal IA

| Rubrique | Contenu |
|---|---|
| Finalité | Répondre aux appels non pris du client : renseigner, prendre des messages, qualifier, prendre des rendez-vous |
| Personnes concernées | Appelants de l'établissement client (ses clients et prospects) |
| Données traitées | Voix (flux audio de l'appel), transcriptions, numéro de téléphone appelant (ou mention « masqué »), nom/prénom déclarés, motif d'appel, degré d'urgence, créneaux et rendez-vous, adresse mail si donnée |
| Données sensibles | En principe aucune ; risque incident chez les clients santé (un appelant peut évoquer son état de santé) : voir point de vigilance A.4 |
| Sur instruction de | Le client (responsable de traitement), via le contrat + le questionnaire d'onboarding validé |
| Lieux de traitement | VPS Hostinger (localisation du datacenter À VÉRIFIER ET CONSIGNER ICI : [France / UE / autre]) + fournisseurs listés en A.3 |
| Durées de conservation | Voir A.2 |
| Mesures de sécurité | Voir A.5 |

## A.2 Données et durées (règles par défaut, ajustables par contrat)

| Donnée | Où | Durée | Remarque |
|---|---|---|---|
| Flux audio de l'appel | Transite en temps réel (Twilio → serveur CS → xAI) | Non conservé par Corsica Studio (pas d'enregistrement stocké sur le VPS par défaut) | La rétention éventuelle chez Twilio et xAI est régie par leurs conditions : à vérifier et documenter (point de vigilance) |
| Transcriptions d'appels (logs applicatifs) | VPS (logs conteneur) | Rotation courte, cible 30 à 90 jours | Servent au debug et à l'amélioration du script |
| Messages et récaps d'appel | Mail/SMS du client + notification | Maîtrisés par le client dans sa boîte ; côté CS, cible 12 mois max | |
| Rendez-vous (nom, téléphone, prestation) | Google Calendar du client | Maîtrisée par le client | CS n'y accède que pour l'exploitation du service |
| Journal d'usage (`usage.jsonl`, attribution, métriques) | VPS | 12 mois max | Pas de contenu de conversation, données de volumétrie |
| Coordonnées de contact du client (le professionnel) | Outils internes CS (Airtable, mail) | Durée de la relation + prescription légale | Traitement dont CS est responsable (gestion clients), hors périmètre du DPA |

## A.3 Sous-traitants ultérieurs et localisation

| Fournisseur | Rôle | Localisation / transfert | Garanties et vigilance |
|---|---|---|---|
| Hostinger | Hébergement VPS (serveur applicatif, logs) | Datacenter [À VÉRIFIER : France / UE] | DPA Hostinger ; vérifier et consigner la localisation exacte du VPS |
| Twilio | Téléphonie programmable (transport des appels, webhook, flux audio) | Entité UE (Irlande) pour les clients européens, groupe US : transferts encadrés | DPA Twilio + clauses contractuelles types (SCC) ; vérifier l'adhésion au Data Privacy Framework |
| **xAI** | Modèle d'IA vocale temps réel (audio + transcription + génération) | **États-Unis : POINT DE VIGILANCE PRINCIPAL, transfert hors UE** | À traiter explicitement : DPA xAI, SCC, statut Data Privacy Framework, options de rétention/opt-out d'entraînement. Signalé au client dans le DPA (B.7). Tant que ce point n'est pas consolidé, ne pas signer de client dont les appels porteraient sur des données sensibles (santé notamment) sans analyse complémentaire |
| Google (Google Calendar) | Écriture des rendez-vous dans l'agenda | Google Ireland pour l'UE ; groupe US | DPA Google Workspace, SCC/DPF ; l'agenda appartient au client |
| Composio | Connecteur d'accès à Google Calendar | États-Unis | Transfert hors UE : DPA/SCC à vérifier ; ne transporte que les champs du rendez-vous |
| n8n (auto-hébergé) | Notifications et routage internes | Sur infrastructure CS (même vigilance localisation que le VPS) | Pas un tiers : composant auto-hébergé |
| Resend | Envoi des mails de récap/confirmation | États-Unis (infrastructure mondiale) | DPA/SCC à vérifier ; limiter le contenu au nécessaire |
| Twilio SMS | Récaps par SMS | idem Twilio | idem Twilio |
| Telegram | Alertes internes CS (nouvel appel, démo lancée) | Hors UE | Ne JAMAIS y faire transiter le contenu détaillé des appels ni les coordonnées des appelants finaux ; alertes limitées à la volumétrie et au nom de l'établissement |

Règle d'or : cette liste est reprise en Annexe 1 du DPA (Partie B). Tout ajout ou
remplacement = information préalable du client (B.6).

## A.4 Points de vigilance actés

1. **xAI aux États-Unis** : le flux audio et les transcriptions passent par un
   fournisseur US. C'est LE point à sécuriser (SCC/DPF + analyse de transfert) et à
   dire honnêtement au client dans le DPA. Ne pas le masquer.
2. **Clients santé** (cabinet médical, dentaire, véto pour les coordonnées des
   maîtres) : risque de données de santé évoquées spontanément par les appelants.
   Avant de signer un client santé : analyse dédiée (minimisation dans les récaps,
   consignes au prompt pour ne pas faire préciser les motifs médicaux, AIPD à
   envisager).
3. **Enregistrement des appels** : l'agent annonce l'enregistrement possible à chaque
   appel. Par défaut, Corsica Studio ne stocke pas l'audio ; si un client demande la
   conservation des enregistrements, traiter comme une évolution (durée, sécurité,
   information des appelants renforcée).
4. **Localisation exacte du VPS Hostinger** : à vérifier une fois et consigner ici
   avec la date. Si le datacenter n'est pas dans l'UE, migration ou mesure
   complémentaire à décider AVANT le premier client signé.

## A.5 Mesures de sécurité (état actuel, honnête)

- Accès VPS par SSH restreint ; secrets hors dépôt git (`.env` + coffre chiffré,
  passphrase dans le trousseau).
- TLS (HTTPS/WSS) sur tous les flux, Traefik + Let's Encrypt.
- Clé API xAI jamais exposée au navigateur (jetons éphémères 5 min).
- Conteneurisation ; config client montée en lecture seule dans le conteneur.
- Journal des actions serveur (`vps/JOURNAL.md`).
- Sauvegardes : [À COMPLÉTER : fréquence et localisation des sauvegardes du VPS].
- Limites assumées : structure unipersonnelle, pas d'astreinte 24/7 ; cohérent avec
  le SLA contractuel (jours ouvrés).

---

# PARTIE B : Modèle d'accord de sous-traitance (DPA), Annexe 3 du contrat

Accord de protection des données conclu en application de l'article 28 du RGPD,
entre :
- **Le Client** (l'établissement), **responsable de traitement** ;
- **[RAISON SOCIALE]** (« Corsica Studio »), **sous-traitant**.

Le présent DPA fait partie intégrante du contrat de prestation et d'abonnement
« Assistante vocale IA ». En cas de contradiction avec le contrat, le DPA prévaut
pour tout ce qui concerne les données personnelles.

## B.1 Objet et instructions

Corsica Studio traite les données personnelles des appelants du Client uniquement
pour fournir le service décrit au contrat (prise d'appels, messages, renseignements,
rendez-vous), et uniquement sur instruction documentée du Client. Le contrat, ses
annexes et le questionnaire d'onboarding validé constituent les instructions. Toute
instruction supplémentaire doit être écrite (mail accepté). Si Corsica Studio estime
qu'une instruction viole le RGPD, elle en informe le Client sans délai.

## B.2 Description du traitement

| Rubrique | Contenu |
|---|---|
| Nature | Collecte orale, transcription, enregistrement de messages et de rendez-vous, notification |
| Finalité | Traitement des appels entrants non pris par le Client |
| Personnes concernées | Appelants du Client |
| Catégories de données | Voix (flux temps réel), transcriptions, identité déclarée, téléphone, mail éventuel, motif d'appel, urgence, rendez-vous |
| Données sensibles | Aucune collecte volontaire ; le script est conçu pour ne pas faire préciser de données sensibles. Si l'activité du Client expose à de telles données, une annexe spécifique est requise avant mise en service |
| Durée | Durée du contrat + délais de suppression (B.9) |

## B.3 Durées de conservation

Sauf instruction écrite contraire du Client :
- flux audio : non conservé par Corsica Studio ;
- transcriptions et journaux applicatifs : [30 à 90] jours ;
- messages et récapitulatifs côté Corsica Studio : [12] mois maximum ;
- données de rendez-vous : dans l'agenda du Client, sous sa maîtrise ;
- journaux techniques de volumétrie : [12] mois maximum.

## B.4 Obligations de Corsica Studio

- Ne traiter que sur instruction (B.1) ;
- garantir la confidentialité (engagement personnel du dirigeant et de toute
  personne autorisée) ;
- mettre en œuvre les mesures techniques et organisationnelles de l'Annexe 2 ;
- assister le Client, dans un délai raisonnable et compte tenu de la nature du
  traitement, pour : les demandes d'exercice de droits (B.8), la sécurité, la
  notification des violations (B.10), et toute analyse d'impact qui s'avérerait
  nécessaire ;
- tenir à disposition les informations nécessaires pour démontrer la conformité et
  permettre un audit (B.11) ;
- supprimer ou restituer les données en fin de contrat (B.9).

## B.5 Obligations du Client (responsable de traitement)

- Disposer d'une base légale pour le traitement des données de ses appelants ;
- assurer l'information de ses appelants (mention sur son site, ses documents ; il
  est rappelé que l'agent annonce oralement, à chaque appel, sa nature d'IA et
  l'enregistrement éventuel) ;
- fournir des instructions licites et des informations exactes ;
- répondre aux demandes de droits de ses appelants (Corsica Studio assiste, B.8).

## B.6 Sous-traitants ultérieurs

Le Client autorise de manière générale le recours aux sous-traitants ultérieurs
listés en **Annexe 1** (liste reprise de la Partie A.3 : Hostinger, Twilio, xAI,
Google, Composio, Resend, opérateurs SMS). Corsica Studio informe le Client par
écrit de tout ajout ou remplacement au moins [15] jours avant sa mise en œuvre ;
le Client peut s'y opposer par écrit pour motif légitime ; en l'absence de solution
alternative raisonnable, chaque partie peut résilier le contrat sans indemnité.
Corsica Studio impose à ses sous-traitants ultérieurs des obligations équivalentes
au présent DPA et demeure responsable de leur exécution.

## B.7 Transferts hors Union européenne

Certains sous-traitants ultérieurs traitent des données hors de l'UE, notamment :
- **xAI (États-Unis)** : traitement du flux audio et des transcriptions par le modèle
  d'IA vocale. Transfert encadré par [clauses contractuelles types de la Commission
  européenne / certification Data Privacy Framework : À VÉRIFIER ET COMPLÉTER avant
  signature] ;
- Composio, Resend (États-Unis) : données limitées respectivement aux champs de
  rendez-vous et aux contenus de mails de récapitulatif ;
- Twilio, Google : entités européennes avec mécanismes de transfert intra-groupe
  (SCC et/ou DPF).

Le Client reconnaît avoir été informé de ces transferts et de leur encadrement,
détaillés en Annexe 1. Corsica Studio s'engage à répercuter toute évolution
(invalidation d'un mécanisme, changement de fournisseur) et à proposer, le cas
échéant, une alternative.

## B.8 Droits des personnes

Corsica Studio transmet au Client, sous [5] jours ouvrés, toute demande d'exercice
de droits reçue directement (accès, rectification, effacement, opposition,
limitation, portabilité) et n'y répond pas elle-même sauf instruction. Elle fournit
au Client, sur demande, les données détenues concernant l'appelant en cause dans un
délai raisonnable, compatible avec le délai d'un mois qui pèse sur le Client.

## B.9 Sort des données en fin de contrat

Au terme du contrat, au choix du Client exprimé par écrit sous [30] jours :
restitution des données dans un format lisible (export) puis suppression, ou
suppression directe. À défaut de choix, suppression à l'issue du délai. Suppression
effective sous [30] jours supplémentaires, sauvegardes purgées au fil de leur
rotation. Une attestation de suppression est fournie sur demande.

## B.10 Violations de données

Corsica Studio notifie au Client toute violation de données personnelles **dans les
meilleurs délais et au plus tard 48 heures** après en avoir pris connaissance, avec
les informations disponibles (nature, catégories et volumes estimés, conséquences
probables, mesures prises). La notification à la CNIL et aux personnes concernées
relève du Client ; Corsica Studio apporte son concours.

## B.11 Audit

Sur demande écrite avec un préavis de [30] jours, au maximum une fois par an et
pendant les heures ouvrées, le Client peut vérifier le respect du présent DPA :
d'abord sur pièces (questionnaire, attestations, extraits de configuration), puis,
si nécessaire et à ses frais, par un audit sur site ou en visio, sans accès aux
données des autres clients de Corsica Studio ni aux secrets d'exploitation.

## B.12 Durée

Le présent DPA s'applique pendant toute la durée du contrat et jusqu'à la
suppression effective des données (B.9).

---

### Annexe 1 du DPA : sous-traitants ultérieurs autorisés

Reprendre le tableau A.3 (fournisseur, rôle, localisation, garanties de transfert),
complété des références exactes des DPA fournisseurs à la date de signature.
[À COMPLÉTER : vérifier chaque ligne avant la première signature, en particulier
xAI et la localisation du VPS Hostinger.]

### Annexe 2 du DPA : mesures de sécurité

Reprendre A.5 (chiffrement TLS de bout en bout des flux, secrets chiffrés hors
dépôt, jetons éphémères, accès SSH restreint, cloisonnement conteneur, journaux,
politique de sauvegarde), rédigé à date.

---

Fait à [VILLE], le [DATE].
Pour le Client : [NOM, QUALITÉ, SIGNATURE]
Pour Corsica Studio : [NOM, QUALITÉ, SIGNATURE]

---

# PARTIE C : Checklist RGPD avant le premier client (interne, à cocher une fois)

- ☐ Vérifier et consigner la localisation exacte du datacenter du VPS Hostinger.
- ☐ Récupérer et archiver les DPA fournisseurs : Twilio, xAI, Google, Composio,
  Resend, Hostinger (dossier `ventes/kit-premier-client/dpa-fournisseurs/`).
- ☐ Statuer sur le mécanisme de transfert xAI (SCC signées ? DPF ?) et compléter B.7.
- ☐ Vérifier la rétention audio réelle chez Twilio et xAI (et l'opt-out
  d'entraînement des modèles si disponible) ; reporter en A.2.
- ☐ Mettre la rotation des logs applicatifs en cohérence avec B.3 (30 à 90 jours).
- ☐ Ajouter la mention sous-traitance agents vocaux à la politique de
  confidentialité du site corsica-studio.com.
- ☐ Purger Telegram de toute donnée d'appelant final (alertes = volumétrie
  uniquement).
