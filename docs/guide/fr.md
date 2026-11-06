# DT3 Agent – Guide d’utilisation (français)

DT3 Agent ajoute à DEVONthink 3 une IA qui fonctionne uniquement sur votre Mac. Il nomme, tague et classe les
documents, lit les QR-factures suisses, repère délais et doublons et répond à vos questions avec les sources.
**Il ne supprime jamais rien dans DT3**, et chaque modification peut être annulée.

*DT3 Agent est un projet open source indépendant, sans lien avec DEVONtechnologies.*

## 1. Prérequis

| | |
|---|---|
| macOS | 11 Big Sur ou plus récent, Intel ou Apple Silicon |
| DEVONthink | 3.9.x (DEVONthink 4 n’est pas pris en charge) |
| Mémoire | 16 Go recommandés ; avec 8 Go, utilisez un serveur IA de votre réseau |
| Espace disque | environ 2,5 Go pour l’app et les modèles d’IA |

## 2. Installer

1. Ouvrez le DMG et glissez **DT3 Agent** dans **Applications**.
2. Premier lancement : l’app est auto-signée (pas d’identifiant de développeur Apple).
   - macOS 11 à 14 : clic droit sur l’app → **Ouvrir** → **Ouvrir**.
   - macOS 15 et plus récent : ouvrez l’app, puis **Réglages Système → Confidentialité et sécurité → Ouvrir quand même**.
3. **Quittez DT3** (Cmd+Q). Le script de la règle intelligente ne peut être copié que si DT3 est fermé.
4. Icône de la barre des menus → **Installation …**. Cochez les deux modèles d’IA (téléchargement depuis
   huggingface.co, environ 1,9 Go, somme de contrôle vérifiée) → **Installer** → attendez « Terminé. »
5. Rouvrez DT3. À la première action, macOS demande si « DT3 Agent Engine » peut contrôler DEVONthink : **OK**.

## 3. Configurer

Icône de la barre des menus → **Configuration …**, puis étape par étape avec **Continuer** :

1. **Contrôle du système** – tout est vert ? Sinon **Vérifier à nouveau**.
2. **IA** – **Tester** → « L’IA répond. »
3. **Vous** – votre nom (utilisé comme destinataire des lettres qui vous sont adressées ; jamais proposé comme contact).
4. **Noms des documents** – le modèle de nom, avec aperçu.
5. **Règle intelligente dans DT3** – dans DT3 : **Tools → New Smart Rule**, événement **On Import**, action
   **Apply Script › External › DT3 Agent Enqueue**. Seuls les groupes avec une telle règle sont traités.
6. **Prêt** – laissez **Garder le mode test (recommandé)** activé.

### Mode test

En mode test (icône : œil), DT3 Agent n’écrit **rien** dans DT3. Toutes les propositions vont dans la **liste de
contrôle**. Quand les propositions vous conviennent : **Réglages → Général → Mode test** désactivé. Les propositions
sûres sont alors appliquées directement ; les incertaines restent dans la liste de contrôle.

## 4. Au quotidien

| Quoi | Comment |
|---|---|
| Nouveaux documents | arrivent dans la file via la règle intelligente |
| Documents isolés | sélectionnez-les dans DT3 → barre des menus → **Traiter les documents sélectionnés** |
| Vérifier les propositions | barre des menus → **Liste de contrôle** → **Accepter**, **Modifier** ou **Refuser** |
| Revenir en arrière | barre des menus → **Annuler le dernier passage …** (vos propres modifications restent) |
| Faire une pause | barre des menus → **Mettre en pause** |

Chaque proposition montre **Avant**, **Proposition** et la **confiance** en pour cent. **Afficher dans DT3** ouvre
le document.

### Courriers suisses

- **QR-factures** : montant, monnaie, référence et créancier sont lus dans le code QR et vérifiés.
- **Délais** : « payable jusqu’au … » devient une proposition d’événement de calendrier avec rappel DT3 – seulement
  après votre accord.
- **Courriers urgents** (poursuites, tribunal, impôts) : signalés dans la liste de contrôle, sur demande déplacés
  dans un groupe.

## 5. Demander et résumer

Barre des menus → **Demander …**

- Tapez une question, puis Retour. La réponse cite ses **sources** ; un clic ouvre le document dans DT3.
- Si aucun document ne correspond, DT3 Agent le dit au lieu de deviner.
- **Résumer** : sélectionnez un document dans DT3, choisissez la langue (DE, FR, IT, EN) → **Résumer**.
- Demander ne peut jamais rien modifier dans DT3. Les ordres adressés à une IA dans les documents sont retirés avant.

Remarque : le modèle fourni est petit. Vérifiez toujours les réponses importantes dans la source.

## 6. Planification (Réglages → Planification)

| Tâche | Par défaut | Effet |
|---|---|---|
| **Zones** | vide | bases et groupes que la tâche de nuit peut lire, une ligne chacun : `Base \| /Groupe/` |
| **Tâche de nuit** | activée, 02:30 | les documents modifiés des zones vont dans la file |
| **Aperçu de la semaine** | désactivé | lundi 07:30 : nouveaux documents, délais ouverts – comme proposition de note |
| **Rapport de rangement** | désactivé | dimanche 03:30 : documents sans tags, anciens éléments du groupe d’entrée, tags similaires |
| **Flux et courriels** | désactivé | chaque jour 06:30 : résumé des nouveaux éléments RSS, web et courriel |
| **Mode économie** | activé | pause sur batterie et quand la mémoire est insuffisante |

Les rapports exigent un **groupe qui existe déjà dans DT3** ; DT3 Agent ne crée jamais de groupe. Chaque rapport
passe d’abord par la liste de contrôle ; seul **Accepter** l’écrit comme note.

Sous **Avancé**, vous pouvez activer les **notes sur les personnes et entreprises** : dès deux documents de la même
entreprise, DT3 Agent propose une note avec des liens.

## 7. Icône de la barre des menus

| Icône | Signification | Que faire |
|---|---|---|
| ✓ | Prêt | – |
| Œil | Mode test | normal ; propositions seulement |
| Pause | En pause | menu → Reprendre |
| Éclair barré | En attente : batterie ou mémoire insuffisante | brancher le chargeur |
| ⚠︎ rouge | IA, index IA ou DT3 injoignable | ouvrir DT3 ; menu → Installation … → Installer |
| Sablier rouge | file bloquée depuis plus de 2 heures | menu → Réglages → Général → Exporter le diagnostic …, l’envoyer au support |
| ⛔ rouge | le moteur ne fonctionne pas | menu → Installation … → Installer |

## 8. Réglages en bref

**Général** (mode test, nom, export/import, diagnostic) · **IA** (adresse du serveur IA, clé API facultative dans le
trousseau) · **Noms** · **Tags** (votre vocabulaire) · **Classement** (groupes par type de document) · **Suisse**
(courriers urgents, conservation) · **Doublons et dossiers** · **Confidentialité** · **Avancé** (seuil, personnes
et entreprises) · **Planification** (voir 6). **Cmd+S** enregistre.

## 9. Supprimer

Barre des menus → **Installation …** → **Supprimer**. Cochez les cases pour effacer aussi les modèles d’IA ou les
réglages, la liste de contrôle et les journaux. Vos bases DT3 restent inchangées. Glissez ensuite l’app des
**Applications** dans la corbeille.

## 10. Confidentialité et aide

- Tout reste sur votre Mac. Détails : [PRIVACY.md](../../PRIVACY.md) (en anglais).
- Signaler un bug : issues GitHub. Problèmes de sécurité : **Security → Report a vulnerability**.
- Support pour les entreprises : [SUPPORT.md](../../SUPPORT.md).
