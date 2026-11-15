"""LLM / Assist tool for sending SimpleX messages."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm

from .const import DOMAIN
from .websocket_client import SimplexWsError

_LOGGER = logging.getLogger(__name__)


class SimplexSendMessageTool(llm.Tool):
    """Tool that lets an LLM send a message to a configured SimpleX alias."""

    def __init__(self, entry_id: str, aliases: list[str]) -> None:
        self._entry_id = entry_id
        self.name = "send_simplex_message"
        self.description = (
            "Send a private message via SimpleX Chat to a configured recipient "
            "(contact or group). Use the exact alias name that was set up in "
            "the SimpleX integration."
        )
        recipient_field: Any = vol.In(aliases) if aliases else str
        self.parameters = vol.Schema(
            {
                vol.Required(
                    "recipient",
                    description="Alias of the contact or group (as configured in the integration)",
                ): recipient_field,
                vol.Required(
                    "text", description="The message text to send"
                ): str,
            }
        )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> dict[str, Any]:
        data = self.parameters(tool_input.tool_args)
        recipient = data["recipient"].strip()
        text = data["text"].strip()
        if not recipient or not text:
            return {"success": False, "error": "recipient and text are required"}

        domain_data = hass.data[DOMAIN][self._entry_id]
        targets = domain_data["targets"]
        t = targets.get(recipient)
        if not t:
            return {
                "success": False,
                "error": f"Unknown recipient alias '{recipient}'. "
                f"Available: {', '.join(sorted(targets)) or '(none)'}",
            }

        chat_ref = t.get("chat_ref")
        if not chat_ref:
            return {
                "success": False,
                "error": f"Recipient '{recipient}' is misconfigured (missing chat_ref)",
            }

        client = domain_data["client"]
        try:
            await client.send_text(str(chat_ref), text)
            return {"success": True, "result": f"Message sent to {recipient}"}
        except SimplexWsError as exc:
            return {
                "success": False,
                "error": f"Failed to send: {exc.reason or exc.message}",
            }


class SimplexAPI(llm.API):
    """Exposes the send_simplex_message tool to Assist / LLMs."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        super().__init__(
            hass=hass,
            id=f"{DOMAIN}_{entry.entry_id}",
            name="SimpleX Chat",
        )
        self._entry_id = entry.entry_id

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        aliases = sorted(
            self.hass.data[DOMAIN][self._entry_id]["targets"].keys()
        )
        tool = SimplexSendMessageTool(self._entry_id, aliases)
        prompt = (
            "You can send private messages through SimpleX Chat using the "
            "send_simplex_message tool. Always use one of the configured "
            f"aliases: {', '.join(aliases) or '(none configured yet)'}."
        )
        return llm.APIInstance(
            api=self,
            api_prompt=prompt,
            llm_context=llm_context,
            tools=[tool],
        )


def register_llm_api(hass: HomeAssistant, entry) -> None:
    """Register the Assist/LLM API for this entry.

    `homeassistant.helpers.llm.async_register_api` has no unregister
    counterpart and raises `HomeAssistantError` if called twice with the
    same id. Since this entry's api id (`simplex_<entry_id>`) is stable
    across reloads and `SimplexAPI.async_get_api_instance` always reads
    `targets` from `hass.data` at call time, re-registering on a reload is
    unnecessary rather than wrong — we just ignore the "already
    registered" error and keep using the existing instance.
    """
    api = SimplexAPI(hass, entry)
    try:
        llm.async_register_api(hass, api)
    except HomeAssistantError:
        _LOGGER.debug(
            "SimpleX LLM API for entry %s already registered, skipping", entry.entry_id
        )