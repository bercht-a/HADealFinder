"""Sensors for Deal Finder."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DealFinderConfigEntry, DealFinderCoordinator
from .entity import DealFinderProductEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DealFinderConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data
    async_add_entities([WishlistSensor(coordinator)])
    for sid, subentry in coordinator.products.items():
        async_add_entities(
            [
                BestPriceSensor(coordinator, subentry, "best_price"),
                LowestEverSensor(coordinator, subentry, "lowest_ever"),
                LastCheckedSensor(coordinator, subentry, "last_checked"),
            ],
            config_subentry_id=sid,
        )


class BestPriceSensor(DealFinderProductEntity, SensorEntity):
    """Current lowest price found on the web."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    @property
    def native_unit_of_measurement(self) -> str:
        """Currency."""
        return self.currency

    @property
    def native_value(self) -> float | None:
        """Lowest current price."""
        best = self.product_state.best
        return best.price if best else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Offer details."""
        state = self.product_state
        best = state.best
        target = self.target_price
        return {
            "deal_finder_role": "best_price",
            "product": self.product_data.get("name"),
            "shop": best.shop if best else None,
            "url": best.url if best else None,
            "title": best.title if best else None,
            "source": best.source if best else None,
            "verified": best.verified if best else None,
            "target_price": target,
            "below_target": bool(best and target is not None and best.price <= target),
            "previous_price": state.previous_price,
            "lowest_ever": state.lowest_ever["price"] if state.lowest_ever else None,
            "stale": state.stale,
            "last_error": state.last_error,
            "searching": self.subentry_id in self.coordinator.searching,
            "offers": [
                {"shop": o.shop, "price": o.price, "url": o.url, "verified": o.verified, "source": o.source}
                for o in state.offers[:10]
            ],
        }


class LowestEverSensor(DealFinderProductEntity, SensorEntity):
    """All-time lowest price seen."""

    _attr_suggested_display_precision = 2

    @property
    def native_unit_of_measurement(self) -> str:
        """Currency."""
        return self.currency

    @property
    def native_value(self) -> float | None:
        """All-time low."""
        low = self.product_state.lowest_ever
        return float(low["price"]) if low else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Where and when."""
        low = self.product_state.lowest_ever or {}
        return {"shop": low.get("shop"), "url": low.get("url"), "date": low.get("date")}


class LastCheckedSensor(DealFinderProductEntity, SensorEntity):
    """Timestamp of the last search."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_registry_enabled_default = True

    @property
    def native_value(self) -> datetime | None:
        """Last check."""
        return self.product_state.last_checked


class WishlistSensor(CoordinatorEntity[DealFinderCoordinator], SensorEntity):
    """Overview: number of products below target, all products as attribute."""

    _attr_has_entity_name = True
    _attr_translation_key = "wishlist"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: DealFinderCoordinator) -> None:
        """Init."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_wishlist"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Deal Finder",
            manufacturer="Deal Finder",
            entry_type=DeviceEntryType.SERVICE,
        )

    def _items(self) -> list[dict[str, Any]]:
        items = []
        for sid, sub in self.coordinator.products.items():
            state = self.coordinator.states.get(sid)
            best = state.best if state else None
            target = sub.data.get("target_price")
            items.append(
                {
                    "name": sub.title,
                    "price": best.price if best else None,
                    "currency": self.coordinator.finder.currency,
                    "shop": best.shop if best else None,
                    "url": best.url if best else None,
                    "target_price": target,
                    "below_target": bool(best and target is not None and best.price <= float(target)),
                    "lowest_ever": state.lowest_ever["price"] if state and state.lowest_ever else None,
                    "last_checked": state.last_checked.isoformat() if state and state.last_checked else None,
                    "error": state.last_error if state else None,
                }
            )
        return sorted(items, key=lambda i: (not i["below_target"], i["name"].lower()))

    @property
    def native_value(self) -> int:
        """Number of products currently below their target price."""
        return sum(1 for i in self._items() if i["below_target"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """All products."""
        return {"products": self._items(), "product_count": len(self.coordinator.products)}
