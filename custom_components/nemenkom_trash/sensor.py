"""Sensor platform — one entity per waste type, two sensors each (date + days)."""

from __future__ import annotations

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
        entities.append(DaysRemainingsensor(coordinator, entry, waste_type))

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

    def _collection_data(self) -> dict:
        if self.coordinator.data is None:
            return {}
        return self.coordinator.data.get(self._waste_type, {})


class NextCollectionDateSensor(_BaseSensor):
    """Shows the ISO date of the next collection."""

    def __init__(self, coordinator, entry, waste_type):
        super().__init__(coordinator, entry, waste_type)
        label = WASTE_TYPE_LABELS[waste_type]
        self._attr_name = f"{label} Next Collection"
        self._attr_unique_id = f"{entry.entry_id}_{waste_type}_next_date"
        self._attr_icon = WASTE_TYPE_ICONS[waste_type]
        self._attr_device_class = SensorDeviceClass.DATE

    @property
    def native_value(self):
        return self._collection_data().get("next_date")

    @property
    def extra_state_attributes(self):
        data = self._collection_data()
        return {
            "upcoming_dates": data.get("upcoming_dates", []),
            "days_remaining": data.get("days_remaining"),
            "street": self.coordinator.street,
        }


class DaysRemainingsensor(_BaseSensor):
    """Shows how many days until the next collection."""

    def __init__(self, coordinator, entry, waste_type):
        super().__init__(coordinator, entry, waste_type)
        label = WASTE_TYPE_LABELS[waste_type]
        self._attr_name = f"{label} Days Remaining"
        self._attr_unique_id = f"{entry.entry_id}_{waste_type}_days_remaining"
        self._attr_icon = "mdi:calendar-clock"
        self._attr_native_unit_of_measurement = "days"

    @property
    def native_value(self):
        return self._collection_data().get("days_remaining")

    @property
    def extra_state_attributes(self):
        data = self._collection_data()
        next_date = data.get("next_date")
        return {
            "next_date": next_date.isoformat() if next_date else None,
            "street": self.coordinator.street,
        }
