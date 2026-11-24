# Docker — SimpleX Bridge + Home Assistant (réseau host)

Ce guide cible la configuration où **Home Assistant et `simplex-bridge` tournent sur le même hôte Linux et utilisent tous les deux `network_mode: host`**.

L'intégration Home Assistant est un client WebSocket : elle ne lance pas le binaire SimpleX. Le dépôt `MX10-AC2N/simplex-bridge` démarre `simplex-chat -p 5225`, dont l'API WebSocket écoute sur `127.0.0.1:5225`.

## Architecture retenue

```text
Home Assistant (conteneur, network_mode: host)
  custom_components/simplex
          |
          | ws://127.0.0.1:5225
          v
SimpleX Bridge (conteneur, network_mode: host)
  simplex-chat -p 5225
  écoute sur 127.0.0.1:5225
```

Les deux conteneurs partagent le namespace réseau de l'hôte. **Dans cette configuration, `127.0.0.1` est bien la bonne adresse depuis Home Assistant.** Il ne faut pas ajouter de port mapping Docker ni activer `SIMPLEX_SOCAT_PORT`.

> Cette configuration suppose Docker Engine sous Linux. Le mode `host` de Docker Desktop/macOS/Windows ne partage pas le loopback de la même manière.

## Compose de référence

Adapte les volumes de configuration Home Assistant à ton installation. Les volumes `simplex-outbox` et `simplex-inbox` sont partagés entre les deux conteneurs ; le volume contenant la base SimpleX et les clés (`simplex-data`) reste privé au bridge.

```yaml
services:
  homeassistant:
    image: ghcr.io/home-assistant/home-assistant:stable
    container_name: homeassistant
    network_mode: host
    volumes:
      - ./config:/config
      - /etc/localtime:/etc/localtime:ro
      - simplex-outbox:/config/simplex_outbox
      - simplex-inbox:/config/simplex_inbox/received_files:ro
    restart: unless-stopped

  simplex-bridge:
    image: ghcr.io/mx10-ac2n/simplex-bridge:latest
    container_name: simplex-bridge
    network_mode: host
    volumes:
      - simplex-data:/data
      - simplex-outbox:/config/simplex_outbox
      - simplex-inbox:/data/received_files
    environment:
      SIMPLEX_DISPLAY_NAME: "Home Assistant"
      SIMPLEX_AUTO_ACCEPT: "true"
      SIMPLEX_FILES_ENABLED: "true"
      SIMPLEX_FILES_DIR: "/data/received_files"
      SIMPLEX_MARK_READ: "false"   # voir la section "Messages lus / non lus"
      SIMPLEX_TOR: "false"
      SIMPLEX_STARTUP_TIMEOUT: "30"
      PUID: "99"
      PGID: "100"
      TZ: "Europe/Paris"
    restart: unless-stopped

volumes:
  simplex-data:
  simplex-outbox:
  simplex-inbox:
```

**Important :** si Home Assistant existe déjà dans ton compose, ne remplace pas ses autres options (`devices`, `privileged`, montages, etc.). Ajoute seulement `network_mode: host` si ce n'est pas déjà présent, les deux volumes partagés et le service bridge. En mode host, supprime `ports:` du service Home Assistant : les ports sont directement ceux de l'hôte.

### Si les deux services sont dans des projets Compose séparés

Le bridge doit créer les volumes partagés `simplex-inbox` et `simplex-outbox` avec ces noms Docker explicites. Dans le compose Home Assistant, déclare-les en volumes externes :

```yaml
volumes:
  simplex-outbox:
    external: true
    name: simplex-outbox
  simplex-inbox:
    external: true
    name: simplex-inbox
```

Ne monte pas `simplex-data` dans Home Assistant : ce volume contient la base et les clés de l'identité SimpleX.

## Configuration de l'intégration

Dans **Paramètres → Appareils et services → Ajouter une intégration → SimpleX Chat**, utiliser :

```text
ws://127.0.0.1:5225
```

C'est aussi la valeur par défaut de l'intégration (`DEFAULT_WS_URL`). Si l'intégration est déjà configurée avec cette URL, aucune modification de configuration n'est nécessaire.

Pour les dossiers dans les options de l'intégration :

- Dossier de dépôt : `/config/simplex_outbox`
- Dossier de réception : `/config/simplex_inbox/received_files`

Le dossier de réception est monté en lecture seule dans Home Assistant. Le bridge écrit les fichiers reçus dans le volume `simplex-inbox` via `SIMPLEX_FILES_DIR`.

## Messages lus / non lus

`SIMPLEX_MARK_READ` contrôle qui marque les messages comme lus.

| Valeur | Effet |
|---|---|
| `false` (recommandé) | Le CLI ne marque rien. Les compteurs de non-lus de l'intégration (`sensor.simplex_chat_unread_messages`, `sensor.<contact>_unread_messages`) et les badges de la carte *conversations* fonctionnent. C'est l'intégration (la carte de discussion, son bouton « marquer comme lu ») qui gère l'état lu/non-lu. |
| `true` | Le CLI ajoute l'option `-r` et marque **chaque** message reçu comme lu, immédiatement. Les compteurs de non-lus restent alors bloqués à 0 et les badges n'apparaissent jamais. Choisis cette valeur seulement si un autre client (la tablette, ton téléphone) consomme les messages et que tu ne veux pas les voir arriver comme « non lus » dans SimpleX Chat. |

Le compose de référence utilise `SIMPLEX_MARK_READ: "false"`.

## Auto-découverte des contacts et des groupes

L'intégration interroge le démon au démarrage (`/_contacts` et `/_groups`) et
se met à jour ensuite sur les événements de connexion (`contactConnected`,
`contactSndReady`, `contactUpdated`, `userJoinedGroup`, …).

Conséquence directe : **plus besoin de coller un lien d'invitation par
contact**. Dès qu'un contact accepte la connexion au bot, il apparaît dans
Home Assistant (entités `notify.*`, capteurs, cartes du dashboard) sans
redémarrage.

`SIMPLEX_AUTO_ACCEPT=true` côté bridge est ce qui rend ça possible : le bot
accepte automatiquement les demandes de contact, et l'intégration les
découvre immédiatement.

Si tu préfères garder la liste des contacts strictement sous contrôle,
désactive l'auto-découverte dans les options de l'intégration
(*Paramètres → Appareils et services → SimpleX Chat → Configurer →
Paramètres → Auto-découverte*). Les contacts restent alors à declaring
manuellement via *Ajouter un contact*.

Alias : un contact découvert reçoit automatiquement un alias dérivé de son
nom d'affichage (`Éric` → `eric`). Tu peux le personnaliser via
*Renommer un contact* dans les options : l'alias devient alors la cible des
services `simplex.send_message` / `simplex.send_file` et le nom des
entités `notify.*` correspondantes.

## Démarrage et vérifications

Depuis le dossier du compose :

```bash
docker compose pull simplex-bridge
docker compose up -d simplex-bridge
docker compose logs -f simplex-bridge
```

Vérifier que le bridge écoute sur le loopback de l'hôte :

```bash
ss -ltnp '( sport = :5225 )'
```

Vérifier depuis l'hôte que le WebSocket répond :

```bash
python3 - <<'PY'
import asyncio, json
import websockets

async def main():
    async with websockets.connect('ws://127.0.0.1:5225', open_timeout=5) as ws:
        await ws.send(json.dumps({'corrId': 'ha-check', 'cmd': '/user'}))
        print(await asyncio.wait_for(ws.recv(), timeout=10))

asyncio.run(main())
PY
```

Puis vérifier dans Home Assistant que `binary_sensor.simplex_chat_connection` passe à l'état connecté.

## Sécurité et conflits de ports

- L'API WebSocket SimpleX ne fournit pas d'authentification intégrée. Ne pas la publier sur Internet.
- Avec les deux conteneurs en `host`, ne pas définir `SIMPLEX_SOCAT_PORT` : le proxy exposerait une API non authentifiée sur une interface réseau.
- Le port TCP `5225` doit être libre sur l'hôte avant le démarrage du bridge. Ne lance pas simultanément un autre `simplex-chat -p 5225`.
- Les clés et la base SimpleX sont dans `simplex-data` : sauvegarder ce volume régulièrement et ne pas le monter dans Home Assistant.

## Dépannage

| Symptôme | Vérification |
|---|---|
| Connexion refusée sur `127.0.0.1:5225` | `docker compose ps` puis `docker compose logs simplex-bridge` |
| Le bridge refuse de démarrer | Vérifier qu'aucun autre processus n'occupe le port 5225 avec `ss -ltnp '( sport = :5225 )'` |
| HA et bridge sont tous deux en host mais ne se voient pas | Vérifier qu'ils tournent sur le même hôte Linux et que le bridge écoute sur `127.0.0.1:5225` |
| Les pièces jointes reçues n'apparaissent pas | Vérifier `SIMPLEX_FILES_DIR=/data/received_files` et le volume `simplex-inbox` partagé |
| Les clips ne partent pas | Vérifier que `simplex-outbox` est monté au même chemin `/config/simplex_outbox` dans les deux conteneurs |

## Autres topologies

Si Home Assistant ou le bridge n'utilise pas le réseau host, `127.0.0.1` ne désigne plus nécessairement le même namespace réseau. Il faut alors concevoir une exposition réseau distincte et sécurisée. Ne pas réutiliser aveuglément cette configuration host.
