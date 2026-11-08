"""Validation / normalisation of wishlist products (shared by config flow and panel)."""

from __future__ import annotations

from typing import Any

from .const import (
    CONF_EXCLUDE,
    CONF_LLM_API_KEY,
    CONF_LLM_PROVIDER,
    CONF_MIN_PRICE,
    CONF_PRODUCT_NAME,
    CONF_QUERY,
    CONF_SERPAPI_KEY,
    CONF_TARGET_PRICE,
    CONF_URLS,
    CONF_WEB_SEARCH,
    LLM_NONE,
)
from .search import split_urls

PRODUCT_FIELDS = (
    CONF_PRODUCT_NAME,
    CONF_QUERY,
    CONF_TARGET_PRICE,
    CONF_MIN_PRICE,
    CONF_URLS,
    CONF_EXCLUDE,
    CONF_WEB_SEARCH,
)


def has_web_search(config: dict[str, Any]) -> bool:
    """Whether an AI provider or SerpAPI is configured."""
    llm = config.get(CONF_LLM_PROVIDER) not in (None, LLM_NONE) and bool(config.get(CONF_LLM_API_KEY))
    return llm or bool(config.get(CONF_SERPAPI_KEY))


def normalize_product(raw: dict[str, Any], config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """Clean user input and validate it. Returns (data, errors)."""
    data: dict[str, Any] = {}
    errors: dict[str, str] = {}

    for key in (CONF_PRODUCT_NAME, CONF_QUERY, CONF_EXCLUDE):
        value = str(raw.get(key) or "").strip()
        if value:
            data[key] = value

    for key in (CONF_TARGET_PRICE, CONF_MIN_PRICE):
        value = raw.get(key)
        if value in (None, ""):
            continue
        try:
            number = round(float(value), 2)
        except (TypeError, ValueError):
            errors[key] = "invalid_number"
            continue
        if number < 0:
            errors[key] = "invalid_number"
        elif number > 0:
            data[key] = number

    data[CONF_WEB_SEARCH] = bool(raw.get(CONF_WEB_SEARCH, True))

    raw_urls = raw.get(CONF_URLS)
    if isinstance(raw_urls, list):
        raw_urls = "\n".join(str(u) for u in raw_urls)
    urls = split_urls(raw_urls)
    if urls:
        data[CONF_URLS] = "\n".join(urls)

    if CONF_PRODUCT_NAME not in data:
        errors[CONF_PRODUCT_NAME] = "name_required"
    if raw_urls and str(raw_urls).strip() and not urls:
        errors[CONF_URLS] = "invalid_url"
    elif not urls and not (data[CONF_WEB_SEARCH] and has_web_search(config)):
        errors["base"] = "no_source"
    return data, errors
