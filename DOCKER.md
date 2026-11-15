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

---

> ⚠️ **Correctif important (v2)** : `libre7/simplex-bridge` fait écouter son démon **uniquement sur `127.0.0.1` à l'intérieur de son propre conteneur**. Sur un bridge network Docker classique, `ws://simplex-ws:5225` n'est donc **pas joignable** depuis le conteneur `homeassistant`, même sur le même réseau — ce n'est pas un problème de DNS. Le fichier [`docker-compose.yml`](docker-compose.yml) à la racine du dépôt documente les deux correctifs possibles (host networking, ou un sidecar `socat` qui republie le port). Utilise ce fichier plutôt que les extraits isolés ci-dessous si tu démarres de zéro.

> ⚠️ **Correctif important (v2)** : `libre7/simplex-bridge` fait écouter son démon **uniquement sur `127.0.0.1` à l'intérieur de son propre conteneur**. Sur un bridge network Docker classique, `ws://simplex-ws:5225` n'est donc **pas joignable** depuis le conteneur `homeassistant`, même sur le même réseau — ce n'est pas un problème de DNS. Le fichier [`docker-compose.yml`](docker-compose.yml) à la racine du dépôt documente les deux correctifs possibles (host networking, ou un sidecar `socat` qui republie le port). Utilise ce fichier plutôt que les extraits isolés ci-dessous si tu démarres de zéro.

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

## Security notes

- The WebSocket API has **no authentication**. Treat it as a local, trusted channel.
- Prefer a private Docker network; avoid publishing `5225` to `0.0.0.0`.
- The SimpleX identity (keys + DB) lives in the `simplex_data` volume — back it up if you care about keeping the same contacts.

---

## Related

- Main README: [README.md](README.md) · [README_fr.md](README_fr.md)
- Integration repo: https://github.com/MX10-AC2N/SimpleX-Chat_HA
- SimpleX Chat: https://simplex.chat
