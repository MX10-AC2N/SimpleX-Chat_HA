# SimpleX Chat for Home Assistant

**Intégration HACS moderne et complète** pour envoyer (et recevoir) des messages via [SimpleX Chat](https://simplex.chat/) depuis Home Assistant.

Basée sur le travail de [jooray/ha-simplex](https://github.com/jooray/ha-simplex), largement améliorée :

- Notifications natives (entité `notify.*` par contact / groupe)
- Réception de messages → événements HA + capteur
- Capteur de connexion WebSocket
- Services avancés (créer une invitation, lister les contacts…)
- Outil LLM / Assist (`send_simplex_message`)
- Reconnexion automatique, gestion d’erreurs robuste
- Traductions FR / EN
- Prêt pour HACS / Marketplace

---

## Prérequis

1. **SimpleX Chat CLI** en mode WebSocket :

```bash
simplex-chat -p 5225
```

Ou via Docker (recommandé) :

```bash
# Voir https://github.com/jooray/simplex-ws-docker
docker run -d --name simplex-ws \
  -p 5225:5225 \
  -v simplex-data:/data \
  jooray/simplex-ws
```

2. Home Assistant **2025.8+** (recommandé 2026.x).

---

## Installation

### Via HACS (recommandé)

1. HACS → Intégrations → ⋮ → **Repositories personnalisés**
2. URL : `https://github.com/YOUR_USERNAME/ha-simplex-chat`
3. Catégorie : **Integration**
4. Télécharger → Redémarrer Home Assistant
5. Paramètres → Appareils & services → Ajouter l’intégration → **SimpleX Chat**
6. Entrer l’URL WebSocket (défaut `ws://127.0.0.1:5225`)

### Installation manuelle

```bash
cd /config/custom_components
git clone https://github.com/YOUR_USERNAME/ha-simplex-chat.git temp
mv temp/custom_components/simplex .
rm -rf temp
```

Redémarrer Home Assistant, puis ajouter l’intégration via l’UI.

---

## Configuration des contacts

1. Aller dans **Paramètres → Appareils & services → SimpleX Chat → Configurer**
2. Choisir **Ajouter un contact / groupe**
3. Donner un alias (ex. `Alice`, `Famille`)
4. Coller le lien d’invitation SimpleX (1:1 ou groupe)
5. Une entité `notify.simplex_alice` (ou similaire) est créée automatiquement

Vous pouvez aussi supprimer des contacts ou lister ceux déjà configurés depuis le même menu.

---

## Utilisation

### Notifications (méthode recommandée)

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

### Créer une invitation depuis HA

```yaml
action: simplex.create_invite
# response_variable: invite
```

La réponse contient `invite_link`.

### Accepter une invitation via service

```yaml
action: simplex.accept_invite
data:
  invite_link: "https://simplex.chat/invitation#..."
  alias: Bob
```

### Événements reçus

Chaque message entrant déclenche l’événement `simplex_message_received` :

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

Données de l’événement :

| Clé          | Description                          |
|--------------|--------------------------------------|
| `alias`      | Alias configuré (si trouvé)          |
| `chat_ref`   | `@123` ou `#456`                     |
| `text`       | Contenu du message                   |
| `direction`  | `incoming` / `outgoing`              |
| `item_id`    | ID interne SimpleX                   |

### Capteurs

| Entité                              | Description                        |
|-------------------------------------|------------------------------------|
| `binary_sensor.simplex_chat_connection` | État de la connexion WebSocket |
| `sensor.simplex_chat_last_message`  | Dernier message reçu               |
| `sensor.simplex_chat_configured_contacts` | Nombre de contacts             |

### Assist / LLM

L’outil `send_simplex_message` est automatiquement enregistré. Vous pouvez dire :

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
                    (messages entrants, état de connexion)
```

Le client WebSocket gère :

- Reconnexion automatique avec backoff exponentiel
- Corrélation des réponses RPC (`corrId`)
- Dispatch des événements asynchrones
- Redaction des liens sensibles dans les logs

---

## Dépannage

Activer le debug :

```yaml
logger:
  default: info
  logs:
    custom_components.simplex: debug
```

Vérifications courantes :

1. `simplex-chat -p 5225` tourne-t-il ?
2. L’entité `binary_sensor.simplex_chat_connection` est-elle `on` ?
3. Les logs montrent-ils des erreurs `chatCmdError` ?
4. Le lien d’invitation est-il encore valide ?

---

## Roadmap possible

- [ ] Génération d’invitations longue durée (adresse utilisateur)
- [ ] Envoi de fichiers / images
- [ ] Support multi-profils SimpleX
- [ ] Carte Lovelace dédiée
- [ ] Découverte automatique des contacts déjà présents dans le CLI

---

## Crédits

- Inspiration et base solide : [jooray/ha-simplex](https://github.com/jooray/ha-simplex)
- SimpleX Chat : [simplex.chat](https://simplex.chat) – le messager vraiment privé

---

## Licence

MIT
