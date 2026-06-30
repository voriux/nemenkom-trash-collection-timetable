"""Sensor platform — one entity per waste type, two sensors each (date + days)."""

from __future__ import annotations

from datetime import date

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, WASTE_TYPES, WASTE_TYPE_LABELS, WASTE_TYPE_ICONS
from .coordinator import NemenkomTrashCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NemenkomTrashCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []
    for waste_type in WASTE_TYPES:
        entities.append(NextCollectionDateSensor(coordinator, entry, waste_type))
        entities.append(DaysRemainingSensor(coordinator, entry, waste_type))

    async_add_entities(entities)


class _BaseSensor(CoordinatorEntity[NemenkomTrashCoordinator], SensorEntity):
    def __init__(
        self,
        coordinator: NemenkomTrashCoordinator,
        entry: ConfigEntry,
        waste_type: str,
    ) -> None:
        super().__init__(coordinator)
        self._waste_type = waste_type
        self._entry_id = entry.entry_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": f"Trash Collection — {coordinator.street}",
            "manufacturer": "Nemenkom",
            "model": "Waste Schedule",
            "entry_type": DeviceEntryType.SERVICE,
        }

    def _upcoming_dates(self) -> list[date]:
        """Return all stored upcoming dates as date objects, filtered to today or later."""
        if self.coordinator.data is None:
            return []
        raw = self.coordinator.data.get(self._waste_type, {}).get("upcoming_dates", [])
        today = date.today()
        result = []
        for d_str in raw:
            try:
                d = date.fromisoformat(d_str)
                if d >= today:
                    result.append(d)
            except (ValueError, TypeError):
                pass
        return result


class NextCollectionDateSensor(_BaseSensor):
    """Shows the date of the next collection. Computed daily from stored dates."""

    def __init__(self, coordinator, entry, waste_type):
        super().__init__(coordinator, entry, waste_type)
        label = WASTE_TYPE_LABELS[waste_type]
        self._attr_name = f"{label} Next Collection"
        self._attr_unique_id = f"{entry.entry_id}_{waste_type}_next_date"
        self._attr_icon = WASTE_TYPE_ICONS[waste_type]
        self._attr_device_class = SensorDeviceClass.DATE

    @property
    def native_value(self) -> date | None:
        upcoming = self._upcoming_dates()
        return upcoming[0] if upcoming else None

    @property
    def extra_state_attributes(self):
        upcoming = self._upcoming_dates()
        return {
            "upcoming_dates": [d.isoformat() for d in upcoming],
            "days_remaining": (upcoming[0] - date.today()).days if upcoming else None,
            "street": self.coordinator.street,
        }


class DaysRemainingSensor(_BaseSensor):
    """Shows how many days until the next collection. Computed daily from stored dates."""

    def __init__(self, coordinator, entry, waste_type):
        super().__init__(coordinator, entry, waste_type)
        label = WASTE_TYPE_LABELS[waste_type]
        self._attr_name = f"{label} Days Remaining"
        self._attr_unique_id = f"{entry.entry_id}_{waste_type}_days_remaining"
        self._attr_icon = "mdi:calendar-clock"
        self._attr_native_unit_of_measurement = "days"

    @property
    def native_value(self) -> int | None:
        upcoming = self._upcoming_dates()
        return (upcoming[0] - date.today()).days if upcoming else None

    @property
    def extra_state_attributes(self):
        upcoming = self._upcoming_dates()
        return {
            "next_date": upcoming[0].isoformat() if upcoming else None,
            "street": self.coordinator.street,
        }
