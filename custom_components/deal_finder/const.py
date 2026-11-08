"""Constants for the Deal Finder integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import Platform

DOMAIN = "deal_finder"
LOGGER = logging.getLogger(__package__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.BUTTON,
]

SUBENTRY_PRODUCT = "product"

# General settings
CONF_COUNTRY = "country"
CONF_CURRENCY = "currency"
CONF_SCAN_INTERVAL = "scan_interval_hours"
CONF_SERPAPI_KEY = "serpapi_key"
CONF_VERIFY_PRICES = "verify_prices"

# LLM settings
CONF_LLM_PROVIDER = "llm_provider"
CONF_LLM_API_KEY = "llm_api_key"
CONF_LLM_MODEL = "llm_model"
CONF_LLM_EFFORT = "llm_effort"

LLM_NONE = "none"
LLM_GEMINI = "gemini"
LLM_CLAUDE = "claude"
LLM_PROVIDERS = [LLM_NONE, LLM_GEMINI, LLM_CLAUDE]

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_CLAUDE_MODEL = "claude-opus-5-5"
DEFAULT_CLAUDE_EFFORT = "low"
CLAUDE_EFFORTS = ["low", "medium", "high"]

# Notification settings
CONF_NOTIFY_SERVICES = "notify_services"
CONF_PERSISTENT_NOTIFICATION = "persistent_notification"
CONF_NOTIFY_ON_DROP = "notify_on_drop"

# Product (subentry) fields
CONF_PRODUCT_NAME = "name"
CONF_QUERY = "query"
CONF_URLS = "urls"
CONF_TARGET_PRICE = "target_price"
CONF_MIN_PRICE = "min_price"
CONF_EXCLUDE = "exclude_terms"
CONF_WEB_SEARCH = "web_search"
CONF_BLOCKED = "blocked_offers"  # managed via the panel, not part of the forms

DEFAULT_SCAN_INTERVAL = 12  # hours
COORDINATOR_TICK_MINUTES = 15

EVENT_PRICE_ALERT = "deal_finder_price_alert"
SIGNAL_UPDATED = "deal_finder_updated"

PANEL_URL_PATH = "deal-finder"
PANEL_COMPONENT = "deal-finder-panel"
STATIC_URL = "/deal_finder_static"

SERVICE_REFRESH = "refresh"
SERVICE_ADD_PRODUCT = "add_product"

# country code -> (name, default currency, helpful price comparison sites / shops)
COUNTRIES: dict[str, tuple[str, str, list[str]]] = {
    "CH": ("Schweiz", "CHF", ["toppreise.ch", "digitec.ch", "galaxus.ch", "brack.ch", "interdiscount.ch"]),
    "LI": ("Liechtenstein", "CHF", ["toppreise.ch", "digitec.ch", "galaxus.ch", "brack.ch"]),
    "DE": ("Deutschland", "EUR", ["geizhals.de", "idealo.de", "amazon.de", "mediamarkt.de"]),
    "AT": ("Österreich", "EUR", ["geizhals.at", "idealo.at", "amazon.de"]),
    "FR": ("France", "EUR", ["idealo.fr", "ledenicheur.fr", "amazon.fr"]),
    "IT": ("Italia", "EUR", ["idealo.it", "trovaprezzi.it", "amazon.it"]),
    "NL": ("Nederland", "EUR", ["tweakers.net", "kieskeurig.nl", "bol.com"]),
    "GB": ("United Kingdom", "GBP", ["pricespy.co.uk", "idealo.co.uk", "amazon.co.uk"]),
    "US": ("United States", "USD", ["google shopping", "amazon.com", "bestbuy.com"]),
}
CURRENCIES = ["CHF", "EUR", "USD", "GBP"]

ACCEPT_LANGUAGE: dict[str, str] = {
    "CH": "de-CH,de;q=0.9,fr-CH;q=0.7,en;q=0.6",
    "LI": "de-CH,de;q=0.9,en;q=0.6",
    "DE": "de-DE,de;q=0.9,en;q=0.6",
    "AT": "de-AT,de;q=0.9,en;q=0.6",
    "FR": "fr-FR,fr;q=0.9,en;q=0.6",
    "IT": "it-IT,it;q=0.9,en;q=0.6",
    "NL": "nl-NL,nl;q=0.9,en;q=0.6",
    "GB": "en-GB,en;q=0.9",
    "US": "en-US,en;q=0.9",
}


def merged_config(entry: Any) -> dict[str, Any]:
    """Return config entry data with options taking precedence."""
    return {**entry.data, **entry.options}
