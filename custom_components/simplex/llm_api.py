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


class SimplexSearchTool(llm.Tool):
    """Tool that lets an LLM search the message history of every chat."""

    def __init__(self, entry_id: str) -> None:
        self._entry_id = entry_id
        self.name = "search_simplex_messages"
        self.description = (
            "Search the SimpleX Chat message history across every "
            "conversation (contacts and groups). Use it to find when "
            "something was said, by whom, or in which conversation."
        )
        self.parameters = vol.Schema(
            {
                vol.Required(
                    "query",
                    description="The text to look for in the messages",
                ): str,
                vol.Optional(
                    "limit",
                    description="Maximum number of results (default 20)",
                ): vol.All(int, vol.Range(min=1, max=100)),
            }
        )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> dict[str, Any]:
        data = self.parameters(tool_input.tool_args)
        query = data["query"].strip()
        limit = data.get("limit", 20)
        if not query:
            return {"success": False, "error": "query is required"}

        domain_data = hass.data[DOMAIN][self._entry_id]
        client = domain_data["client"]
        try:
            raw_items = await client.search_items(query, limit=limit)
        except SimplexWsError as exc:
            return {"success": False, "error": f"Search failed: {exc.reason or exc.message}"}

        from . import normalize_chat_item

        targets = domain_data.get("targets", {})
        results = []
        for raw in raw_items:
            normalized = normalize_chat_item(raw, targets, domain_data.get("inbox_dir"))
            if normalized is None:
                continue
            results.append(
                {
                    "chat": normalized.get("alias") or normalized.get("display_name"),
                    "chat_ref": normalized.get("chat_ref"),
                    "from": normalized.get("sender") or normalized.get("display_name"),
                    "text": normalized.get("text"),
                    "timestamp": normalized.get("timestamp"),
                    "direction": normalized.get("direction"),
                }
            )

        return {"success": True, "count": len(results), "results": results}


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
        search_tool = SimplexSearchTool(self._entry_id)
        prompt = (
            "You can send private messages through SimpleX Chat using the "
            "send_simplex_message tool. Always use one of the configured "
            f"aliases: {', '.join(aliases) or '(none configured yet)'}. "
            "You can also look for past messages in every conversation with "
            "the search_simplex_messages tool."
        )
        return llm.APIInstance(
            api=self,
            api_prompt=prompt,
            llm_context=llm_context,
            tools=[tool, search_tool],
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