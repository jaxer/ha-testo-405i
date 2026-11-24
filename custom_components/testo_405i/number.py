"""Number: the round duct diameter the volume flow is computed for."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberMode, RestoreNumber
from homeassistant.const import EntityCategory, UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import Testo405iConfigEntry, Testo405iCoordinator
from .entity import Testo405iEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Testo405iConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the duct diameter setting of one probe."""
    async_add_entities([DuctDiameterNumber(entry.runtime_data)])


class DuctDiameterNumber(Testo405iEntity, RestoreNumber):
    """Diameter of the duct being measured; survives restarts."""

    _attr_device_class = NumberDeviceClass.DISTANCE
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 50
    _attr_native_max_value = 500
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfLength.MILLIMETERS

    def __init__(self, coordinator: Testo405iCoordinator) -> None:
        """Set up the duct diameter setting."""
        super().__init__(coordinator, "duct_diameter")

    async def async_added_to_hass(self) -> None:
        """Bring back the diameter set before the restart."""
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self.coordinator.set_duct_diameter(last.native_value)

    @property
    def native_value(self) -> float:
        """Diameter in mm."""
        return self.coordinator.duct_diameter_mm

    async def async_set_native_value(self, value: float) -> None:
        """Use another duct diameter."""
        self.coordinator.set_duct_diameter(value)
