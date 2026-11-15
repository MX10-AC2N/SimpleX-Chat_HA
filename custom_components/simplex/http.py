"""HTTP endpoint used by the tablet Lovelace card to upload audio/video clips.

The simplex-chat CLI can only send a file it can read from its own
filesystem (`/f @contact <path>`), so this view writes the uploaded blob to
the integration's configured outbox directory — which must be a volume
shared with the container running the CLI — and then asks the
SimplexWsClient to send it.
"""

from __future__ import annotations

import logging
import secrets
import time
from pathlib import Path
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DEFAULT_OUTBOX_DIR,
    DOMAIN,
    ERROR_FILE_TOO_LARGE,
    ERROR_UNKNOWN_ALIAS,
    MAX_UPLOAD_BYTES,
    UPLOAD_EXTENSIONS,
    UPLOAD_URL_PATH,
)
from .websocket_client import SimplexWsError

_LOGGER = logging.getLogger(__name__)

_READ_CHUNK = 1024 * 1024  # 1 MiB


class SimplexUploadView(HomeAssistantView):
    """Receive a recorded audio/video clip from a tablet card and forward it to SimpleX.

    POST multipart/form-data to /api/simplex/upload with fields:
      - alias     : configured SimpleX alias to send to (required)
      - kind      : "audio" or "video" (required)
      - file      : the recorded blob (required)
      - entry_id  : optional, only needed with several SimpleX entries configured
    """

    url = UPLOAD_URL_PATH
    name = "api:simplex:upload"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        hass = self.hass
        try:
            data = await request.post()
        except Exception as exc:  # noqa: BLE001
            return web.json_response(
                {"success": False, "error": f"Invalid upload: {exc}"}, status=400
            )

        alias = str(data.get("alias", "")).strip()
        kind = str(data.get("kind", "")).strip().lower()
        entry_id = str(data.get("entry_id", "")).strip() or None
        file_field = data.get("file")

        if not alias:
            return web.json_response({"success": False, "error": "missing 'alias'"}, status=400)
        if kind not in UPLOAD_EXTENSIONS:
            return web.json_response(
                {"success": False, "error": "kind must be 'audio' or 'video'"}, status=400
            )
        if file_field is None or not hasattr(file_field, "file"):
            return web.json_response({"success": False, "error": "missing 'file'"}, status=400)

        entry_data = _find_entry_for_alias(hass, alias, entry_id)
        if entry_data is None:
            return web.json_response(
                {"success": False, "error": ERROR_UNKNOWN_ALIAS}, status=404
            )

        outbox_dir = Path(entry_data.get("outbox_dir", DEFAULT_OUTBOX_DIR))
        ext = UPLOAD_EXTENSIONS[kind]
        filename = f"{int(time.time())}_{secrets.token_hex(4)}{ext}"
        dest_path = outbox_dir / filename

        def _write() -> int:
            outbox_dir.mkdir(parents=True, exist_ok=True)
            size = 0
            with dest_path.open("wb") as fh:
                while True:
                    chunk = file_field.file.read(_READ_CHUNK)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise HomeAssistantError(ERROR_FILE_TOO_LARGE)
                    fh.write(chunk)
            return size

        try:
            size = await hass.async_add_executor_job(_write)
        except HomeAssistantError as exc:
            await hass.async_add_executor_job(lambda: dest_path.unlink(missing_ok=True))
            return web.json_response({"success": False, "error": str(exc)}, status=413)

        _LOGGER.debug(
            "SimpleX upload saved: %s (%d bytes, kind=%s, alias=%s)",
            dest_path,
            size,
            kind,
            alias,
        )

        chat_ref = entry_data["targets"][alias].get("chat_ref")
        if not chat_ref:
            return web.json_response(
                {"success": False, "error": f"Alias '{alias}' has no chat_ref"}, status=400
            )

        try:
            await entry_data["client"].send_file(chat_ref, str(dest_path))
        except SimplexWsError as exc:
            return web.json_response({"success": False, "error": str(exc)}, status=502)

        return web.json_response({"success": True, "file": filename})


def _find_entry_for_alias(
    hass: HomeAssistant, alias: str, entry_id: str | None
) -> dict[str, Any] | None:
    domain_data = {
        k: v
        for k, v in hass.data.get(DOMAIN, {}).items()
        if isinstance(v, dict) and "client" in v
    }
    if entry_id:
        data = domain_data.get(entry_id)
        if data and alias in data.get("targets", {}):
            return data
        return None
    for data in domain_data.values():
        if alias in data.get("targets", {}):
            return data
    return None
