# SimpleX Chat for Home Assistant

Intégration HACS complète pour envoyer et recevoir des messages via [SimpleX Chat](https://simplex.chat/) depuis Home Assistant.

SimpleX est un messager privé par conception (pas d’identifiants utilisateurs, E2E, pas de métadonnées). Cette intégration permet d’utiliser SimpleX comme canal de notification et de communication sécurisé pour votre maison.

---

## Fonctionnalités

- **Notifications natives** — une entité `notify.*` par contact ou groupe
- **Réception de messages** — événement `simplex_message_received` + capteur
- **État de connexion** — `binary_sensor` WebSocket
- **Services** — envoyer, créer une invitation, accepter un lien, lister les contacts
- **Outil LLM / Assist** — `send_simplex_message` pour la voix et les agents
- **Reconnexion automatique** avec backoff exponentiel
- **Traductions** FR / EN
- Prêt pour **HACS** et le **Marketplace** Home Assistant

---

## Prérequis

1. **SimpleX Chat CLI** en mode WebSocket :

```bash
simplex-chat -p 5225
```

Exemple Docker minimal :

```bash
docker run -d --name simplex-ws \
  -p 5225:5225 \
  -v simplex-data:/home/user/.local/share/simplex \
  --restart unless-stopped \
  <image-simplex-ws>
```

2. Home Assistant **2025.8+** (recommandé 2026.x).

---

## Installation

### Via HACS (recommandé)

1. HACS → Intégrations → ⋮ → **Repositories personnalisés**
2. URL : `https://github.com/MX10-AC2N/SimpleX-Chat_HA`
3. Catégorie : **Integration**
4. Télécharger → Redémarrer Home Assistant
5. **Paramètres → Appareils & services → Ajouter l’intégration → SimpleX Chat**
6. Entrer l’URL WebSocket (défaut : `ws://127.0.0.1:5225`)

### Installation manuelle

```bash
cd /config/custom_components
# copier le dossier simplex/ depuis ce dépôt
```

Redémarrer Home Assistant, puis ajouter l’intégration via l’UI.

---

## Configuration des contacts

1. **Paramètres → Appareils & services → SimpleX Chat → Configurer**
2. Choisir **Ajouter un contact / groupe**
3. Donner un alias (ex. `Alice`, `Famille`)
4. Coller le lien d’invitation SimpleX (1:1 ou groupe)
5. Une entité `notify.simplex_alice` (ou similaire) est créée automatiquement

Vous pouvez aussi supprimer des contacts ou les lister depuis le même menu.

---

## Utilisation

### Notifications

```yaml
action: notify.send_message
data:
  message: "Le dîner est prêt !"
  title: "Maison"
target:
  entity_id: notify.simplex_alice
```

Plusieurs destinataires :

```yaml
target:
  entity_id:
    - notify.simplex_alice
    - notify.simplex_famille
```

### Service dédié

```yaml
action: simplex.send_message
data:
  alias: Alice
  message: "Porte d'entrée ouverte"
  title: "Sécurité"
```

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

### Événements reçus

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

| Clé         | Description                     |
|-------------|---------------------------------|
| `alias`     | Alias configuré (si trouvé)     |
| `chat_ref`  | `@123` ou `#456`                |
| `text`      | Contenu du message              |
| `direction` | `incoming` / `outgoing`         |
| `item_id`   | ID interne SimpleX              |

### Capteurs

| Entité | Description |
|--------|-------------|
| `binary_sensor.simplex_chat_connection` | État WebSocket |
| `sensor.simplex_chat_last_message` | Dernier message reçu |
| `sensor.simplex_chat_configured_contacts` | Nombre de contacts |

### Assist / LLM

L’outil `send_simplex_message` est enregistré automatiquement. Exemple :

> « Envoie un message SimpleX à Alice : j’arrive dans 10 minutes »

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

Le client WebSocket gère la reconnexion automatique, la corrélation des réponses RPC (`corrId`), le dispatch des événements et la redaction des liens sensibles dans les logs.

---

## Dépannage

Activer le debug :

```yaml
logger:
  default: info
  logs:
    custom_components.simplex: debug
```

Vérifications :

1. `simplex-chat -p 5225` tourne-t-il ?
2. `binary_sensor.simplex_chat_connection` est-il `on` ?
3. Y a-t-il des erreurs `chatCmdError` dans les logs ?
4. Le lien d’invitation est-il encore valide ?

---

## Roadmap

- [ ] Adresse utilisateur longue durée
- [ ] Envoi de fichiers / images
- [ ] Multi-profils SimpleX
- [ ] Carte Lovelace
- [ ] Découverte des contacts déjà présents dans le CLI

---

## Licence

MIT

SimpleX Chat est un projet de [SimpleX Chat Ltd](https://simplex.chat). Cette intégration est un projet communautaire indépendant, non affilié officiellement.
