"""Binary sensors for SimpleX Chat.

  * `binary_sensor.simplex_chat_connection` — the state of the WebSocket
    connection to the SimpleX CLI (with the last CLI error attached);
  * one `binary_sensor` per contact/group — whether that contact is
    currently connected.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    EVENT_ERROR,
    EVENT_TARGETS_UPDATED,
)
from .entity_base import contact_device_info, contact_unique_id, main_device_info
from .targets import SimplexTarget, registry_for
from .websocket_client import SimplexWsClient

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SimpleX binary sensors."""
    async_add_entities([SimplexConnectionSensor(hass, config_entry)])

    registry = registry_for(hass, config_entry.entry_id)
    created: set[str] = set()

    def _add_target(target: SimplexTarget) -> None:
        if target.chat_ref in created:
            return
        created.add(target.chat_ref)
        async_add_entities(
            [SimplexContactConnectedSensor(hass, config_entry, target)]
        )

    if registry is not None:
        for target in registry.targets:
            _add_target(target)

    @callback
    def _handle_targets_updated(event) -> None:
        if event.data.get("entry_id") != config_entry.entry_id:
            return
        current = registry_for(hass, config_entry.entry_id)
        if current is None:
            return
        for target in current.targets:
            _add_target(target)

    hass.bus.async_listen(EVENT_TARGETS_UPDATED, _handle_targets_updated)


class SimplexConnectionSensor(BinarySensorEntity):
    """Represents the WebSocket connection state to the SimpleX CLI."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_has_entity_name = True
    _attr_name = "Connection"
    _attr_should_poll = False
    _attr_entity_category = "diagnostic"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.hass = hass
        self.config_entry = config_entry
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_connection"
        self._attr_device_info = main_device_info(config_entry)
        self._attr_extra_state_attributes: dict[str, Any] = {}

    def _client(self) -> SimplexWsClient | None:
        data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        return data.get("client") if data else None

    @property
    def is_on(self) -> bool:
        client = self._client()
        return bool(client and client.connected)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        client = self._client()
        if client is None:
            return {}
        last_error = client.last_error
        if not last_error:
            return {}
        return {
            "last_error": last_error.get("message"),
            "last_error_reason": last_error.get("reason"),
            "last_error_command": last_error.get("command"),
            "last_error_timestamp": last_error.get("timestamp"),
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        client = self._client()
        if client is not None:
            self.async_on_remove(
                client.add_connection_listener(
                    lambda _state: self.async_write_ha_state()
                )
            )

        @callback
        def _handle_error(event) -> None:
            if event.data.get("entry_id") != self.config_entry.entry_id:
                return
            self.async_write_ha_state()

        self.async_on_remove(self.hass.bus.async_listen(EVENT_ERROR, _handle_error))


class SimplexContactConnectedSensor(BinarySensorEntity):
    """Whether a given contact/group is connected."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_has_entity_name = True
    _attr_name = "Connected"
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        target: SimplexTarget,
    ) -> None:
        self.hass = hass
        self.config_entry = config_entry
        self._target = target
        self._attr_unique_id = contact_unique_id(config_entry, target, "connected")
        self._attr_device_info = contact_device_info(config_entry, target)

    @property
    def is_on(self) -> bool:
        registry = registry_for(self.hass, self.config_entry.entry_id)
        target = registry.by_ref(self._target.chat_ref) if registry else None
        return bool(target.connected) if target else False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _handle_targets(event) -> None:
            if event.data.get("entry_id") != self.config_entry.entry_id:
                return
            self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_TARGETS_UPDATED, _handle_targets)
        )
