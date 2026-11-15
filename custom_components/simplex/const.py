"""Constants for the SimpleX Chat integration."""

from homeassistant.const import Platform

DOMAIN = "simplex"

CONF_WS_URL = "ws_url"
CONF_TARGETS = "targets"  # dict: alias -> {"chat_ref": "@id|#id", "name": "...", "type": "contact|group"}
CONF_OUTBOX_DIR = "outbox_dir"  # dossier partagé avec le conteneur simplex-ws (clips audio/vidéo)
DEFAULT_WS_URL = "ws://127.0.0.1:5225"
DEFAULT_OUTBOX_DIR = "/config/simplex_outbox"

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

# HTTP upload view (tablette → HA)
UPLOAD_URL_PATH = "/api/simplex/upload"

# Errors
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_INVITE_FAILED = "invite_failed"
ERROR_ALIAS_EXISTS = "alias_exists"
ERROR_INVALID_LINK = "invite_invalid"
ERROR_TIMEOUT = "invite_timeout"
ERROR_WS_NOT_CONNECTED = "ws_not_connected"
ERROR_FILE_TOO_LARGE = "file_too_large"
ERROR_UNKNOWN_ALIAS = "unknown_alias"