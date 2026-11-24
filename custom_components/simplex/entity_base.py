"""Shared helpers for the SimpleX entity platforms.

Every chat the integration knows about (configured *and* auto-discovered)
gets its own Home Assistant device, so the entity tree reads naturally:

    SimpleX Chat                     (the integration itself)
      ├── Last message
      ├── Configured contacts
      ├── …
      ├── Alice                      (one device per contact/group)
      │     ├── Last message
      │     ├── Unread messages
      │     └── Connected
      └── Family group
            └── …
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import DOMAIN
from .targets import SimplexTarget, chat_ref_key


def main_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return the device of the integration itself.

    The device name is what Home Assistant uses to build the entity ids
    ("Simplex Chat Last message" -> `sensor.simplex_chat_last_message`),
    so it must stay exactly in sync with the ids documented in the README
    and used by the shipped dashboards.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Simplex Chat",
        manufacturer="SimpleX Chat",
        model="Home Assistant Integration",
        entry_type=DeviceEntryType.SERVICE,
        configuration_url="https://simplex.chat",
    )


def contact_device_info(entry: ConfigEntry, target: SimplexTarget) -> DeviceInfo:
    """Return the device of a single contact / group."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}:{target.chat_ref}")},
        name=target.name,
        manufacturer="SimpleX Chat",
        model="Contact" if target.type == "contact" else "Group",
        entry_type=DeviceEntryType.SERVICE,
        configuration_url="https://simplex.chat",
    )


def contact_unique_id(entry: ConfigEntry, target: SimplexTarget, suffix: str) -> str:
    """Return a stable unique id for a per-contact entity.

    The chat reference is used instead of the alias so the id does not
    change when a contact is renamed.
    """
    return f"{DOMAIN}_{entry.entry_id}_{chat_ref_key(target.chat_ref)}_{suffix}"
