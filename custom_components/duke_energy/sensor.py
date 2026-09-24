"""Sensor platform for Duke Energy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DukeEnergyConfigEntry, DukeEnergyCoordinator

if TYPE_CHECKING:
    from decimal import Decimal

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DukeEnergyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Duke Energy total-cost sensors."""
    coordinator = entry.runtime_data
    entity_registry = er.async_get(hass)
    entities: list[DukeEnergyTotalCostSensor] = []

    for serial_number, meter in coordinator.meters.items():
        service_type = meter["serviceType"]
        if service_type not in ("ELECTRIC", "GAS"):
            continue

        meter_id = f"{service_type.lower()}_{serial_number}"
        legacy_unique_id = f"{meter_id}_consumption"
        if entity_id := entity_registry.async_get_entity_id(
            "sensor", DOMAIN, legacy_unique_id
        ):
            entity_registry.async_remove(entity_id)

        entities.append(DukeEnergyTotalCostSensor(coordinator, serial_number))

    async_add_entities(entities)


class DukeEnergyTotalCostSensor(CoordinatorEntity[DukeEnergyCoordinator], SensorEntity):
    """Represent cumulative usage cost for a Duke Energy meter."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2
    _attr_translation_key = "total_cost"

    def __init__(
        self,
        coordinator: DukeEnergyCoordinator,
        serial_number: str,
    ) -> None:
        """Initialize a Duke Energy total-cost sensor."""
        super().__init__(coordinator)

        self._serial_number = serial_number
        meter = coordinator.meters[serial_number]
        service_type = meter["serviceType"]
        service_name = service_type.capitalize()
        meter_id = f"{service_type.lower()}_{serial_number}"

        self._attr_unique_id = f"{meter_id}_total_cost"
        self._attr_native_unit_of_measurement = coordinator.hass.config.currency
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, meter_id)},
            manufacturer="Duke Energy",
            model=f"{service_name} meter",
            name=f"Duke Energy {service_name} Meter",
            serial_number=serial_number,
        )

    @property
    def available(self) -> bool:
        """Return whether cost tracking is enabled for this service."""
        meter = self.coordinator.meters[self._serial_number]
        return super().available and self.coordinator.rate_provider.enabled(
            meter["serviceType"]
        )

    @property
    def native_value(self) -> Decimal | None:
        """Return cumulative usage cost."""
        if not self.available:
            return None
        if data := self.coordinator.data.get(self._serial_number):
            return data["total_cost"]
        meter = self.coordinator.meters[self._serial_number]
        meter_id = f"{meter['serviceType'].lower()}_{self._serial_number}"
        return self.coordinator.cost_ledger.total(meter_id)
