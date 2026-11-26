"""Install the bundled Lovelace dashboards from the integration.

Home Assistant does not expose its dashboards collection to other
integrations, so creating a dashboard goes through the same admin-only
websocket command the UI uses (`lovelace/dashboards/create`), invoked
in-process. Writing the content then uses the public `LovelaceStorage`
object. If either internal moves, `DashboardInstallError` is raised and the
caller falls back to handing the YAML to the user.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import yaml

_LOGGER = logging.getLogger(__name__)

DASHBOARDS_DIR = Path(__file__).parent / "dashboards"
CARDS_DIR = Path(__file__).parent / "cards"
CARDS_URL = "/simplex_cards"
_FLAG = "cards_registered"

# stem -> (title, icon)
CATALOG: dict[str, tuple[str, str]] = {
    "simplex_auto_fr": ("SimpleX (auto, FR)", "mdi:message-lock"),
    "simplex_auto_en": ("SimpleX (auto, EN)", "mdi:message-lock"),
    "simplex_messenger_fr": ("SimpleX Messenger (FR)", "mdi:message-lock"),
    "simplex_messenger_en": ("SimpleX Messenger (EN)", "mdi:message-lock"),
    "simplex_fr": ("SimpleX Chat (FR)", "mdi:message-text"),
    "simplex_en": ("SimpleX Chat (EN)", "mdi:message-text"),
    "simplex_mushroom_fr": ("SimpleX Mushroom (FR)", "mdi:mushroom"),
    "simplex_mushroom_en": ("SimpleX Mushroom (EN)", "mdi:mushroom"),
    "simplex_android_home_fr": ("SimpleX Android accueil (FR)", "mdi:cellphone"),
    "simplex_android_look_fr": ("SimpleX Android chat (FR)", "mdi:cellphone-message"),
    "simplex_tablet_fr": ("SimpleX Tablette interphone (FR)", "mdi:tablet"),
}

class DashboardInstallError(Exception):
    """The dashboard could not be installed (message is user-presentable)."""


def available_dashboards() -> list[str]:
    return [s for s in CATALOG if (DASHBOARDS_DIR / f"{s}.yaml").is_file()]


def default_url_path(name: str) -> str:
    return name.replace("_", "-")  # always contains a hyphen


def load_dashboard(name: str) -> dict[str, Any]:
    if name not in CATALOG:
        raise DashboardInstallError(f"Unknown dashboard '{name}'")
    path = DASHBOARDS_DIR / f"{name}.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as err:
        raise DashboardInstallError(f"Cannot read {path.name}: {err}") from err
    if not isinstance(data, dict) or not data.get("views"):
        raise DashboardInstallError(f"{path.name} is not a valid dashboard")
    return data


def _walk(node: Any):
    yield node
    if isinstance(node, dict):
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def rewrite_navigation(config: dict[str, Any], url_path: str) -> dict[str, Any]:
    """Point `navigate_prefix` at the installed dashboard.

    The shipped YAML says `/simplex-chat` (a bare view path), which only
    resolves inside a dashboard as `/<url_path>/simplex-chat`.
    """
    for node in _walk(config):
        if isinstance(node, dict) and isinstance(node.get("navigate_prefix"), str):
            view = node["navigate_prefix"].rstrip("/").rsplit("/", 1)[-1]
            node["navigate_prefix"] = f"/{url_path}/{view}"
    return config


def _lovelace(hass: Any) -> Any:
    try:
        from homeassistant.components.lovelace.const import LOVELACE_DATA

        key = LOVELACE_DATA
    except Exception:  # noqa: BLE001
        key = "lovelace"
    data = hass.data.get(key)
    if data is None:
        raise DashboardInstallError("The Lovelace integration is not loaded")
    return data


class _Conn:
    """Minimal ActiveConnection: an admin user and a result future."""

    class _User:
        is_admin = True
        id = "simplex"

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.user = self._User()
        self.fut: asyncio.Future = loop.create_future()
        self.refresh_token_id = None

    def send_result(self, msg_id: Any, result: Any = None) -> None:
        if not self.fut.done():
            self.fut.set_result(result)

    def send_error(self, msg_id: Any, code: str, message: str, *a: Any, **k: Any) -> None:
        if not self.fut.done():
            self.fut.set_exception(DashboardInstallError(f"{code}: {message}"))

    def send_message(self, msg: Any) -> None:  # pragma: no cover
        if not self.fut.done():
            self.fut.set_result(msg)


async def _create_dashboard(hass: Any, url_path: str, title: str, icon: str) -> None:
    handlers = hass.data.get("websocket_api") or {}
    entry = handlers.get("lovelace/dashboards/create")
    if not entry:
        raise DashboardInstallError("Home Assistant's dashboard API is unavailable")
    handler = entry[0]
    conn = _Conn(asyncio.get_running_loop())
    msg = {
        "id": 1,
        "type": "lovelace/dashboards/create",
        "url_path": url_path,
        "title": title,
        "icon": icon,
        "show_in_sidebar": True,
        "require_admin": False,
        "allow_single_word": True,
        "mode": "storage",
    }
    try:
        handler(hass, conn, msg)
        await asyncio.wait_for(conn.fut, 15)
    except DashboardInstallError:
        raise
    except Exception as err:  # noqa: BLE001
        raise DashboardInstallError(f"Dashboard creation failed: {err}") from err


async def async_install_dashboard(
    hass: Any,
    name: str,
    url_path: str | None = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Create (or, with overwrite, replace) a storage-mode dashboard."""
    loop_config = await hass.async_add_executor_job(load_dashboard, name)
    url_path = (url_path or default_url_path(name)).strip().strip("/")
    if "-" not in url_path:
        raise DashboardInstallError("url_path must contain a hyphen (-)")
    config = rewrite_navigation(loop_config, url_path)
    title, icon = CATALOG[name]

    lovelace = _lovelace(hass)
    existing = lovelace.dashboards.get(url_path)
    created = False
    if existing is not None:
        if getattr(existing, "mode", "storage") != "storage":
            raise DashboardInstallError(
                f"'{url_path}' is a YAML-mode dashboard and cannot be written"
            )
        if not overwrite:
            raise DashboardInstallError(
                f"Dashboard '{url_path}' already exists (use overwrite to replace it)"
            )
    else:
        await _create_dashboard(hass, url_path, title, icon)
        existing = lovelace.dashboards.get(url_path)
        if existing is None:
            raise DashboardInstallError("Dashboard was created but not registered")
        created = True

    await existing.async_save(config)
    return {"url_path": url_path, "created": created}


def card_files() -> list[str]:
    """Published paths of the bundled cards, e.g. simplex-chat-card/simplex-chat-card.js."""
    cards = sorted(
        f"{p.parent.name}/{p.name}" for p in CARDS_DIR.glob("simplex-*-card/simplex-*-card.js")
    )
    # The shared visual editor goes first so it is defined before any card asks for it.
    return (["simplex-card-editor.js"] if (CARDS_DIR / "simplex-card-editor.js").is_file() else []) + cards


def _version() -> str:
    try:
        return str(json.loads((Path(__file__).parent / "manifest.json").read_text())["version"])
    except (OSError, ValueError, KeyError):
        return "0"


async def async_register_cards(hass: Any, domain_data: dict[str, Any]) -> list[str]:
    """Serve the bundled cards and load them in every frontend session.

    Done by the integration itself so nothing has to be copied to /config/www
    nor declared as a Lovelace resource. The ?v= suffix busts the browser cache
    on every integration update.
    """
    if domain_data.get(_FLAG):
        return []
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARDS_URL, str(CARDS_DIR), False)]
    )
    version = _version()
    urls = [f"{CARDS_URL}/{f}?v={version}" for f in card_files()]
    for url in urls:
        add_extra_js_url(hass, url)
    domain_data[_FLAG] = True
    return urls
