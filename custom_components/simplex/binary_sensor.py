"""Binary sensor for SimpleX Chat connection status."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .websocket_client import SimplexWsClient


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([SimplexConnectionSensor(hass, config_entry)])


class SimplexConnectionSensor(BinarySensorEntity):
    """Represents the WebSocket connection state to the SimpleX CLI."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_has_entity_name = True
    _attr_name = "Connection"
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.hass = hass
        self.config_entry = config_entry
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_connection"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="SimpleX Chat",
            manufacturer="SimpleX Chat",
            model="Home Assistant Integration",
            entry_type=DeviceEntryType.SERVICE,
        )

    def _client(self) -> SimplexWsClient | None:
        data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        return data.get("client") if data else None

    @property
    def is_on(self) -> bool:
        client = self._client()
        return bool(client and client.connected)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        client = self._client()
        if client is not None:
            self.async_on_remove(
                client.add_connection_listener(
                    lambda _state: self.async_write_ha_state()
                )
            )