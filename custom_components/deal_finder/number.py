"""Target price number entity."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_TARGET_PRICE
from .coordinator import DealFinderConfigEntry
from .entity import DealFinderProductEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DealFinderConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities."""
    coordinator = entry.runtime_data
    for sid, subentry in coordinator.products.items():
        async_add_entities([TargetPriceNumber(coordinator, subentry, "target_price")], config_subentry_id=sid)


class TargetPriceNumber(DealFinderProductEntity, NumberEntity):
    """Target price; 0 removes the target."""

    _attr_native_min_value = 0
    _attr_native_max_value = 1_000_000
    _attr_native_step = 0.05
    _attr_mode = NumberMode.BOX

    @property
    def native_unit_of_measurement(self) -> str:
        """Currency."""
        return self.currency

    @property
    def native_value(self) -> float | None:
        """Target price."""
        return self.target_price

    async def async_set_native_value(self, value: float) -> None:
        """Store the new target in the product subentry (entry reloads, prices stay cached)."""
        entry = self.coordinator.config_entry
        subentry = entry.subentries[self.subentry_id]
        data = dict(subentry.data)
        if value > 0:
            data[CONF_TARGET_PRICE] = round(value, 2)
        else:
            data.pop(CONF_TARGET_PRICE, None)
        self.hass.config_entries.async_update_subentry(entry, subentry, data=data)
