"""Minimal Home Assistant stubs.

The unit tests of this repository must run on a bare Python interpreter —
no Home Assistant installation, no network access — so the handful of
Home Assistant symbols the integration touches at import time are stubbed
here.

Only *import-time* behaviour is stubbed (classes, decorators, enums). The
tests themselves exercise pure-Python logic (the chat-item mapping and the
target registry), which is exactly where the bugs that broke the
integration lived.
"""

from __future__ import annotations

import sys
import types
from enum import Enum
from typing import Any


def _module(name: str, **attrs: Any) -> types.ModuleType:
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    sys.modules[name] = value_module = mod
    parent_name, _, child = name.rpartition(".")
    if parent_name:
        parent = sys.modules.get(parent_name)
        if parent is not None:
            setattr(parent, child, value_module)
    return mod


# --------------------------------------------------------------------------
# voluptuous
# --------------------------------------------------------------------------


class _Marker:
    def __init__(self, schema: Any = None, default: Any = None, **kwargs: Any) -> None:
        self.schema = schema
        self.default = default

    def __call__(self, value: Any) -> Any:
        return value


class Required(_Marker):
    pass


class Optional(_Marker):
    pass


class Schema:
    def __init__(self, schema: Any = None, extra: Any = None, **kwargs: Any) -> None:
        self.schema = schema

    def __call__(self, data: Any) -> Any:
        return data


def _identity(*args: Any, **kwargs: Any):
    return args[0] if len(args) == 1 else args


def install() -> None:
    """Register every stub module into ``sys.modules``."""
    if "homeassistant" in sys.modules:
        return

    # ---------------- voluptuous ----------------
    _module(
        "voluptuous",
        Schema=Schema,
        Required=Required,
        Optional=Optional,
        All=_identity,
        In=_identity,
        Range=_identity,
        Coerce=_identity,
        ensure_list=lambda v: v if isinstance(v, list) else [v],
    )

    # ---------------- aiohttp ----------------
    class ClientError(Exception):
        pass

    class ClientSession:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.closed = False

    class ClientWebSocketResponse:
        closed = True

    class WSMsgType(Enum):
        TEXT = 1
        CLOSE = 2
        CLOSED = 3
        ERROR = 4
        PING = 5
        PONG = 6

    class _Web(types.ModuleType):
        class Request:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.query: dict[str, str] = {}

        class Response:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.body = b""
                self.content_type = "text/plain"
                self.status = 200

            @classmethod
            def json_response(cls, *args: Any, **kwargs: Any) -> "Response":
                return cls()

            @classmethod
            def text_response(cls, *args: Any, **kwargs: Any) -> "Response":
                return cls()

        @staticmethod
        def json_response(*args: Any, **kwargs: Any) -> "Response":
            return _Web.Response()

    _module(
        "aiohttp",
        ClientError=ClientError,
        ClientSession=ClientSession,
        ClientWebSocketResponse=ClientWebSocketResponse,
        WSMsgType=WSMsgType,
        web=_Web("aiohttp.web"),
    )

    # ---------------- homeassistant ----------------
    _module("homeassistant")

    class Platform(Enum):
        NOTIFY = "notify"
        BINARY_SENSOR = "binary_sensor"
        SENSOR = "sensor"

    _module("homeassistant.const", Platform=Platform)

    class HomeAssistant:
        def __init__(self) -> None:
            self.data: dict[str, Any] = {}
            self.bus = types.SimpleNamespace()
            self.services = types.SimpleNamespace()
            self.config_entries = types.SimpleNamespace()
            self.http = types.SimpleNamespace()
            self.loop = None

    class ServiceCall:
        def __init__(self, domain: str = "", service: str = "", data: Any = None) -> None:
            self.domain = domain
            self.service = service
            self.data = data or {}

    def callback(func):
        return func

    _module(
        "homeassistant.core",
        HomeAssistant=HomeAssistant,
        ServiceCall=ServiceCall,
        callback=callback,
        Event=type("Event", (), {"data": {}}),
    )

    class HomeAssistantError(Exception):
        pass

    class ConfigEntryNotReady(HomeAssistantError):
        pass

    class ConfigEntryAuthFailed(HomeAssistantError):
        pass

    _module(
        "homeassistant.exceptions",
        HomeAssistantError=HomeAssistantError,
        ConfigEntryNotReady=ConfigEntryNotReady,
        ConfigEntryAuthFailed=ConfigEntryAuthFailed,
    )

    class ConfigEntry:
        def __init__(self, entry_id: str = "entry", data: Any = None, options: Any = None):
            self.entry_id = entry_id
            self.data = data or {}
            self.options = options or {}
            self.title = "SimpleX Chat"

        def add_update_listener(self, listener):
            return lambda: None

        def async_on_unload(self, func):
            return func

    class OptionsFlowWithReload:
        pass

    _module(
        "homeassistant.config_entries",
        ConfigEntry=ConfigEntry,
        OptionsFlowWithReload=OptionsFlowWithReload,
        ConfigFlow=type("ConfigFlow", (), {}),
    )
    _module("homeassistant.data_entry_flow", FlowResult=dict)

    # ---------------- helpers ----------------
    _module("homeassistant.helpers")

    _module(
        "homeassistant.helpers.config_validation",
        string=str,
        boolean=bool,
        positive_int=int,
        ensure_list=lambda v: v if isinstance(v, list) else [v],
        config_entry_only_config_schema=lambda schema: schema,
    )
    _module("homeassistant.helpers.typing", ConfigType=dict)

    class DeviceEntryType(Enum):
        SERVICE = "service"

    class DeviceInfo(dict):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

    _module(
        "homeassistant.helpers.device_registry",
        DeviceEntryType=DeviceEntryType,
        DeviceInfo=DeviceInfo,
    )
    _module(
        "homeassistant.helpers.entity_platform",
        AddEntitiesCallback=type("AddEntitiesCallback", (), {}),
    )

    class Tool:
        def __init__(self) -> None:
            self.name = ""
            self.description = ""
            self.parameters: Any = None

    class API:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

    class APIInstance:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.tools = kwargs.get("tools", [])

    class ToolInput:
        def __init__(self, tool_args: Any = None, tool_name: str = "") -> None:
            self.tool_args = tool_args
            self.tool_name = tool_name

    def async_register_api(hass, api):
        return None

    _module(
        "homeassistant.helpers.llm",
        Tool=Tool,
        API=API,
        APIInstance=APIInstance,
        ToolInput=ToolInput,
        async_register_api=async_register_api,
    )

    # ---------------- components ----------------
    _module("homeassistant.components")

    class HomeAssistantView:
        url = ""
        name = ""
        requires_auth = False

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

    _module("homeassistant.components.http", HomeAssistantView=HomeAssistantView)

    def websocket_command(schema):
        def decorator(func):
            func._ws_schema = schema
            return func

        return decorator

    def async_response(func):
        func._ws_async_response = True
        return func

    class ActiveConnection:
        pass

    _module(
        "homeassistant.components.websocket_api",
        websocket_command=websocket_command,
        async_response=async_response,
        ActiveConnection=ActiveConnection,
        async_register_command=lambda hass, cmd: None,
    )

    class NotifyEntityFeature(Enum):
        TITLE = 1
        ATTACH_IMAGE = 2
        DELETE_ATTACHMENT = 4
        GROUP = 8

    class NotifyEntity:
        _attr_should_poll = True

        async def async_added_to_hass(self) -> None:
            pass

        def async_on_remove(self, func):
            return func

    _module(
        "homeassistant.components.notify",
        NotifyEntity=NotifyEntity,
        NotifyEntityFeature=NotifyEntityFeature,
    )

    class Entity:
        _attr_should_poll = True
        _attr_has_entity_name = False

        async def async_added_to_hass(self) -> None:
            pass

        def async_on_remove(self, func):
            return func

        def async_write_ha_state(self) -> None:
            pass

    _module("homeassistant.components.sensor", SensorEntity=Entity)

    class BinarySensorDeviceClass(Enum):
        CONNECTIVITY = "connectivity"

    class BinarySensorEntity(Entity):
        pass

    _module(
        "homeassistant.components.binary_sensor",
        BinarySensorEntity=BinarySensorEntity,
        BinarySensorDeviceClass=BinarySensorDeviceClass,
    )
