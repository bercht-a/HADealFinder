"""Tests for hiding unsuitable offers."""

from __future__ import annotations

from datetime import UTC, datetime
from types import MappingProxyType
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.deal_finder.const import (
    CONF_BLOCKED,
    CONF_COUNTRY,
    CONF_CURRENCY,
    CONF_LLM_PROVIDER,
    CONF_SCAN_INTERVAL,
    DOMAIN,
    LLM_NONE,
    SUBENTRY_PRODUCT,
)
from custom_components.deal_finder.llm import build_search_prompt
from custom_components.deal_finder.models import Offer, block_entry, is_blocked, normalize_url
from custom_components.deal_finder.search import PriceFinder

FIND = "custom_components.deal_finder.search.PriceFinder.async_find"
NOW = datetime(2026, 11, 8, tzinfo=UTC)


def test_normalize_url() -> None:
    """Tracking params, scheme, www and trailing slash are ignored."""
    a = normalize_url("https://www.Shop.ch/p/123/?utm_source=x&gclid=1&variant=blue#top")
    b = normalize_url("http://shop.ch/p/123?variant=blue&srsltid=abc")
    assert a == b == "shop.ch/p/123?variant=blue"
    assert normalize_url("https://shop.ch/p/123?variant=red") != a
    assert normalize_url(None) is None
    assert normalize_url("not a url") is None


def test_is_blocked() -> None:
    """Match by URL, or by shop + title when the URL differs."""
    blocked = [block_entry({"url": "https://a.ch/case?ref=x", "shop": "A", "title": "Hülle für XM6", "price": 9.9}, NOW)]
    assert is_blocked(Offer(price=9.9, currency="CHF", shop="other", url="https://www.a.ch/case/"), blocked)
    assert is_blocked(Offer(price=8.0, currency="CHF", shop="a", url="https://a.ch/other-url", title="hülle  für XM6"), blocked)
    assert not is_blocked(Offer(price=279, currency="CHF", shop="A", url="https://a.ch/xm6", title="Sony XM6"), blocked)
    assert not is_blocked(Offer(price=279, currency="CHF", shop="A"), [])


async def test_filter_and_prompt(hass: HomeAssistant) -> None:
    """Blocked offers are filtered, the AI is told about them."""
    finder = PriceFinder(hass, {CONF_COUNTRY: "CH", CONF_CURRENCY: "CHF"})
    product = {"name": "XM6", CONF_BLOCKED: [block_entry({"url": "https://a.ch/case", "shop": "A"}, NOW)]}
    offers = [
        Offer(price=9.9, currency="CHF", shop="A", url="https://a.ch/case?utm_medium=x"),
        Offer(price=279, currency="CHF", shop="B", url="https://b.ch/xm6"),
    ]
    assert [o.shop for o in finder._filter(offers, product)] == ["B"]
    prompt = build_search_prompt("XM6", "CH", "CHF", [], ["A – Hülle – a.ch/case"])
    assert "rejected" in prompt
    assert "A – Hülle – a.ch/case" in prompt


async def _setup(hass: HomeAssistant, offers: list[Offer]) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_COUNTRY: "CH", CONF_CURRENCY: "CHF", CONF_SCAN_INTERVAL: 12, CONF_LLM_PROVIDER: LLM_NONE},
        subentries_data=[
            ConfigSubentryData(
                data=MappingProxyType({"name": "XM6", "target_price": 250.0, "urls": "https://shop.example/p"}),
                subentry_id="prod1",
                subentry_type=SUBENTRY_PRODUCT,
                title="XM6",
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    with patch(FIND, AsyncMock(return_value=offers)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    return entry


async def _ws(client, msg: dict) -> dict:
    await client.send_json_auto_id(msg)
    while True:
        res = await client.receive_json()
        if res.get("type") == "result":
            return res


async def test_block_and_unblock_via_ws(hass: HomeAssistant, hass_ws_client) -> None:
    """Blocking removes the offer immediately and keeps it out of later searches."""
    case = Offer(price=9.9, currency="CHF", shop="A", url="https://a.ch/case", title="Hülle")
    real = Offer(price=279.0, currency="CHF", shop="B", url="https://b.ch/xm6", title="Sony XM6")
    entry = await _setup(hass, [case, real])
    assert entry.runtime_data.states["prod1"].best.price == 9.9

    client = await hass_ws_client(hass)
    res = await _ws(
        client,
        {
            "type": "deal_finder/offer/block",
            "product_id": "prod1",
            "offer": {"url": case.url, "shop": case.shop, "title": case.title, "price": case.price},
        },
    )
    assert res["success"], res
    await hass.async_block_till_done(wait_background_tasks=True)

    entry = hass.config_entries.async_get_entry(entry.entry_id)
    blocked = entry.subentries["prod1"].data[CONF_BLOCKED]
    assert [b["url"] for b in blocked] == ["a.ch/case"]
    state = entry.runtime_data.states["prod1"]
    assert [o.shop for o in state.offers] == ["B"]
    assert state.lowest_ever["price"] == 279.0  # the hidden offer no longer counts as all-time low

    # editing the product keeps the blocklist
    res = await _ws(
        client,
        {
            "type": "deal_finder/product/save",
            "product_id": "prod1",
            "data": {"name": "XM6", "target_price": 260, "urls": "https://shop.example/p"},
        },
    )
    assert res["result"]["success"]
    await hass.async_block_till_done(wait_background_tasks=True)
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert entry.subentries["prod1"].data[CONF_BLOCKED] == blocked

    # unblock
    res = await _ws(
        client, {"type": "deal_finder/offer/unblock", "product_id": "prod1", "block_id": blocked[0]["id"]}
    )
    assert res["success"]
    await hass.async_block_till_done(wait_background_tasks=True)
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert CONF_BLOCKED not in entry.subentries["prod1"].data


async def test_search_result_filtered_by_current_blocklist(hass: HomeAssistant) -> None:
    """Even if a source returns a blocked offer, it is not applied."""
    case = Offer(price=9.9, currency="CHF", shop="A", url="https://a.ch/case")
    real = Offer(price=279.0, currency="CHF", shop="B", url="https://b.ch/xm6")
    entry = await _setup(hass, [real])
    await entry.runtime_data.async_block_offer("prod1", case.as_dict())
    await hass.async_block_till_done(wait_background_tasks=True)
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    with patch(FIND, AsyncMock(return_value=[case, real])):
        await entry.runtime_data.async_search_now()
    assert [o.shop for o in entry.runtime_data.states["prod1"].offers] == ["B"]
