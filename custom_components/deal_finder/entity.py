"""Base entities for Deal Finder."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigSubentry
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_TARGET_PRICE, DOMAIN
from .coordinator import DealFinderCoordinator
from .models import ProductState


class DealFinderProductEntity(CoordinatorEntity[DealFinderCoordinator]):
    """Entity belonging to one wishlist product (one device per product)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: DealFinderCoordinator, subentry: ConfigSubentry, key: str) -> None:
        """Init."""
        super().__init__(coordinator)
        self.subentry_id = subentry.subentry_id
        self._attr_unique_id = f"{subentry.subentry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="Deal Finder",
            model="Wishlist product",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def product_state(self) -> ProductState:
        """Current state of this product."""
        return self.coordinator.states.get(self.subentry_id) or ProductState()

    @property
    def product_data(self) -> dict[str, Any]:
        """Configured product data."""
        sub = self.coordinator.config_entry.subentries.get(self.subentry_id)
        return dict(sub.data) if sub else {}

    @property
    def target_price(self) -> float | None:
        """Configured target price."""
        value = self.product_data.get(CONF_TARGET_PRICE)
        return float(value) if value not in (None, "") else None

    @property
    def currency(self) -> str:
        """Configured currency."""
        return self.coordinator.finder.currency
