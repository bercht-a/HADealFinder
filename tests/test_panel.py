"""Tests for the sidebar panel and its WebSocket API."""

from __future__ import annotations

from types import MappingProxyType
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.deal_finder.const import (
    CONF_COUNTRY,
    CONF_CURRENCY,
    CONF_LLM_PROVIDER,
    CONF_SCAN_INTERVAL,
    DOMAIN,
    LLM_NONE,
    PANEL_URL_PATH,
    SUBENTRY_PRODUCT,
)
from custom_components.deal_finder.models import Offer

FIND = "custom_components.deal_finder.search.PriceFinder.async_find"


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_COUNTRY: "CH", CONF_CURRENCY: "CHF", CONF_SCAN_INTERVAL: 12, CONF_LLM_PROVIDER: LLM_NONE},
        subentries_data=[
            ConfigSubentryData(
                data=MappingProxyType({"name": "Kopfhörer", "target_price": 250.0, "urls": "https://shop.example/p"}),
                subentry_id="prod1",
                subentry_type=SUBENTRY_PRODUCT,
                title="Kopfhörer",
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


async def test_panel_registered(hass: HomeAssistant) -> None:
    """The sidebar panel is registered and survives a reload."""
    offers = [Offer(price=239.0, currency="CHF", shop="shop-a", url="https://a.example/p")]
    with patch(FIND, AsyncMock(return_value=offers)):
        entry = await _setup(hass)
        assert PANEL_URL_PATH in hass.data["frontend_panels"]
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert PANEL_URL_PATH in hass.data["frontend_panels"]
    panel = hass.data["frontend_panels"][PANEL_URL_PATH]
    assert panel.config["_panel_custom"]["name"] == "deal-finder-panel"


async def test_ws_subscribe_save_delete(hass: HomeAssistant, hass_ws_client) -> None:
    """Subscribe, add, edit and delete products via WebSocket."""
    offers = [Offer(price=239.0, currency="CHF", shop="shop-a", url="https://a.example/p")]
    with patch(FIND, AsyncMock(return_value=offers)):
        entry = await _setup(hass)
        client = await hass_ws_client(hass)

        await client.send_json_auto_id({"type": "deal_finder/subscribe"})
        assert (await client.receive_json())["success"]
        event = (await client.receive_json())["event"]
        assert event["loaded"] is True
        assert event["currency"] == "CHF"
        [prod] = event["products"]
        assert prod["title"] == "Kopfhörer"
        assert prod["best"]["price"] == 239.0
        assert prod["below_target"] is True

        # validation error
        await client.send_json_auto_id({"type": "deal_finder/product/save", "data": {"name": "X", "web_search": True}})
        res = await client.receive_json()
        assert res["result"] == {"success": False, "errors": {"base": "no_source"}}

        # add
        await client.send_json_auto_id(
            {
                "type": "deal_finder/product/save",
                "data": {"name": " Lego 10333 ", "target_price": "380", "urls": "https://x.example/lego", "min_price": ""},
            }
        )
        res = await client.receive_json()
        while res.get("type") == "event":
            res = await client.receive_json()
        assert res["result"]["success"] is True
        new_id = res["result"]["product_id"]
        await hass.async_block_till_done(wait_background_tasks=True)
        sub = hass.config_entries.async_get_entry(entry.entry_id).subentries[new_id]
        assert sub.title == "Lego 10333"
        assert sub.data["target_price"] == 380.0
        assert "min_price" not in sub.data

        # edit
        await client.send_json_auto_id(
            {
                "type": "deal_finder/product/save",
                "product_id": "prod1",
                "data": {"name": "Kopfhörer XM6", "target_price": 230, "urls": "https://shop.example/p"},
            }
        )
        res = await client.receive_json()
        while res.get("type") == "event":
            res = await client.receive_json()
        assert res["result"]["success"] is True
        await hass.async_block_till_done(wait_background_tasks=True)
        entry = hass.config_entries.async_get_entry(entry.entry_id)
        assert entry.subentries["prod1"].title == "Kopfhörer XM6"
        assert entry.subentries["prod1"].data["target_price"] == 230

        # delete
        await client.send_json_auto_id({"type": "deal_finder/product/delete", "product_id": new_id})
        res = await client.receive_json()
        while res.get("type") == "event":
            res = await client.receive_json()
        assert res["success"]
        await hass.async_block_till_done(wait_background_tasks=True)
        assert new_id not in hass.config_entries.async_get_entry(entry.entry_id).subentries


async def test_ws_search(hass: HomeAssistant, hass_ws_client) -> None:
    """Search command triggers a background search."""
    with patch(FIND, AsyncMock(return_value=[])) as find:
        await _setup(hass)
        assert find.call_count == 1
        client = await hass_ws_client(hass)
        await client.send_json_auto_id({"type": "deal_finder/search", "product_id": "prod1"})
        assert (await client.receive_json())["success"]
        await hass.async_block_till_done(wait_background_tasks=True)
        assert find.call_count == 2

        await client.send_json_auto_id({"type": "deal_finder/search", "product_id": "nope"})
        res = await client.receive_json()
        assert res["error"]["code"] == "not_found"
