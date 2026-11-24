"""Sensors: air velocity, air temperature, volume flow for the set duct, battery."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import Testo405iConfigEntry, Testo405iCoordinator
from .entity import Testo405iEntity


@dataclass(frozen=True, kw_only=True)
class Testo405iSensorDescription(SensorEntityDescription):
    """A sensor and where its value comes from."""

    value_fn: Callable[[Testo405iCoordinator], float | None]
    # A live reading exists only while the probe is connected.
    live: bool = True


SENSORS: tuple[Testo405iSensorDescription, ...] = (
    Testo405iSensorDescription(
        key="velocity",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda coordinator: coordinator.data.velocity_m_s,
    ),
    Testo405iSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda coordinator: coordinator.data.temperature_c,
    ),
    Testo405iSensorDescription(
        key="flow",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda coordinator: coordinator.flow_l_s,
    ),
    # The battery level keeps its last value after the probe switches off.
    Testo405iSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda coordinator: coordinator.data.battery_percent,
        live=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Testo405iConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the sensors of one probe."""
    async_add_entities(Testo405iSensor(entry.runtime_data, description) for description in SENSORS)


class Testo405iSensor(Testo405iEntity, SensorEntity):
    """One reading of the probe."""

    entity_description: Testo405iSensorDescription

    def __init__(
        self, coordinator: Testo405iCoordinator, description: Testo405iSensorDescription
    ) -> None:
        """Set up the sensor from its description."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Live readings are unavailable while the probe is off."""
        connected = self.coordinator.data.connected
        return super().available and (connected or not self.entity_description.live)

    @property
    def native_value(self) -> float | None:
        """The reading in the sensor's unit."""
        return self.entity_description.value_fn(self.coordinator)
