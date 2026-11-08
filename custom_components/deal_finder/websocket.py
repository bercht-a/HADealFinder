"""WebSocket API used by the Deal Finder sidebar panel."""

from __future__ import annotations

from types import MappingProxyType
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    CONF_COUNTRY,
    CONF_LLM_MODEL,
    CONF_LLM_PROVIDER,
    CONF_PRODUCT_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TARGET_PRICE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LLM_NONE,
    SIGNAL_UPDATED,
    SUBENTRY_PRODUCT,
)
from .coordinator import DealFinderConfigEntry, DealFinderCoordinator
from .product import PRODUCT_FIELDS, has_web_search, normalize_product


def _entry(hass: HomeAssistant) -> DealFinderConfigEntry | None:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry
    return None


def _product_payload(coordinator: DealFinderCoordinator, sid: str, sub: ConfigSubentry) -> dict[str, Any]:
    state = coordinator.states.get(sid)
    best = state.best if state else None
    target = sub.data.get(CONF_TARGET_PRICE)
    return {
        "id": sid,
        "title": sub.title,
        "data": {k: sub.data.get(k) for k in PRODUCT_FIELDS},
        "best": best.as_dict() if best else None,
        "offers": [o.as_dict() for o in state.offers[:10]] if state else [],
        "below_target": bool(best and target is not None and best.price <= float(target)),
        "lowest_ever": state.lowest_ever if state else None,
        "previous_price": state.previous_price if state else None,
        "last_checked": state.last_checked.isoformat() if state and state.last_checked else None,
        "last_error": state.last_error if state else None,
        "stale": state.stale if state else False,
        "searching": sid in coordinator.searching,
    }


def build_payload(hass: HomeAssistant) -> dict[str, Any]:
    """Full panel state."""
    entry = _entry(hass)
    if entry is None:
        return {"loaded": False, "products": []}
    coordinator = entry.runtime_data
    config = coordinator.config
    return {
        "loaded": True,
        "currency": coordinator.finder.currency,
        "country": config.get(CONF_COUNTRY),
        "llm_provider": config.get(CONF_LLM_PROVIDER) or LLM_NONE,
        "llm_model": config.get(CONF_LLM_MODEL),
        "has_web_search": has_web_search(config),
        "scan_interval_hours": config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        "entry_id": entry.entry_id,
        "products": [_product_payload(coordinator, sid, sub) for sid, sub in coordinator.products.items()],
    }


@callback
def async_register_websocket(hass: HomeAssistant) -> None:
    """Register all commands."""
    websocket_api.async_register_command(hass, ws_subscribe)
    websocket_api.async_register_command(hass, ws_save_product)
    websocket_api.async_register_command(hass, ws_delete_product)
    websocket_api.async_register_command(hass, ws_search)


@websocket_api.websocket_command({vol.Required("type"): "deal_finder/subscribe"})
@callback
def ws_subscribe(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Send the panel state now and on every change."""

    @callback
    def forward() -> None:
        connection.send_message(websocket_api.event_message(msg["id"], build_payload(hass)))

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(hass, SIGNAL_UPDATED, forward)
    connection.send_result(msg["id"])
    forward()


@websocket_api.websocket_command(
    {
        vol.Required("type"): "deal_finder/product/save",
        vol.Optional("product_id"): str,
        vol.Required("data"): dict,
    }
)
@websocket_api.require_admin
@callback
def ws_save_product(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Create or update a product."""
    entry = _entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "Deal Finder is not loaded")
        return
    data, errors = normalize_product(msg["data"], entry.runtime_data.config)
    if errors:
        connection.send_result(msg["id"], {"success": False, "errors": errors})
        return

    if product_id := msg.get("product_id"):
        subentry = entry.subentries.get(product_id)
        if subentry is None or subentry.subentry_type != SUBENTRY_PRODUCT:
            connection.send_error(msg["id"], "not_found", "Product not found")
            return
        hass.config_entries.async_update_subentry(entry, subentry, title=data[CONF_PRODUCT_NAME], data=data)
    else:
        subentry = ConfigSubentry(
            data=MappingProxyType(data),
            subentry_type=SUBENTRY_PRODUCT,
            title=data[CONF_PRODUCT_NAME],
            unique_id=None,
        )
        hass.config_entries.async_add_subentry(entry, subentry)
        product_id = subentry.subentry_id
    connection.send_result(msg["id"], {"success": True, "product_id": product_id})


@websocket_api.websocket_command(
    {vol.Required("type"): "deal_finder/product/delete", vol.Required("product_id"): str}
)
@websocket_api.require_admin
@callback
def ws_delete_product(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Remove a product (its devices and entities are removed by HA)."""
    entry = _entry(hass)
    if entry is None or msg["product_id"] not in entry.subentries:
        connection.send_error(msg["id"], "not_found", "Product not found")
        return
    hass.config_entries.async_remove_subentry(entry, msg["product_id"])
    connection.send_result(msg["id"], {"success": True})


@websocket_api.websocket_command(
    {vol.Required("type"): "deal_finder/search", vol.Optional("product_id"): str}
)
@callback
def ws_search(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Start a search in the background (results arrive via subscription)."""
    entry = _entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_loaded", "Deal Finder is not loaded")
        return
    coordinator = entry.runtime_data
    sids = [msg["product_id"]] if msg.get("product_id") else None
    if sids and sids[0] not in coordinator.products:
        connection.send_error(msg["id"], "not_found", "Product not found")
        return
    entry.async_create_background_task(hass, coordinator.async_search_now(sids), f"{DOMAIN}_ws_search")
    connection.send_result(msg["id"], {"success": True})
