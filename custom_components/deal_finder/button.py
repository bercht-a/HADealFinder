"""Search-now button."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import DealFinderConfigEntry
from .entity import DealFinderProductEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DealFinderConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons."""
    coordinator = entry.runtime_data
    for sid, subentry in coordinator.products.items():
        async_add_entities([SearchNowButton(coordinator, subentry, "search_now")], config_subentry_id=sid)


class SearchNowButton(DealFinderProductEntity, ButtonEntity):
    """Trigger an immediate price search for this product."""

    async def async_press(self) -> None:
        """Start the search in the background (LLM searches can take a while)."""
        self.coordinator.config_entry.async_create_background_task(
            self.hass,
            self.coordinator.async_search_now([self.subentry_id]),
            f"{DOMAIN}_search_{self.subentry_id}",
        )
