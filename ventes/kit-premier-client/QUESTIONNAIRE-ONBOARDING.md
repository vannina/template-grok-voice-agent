# Questionnaire d'onboarding client : Assistante vocale IA

> Objectif : tout collecter en **UN seul rendez-vous** (45 à 60 min, visio ou sur
> place). Chaque réponse alimente directement un des 4 fichiers de config
> (`system_prompt.txt`, `tools.json`, `business.json`, `profile.json`) ou le contrat.
> Astuce : remplir ce document EN DIRECT pendant le rendez-vous, puis le faire
> valider par mail au client. C'est cette version validée qui fait foi (article 2.3
> du contrat : le client est responsable des infos fournies).

Client : ______________________ · Date : ____________ · Rempli par : ____________

---

## 1. Identité de l'établissement (contrat + business.json)

- Raison sociale exacte : ______________________
- Nom commercial (celui que l'agent prononce) : ______________________
- Forme juridique / SIREN / RCS : ______________________
- Adresse complète (celle à donner aux appelants) : ______________________
- Repère d'accès utile à dire au téléphone (parking, étage, « en face de… ») : ______
- Site web / page Google : ______________________
- Email de contact public : ______________________
- Signataire du contrat (nom, qualité) : ______________________

## 2. Activité et prestations (business.json + system_prompt)

- Métier en une phrase, telle que l'agent doit le dire : ______________________
- Liste des prestations principales (5 à 15 max, libellé + durée + prix indicatif) :

| Prestation | Durée | Prix indicatif HT ou TTC ? | L'agent peut-il l'annoncer ? |
|---|---|---|---|
| | | | oui / non / « à partir de » |

- Prestations que l'agent ne doit JAMAIS chiffrer (devis obligatoire) : ______
- Zone d'intervention / de livraison (communes, rayon km) : ______________________
- Questions les plus fréquentes au téléphone (top 5, avec la réponse voulue) :
  1. ______
  2. ______
  3. ______
  4. ______
  5. ______
- Ce que l'agent ne doit PAS dire ou promettre (liste d'interdits) : ______
- Vocabulaire métier à employer / à éviter (ex. « shampouineuse » vs « bac ») : ______

## 3. Ton et personnalité de l'agent (system_prompt + profile.json)

- Prénom de l'agent (voix féminine par défaut) : ______________________
- **Tutoiement ou vouvoiement des appelants** : tu / vous
  (repère CS : tutoiement artisans, vouvoiement professions libérales et hôteliers,
  mais c'est le client qui tranche)
- Ton souhaité : chaleureux / neutre pro / dynamique / autre : ______
- Formule d'accueil souhaitée (sinon gabarit CS) : ______________________
- Langues à gérer : FR seul / FR + EN / autres : ______
- Rappel non négociable, à dire au client : l'agent annonce à chaque appel qu'il est
  une IA et que l'appel peut être enregistré. Client informé : oui ☐

## 4. Horaires (business.json + logique de renvoi)

- Horaires d'ouverture (par jour, avec coupures) : ______________________
- Jours de fermeture / congés récurrents : ______________________
- Fermetures exceptionnelles déjà connues : ______________________
- L'agent intervient : ☐ seulement sur non-réponse ☐ aussi hors horaires
  ☐ aussi quand la ligne est occupée
- Délai de sonnerie avant bascule vers l'agent (recommandé 15 à 25 s) : ______ s

## 5. Ce que l'agent doit faire pendant l'appel (tools.json + system_prompt)

- Prise de message qualifié : quelles infos minimum ?
  ☐ nom ☐ téléphone ☐ motif ☐ niveau d'urgence ☐ créneau de rappel souhaité
  ☐ autre : ______
- Prise de rendez-vous en direct dans l'agenda : oui / non (si oui, remplir §6)
- Cas à transférer vers un humain (transfert ou promesse de rappel immédiat) :
  - urgence réelle (définir ce qu'est une urgence DANS ce métier) : ______
  - client mécontent / litige : ______
  - demande de devis complexe : ______
  - autre : ______
- Numéro vers lequel transférer / faire rappeler en urgence : ______________________
- Appels à filtrer sans prise de RDV (démarcheurs, stages, candidatures) :
  consigne = prendre un message court, jamais de RDV. OK client : oui ☐
- Récapitulatif des appels envoyé au client par : ☐ SMS ☐ email ☐ les deux
  Destinataire(s) : ______________________
- Fréquence souhaitée : à chaque appel / digest quotidien : ______

## 6. Agenda et rendez-vous (profile.json + Composio)

- Outil actuel : ☐ Google Calendar ☐ Planity ☐ Doctolib ☐ papier ☐ autre : ______
  - **Google Calendar** : intégration directe (partage du calendrier requis).
  - **Planity / Doctolib / autre plateforme fermée** : pas d'écriture directe ;
    l'agent prend les coordonnées + créneau souhaité et le client confirme
    (le noter comme limite, ne rien promettre d'autre).
  - **Papier** : proposer un Google Calendar dédié « Rendez-vous IA » consulté par
    le client, ou mode message seul.
- Compte Google à connecter (adresse) : ______________________
- Durée standard d'un RDV : ______ min · Capacité par créneau : ______
- Contraintes de planning (pause déjeuner, pas de RDV après 17 h, etc.) : ______
- Infos à collecter pour chaque RDV : ☐ nom ☐ téléphone ☐ prestation ☐ remarque
- Politique no-show / annulation à énoncer : ______________________

## 7. Téléphonie (contrat Annexe 1 + runbook)

- Numéro principal à couvrir : ______________________
- Type de ligne : ☐ mobile ☐ fixe box internet ☐ fixe standard / IPBX
- Opérateur : ☐ Orange ☐ SFR ☐ Bouygues ☐ Free ☐ autre : ______
- Qui connaît les codes / l'interface de gestion de la ligne ? ______________________
- Mode de raccordement retenu :
  ☐ renvoi d'appel sur non-réponse vers un numéro fourni par Corsica Studio (défaut)
  ☐ numéro dédié communiqué au public (rare)
- Messagerie vocale actuelle : à conserver en repli si l'agent est indisponible ?
  oui / non
- Test à faire séance tenante si possible : vérifier que le client sait activer un
  renvoi (voir codes dans RUNBOOK-INSTALLATION.md §5). Fait : oui ☐

## 8. Mentions légales et RGPD (contrat + DPA)

- Mentions légales du site à jour ? oui / non · URL : ______
- Le client a-t-il une politique de confidentialité ? oui / non
- Information des appelants : l'agent annonce IA + enregistrement ; le client ajoute
  la mention sur son site / répondeur si souhaité. À prévoir : oui / non
- Durée de conservation souhaitée des transcriptions et messages
  (recommandation CS : 12 mois max) : ______ mois
- Signature du DPA prévue avec le contrat : oui ☐

## 9. Contacts et urgences (runbook + suivi)

- Interlocuteur principal (nom, portable, mail) : ______________________
- Contact de secours si injoignable : ______________________
- Canal préféré pour le suivi première semaine : ☐ téléphone ☐ SMS ☐ email ☐ WhatsApp
- Créneau de disponibilité pour la recette (30 min, appels tests ensemble) : ______
- Date cible de mise en service : ______________________

## 10. Verrouillage de fin de rendez-vous (checklist)

- ☐ Prestations + tarifs + horaires relus à voix haute avec le client
- ☐ Ton (tu/vous) et prénom de l'agent validés
- ☐ Cas d'urgence et numéro de transfert validés
- ☐ Mode agenda validé (et limites expliquées si Planity/Doctolib)
- ☐ Opérateur + faisabilité du renvoi vérifiés
- ☐ Pack, fourchette de prix HT et période d'engagement confirmés
- ☐ Ce questionnaire envoyé par mail pour validation écrite
- ☐ Prochaine étape annoncée : recette ensemble le [DATE], mise en service le [DATE]
