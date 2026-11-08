"""Tests for the config, options and product flows."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.deal_finder.const import (
    CONF_COUNTRY,
    CONF_CURRENCY,
    CONF_LLM_API_KEY,
    CONF_LLM_EFFORT,
    CONF_LLM_MODEL,
    CONF_LLM_PROVIDER,
    CONF_NOTIFY_ON_DROP,
    CONF_PERSISTENT_NOTIFICATION,
    CONF_SCAN_INTERVAL,
    CONF_VERIFY_PRICES,
    DOMAIN,
    LLM_CLAUDE,
    LLM_NONE,
    SUBENTRY_PRODUCT,
)
from custom_components.deal_finder.llm import InvalidAuth

GENERAL = {CONF_COUNTRY: "CH", CONF_CURRENCY: "CHF", CONF_SCAN_INTERVAL: 12}
NOTIFY = {CONF_PERSISTENT_NOTIFICATION: True, CONF_NOTIFY_ON_DROP: False}


async def test_flow_without_llm(hass: HomeAssistant) -> None:
    """Setup without AI."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], GENERAL)
    assert result["step_id"] == "llm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_LLM_PROVIDER: LLM_NONE})
    assert result["step_id"] == "notify"
    with patch("custom_components.deal_finder.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], NOTIFY)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_LLM_PROVIDER] == LLM_NONE
    assert result["data"][CONF_COUNTRY] == "CH"


async def test_flow_with_claude(hass: HomeAssistant) -> None:
    """Setup with Claude, including an invalid key first."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], GENERAL)

    path = "custom_components.deal_finder.llm.ClaudeClient.async_list_models"
    with patch(path, side_effect=InvalidAuth("bad")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_LLM_PROVIDER: LLM_CLAUDE, CONF_LLM_API_KEY: "bad"}
        )
    assert result["errors"] == {"base": "invalid_auth"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_LLM_PROVIDER: LLM_CLAUDE})
    assert result["errors"] == {CONF_LLM_API_KEY: "api_key_required"}

    with patch(path, return_value=["claude-opus-5-5", "claude-sonnet-5-5"]):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_LLM_PROVIDER: LLM_CLAUDE, CONF_LLM_API_KEY: "sk-good"}
        )
    assert result["step_id"] == "llm_model"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_LLM_MODEL: "claude-sonnet-5-5", CONF_LLM_EFFORT: "low", CONF_VERIFY_PRICES: True}
    )
    assert result["step_id"] == "notify"
    with patch("custom_components.deal_finder.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], NOTIFY)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_LLM_MODEL] == "claude-sonnet-5-5"
    assert result["data"][CONF_LLM_API_KEY] == "sk-good"


async def test_single_instance(hass: HomeAssistant) -> None:
    """Only one instance allowed."""
    MockConfigEntry(domain=DOMAIN, data={**GENERAL, CONF_LLM_PROVIDER: LLM_NONE}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_general(hass: HomeAssistant) -> None:
    """Options menu: general settings."""
    entry = MockConfigEntry(domain=DOMAIN, data={**GENERAL, CONF_LLM_PROVIDER: LLM_NONE})
    entry.add_to_hass(hass)
    with patch("custom_components.deal_finder.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.MENU
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "general"})
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_COUNTRY: "DE", CONF_CURRENCY: "EUR", CONF_SCAN_INTERVAL: 6}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_COUNTRY] == "DE"
    assert entry.options[CONF_SCAN_INTERVAL] == 6


async def test_product_subentry(hass: HomeAssistant) -> None:
    """Add a product; without AI a URL is required."""
    entry = MockConfigEntry(domain=DOMAIN, data={**GENERAL, CONF_LLM_PROVIDER: LLM_NONE})
    entry.add_to_hass(hass)
    with patch("custom_components.deal_finder.async_setup_entry", return_value=True):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_PRODUCT), context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"name": "Sony WH-1000XM6", "web_search": True}
        )
        assert result["errors"] == {"base": "no_source"}
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                "name": "Sony WH-1000XM6",
                "target_price": 299,
                "urls": "https://www.toppreise.ch/preisvergleich/x\n  https://www.digitec.ch/de/s1/product/y ",
                "web_search": True,
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    sub = next(iter(entry.subentries.values()))
    assert sub.title == "Sony WH-1000XM6"
    assert sub.data["urls"] == "https://www.toppreise.ch/preisvergleich/x\nhttps://www.digitec.ch/de/s1/product/y"
    assert sub.data["target_price"] == 299
