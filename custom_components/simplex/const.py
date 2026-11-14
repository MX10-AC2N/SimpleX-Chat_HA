"""Constants for the SimpleX Chat integration."""

from homeassistant.const import Platform

DOMAIN = "simplex"

CONF_WS_URL = "ws_url"
CONF_TARGETS = "targets"  # dict: alias -> {"chat_ref": "@id|#id", "name": "...", "type": "contact|group"}
DEFAULT_WS_URL = "ws://127.0.0.1:5225"

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
SERVICE_ACCEPT_INVITE = "accept_invite"
SERVICE_CREATE_INVITE = "create_invite"
SERVICE_LIST_CONTACTS = "list_contacts"

# Errors
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_INVITE_FAILED = "invite_failed"
ERROR_ALIAS_EXISTS = "alias_exists"
ERROR_INVALID_LINK = "invite_invalid"
ERROR_TIMEOUT = "invite_timeout"
ERROR_WS_NOT_CONNECTED = "ws_not_connected"