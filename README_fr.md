# SimpleX Chat pour Home Assistant

Intégration HACS complète pour envoyer et recevoir des messages via [SimpleX Chat](https://simplex.chat/) depuis Home Assistant.

SimpleX est une messagerie privée par conception (aucun identifiant utilisateur, chiffrement de bout en bout, métadonnées minimales). Cette intégration permet d'utiliser SimpleX comme canal de notification et de messagerie sécurisé pour votre maison connectée.

> 🇬🇧 **English version** : [README.md](README.md)

---

## Fonctionnalités

- **Auto-découverte** — les contacts et groupes du CLI sont découverts automatiquement ; plus besoin de coller un lien d'invitation à usage unique pour chaque contact
- **Notifications natives** — une entité `notify.*` par contact ou groupe, créée dès que le bot les connaît
- **Messages entrants** — événement `simplex_message_received` + capteur
- **Suivi des connexions en direct** — un contact accepté pendant que Home Assistant tourne apparaît immédiatement, sans redémarrage
- **Entités par contact** — dernier message, compteur de non-lus et connectivité, sur un appareil par contact/groupe
- **Envoi de fichiers et médias** — `simplex.send_file`, plus le point d'entrée d'upload tablette
- **État de connexion et erreurs** — `binary_sensor` WebSocket + capteur de dernière erreur CLI
- **Services** — envoyer un message, envoyer un fichier, créer une invitation, accepter un lien, lister contacts/groupes, rafraîchir, marquer comme lu
- **Outil LLM / Assist** — `send_simplex_message` pour les agents vocaux et IA
- **Reconnexion automatique** avec backoff exponentiel
- **Traductions** EN / FR
- Prêt pour **HACS** et le **Marketplace** Home Assistant

---

## Docker / Home Assistant en conteneur

Si Home Assistant tourne en Docker, vous **devez** faire tourner en parallèle un démon SimpleX Chat en mode WebSocket.

→ Guide complet : **[DOCKER.md](DOCKER.md)** (exemples compose, réseau, dépannage).

Le démon de référence est **[MX10-AC2N/simplex-bridge](https://github.com/MX10-AC2N/simplex-bridge)**, dont le contrat WebSocket est validé par une suite de tests dédiée (T01–T13).

## Prérequis

1. **SimpleX Chat CLI** en mode WebSocket :

```bash
simplex-chat -p 5225
```

Quand Home Assistant tourne en Docker, n'utilisez **pas** `127.0.0.1` depuis le conteneur HA
sauf si les deux conteneurs partagent le namespace réseau de l'hôte.
Voir le guide dédié : **[DOCKER.md](DOCKER.md)**.

2. Home Assistant **2025.8+** (2026.x recommandé).

---

## Installation

### Via HACS (recommandé)

1. HACS → Intégrations → ⋮ → **Dépôts personnalisés**
2. URL : `https://github.com/MX10-AC2N/SimpleX-Chat_HA`
3. Catégorie : **Intégration**
4. Télécharger → Redémarrer Home Assistant
5. **Paramètres → Appareils et services → Ajouter une intégration → SimpleX Chat**
6. Saisir l'URL du WebSocket (par défaut : `ws://127.0.0.1:5225`)

### Installation manuelle

```bash
cd /config/custom_components
# copiez le dossier simplex/ de ce dépôt
```

Redémarrez Home Assistant, puis ajoutez l'intégration depuis l'interface.

---

## Configurer les contacts

### Automatique (recommandé)

Rien à faire. Au démarrage, l'intégration interroge le CLI pour ses contacts
(`/_contacts`) et ses groupes (`/_groups`), puis tient la liste à jour via les
événements de connexion (`contactConnected`, `contactSndReady`,
`contactUpdated`, `userJoinedGroup`, …).

Chaque chat découvert obtient :

- une entité `notify.simplex_chat_<alias>`,
- un appareil avec les entités *Last message*, *Unread messages* et *Connected*,
- une ligne dans la carte dashboard *SimpleX Conversations*.

L'alias est dérivé du nom d'affichage (`Éric` → `eric`). Pour en choisir un
autre : **Paramètres → Appareils et services → SimpleX Chat → Configurer →
Renommer un contact / groupe**.

> L'auto-découverte suppose que le bridge accepte automatiquement les
> demandes de contact (`SIMPLEX_AUTO_ACCEPT=true`). Voir [DOCKER.md](DOCKER.md).

### Manuel

1. **Paramètres → Appareils et services → SimpleX Chat → Configurer**
2. Choisir **Ajouter un contact / groupe**
3. Saisir un alias convivial (ex. `Alice`, `Famille`)
4. Coller un lien d'invitation SimpleX (1:1 ou groupe)
5. Une entité `notify.simplex_chat_alice` (ou similaire) est créée automatiquement

Les contacts manuels et découverts peuvent coexister ; un alias configuré
manuellement l'emporte toujours sur l'alias automatique.

---

## Utilisation

### Notifications

```yaml
action: notify.send_message
data:
  message: "Dîner prêt !"
  title: "Maison"
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

### Service dédié

```yaml
action: simplex.send_message
data:
  alias: Alice
  message: "La porte d'entrée a été ouverte"
  title: "Sécurité"
```

Par référence de chat plutôt que par alias :

```yaml
action: simplex.send_message
data:
  chat_ref: "@3"
  message: "La porte d'entrée a été ouverte"
```

### Envoyer un fichier

```yaml
action: simplex.send_file
data:
  alias: Alice
  file_path: /config/simplex_outbox/clip.ogg
```

Le chemin doit être lisible par le processus `simplex-chat` — utilisez un
volume partagé avec le conteneur du bridge (voir [DOCKER.md](DOCKER.md)).

### Créer une invitation

```yaml
action: simplex.create_invite
```

La réponse contient `invite_link`.

### Accepter une invitation

```yaml
action: simplex.accept_invite
data:
  invite_link: "https://simplex.chat/invitation#..."
  alias: Bob
```

### Découvrir / rafraîchir

```yaml
action: simplex.refresh_contacts
```

Force une relecture des listes de contacts et de groupes du CLI.

### Marquer comme lu

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

| Clé            | Description                                       |
|----------------|---------------------------------------------------|
| `alias`        | Alias du chat (configuré ou dérivé)               |
| `chat_ref`     | `@123` ou `#456`                                  |
| `display_name` | Nom d'affichage du contact / groupe               |
| `type`         | `contact` ou `group`                              |
| `text`         | Corps du message                                  |
| `direction`    | `incoming` / `outgoing`                           |
| `status`       | `sent` / `delivered` / `read` / `sending`         |
| `item_id`      | ID interne SimpleX                                |
| `timestamp`    | Horodatage du message                             |
| `edited`       | Message modifié                                   |
| `file`         | Métadonnées de la pièce jointe (nom, taille, URL) |

Autres événements : `simplex_targets_updated` (un chat découvert ou retiré) et
`simplex_error` (le CLI a répondu avec une `chatCmdError`).

### Capteurs

Les entités vivent sur deux types d'appareils :

- l'appareil **Simplex Chat** — l'intégration elle-même
  (`sensor.simplex_chat_*`, `binary_sensor.simplex_chat_connection`) ;
- un appareil **par contact/groupe**, nommé d'après lui
  (`sensor.alice_last_message`, `binary_sensor.alice_connected`, …).

| Entité | Description |
|--------|-------------|
| `binary_sensor.simplex_chat_connection` | État WebSocket (+ dernière erreur CLI en attributs) |
| `sensor.simplex_chat_last_message` | Dernier message **reçu**, avec expéditeur/horodatage |
| `sensor.simplex_chat_known_contacts` | Nombre de chats connus (configurés + découverts) |
| `sensor.simplex_chat_configured_contacts` | Nombre de chats configurés à la main |
| `sensor.simplex_chat_discovered_contacts` | Nombre de chats auto-découverts |
| `sensor.simplex_chat_unread_messages` | Total des messages non lus |
| `sensor.simplex_chat_last_error` | Dernière erreur CLI (diagnostic) |
| `sensor.<contact>_last_message` | Dernier message d'un contact/groupe |
| `sensor.<contact>_unread_messages` | Compteur de non-lus d'un contact/groupe |
| `binary_sensor.<contact>_connected` | Connectivité d'un contact/groupe |

> **Entity ids et la mise à niveau 2.0** — l'appareil de l'intégration
> s'appelait *SimpleX Chat*, que Home Assistant transforme en
> `simple_x_chat_*`. Les ids documentés ci-dessus (`simplex_chat_*`) ont
> toujours été ceux du README et des tableaux de bord : avant la 2.0, les
> tableaux de bord fournis ne pouvaient donc pas trouver leurs entités. La
> version 2.0 renomme l'appareil et migre automatiquement les entity ids
> des installations existantes.

### Assist / LLM

L'outil `send_simplex_message` est enregistré automatiquement. Exemple :

> « Envoie un message SimpleX à Alice : je serai là dans 10 minutes »

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

Le client WebSocket gère la reconnexion automatique, la corrélation des réponses RPC (`corrId`), la distribution des événements et l'obfuscation des liens sensibles dans les logs.

Le **registre des cibles** (`targets.py`) fusionne les chats configurés manuellement
et les chats auto-découverts en une vue unique : toutes les consumers —
entités notify, capteurs, outil LLM, cartes du dashboard — voient la même
liste. La découverte reste en mémoire : elle ne réécrit jamais l'entrée de
configuration.

---

## Dépannage

Activer les logs de debug :

```yaml
logger:
  default: info
  logs:
    custom_components.simplex: debug
```

Checklist :

1. `simplex-chat -p 5225` tourne-t-il ?
2. `binary_sensor.simplex_chat_connection` est-il `on` ?
3. Des entrées `chatCmdError` dans les logs ? (`sensor.simplex_chat_last_error`)
4. Le lien d'invitation est-il encore valide ?

---

## Feuille de route

- [x] Adresse longue durée
- [x] Envoi de fichiers / images
- [x] Auto-découverte des contacts et groupes
- [x] Capteurs et binary sensors par contact
- [x] Cartes Lovelace
- [ ] Support multi-profils
- [ ] Recherche dans les conversations

---

## Tests

Le dépôt embarque une suite de tests sans dépendance qui rejoue des frames
**réelles** du CLI SimpleX Chat v7.1.4.0 à travers le mapping de
l'intégration :

```bash
python3 -m unittest discover -s tests -v
```

---

## Licence

MIT

SimpleX Chat est un projet de [SimpleX Chat Ltd](https://simplex.chat). Cette intégration est un projet communautaire indépendant, non affilié officiellement.
