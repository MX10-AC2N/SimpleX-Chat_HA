"""Notify platform for SimpleX Chat."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_TARGETS, DOMAIN
from .websocket_client import SimplexWsClient, SimplexWsError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SimpleX notify entities."""
    targets: dict[str, Any] = config_entry.options.get(CONF_TARGETS, {})
    entities: list[SimplexNotifyEntity] = []

    for alias_id, alias_data in targets.items():
        name = alias_data.get("name", alias_id)
        entities.append(
            SimplexNotifyEntity(hass, config_entry, alias_id, name)
        )

    if not targets:
        # Fallback entity that can later be used once targets are added
        entities.append(
            SimplexNotifyEntity(hass, config_entry, None, "SimpleX")
        )

    if entities:
        async_add_entities(entities)


class SimplexNotifyEntity(NotifyEntity):
    """A notify entity that sends messages to one SimpleX contact/group."""

    _attr_supported_features = NotifyEntityFeature.TITLE
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        alias_id: str | None,
        alias_name: str,
    ) -> None:
        self.hass = hass
        self.config_entry = config_entry
        self.alias_id = alias_id
        self.alias_name = alias_name

        if alias_id:
            clean = re.sub(r"[^a-z0-9_]", "", alias_name.lower().replace(" ", "_"))
            clean = clean.strip("_") or f"alias_{alias_id}"
            self._attr_name = alias_name
            self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_{alias_id}"
        else:
            self._attr_name = "Broadcast"
            self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="SimpleX Chat",
            manufacturer="SimpleX Chat",
            model="Home Assistant Integration",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://simplex.chat",
        )

    def _client(self) -> SimplexWsClient | None:
        data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        return data.get("client") if data else None

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
        targets = self.config_entry.options.get(CONF_TARGETS, {})

        if self.alias_id:
            data = targets.get(self.alias_id, {})
            chat_ref = data.get("chat_ref")
            if not chat_ref:
                raise HomeAssistantError(
                    f"No chat_ref configured for '{self.alias_name}'"
                )
            try:
                await client.send_text(chat_ref, full)
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