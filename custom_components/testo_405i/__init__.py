"""Testo 405i: local Bluetooth integration for the thermal anemometer smart probe."""

from __future__ import annotations

from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .coordinator import Testo405iConfigEntry, Testo405iCoordinator

PLATFORMS = [Platform.NUMBER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: Testo405iConfigEntry) -> bool:
    """Start following one probe."""
    coordinator = Testo405iCoordinator(hass, entry, entry.data[CONF_ADDRESS])
    await coordinator.async_start()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: Testo405iConfigEntry) -> bool:
    """Stop following the probe."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded
