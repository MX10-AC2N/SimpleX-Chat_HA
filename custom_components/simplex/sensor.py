"""Sensors for SimpleX Chat.

Three families of entities are exposed:

  * integration-level sensors (last message, contact counters, last CLI
    error) on the "SimpleX Chat" device;
  * per-chat sensors (last message, unread counter) on one device per
    contact/group, created as soon as the chat is discovered.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    EVENT_ACTIVITY_UPDATED,
    EVENT_ERROR,
    EVENT_MESSAGE_RECEIVED,
    EVENT_TARGETS_UPDATED,
)
from .entity_base import contact_device_info, contact_unique_id, main_device_info
from .stats import summary as activity_summary
from .targets import SimplexTarget, SimplexTargetRegistry, registry_for

_LOGGER = logging.getLogger(__name__)


def _window(registry: SimplexTargetRegistry | None, days: int) -> int:
    """Number of messages received over the last ``days`` days."""
    if registry is None:
        return 0
    return activity_summary(registry.targets, days)["total_window"]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SimpleX sensors."""
    registry = registry_for(hass, config_entry.entry_id)

    entities: list[SensorEntity] = [
        SimplexLastMessageSensor(hass, config_entry),
        SimplexTargetCountSensor(hass, config_entry),
        SimplexKnownCountSensor(hass, config_entry),
        SimplexDiscoveredCountSensor(hass, config_entry),
        SimplexUnreadTotalSensor(hass, config_entry),
        SimplexMessagesTodaySensor(hass, config_entry),
        SimplexMessagesWeekSensor(hass, config_entry),
        SimplexLastErrorSensor(hass, config_entry),
    ]
    async_add_entities(entities)

    # Per-contact sensors, created as the chats are discovered.
    created: set[str] = set()

    def _add_target(target: SimplexTarget) -> None:
        if target.chat_ref in created:
            return
        created.add(target.chat_ref)
        async_add_entities(
            [
                SimplexContactLastMessageSensor(hass, config_entry, target),
                SimplexContactUnreadSensor(hass, config_entry, target),
                SimplexContactMessagesSensor(hass, config_entry, target),
            ]
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


class _RegistrySensor(SensorEntity):
    """Base class for the sensors that read their state from the registry."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    # Sensors that also depend on the activity counters listen to the
    # activity event.
    _activity_aware = False

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        self.hass = hass
        self.config_entry = config_entry
        self._attr_device_info = main_device_info(config_entry)

    @property
    def _registry(self) -> SimplexTargetRegistry | None:
        return registry_for(self.hass, self.config_entry.entry_id)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _refresh(event) -> None:
            self.async_write_ha_state()

        # The registry changed (a chat was discovered/removed): every
        # registry-backed sensor has to re-read its value.
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_TARGETS_UPDATED, _refresh)
        )

        if self._activity_aware:
            self.async_on_remove(
                self.hass.bus.async_listen(EVENT_ACTIVITY_UPDATED, _refresh)
            )


class SimplexLastMessageSensor(_RegistrySensor):
    """Shows the text of the last *received* message.

    Only incoming messages update this sensor: it is the entity automations
    watch ("a message arrived"), so an outgoing message must not trigger
    them. The per-contact sensors below expose both directions.
    """

    _attr_name = "Last message"
    _attr_icon = "mdi:message-text"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        super().__init__(hass, config_entry)
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_last_message"
        self._attr_native_value = None
        self._attr_extra_state_attributes: dict[str, Any] = {}

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
                "display_name": event.data.get("display_name"),
                "sender": event.data.get("sender"),
                "type": event.data.get("type"),
                "item_id": event.data.get("item_id"),
                "timestamp": event.data.get("timestamp"),
                "direction": event.data.get("direction"),
                "edited": event.data.get("edited"),
                "status": event.data.get("status"),
                "file": event.data.get("file"),
            }
            self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_MESSAGE_RECEIVED, _handle_event)
        )


class SimplexTargetCountSensor(_RegistrySensor):
    """Number of chats configured by hand in the options flow."""

    _attr_name = "Configured contacts"
    _attr_icon = "mdi:account-group"
    _attr_native_unit_of_measurement = "contacts"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        super().__init__(hass, config_entry)
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_target_count"

    @property
    def native_value(self) -> int:
        registry = self._registry
        return len(registry.configured) if registry else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        registry = self._registry
        if registry is None:
            return {}
        return {
            "configured": len(registry.configured),
            "discovered": len(registry.discovered),
            "known": len(registry.targets),
        }


class SimplexKnownCountSensor(_RegistrySensor):
    """Number of chats known by the integration (configured + discovered)."""

    _attr_name = "Known contacts"
    _attr_icon = "mdi:account-multiple"
    _attr_native_unit_of_measurement = "contacts"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        super().__init__(hass, config_entry)
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_known_count"

    @property
    def native_value(self) -> int:
        registry = self._registry
        return len(registry.targets) if registry else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        registry = self._registry
        if registry is None:
            return {}
        return {
            "configured": len(registry.configured),
            "discovered": len(registry.discovered),
            "contacts": len([t for t in registry.targets if t.type == "contact"]),
            "groups": len([t for t in registry.targets if t.type == "group"]),
            "aliases": [target.alias for target in registry.targets],
        }


class SimplexDiscoveredCountSensor(_RegistrySensor):
    """Number of chats that were auto-discovered (not configured by hand)."""

    _attr_name = "Discovered contacts"
    _attr_icon = "mdi:radar"
    _attr_native_unit_of_measurement = "contacts"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        super().__init__(hass, config_entry)
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_discovered_count"

    @property
    def native_value(self) -> int:
        registry = self._registry
        return len(registry.discovered) if registry else 0


class SimplexUnreadTotalSensor(_RegistrySensor):
    """Total number of unread messages across every known chat."""

    _attr_name = "Unread messages"
    _attr_icon = "mdi:email-unread"
    _attr_native_unit_of_measurement = "messages"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        super().__init__(hass, config_entry)
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_unread_total"

    @property
    def native_value(self) -> int:
        registry = self._registry
        if registry is None:
            return 0
        return sum(target.unread_count or 0 for target in registry.targets)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        registry = self._registry
        if registry is None:
            return {}
        return {
            target.alias: target.unread_count
            for target in registry.targets
            if target.unread_count
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _handle_event(event) -> None:
            if event.data.get("entry_id") != self.config_entry.entry_id:
                return
            if event.data.get("direction") != "incoming":
                return
            self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_MESSAGE_RECEIVED, _handle_event)
        )


class SimplexMessagesTodaySensor(_RegistrySensor):
    """Number of messages received today, across every chat."""

    _activity_aware = True
    _attr_name = "Messages today"
    _attr_icon = "mdi:message-text-outline"
    _attr_native_unit_of_measurement = "messages"
    _attr_state_class = "total"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        super().__init__(hass, config_entry)
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_messages_today"

    @property
    def native_value(self) -> int:
        registry = self._registry
        if registry is None:
            return 0
        return activity_summary(registry.targets, 1)["total_today"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        registry = self._registry
        if registry is None:
            return {}
        summary = activity_summary(registry.targets, 30)
        return {
            "today": summary["total_today"],
            "last_7_days": _window(registry, 7),
            "all_time": summary["total_all_time"],
            "daily": summary["daily"][-7:],
        }


class SimplexMessagesWeekSensor(_RegistrySensor):
    """Number of messages received over the last seven days."""

    _activity_aware = True
    _attr_name = "Messages this week"
    _attr_icon = "mdi:chart-line"
    _attr_native_unit_of_measurement = "messages"
    _attr_state_class = "total"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        super().__init__(hass, config_entry)
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_messages_week"

    @property
    def native_value(self) -> int:
        registry = self._registry
        if registry is None:
            return 0
        return _window(registry, 7)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        registry = self._registry
        if registry is None:
            return {}
        return {"daily": activity_summary(registry.targets, 7)["daily"]}


class SimplexLastErrorSensor(_RegistrySensor):
    """The last error reported by the SimpleX CLI (chatCmdError)."""

    _attr_name = "Last error"
    _attr_icon = "mdi:alert-circle-outline"
    _attr_entity_category = "diagnostic"

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        super().__init__(hass, config_entry)
        self._attr_unique_id = f"{DOMAIN}_{config_entry.entry_id}_last_error"
        self._attr_native_value = None
        self._attr_extra_state_attributes: dict[str, Any] = {}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _handle_error(event) -> None:
            if event.data.get("entry_id") != self.config_entry.entry_id:
                return
            self._attr_native_value = event.data.get("message")
            self._attr_extra_state_attributes = {
                "reason": event.data.get("reason"),
                "command": event.data.get("command"),
                "timestamp": event.data.get("timestamp"),
            }
            self.async_write_ha_state()

        self.async_on_remove(self.hass.bus.async_listen(EVENT_ERROR, _handle_error))


class SimplexContactLastMessageSensor(_RegistrySensor):
    """Last message of one contact/group (both directions)."""

    _attr_icon = "mdi:message-text"

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        target: SimplexTarget,
    ) -> None:
        super().__init__(hass, config_entry)
        self._target = target
        self._attr_unique_id = contact_unique_id(config_entry, target, "last_message")
        self._attr_name = "Last message"
        self._attr_device_info = contact_device_info(config_entry, target)
        self._attr_extra_state_attributes: dict[str, Any] = {}

    @property
    def native_value(self) -> str | None:
        registry = self._registry
        target = registry.by_ref(self._target.chat_ref) if registry else None
        return target.last_message if target else None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _handle_event(event) -> None:
            if event.data.get("entry_id") != self.config_entry.entry_id:
                return
            if event.data.get("chat_ref") != self._target.chat_ref:
                return
            self._attr_extra_state_attributes = {
                "alias": event.data.get("alias"),
                "display_name": event.data.get("display_name"),
                "sender": event.data.get("sender"),
                "direction": event.data.get("direction"),
                "status": event.data.get("status"),
                "item_id": event.data.get("item_id"),
                "timestamp": event.data.get("timestamp"),
                "edited": event.data.get("edited"),
                "file": event.data.get("file"),
            }
            self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_MESSAGE_RECEIVED, _handle_event)
        )


class SimplexContactMessagesSensor(_RegistrySensor):
    """Messages received today on one contact/group."""

    _activity_aware = True
    _attr_name = "Messages today"
    _attr_icon = "mdi:message-text-outline"
    _attr_native_unit_of_measurement = "messages"
    _attr_state_class = "total"

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        target: SimplexTarget,
    ) -> None:
        super().__init__(hass, config_entry)
        self._target = target
        self._attr_unique_id = contact_unique_id(config_entry, target, "messages")
        self._attr_device_info = contact_device_info(config_entry, target)

    @property
    def native_value(self) -> int:
        registry = self._registry
        target = registry.by_ref(self._target.chat_ref) if registry else None
        if target is None:
            return 0
        return activity_summary([target], 1)["total_today"]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _handle_event(event) -> None:
            if event.data.get("entry_id") != self.config_entry.entry_id:
                return
            if event.data.get("chat_ref") != self._target.chat_ref:
                return
            if event.data.get("direction") != "incoming":
                return
            self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_MESSAGE_RECEIVED, _handle_event)
        )


class SimplexContactUnreadSensor(_RegistrySensor):
    """Unread message counter of one contact/group."""

    _attr_name = "Unread messages"
    _attr_icon = "mdi:email-unread"
    _attr_native_unit_of_measurement = "messages"
    _attr_state_class = "measurement"

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        target: SimplexTarget,
    ) -> None:
        super().__init__(hass, config_entry)
        self._target = target
        self._attr_unique_id = contact_unique_id(config_entry, target, "unread")
        self._attr_device_info = contact_device_info(config_entry, target)

    @property
    def native_value(self) -> int:
        registry = self._registry
        target = registry.by_ref(self._target.chat_ref) if registry else None
        return target.unread_count if target else 0

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        @callback
        def _handle_event(event) -> None:
            if event.data.get("entry_id") != self.config_entry.entry_id:
                return
            if event.data.get("chat_ref") != self._target.chat_ref:
                return
            if event.data.get("direction") != "incoming":
                return
            self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_MESSAGE_RECEIVED, _handle_event)
        )

        @callback
        def _handle_targets(event) -> None:
            if event.data.get("entry_id") != self.config_entry.entry_id:
                return
            self.async_write_ha_state()

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_TARGETS_UPDATED, _handle_targets)
        )
