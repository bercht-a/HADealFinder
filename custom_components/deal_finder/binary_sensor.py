"""Binary sensors for Deal Finder."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DealFinderConfigEntry
from .entity import DealFinderProductEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DealFinderConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinator = entry.runtime_data
    for sid, subentry in coordinator.products.items():
        async_add_entities([BelowTargetSensor(coordinator, subentry, "below_target")], config_subentry_id=sid)


class BelowTargetSensor(DealFinderProductEntity, BinarySensorEntity):
    """On when the best price is at or below the target price."""

    @property
    def is_on(self) -> bool | None:
        """Below target?"""
        best = self.product_state.best
        target = self.target_price
        if best is None or target is None:
            return None
        return best.price <= target
