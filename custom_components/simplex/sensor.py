"""Sensors for SimpleX Chat."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, EVENT_MESSAGE_RECEIVED


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        [
            SimplexLastMessageSensor(hass, config_entry),
            SimplexTargetCountSensor(hass, config_entry),
        ]
    )


class SimplexLastMessageSensor(SensorEntity):
    """Shows the text of the last received message."""

    _attr_has_entity_name = True
    _attr_name = "Last message"
    _attr_icon = "mdi:message-text"
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.hass = hass
        self.config_entry = config_entry
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_last_message"
        self._attr_native_value = None
        self._attr_extra_state_attributes: dict = {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="SimpleX Chat",
            manufacturer="SimpleX Chat",
            model="Home Assistant Integration",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _handle_event(event) -> None:
            if event.data.get("entry_id") != self.config_entry.entry_id:
                return
            if event.data.get("direction") != "incoming":
                return
            self._attr_native_value = event.data.get("text")
            self._attr_extra_state_attributes = {
                "alias": event.data.get("alias"),
                "chat_ref": event.data.get("chat_ref"),
                "item_id": event.data.get("item_id"),
            }
            self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_MESSAGE_RECEIVED, _handle_event)
        )


class SimplexTargetCountSensor(SensorEntity):
    """Number of configured contacts / groups."""

    _attr_has_entity_name = True
    _attr_name = "Configured contacts"
    _attr_icon = "mdi:account-group"
    _attr_should_poll = False
    _attr_native_unit_of_measurement = "contacts"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.hass = hass
        self.config_entry = config_entry
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_target_count"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name="SimpleX Chat",
            manufacturer="SimpleX Chat",
            model="Home Assistant Integration",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> int:
        targets = self.config_entry.options.get("targets", {})
        return len(targets)