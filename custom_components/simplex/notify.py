"""Notify platform for SimpleX Chat.

One notify entity per known chat (contact or group), whether it was
configured by hand or auto-discovered — which is what makes the
`notify.simplex_*` services usable right after the integration is set up,
without pasting a one-time invitation link for every contact.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_TARGETS_UPDATED
from .entity_base import main_device_info
from .targets import SimplexTarget, registry_for
from .websocket_client import SimplexWsClient, SimplexWsError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SimpleX notify entities."""
    registry = registry_for(hass, config_entry.entry_id)
    entities: list[SimplexNotifyEntity] = []
    created: set[str] = set()

    def _add_target(target: SimplexTarget) -> None:
        # One entity per chat: never create a second one for a chat that is
        # already covered (a contact can be auto-discovered *and* later be
        # configured by hand).
        if target.chat_ref in created:
            return
        created.add(target.chat_ref)
        entities.append(
            SimplexNotifyEntity(hass, config_entry, target.chat_ref, target.alias, target.name)
        )

    if registry is not None:
        for target in registry.targets:
            _add_target(target)

    if not entities:
        # Fallback entity that can later be used once chats are known.
        entities.append(
            SimplexNotifyEntity(hass, config_entry, None, None, "SimpleX")
        )

    async_add_entities(entities)

    @callback
    def _handle_targets_updated(event) -> None:
        if event.data.get("entry_id") != config_entry.entry_id:
            return
        current = registry_for(hass, config_entry.entry_id)
        if current is None:
            return
        new_entities: list[SimplexNotifyEntity] = []
        for target in current.targets:
            if target.chat_ref in created:
                continue
            created.add(target.chat_ref)
            new_entities.append(
                SimplexNotifyEntity(
                    hass, config_entry, target.chat_ref, target.alias, target.name
                )
            )
        if new_entities:
            async_add_entities(new_entities)

    hass.bus.async_listen(EVENT_TARGETS_UPDATED, _handle_targets_updated)


class SimplexNotifyEntity(NotifyEntity):
    """A notify entity that sends messages to one SimpleX contact/group."""

    _attr_supported_features = NotifyEntityFeature.TITLE
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        chat_ref: str | None,
        alias: str | None,
        alias_name: str,
    ) -> None:
        self.hass = hass
        self.config_entry = config_entry
        self.chat_ref = chat_ref
        self.alias = alias
        self.alias_name = alias_name

        if chat_ref:
            self._attr_name = alias_name
            self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_{alias}"
        else:
            self._attr_name = "Broadcast"
            self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}"

        self._attr_device_info = main_device_info(config_entry)

    def _client(self) -> SimplexWsClient | None:
        data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        return data.get("client") if data else None

    def _targets(self) -> dict[str, dict[str, Any]]:
        data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        return (data or {}).get("targets", {})

    @property
    def available(self) -> bool:
        client = self._client()
        return client is not None and client.connected

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        client = self._client()
        if client is not None:
            self.async_on_remove(
                client.add_connection_listener(
                    lambda _connected: self.async_write_ha_state()
                )
            )

    async def async_send_message(
        self, message: str, title: str | None = None, **kwargs: Any
    ) -> None:
        client = self._client()
        if not client:
            raise HomeAssistantError("SimpleX WebSocket client not available")

        full = f"{title}: {message}" if title else message
        targets = self._targets()

        if self.chat_ref:
            try:
                await client.send_text(self.chat_ref, full)
            except SimplexWsError as err:
                raise HomeAssistantError(
                    f"Failed to send to {self.alias_name}: {err}"
                ) from err
            return

        # Broadcast mode
        if not targets:
            raise HomeAssistantError("No SimpleX contacts configured")

        failures: list[str] = []
        for alias, data in targets.items():
            chat_ref = data.get("chat_ref")
            name = data.get("name", alias)
            if not chat_ref:
                failures.append(f"{name}: no chat_ref")
                continue
            try:
                await client.send_text(chat_ref, full)
            except SimplexWsError as err:
                failures.append(f"{name}: {err}")

        if failures:
            raise HomeAssistantError(
                f"Failed for {len(failures)}/{len(targets)} contacts: "
                + "; ".join(failures)
            )
