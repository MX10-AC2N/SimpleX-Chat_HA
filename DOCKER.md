# Docker setup – SimpleX Chat + Home Assistant

This guide shows how to run the **SimpleX Chat CLI in WebSocket mode** next to Home Assistant so the integration can connect.

The integration is a **client only**. It does **not** embed the `simplex-chat` binary. You need a separate process/container that exposes `ws://…:5225`.

---

## Architecture

```
┌─────────────────────┐         WebSocket          ┌──────────────────────┐
│  Home Assistant     │  ws://simplex-ws:5225      │  simplex-ws          │
│  (this integration) │ ─────────────────────────► │  simplex-chat -p 5225│
└─────────────────────┘                            └──────────────────────┘
```

## Option A – Same Docker Compose stack (recommended)

Add a `simplex-ws` service next to your existing `homeassistant` service and put both on the **same Docker network**.

### 1. Example `docker-compose.yml`

```yaml
services:
  homeassistant:
    image: ghcr.io/home-assistant/home-assistant:stable
    container_name: homeassistant
    volumes:
      - ./config:/config
      - /etc/localtime:/etc/localtime:ro
    restart: unless-stopped
    networks:
      - home
    # ports / privileged / devices as you already use them…

  simplex-ws:
    # Official-style bridge image (CLI in WS mode)
    image: libre7/simplex-bridge:latest
    container_name: simplex-ws
    restart: unless-stopped
    volumes:
      - simplex_data:/data
    environment:
      - TZ=Europe/Paris
      # Optional: display name used for the bot profile on first init
      - SIMPLEX_DISPLAY_NAME=Home Assistant
    networks:
      - home
    # Do NOT publish 5225 to the internet.
    # HA reaches it via the internal Docker DNS name "simplex-ws".

networks:
  home:

volumes:
  simplex_data:
```

> If you already have a `homeassistant` service, only add the `simplex-ws` block, the shared `networks.home`, and the volume. Attach your existing HA service to `networks: [home]`.

### 2. Start

```bash
docker compose up -d
```

### 3. First-run profile (if the image requires it)

Some images create the profile automatically. If the container exits or logs ask for interactive setup:

```bash
docker compose run --rm -it simplex-ws
# follow prompts (display name, etc.), then /quit
docker compose up -d simplex-ws
```

Check that the WebSocket is up:

```bash
docker compose logs -f simplex-ws
# you should see the process listening on 5225
```

### 4. Configure the integration in Home Assistant

1. **Settings → Devices & services → Add integration → SimpleX Chat**
2. WebSocket URL:

   ```
   ws://simplex-ws:5225
   ```

   (`simplex-ws` is the **service name** on the shared Docker network.)

3. Submit → connection should succeed.
4. **Configure** the integration → **Add a contact / group** → paste a SimpleX invite link.

---

## Option B – Host network

Useful if HA already uses `network_mode: host`.

```yaml
services:
  homeassistant:
    network_mode: host
    # …

  simplex-ws:
    image: libre7/simplex-bridge:latest
    container_name: simplex-ws
    network_mode: host
    volumes:
      - simplex_data:/data
    restart: unless-stopped

volumes:
  simplex_data:
```

In the integration, use:

```
ws://127.0.0.1:5225
```

---

## Option C – SimpleX on the host, HA in Docker

1. Install the CLI on the host:  
   https://github.com/simplex-chat/simplex-chat/blob/stable/docs/CLI.md

2. Run:

   ```bash
   simplex-chat -p 5225 -d ~/.local/share/simplex/ha-bot
   ```

3. In the integration, use the **host IP as seen from the container**:

   | HA networking | URL example |
   |---------------|-------------|
   | Bridge (default) | `ws://172.17.0.1:5225` or your LAN IP |
   | Host network | `ws://127.0.0.1:5225` |
   | Extra hosts | `ws://host.docker.internal:5225` (Docker Desktop) |

Ensure nothing blocks port 5225 between the container and the host.

---

## Alternative images

| Image | Notes |
|-------|--------|
| `libre7/simplex-bridge:latest` | Ready-made WS daemon, good default |
| Build from [jooray/simplex-ws-docker](https://github.com/jooray/simplex-ws-docker) | Dockerfile + compose example |
| Official binary on host | See [CLI docs](https://github.com/simplex-chat/simplex-chat/blob/stable/docs/CLI.md) |

Always keep **5225 internal** (Docker network or localhost). Do not expose it on the public internet.

---

## Troubleshooting

| Symptom | Check |
|---------|--------|
| `Impossible de se connecter au WebSocket` | Is `simplex-ws` running? `docker compose ps` / `docker compose logs simplex-ws` |
| `ws://127.0.0.1:5225` fails with HA in bridge mode | Use `ws://simplex-ws:5225` (same network) or the host IP |
| Container restarts in a loop | Profile not initialized → interactive first run (Option A §3) |
| Connection OK but no messages | Add a contact via invite link in the integration options |
| Permission / volume errors | Ensure the volume is writable by the container user |

Enable debug logs in Home Assistant:

```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.simplex: debug
```

---

## Volume partagé pour les clips audio/vidéo (tablette → SimpleX)

Si tu utilises la carte Lovelace `simplex-intercom-card` sur une tablette, les
clips enregistrés sont écrits par Home Assistant dans un dossier **"outbox"**
puis le CLI `simplex-chat` doit pouvoir lire ce même fichier pour l'envoyer
(`/f @contact <chemin>`). Comme HA et `simplex-ws` tournent dans deux
conteneurs différents, ce dossier doit être un **volume Docker partagé**,
monté **au même chemin absolu dans les deux conteneurs** (voir
[`docker-compose.yml`](docker-compose.yml)) :

```yaml
volumes:
  - simplex_outbox:/config/simplex_outbox   # côté homeassistant
  - simplex_outbox:/config/simplex_outbox   # côté simplex-ws, même chemin
```

Dans l'intégration : **Configurer → Paramètres** → vérifie que le
*dossier de dépôt* correspond bien à `/config/simplex_outbox` (valeur par
défaut). Si tu changes ce chemin, change-le identiquement des deux côtés
du compose.

---

## Volume en lecture seule pour les fichiers REÇUS (lecture inline dans la carte)

Pour que `simplex-chat-card` puisse lire une image/un message vocal reçu au lieu
d'afficher juste son nom, il faut que Home Assistant ait un accès **lecture
seule** au dossier où le CLI `simplex-chat` écrit les fichiers entrants.

**⚠️ Ce chemin n'est pas garanti par défaut** : le CLI n'a pas forcément de
dossier de fichiers dédié tant qu'on ne le lui indique pas explicitement. Il
faut patcher `entrypoint.sh` de ton fork `simplex-bridge` pour ajouter le flag
`--files-folder` :

```bash
# Dans simplex-bridge/entrypoint.sh, dans le tableau FLAGS :
FLAGS=(-d "$DATA_DIR/simplex" -p 5225 --files-folder "$DATA_DIR/received_files")
```

Comme `received_files` est un sous-dossier de `/data` (déjà le volume
`simplex-data`), il hérite de la correction de propriétaire faite par
l'entrypoint au premier démarrage — pas de permission à gérer en plus côté
bridge.

Monte ensuite ce même volume nommé, **en lecture seule**, dans Home Assistant :

```yaml
services:
  homeassistant:
    volumes:
      - simplex-data:/config/simplex_inbox:ro   # :ro = lecture seule

  simplex-bridge:
    volumes:
      - simplex-data:/data   # (déjà présent)
```

Comme c'est le **même volume** que la base de données (`simplex-data`), vu
depuis HA il apparaît à sa racine : les fichiers reçus sont donc sous
`/config/simplex_inbox/received_files/`, pas directement sous
`/config/simplex_inbox/`.

Dans l'intégration : **Configurer → Paramètres** → *dossier de réception*
doit donc valoir `/config/simplex_inbox/received_files` (valeur par défaut).

**Activation automatique des fichiers reçus** : l'intégration appelle une
commande d'acceptation de fichier (best-effort, voir le docstring de
`receive_file()` dans `websocket_client.py` — la syntaxe exacte de
`APIReceiveFile` n'est pas confirmée pour toutes les versions du CLI, un
fallback vers la commande historique `/fr <fileId>` est utilisé). Tu peux
désactiver ce comportement dans **Paramètres** si tu préfères accepter les
fichiers manuellement depuis l'appli SimpleX.

**Limite connue** : sans ce volume (ou si `--files-folder` n'est pas
configuré côté bridge), les pièces jointes reçues s'affichent quand même
dans la carte — juste comme un nom de fichier non cliquable, pas de
régression, juste pas de lecture inline.

## Limites connues (v2.3)

- **Scroll infini vers l'historique ancien** : implémenté depuis la v2.3. `simplex-chat-card` charge d'abord les messages les plus récents, puis récupère les pages précédentes au fur et à mesure que tu remontes dans la conversation (déclenché automatiquement en haut du fil). Côté bridge, cela utilise la commande `/_get chat <ref> before=<id> count=<limite>` (`APIGetChat`), dont la syntaxe exacte a été confirmée en lisant directement le code source Haskell du CLI **v7.1.4** (la version réellement épinglée dans `ghcr.io/mx10-ac2n/simplex-bridge` — vérifié aussi contre v7.0.2, inchangé entre les deux), et non plus devinée via des bindings tiers.
- **Liste des conversations complète** : corrigé en v2.3. La commande `/chats` (sans argument) ne renvoie que les **20 conversations les plus récemment actives** côté CLI (`LastChats (Just 20)`) — un foyer avec plus de 20 contacts perdait silencieusement les plus anciens de l'écran d'accueil / des événements. L'intégration utilise maintenant `/chats all`, confirmé par le même examen du code source (v7.1.4).
- **Réception de fichiers corrigée en v2.3** : la commande utilisée jusqu'ici (`/_receive <fileId> userApprovedRelays=on`) n'existe pas côté CLI — c'était une confusion entre le nom du champ interne Haskell/JSON (`userApprovedRelays`) et le vrai texte de commande. La vraie commande, confirmée dans le code source, est `/fr <fileId> approved_relays=on` (alias : `/freceive`). Corrigé dans `websocket_client.py::receive_file()`.
- **Coches lu/envoyé/livré** (`✓`/`✓✓`) : best-effort, basées sur `meta.itemStatus.type` quand ce champ existe. Si ton CLI ne l'expose pas (ou sous une autre forme), tous les messages sortants restent affichés comme "envoyé" (une seule coche), sans erreur.
- **Badge non-lus** sur l'écran de conversations : basé sur `chatStats.unreadCount`, confirmé présent sur chaque aperçu de conversation (champ `ChatStats.unreadCount` du code source, v7.1.4) — n'est plus du best-effort.

## Security notes

- The WebSocket API has **no authentication**. Treat it as a local, trusted channel.
- Prefer a private Docker network; avoid publishing `5225` to `0.0.0.0`.
- The SimpleX identity (keys + DB) lives in the `simplex_data` volume — back it up if you care about keeping the same contacts.

---

## Related

- Main README: [README.md](README.md) · [README_fr.md](README_fr.md)
- Integration repo: https://github.com/MX10-AC2N/SimpleX-Chat_HA
- SimpleX Chat: https://simplex.chat
