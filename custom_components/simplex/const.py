"""Constants for the SimpleX Chat integration."""

from homeassistant.const import Platform

DOMAIN = "simplex"

CONF_WS_URL = "ws_url"
CONF_TARGETS = "targets"  # dict: alias -> {"chat_ref": "@id|#id", "name": "...", "type": "contact|group"}
CONF_OUTBOX_DIR = "outbox_dir"  # dossier partagé avec le conteneur simplex-ws (clips audio/vidéo)
CONF_INBOX_DIR = "inbox_dir"  # dossier (lecture seule) où le CLI dépose les fichiers REÇUS
CONF_AUTO_ACCEPT_FILES = "auto_accept_files"
DEFAULT_WS_URL = "ws://127.0.0.1:5225"
DEFAULT_OUTBOX_DIR = "/config/simplex_outbox"
# Doit correspondre au sous-dossier où ton fork simplex-bridge écrit les
# fichiers reçus (flag CLI --files-folder) — voir DOCKER.md. On ne peut pas
# déduire ce chemin automatiquement : il dépend de la version/configuration
# du CLI dans le bridge.
DEFAULT_INBOX_DIR = "/config/simplex_inbox/received_files"
DEFAULT_AUTO_ACCEPT_FILES = True

# Taille max d'un clip envoyé depuis la tablette (octets) — garde-fou upload
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 Mo

# Extensions autorisées selon le type de clip
UPLOAD_EXTENSIONS = {
    "audio": ".ogg",
    "video": ".webm",
}

PLATFORMS: list[Platform] = [
    Platform.NOTIFY,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]

# Events
EVENT_MESSAGE_RECEIVED = f"{DOMAIN}_message_received"
EVENT_CONNECTION_CHANGED = f"{DOMAIN}_connection_changed"

# Services
SERVICE_SEND_MESSAGE = "send_message"
SERVICE_SEND_FILE = "send_file"
SERVICE_ACCEPT_INVITE = "accept_invite"
SERVICE_CREATE_INVITE = "create_invite"
SERVICE_LIST_CONTACTS = "list_contacts"

# HTTP upload view (tablette → HA) and read-only media view (fichiers reçus)
UPLOAD_URL_PATH = "/api/simplex/upload"
MEDIA_URL_PATH = "/api/simplex/media"

EVENT_FILE_RECEIVED = f"{DOMAIN}_file_received"

# Errors
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_INVITE_FAILED = "invite_failed"
ERROR_ALIAS_EXISTS = "alias_exists"
ERROR_INVALID_LINK = "invite_invalid"
ERROR_TIMEOUT = "invite_timeout"
ERROR_WS_NOT_CONNECTED = "ws_not_connected"
ERROR_FILE_TOO_LARGE = "file_too_large"
ERROR_UNKNOWN_ALIAS = "unknown_alias"