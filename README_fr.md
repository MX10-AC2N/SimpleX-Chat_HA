# 💬 SimpleX Chat pour Home Assistant

[![hacs][hacs-badge]][hacs-url]
[![release][release-badge]][release-url]
![downloads][downloads-badge]

[![Ouvrez votre instance Home Assistant et ouvrez un dépôt dans le Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=MX10-AC2N&repository=SimpleX-Chat_HA)

> 🇬🇧 **English version** : [README.md](README.md)

---

## Qu'est-ce que SimpleX Chat pour Home Assistant ?

Une intégration Home Assistant complète pour envoyer et recevoir des messages
via [SimpleX Chat][simplex] — la messagerie privée par conception : pas
d'identifiants utilisateur, chiffrement de bout en bout, métadonnées
minimales.

Utilisez-la comme canal de notification sécurisé pour votre maison, comme
interface de messagerie sur une tablette murale, ou comme cible pour les
assistants vocaux et les agents IA.

### Fonctionnalités

- 🔎 **Auto-découverte** — les contacts et les groupes du CLI sont découverts automatiquement ; plus besoin de coller un lien d'invitation à usage unique pour chaque contact
- 🔔 **Notifications natives** — une entité `notify.*` par contact ou groupe, créée dès que le bot les connaît
- 💬 **Messages entrants** — événement `simplex_message_received` + capteurs
- 🔍 **Recherche dans toutes les conversations** — une seule barre de recherche sur tout l'historique
- 🖼️ **Images, audio et vidéo** — envoyés comme du vrai contenu SimpleX, affichés en ligne par les clients
- 📊 **Statistiques d'activité** — messages par jour et par contact, déduits de l'historique
- ⚡ **Suivi de connexion en direct** — un contact accepté pendant que Home Assistant tourne apparaît immédiatement, sans redémarrage
- 📇 **Entités par contact** — dernier message, compteur de non-lus et connectivité, sur un device par contact/groupe
- 🧩 **Services** — envoyer un message, envoyer un fichier, rechercher, statistiques d'activité, créer une invitation, accepter un lien, lister les chats, rafraîchir, marquer comme lu
- 🤖 **Outils LLM / Assist** — `send_simplex_message` et `search_simplex_messages`
- 🔄 **Reconnexion automatique** avec backoff exponentiel
- 🌍 **Traductions** EN / FR
- 📦 **Tableaux de bord prêts à l'emploi** — 9, du mur d'état au messager façon application

---

## Prérequis

### Obligatoires

1. **SimpleX Chat CLI** en mode WebSocket :

   ```bash
   simplex-chat -p 5225
   ```

   Quand Home Assistant tourne en Docker, n'utilisez **pas** `127.0.0.1` depuis
   le conteneur HA, sauf si les deux conteneurs partagent le namespace réseau
   de l'hôte.
   Voir le guide dédié : **[DOCKER.md](DOCKER.md)**.

2. Home Assistant **2025.8+** (2026.x recommandé).

### Uniquement pour les tableaux de bord fournis

Les tableaux de bord de [`dashboards/`](dashboards) sont facultatifs —
l'intégration fonctionne toute seule. Mais ils reposent sur deux cartes
Lovelace de la communauté, à installer au préalable :

| Tableau de bord | [Mushroom][mushroom-url] | [Auto Entities][auto-entities-url] | Cartes SimpleX |
|-----------------|--------------------------|-----------------------------------|----------------|
| `simplex_fr.yaml` / `simplex_en.yaml` | – | ✅ obligatoire | – |
| `simplex_mushroom_fr.yaml` / `simplex_mushroom_en.yaml` | ✅ **obligatoire** | ✅ obligatoire | – |
| `simplex_auto_fr.yaml` / `simplex_auto_en.yaml` | – | – | ✅ obligatoire |
| `simplex_tablet_fr.yaml` | – | – | ✅ obligatoire (intercom) |
| `simplex_android_home_fr.yaml` | – | – | ✅ obligatoire |
| `simplex_android_look_fr.yaml` | – | – | ✅ obligatoire |

> ⚠️ **`simplex_mushroom_*.yaml` ne s'affiche pas du tout sans Mushroom.**
> Les cartes apparaissent comme « Custom element: mushroom-… » avec une
> erreur dans la console du navigateur. Installez-le via HACS →
> *Intégrations* → cherchez **Mushroom** → téléchargez, puis rechargez les
> ressources dans *Paramètres → Tableaux de bord → Ressources*.

```yaml
# Paramètres → Tableaux de bord → Ressources → Ajouter une ressource
url: /local/mushroom.js
type: JavaScript Module
```

Les **cartes SimpleX** (liste de conversations, vue de discussion,
interphone) sont livrées avec ce dépôt — pas besoin de HACS, il suffit de
les copier dans `/config/www/` (voir
[Installer les cartes personnalisées](#installer-les-cartes-personnalisées)).

---

## Installation

### HACS (recommandé)

1. HACS → Intégrations → ⋮ → **Dépôts personnalisés**
2. URL : `https://github.com/MX10-AC2N/SimpleX-Chat_HA`
3. Catégorie : **Intégration**
4. Télécharger → Redémarrer Home Assistant
5. **Paramètres → Appareils et services → Ajouter une intégration → SimpleX Chat**
6. Saisissez l'URL WebSocket (par défaut : `ws://127.0.0.1:5225`)

### Installation manuelle

```bash
cd /config/custom_components
# copiez le dossier simplex/ de ce dépôt
```

Redémarrez Home Assistant, puis ajoutez l'intégration depuis l'interface.

### Docker

Si Home Assistant tourne en Docker, vous **devez** faire tourner un démon
WebSocket SimpleX Chat à côté de lui.

→ Guide complet : **[DOCKER.md](DOCKER.md)** (exemples compose, réseau,
dépannage).

Le démon de référence est **[MX10-AC2N/simplex-bridge][bridge-url]**, dont le
contrat WebSocket est validé par une suite de tests dédiée (T01–T13).

---

## Configuration

### Automatique (recommandé)

Rien à faire. Au démarrage, l'intégration demande au CLI sa liste de
contacts (`/_contacts`) et de groupes (`/_groups`), et la tient à jour grâce
aux événements de connexion (`contactConnected`, `contactSndReady`,
`contactUpdated`, `userJoinedGroup`, …).

Chaque chat découvert obtient :

- une entité `notify.simplex_chat_<alias>`,
- un device avec les entités *Dernier message*, *Messages non lus* et
  *Connecté*,
- une ligne dans la carte *SimpleX Conversations* du tableau de bord.

L'alias est dérivé du nom affiché (`Éric` → `eric`). Pour en choisir un
autre : **Paramètres → Appareils et services → SimpleX Chat → Configurer →
Renommer un contact / groupe**.

> L'auto-découverte nécessite que le bridge accepte automatiquement les
> demandes de contact (`SIMPLEX_AUTO_ACCEPT=true`). Voir [DOCKER.md](DOCKER.md).
>
> Les badges de non-lus nécessitent aussi `SIMPLEX_MARK_READ=false` sur le
> bridge : avec `true`, le CLI marque chaque message comme lu à sa
> réception et les compteurs restent à zéro. Voir [DOCKER.md](DOCKER.md).

### Manuelle

1. **Paramètres → Appareils et services → SimpleX Chat → Configurer**
2. Choisissez **Ajouter un contact / groupe**
3. Saisissez un alias (par ex. `Alice`, `Famille`)
4. Collez un lien d'invitation SimpleX (1:1 ou groupe)
5. Une entité `notify.simplex_chat_alice` (ou similaire) est créée
   automatiquement

Les contacts manuels et découverts peuvent coexister : un alias configuré à
la main l'emporte toujours sur l'alias dérivé.

---

## Utilisation

### Notifications

```yaml
action: notify.send_message
data:
  message: "Le dîner est prêt !"
target:
  entity_id: notify.simplex_chat_alice
```

Plusieurs destinataires :

```yaml
target:
  entity_id:
    - notify.simplex_chat_alice
    - notify.simplex_chat_family
```

### Services

#### Envoyer un message

```yaml
action: simplex.send_message
data:
  alias: Alice
  message: "La porte d'entrée est ouverte"
  title: "Sécurité"
```

Par référence de chat au lieu de l'alias :

```yaml
action: simplex.send_message
data:
  chat_ref: "@3"
  message: "La porte d'entrée est ouverte"
```

#### Envoyer un fichier ou une image

```yaml
action: simplex.send_file
data:
  alias: Alice
  file_path: /config/simplex_outbox/clip.ogg
  message: "Enregistrement de la sonnette"   # légende optionnelle
```

Le chemin doit être lisible par le processus `simplex-chat` — utilisez un
volume partagé avec le conteneur du bridge (voir [DOCKER.md](DOCKER.md)).

#### Rechercher dans toutes les conversations

```yaml
action: simplex.search
data:
  query: "dîner"
  limit: 50
```

#### Statistiques d'activité

```yaml
action: simplex.activity_stats
data:
  days: 30
```

Renvoie la série par jour et le détail par chat (nombre sur la fenêtre,
total historique, non-lus).

#### Créer une invitation

```yaml
action: simplex.create_invite
```

La réponse contient `invite_link`.

#### Accepter une invitation

```yaml
action: simplex.accept_invite
data:
  invite_link: "https://simplex.chat/invitation#..."
  alias: Bob
```

#### Découvrir / rafraîchir

```yaml
action: simplex.refresh_contacts
```

Force une relecture des listes de contacts et de groupes du CLI.

#### Marquer comme lu

```yaml
action: simplex.mark_read
data:
  alias: Alice
  item_ids: [17, 18]
```

### Événements entrants

Chaque message entrant déclenche `simplex_message_received` :

```yaml
automation:
  - alias: "Réagir à un message SimpleX"
    trigger:
      - platform: event
        event_type: simplex_message_received
    condition:
      - condition: template
        value_template: "{{ trigger.event.data.alias == 'Alice' }}"
    action:
      - action: notify.persistent_notification
        data:
          message: "{{ trigger.event.data.text }}"
```

| Clé            | Description                                |
|----------------|--------------------------------------------|
| `alias`        | Alias du chat (configuré ou dérivé)        |
| `chat_ref`     | `@123` ou `#456`                           |
| `display_name` | Nom affiché du contact / groupe            |
| `sender`       | Qui a écrit (membres de groupe)            |
| `type`         | `contact` ou `group`                       |
| `text`         | Corps du message                           |
| `direction`    | `incoming` / `outgoing`                    |
| `status`       | `sent` / `delivered` / `read` / `sending`  |
| `item_id`      | ID SimpleX interne                         |
| `timestamp`    | Horodatage du message                      |
| `edited`       | Message modifié ou non                     |
| `file`         | Métadonnées de la pièce jointe (nom, taille, URL média) |

Autres événements : `simplex_targets_updated` (un chat découvert ou
supprimé), `simplex_activity_updated` (les compteurs d'activité ont changé)
et `simplex_error` (le CLI a répondu `chatCmdError`).

### Entités

Les entités vivent sur deux types de devices :

- le device **Simplex Chat** — l'intégration elle-même
  (`sensor.simplex_chat_*`, `binary_sensor.simplex_chat_connection`) ;
- un device **par contact/groupe**, nommé d'après lui
  (`sensor.alice_last_message`, `binary_sensor.alice_connected`, …).

| Entité | Description |
|--------|-------------|
| `binary_sensor.simplex_chat_connection` | État du WebSocket (+ dernière erreur CLI en attributs) |
| `sensor.simplex_chat_last_message` | Dernier message **reçu**, avec attributs expéditeur/horodatage |
| `sensor.simplex_chat_known_contacts` | Nombre de chats connus (configurés + découverts) |
| `sensor.simplex_chat_configured_contacts` | Nombre de chats configurés à la main |
| `sensor.simplex_chat_discovered_contacts` | Nombre de chats auto-découverts |
| `sensor.simplex_chat_unread_messages` | Total des messages non lus |
| `sensor.simplex_chat_last_error` | Dernière erreur CLI (diagnostic) |
| `sensor.simplex_chat_messages_today` | Messages reçus aujourd'hui (tous les chats) |
| `sensor.simplex_chat_messages_week` | Messages reçus sur les 7 derniers jours |
| `sensor.<contact>_last_message` | Dernier message d'un contact/groupe |
| `sensor.<contact>_unread_messages` | Compteur de non-lus d'un contact/groupe |
| `sensor.<contact>_messages_today` | Messages reçus aujourd'hui sur un contact/groupe |
| `binary_sensor.<contact>_connected` | Connectivité d'un contact/groupe |

> **Entity ids et la mise à niveau 2.0** — le device de l'intégration
> s'appelait *SimpleX Chat*, que Home Assistant transformait en
> `simple_x_chat_*`. Les ids documentés ci-dessus (`simplex_chat_*`) ont
> toujours été ceux du README et des tableaux de bord : avant la 2.0, les
> tableaux de bord fournis ne pouvaient donc pas trouver leurs entités. La
> version 2.0 renomme le device et migre automatiquement les entity ids des
> installations existantes.

### Rechercher dans toutes les conversations

Le champ de recherche de la carte des conversations filtre la liste au fil
de la frappe. Appuyez sur **Entrée** (ou sur le bouton 🔍) pour chercher
dans le *texte des messages* de toutes les conversations à la fois — la
commande CLI utilisée est `/_get items count=<n> search=<text>`, qui
cherche par-dessus tous les chats.

Les résultats sont regroupés par conversation, avec les extraits
correspondants surlignés ; un clic ouvre la conversation. La même
recherche est disponible en service `simplex.search` et en commande
websocket `simplex/search`.

### Envoyer des images

La vue de discussion et la carte intercom ont un **bouton image** (📷).
L'endpoint d'upload accepte `image` en plus de `audio` et `video`, et le
type est déduit de l'extension du fichier quand il n'est pas précisé.

Les images sont envoyées comme contenu SimpleX `image` (et non comme
pièces jointes génériques), donc elles s'affichent en ligne dans les
clients SimpleX.

Extensions image acceptées : `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`,
`.bmp`, `.heic`, `.heif`.

### Statistiques d'activité

SimpleX n'expose aucun compteur : l'intégration les déduit de l'historique
des conversations. Les compteurs sont pré-remplis depuis l'historique au
démarrage, puis maintenus à jour en continu.

L'attribut `daily` de `sensor.simplex_chat_messages_week` contient la
série par jour que les tableaux de bord dessinent en petit histogramme. Le
service `simplex.activity_stats` renvoie cette série plus un détail par
chat.

### Assist / LLM

Deux outils sont enregistrés automatiquement :

- `send_simplex_message` — « Envoie un message SimpleX à Alice : je serai à la maison dans 10 minutes »
- `search_simplex_messages` — « Quand ai-je parlé du dîner à Alice ? »

---

## Tableaux de bord & cartes

Neuf tableaux de bord prêts à l'emploi sont fournis dans
[`dashboards/`](dashboards). Vérifiez le
[tableau des dépendances](#uniquement-pour-les-tableaux-de-bord-fournis)
avant d'en copier un — `simplex_mushroom_*.yaml` en particulier exige
[Mushroom][mushroom-url] et [Auto Entities][auto-entities-url].

| Fichier | Style |
|---------|-------|
| `simplex_fr.yaml` / `simplex_en.yaml` | Statut, actions, liste des contacts |
| `simplex_mushroom_fr.yaml` / `_en.yaml` | Idem, style Mushroom |
| `simplex_tablet_fr.yaml` | Tablette murale (interphone) |
| `simplex_auto_fr.yaml` / `simplex_auto_en.yaml` | **Fçon application** : liste de conversations + discussion |
| `simplex_android_home_fr.yaml` | Fçon application, une vue de discussion générique |
| `simplex_android_look_fr.yaml` | Fil de discussion seul |

### Installer les cartes personnalisées

Les tableaux de bord « façon application » ont besoin de deux cartes
Lovelace. Copiez-les dans `/config/www/` et déclarez-les dans *Paramètres →
Tableaux de bord → Ressources* :

```
/config/www/simplex-conversations-card/simplex-conversations-card.js
/config/www/simplex-chat-card/simplex-chat-card.js
```

Les deux en **JavaScript Module**. Le tableau de bord tablette murale
ajoute `/config/www/simplex-intercom-card/simplex-intercom-card.js`.

### Le mode dynamique — une vue pour tous les contacts

La liste des conversations est remplie par l'auto-découverte, donc déclarer
une vue de tableau de bord par contact ne servirait à rien. La carte de
discussion gère donc un alias `auto` : elle lit l'alias dans l'URL.

```yaml
- type: custom:simplex-conversations-card
  navigate_prefix: /simplex-chat
  navigate_mode: hash        # par défaut
- type: custom:simplex-chat-card
  alias: auto
```

Un clic sur une ligne navigue vers `/simplex-chat#alice`. Le fragment (`#`)
porte l'alias et survit à un rechargement de page : une seule vue générique
sert donc tous les contacts. `navigate_mode: path` (`/simplex-chat/alice`)
est disponible si vous préférez une URL par contact.

Un `alias:` explicite fonctionne exactement comme avant — le mode
dynamique est optionnel, carte par carte.

### Ce qu'apportent les cartes

**Liste de conversations** — barre de recherche, couleurs d'avatar
déterministes, surlignage et badge des non-lus, pastille de connexion,
heures relatives, icônes de groupe, compteur de non-lus. Elle se rafraîchit
à chaque nouveau message et à chaque découverte de contact.

**Vue de discussion** — séparateurs de jour, noms d'expéditeurs dans les
groupes, état de connexion dans l'en-tête, bouton « marquer comme lu »,
enregistrement vocal/vidéo, envoi d'images, défilement infini dans
l'historique.

---

## Architecture

```
Home Assistant
    │
    ├── notify.* entities  ──┐
    ├── services           ──┼──► SimplexWsClient ──► ws://…:5225 ──► simplex-chat CLI
    ├── LLM tool           ──┘                              │
    │                                                       │
    └── events + sensors  ◄─────────────────────────────────┘
```

Le client WebSocket gère la reconnexion automatique, la corrélation des
réponses RPC (`corrId`), la distribution des événements et l'obfuscation des
liens sensibles dans les logs.

Le **registre des cibles** (`targets.py`) fusionne les chats configurés à la
main et les chats auto-découverts dans une vue unique, afin que chaque
consommateur — entités notify, capteurs, outil LLM, cartes du tableau de
bord — voie la même liste. La découverte reste en mémoire : elle ne réécrit
jamais l'entrée de configuration.

---

## Dépannage

### Le tableau de bord affiche « Custom element: mushroom-… »

Mushroom n'est pas installé, ou la ressource n'est pas déclarée. Installez-le
via HACS, puis ajoutez `/local/mushroom.js` en **JavaScript Module** dans
*Paramètres → Tableaux de bord → Ressources* et videz le cache du
navigateur.

### La carte des conversations est vide

Les tableaux de bord « façon application » ont besoin des trois cartes
SimpleX dans `/config/www/` (voir
[Installer les cartes personnalisées](#installer-les-cartes-personnalisées))
**et** de la ressource `simplex-conversations-card` déclarée. Si la liste
reste vide, vérifiez que l'auto-découverte a fonctionné —
`sensor.simplex_chat_discovered_contacts` doit être supérieur à 0.

### Aucun message n'arrive

Activez les logs de debug :

```yaml
logger:
  default: info
  logs:
    custom_components.simplex: debug
```

Puis vérifiez :

1. `simplex-chat -p 5225` tourne-t-il ?
2. `binary_sensor.simplex_chat_connection` est-il sur `on` ?
3. Des entrées `chatCmdError` dans les logs ? (`sensor.simplex_chat_last_error`)
4. Le lien d'invitation est-il toujours valide ?
5. Un contact manque ? Appelez `simplex.refresh_contacts`. L'intégration relit aussi les contacts et les groupes du CLI après chaque reconnexion, et journalise un avertissement (`auto-discovery incomplete`) si un inventaire échoue.

### Les compteurs de non-lus restent à zéro

Le bridge marque les messages comme lus à leur arrivée. Passez
`SIMPLEX_MARK_READ=false` dans l'environnement du bridge — voir
[DOCKER.md](DOCKER.md).

---

## Feuille de route

- [x] Adresse longue durée
- [x] Envoi de fichiers / images
- [x] Auto-découverte des contacts et des groupes
- [x] Capteurs et binary sensors par contact
- [x] Cartes Lovelace
- [x] Recherche dans les conversations
- [x] Statistiques d'activité
- [ ] Support multi-profils

---

## Tests

Le dépôt fournit une suite de tests sans dépendance qui rejoue de **vraies**
frames du CLI SimpleX Chat v7.1.4.0 à travers le mapping de l'intégration :

```bash
python3 -m unittest discover -s tests -v
```

---

## Crédits

- [SimpleX Chat][simplex] — la messagerie elle-même, par [SimpleX Chat Ltd][simplex-ltd]
- [Mushroom][mushroom-url] — les cartes Lovelace des tableaux de bord Mushroom
- [Auto Entities][auto-entities-url] — utilisé par les tableaux de bord pour lister les entités dynamiquement
- [simplex-bridge][bridge-url] — le démon WebSocket de référence

---

## Licence

MIT

SimpleX Chat est un projet de [SimpleX Chat Ltd][simplex-ltd]. Cette
intégration est un projet communautaire indépendant, sans affiliation
officielle.

<!-- Badges -->

[hacs-url]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/hacs-default-orange.svg?style=flat-square
[release-badge]: https://img.shields.io/github/v/release/MX10-AC2N/SimpleX-Chat_HA?style=flat-square
[downloads-badge]: https://img.shields.io/github/downloads/MX10-AC2N/SimpleX-Chat_HA/total?style=flat-square

<!-- References -->

[simplex]: https://simplex.chat/
[simplex-ltd]: https://simplex.chat/
[mushroom-url]: https://github.com/piitaya/lovelace-mushroom
[auto-entities-url]: https://github.com/thomasloven/lovelace-auto-entities
[bridge-url]: https://github.com/MX10-AC2N/simplex-bridge
