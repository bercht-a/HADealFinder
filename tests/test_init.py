"""Tests for setup, entities and alerts."""

from __future__ import annotations

from types import MappingProxyType
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events

from custom_components.deal_finder.const import (
    CONF_COUNTRY,
    CONF_CURRENCY,
    CONF_LLM_PROVIDER,
    CONF_PERSISTENT_NOTIFICATION,
    CONF_SCAN_INTERVAL,
    DOMAIN,
    EVENT_PRICE_ALERT,
    LLM_NONE,
    SUBENTRY_PRODUCT,
)
from custom_components.deal_finder.models import Offer

FIND = "custom_components.deal_finder.search.PriceFinder.async_find"


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_COUNTRY: "CH",
            CONF_CURRENCY: "CHF",
            CONF_SCAN_INTERVAL: 12,
            CONF_LLM_PROVIDER: LLM_NONE,
            CONF_PERSISTENT_NOTIFICATION: True,
        },
        subentries_data=[
            ConfigSubentryData(
                data=MappingProxyType(
                    {"name": "Kopfhörer", "target_price": 250.0, "urls": "https://shop.example/p", "web_search": False}
                ),
                subentry_id="prod1",
                subentry_type=SUBENTRY_PRODUCT,
                title="Kopfhörer",
                unique_id=None,
            )
        ],
    )


def _eid(hass: HomeAssistant, domain: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"prod1_{key}")
    assert entity_id, key
    return entity_id


async def test_setup_and_alert(hass: HomeAssistant) -> None:
    """Search runs on setup, entities show the best price, alert fires once."""
    entry = _entry()
    entry.add_to_hass(hass)
    events = async_capture_events(hass, EVENT_PRICE_ALERT)
    offers = [
        Offer(price=279.0, currency="CHF", shop="shop-b", url="https://b.example/p", source="url"),
        Offer(price=239.0, currency="CHF", shop="shop-a", url="https://a.example/p", source="url", verified=True),
    ]
    with patch(FIND, AsyncMock(return_value=offers)) as find:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert find.call_count == 1

    best = hass.states.get(_eid(hass, "sensor", "best_price"))
    assert best is not None
    assert float(best.state) == 239.0
    assert best.attributes["unit_of_measurement"] == "CHF"
    assert best.attributes["shop"] == "shop-a"
    assert best.attributes["below_target"] is True
    assert hass.states.get(_eid(hass, "binary_sensor", "below_target")).state == "on"
    assert float(hass.states.get(_eid(hass, "number", "target_price")).state) == 250.0
    assert float(hass.states.get(_eid(hass, "sensor", "lowest_ever")).state) == 239.0

    wishlist = hass.states.get(
        er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_wishlist")
    )
    assert wishlist.state == "1"
    assert wishlist.attributes["products"][0]["name"] == "Kopfhörer"

    assert len(events) == 1
    assert events[0].data["price"] == 239.0
    assert events[0].data["type"] == "below_target"

    # Same price again -> no duplicate alert. Lower price -> new alert.
    coordinator = entry.runtime_data
    with patch(FIND, AsyncMock(return_value=offers)):
        await coordinator.async_search_now()
    assert len(events) == 1
    cheaper = [Offer(price=219.0, currency="CHF", shop="shop-c", url="https://c.example/p")]
    with patch(FIND, AsyncMock(return_value=cheaper)):
        await coordinator.async_search_now()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(events) == 2
    assert float(hass.states.get(_eid(hass, "sensor", "best_price")).state) == 219.0


async def test_target_change_reload_uses_cache(hass: HomeAssistant) -> None:
    """Changing the target reloads the entry without a new (paid) search."""
    entry = _entry()
    entry.add_to_hass(hass)
    offers = [Offer(price=260.0, currency="CHF", shop="shop-a", url="https://a.example/p")]
    with patch(FIND, AsyncMock(return_value=offers)) as find:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert hass.states.get(_eid(hass, "binary_sensor", "below_target")).state == "off"

        await hass.services.async_call(
            "number", "set_value", {"entity_id": _eid(hass, "number", "target_price"), "value": 270}, blocking=True
        )
        await hass.async_block_till_done(wait_background_tasks=True)
        assert find.call_count == 1

    assert entry.subentries["prod1"].data["target_price"] == 270
    assert float(hass.states.get(_eid(hass, "sensor", "best_price")).state) == 260.0
    assert hass.states.get(_eid(hass, "binary_sensor", "below_target")).state == "on"


async def test_search_error_keeps_last_price(hass: HomeAssistant) -> None:
    """A failing search keeps the last known offers, marked stale."""
    entry = _entry()
    entry.add_to_hass(hass)
    offers = [Offer(price=260.0, currency="CHF", shop="shop-a")]
    with patch(FIND, AsyncMock(return_value=offers)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    with patch(FIND, AsyncMock(side_effect=RuntimeError("blocked"))):
        await entry.runtime_data.async_search_now()
    state = hass.states.get(_eid(hass, "sensor", "best_price"))
    assert float(state.state) == 260.0
    assert state.attributes["stale"] is True
    assert state.attributes["last_error"] == "blocked"


async def test_add_product_service(hass: HomeAssistant) -> None:
    """Products can be added via service."""
    entry = _entry()
    entry.add_to_hass(hass)
    with patch(FIND, AsyncMock(return_value=[])):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        await hass.services.async_call(
            DOMAIN,
            "add_product",
            {"name": "Lego 10333", "urls": ["https://x.example/lego"], "target_price": 400},
            blocking=True,
        )
        await hass.async_block_till_done(wait_background_tasks=True)
    titles = sorted(s.title for s in entry.subentries.values())
    assert titles == ["Kopfhörer", "Lego 10333"]
