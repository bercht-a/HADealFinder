"""Deal Finder: track the lowest web prices for your wishlist."""

from __future__ import annotations

from types import MappingProxyType

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_EXCLUDE,
    CONF_MIN_PRICE,
    CONF_PRODUCT_NAME,
    CONF_QUERY,
    CONF_TARGET_PRICE,
    CONF_URLS,
    CONF_WEB_SEARCH,
    DOMAIN,
    PLATFORMS,
    SERVICE_ADD_PRODUCT,
    SERVICE_REFRESH,
    SUBENTRY_PRODUCT,
)
from .coordinator import DealFinderConfigEntry, DealFinderCoordinator
from .panel import async_register_panel, async_remove_panel
from .product import normalize_product
from .websocket import async_register_websocket

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

REFRESH_SCHEMA = vol.Schema({vol.Optional("product"): cv.string})
ADD_PRODUCT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PRODUCT_NAME): cv.string,
        vol.Optional(CONF_QUERY): cv.string,
        vol.Optional(CONF_TARGET_PRICE): vol.Coerce(float),
        vol.Optional(CONF_MIN_PRICE): vol.Coerce(float),
        vol.Optional(CONF_URLS): vol.Any(cv.string, [cv.string]),
        vol.Optional(CONF_EXCLUDE): cv.string,
        vol.Optional(CONF_WEB_SEARCH, default=True): cv.boolean,
    }
)


def _loaded_entries(hass: HomeAssistant) -> list[DealFinderConfigEntry]:
    return [e for e in hass.config_entries.async_entries(DOMAIN) if e.state is ConfigEntryState.LOADED]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register services."""

    async def handle_refresh(call: ServiceCall) -> None:
        wanted = (call.data.get("product") or "").strip().lower()
        for entry in _loaded_entries(hass):
            coordinator = entry.runtime_data
            sids = [sid for sid, sub in coordinator.products.items() if not wanted or sub.title.lower() == wanted]
            if wanted and not sids:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="product_not_found",
                    translation_placeholders={"product": call.data["product"]},
                )
            await coordinator.async_search_now(sids)

    async def handle_add_product(call: ServiceCall) -> None:
        entries = _loaded_entries(hass)
        if not entries:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_loaded")
        data, errors = normalize_product(dict(call.data), entries[0].runtime_data.config)
        if errors:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_product",
                translation_placeholders={"errors": ", ".join(f"{k}: {v}" for k, v in errors.items())},
            )
        hass.config_entries.async_add_subentry(
            entries[0],
            ConfigSubentry(
                data=MappingProxyType(data),
                subentry_type=SUBENTRY_PRODUCT,
                title=data[CONF_PRODUCT_NAME],
                unique_id=None,
            ),
        )

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, handle_refresh, schema=REFRESH_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_ADD_PRODUCT, handle_add_product, schema=ADD_PRODUCT_SCHEMA)
    async_register_websocket(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: DealFinderConfigEntry) -> bool:
    """Set up Deal Finder from a config entry."""
    coordinator = DealFinderCoordinator(hass, entry)
    await coordinator.async_load()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # The panel stays registered across reloads (editing a product reloads the
    # entry); it is only removed when the integration is deleted.
    await async_register_panel(hass)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Search due products in the background so HA startup is not delayed.
    entry.async_create_background_task(hass, coordinator.async_refresh(), f"{DOMAIN}_initial_search")
    return True


async def _async_update_listener(hass: HomeAssistant, entry: DealFinderConfigEntry) -> None:
    """Reload on option / product changes (cached prices are kept)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: DealFinderConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: DealFinderConfigEntry) -> None:
    """Delete stored price history when the integration is removed."""
    from homeassistant.helpers.storage import Store  # noqa: PLC0415

    async_remove_panel(hass)
    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}").async_remove()
