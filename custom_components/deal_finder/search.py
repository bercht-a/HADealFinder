"""Price search pipeline combining product URLs, LLM web search and SerpAPI."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_BLOCKED,
    CONF_COUNTRY,
    CONF_CURRENCY,
    CONF_EXCLUDE,
    CONF_MIN_PRICE,
    CONF_PRODUCT_NAME,
    CONF_QUERY,
    CONF_SERPAPI_KEY,
    CONF_URLS,
    CONF_VERIFY_PRICES,
    CONF_WEB_SEARCH,
    LOGGER,
)
from .extract import PageFetchError, fetch_page, parse_page, parse_price
from .llm import LLMClient, llm_from_config
from .models import Offer, is_blocked, normalize_url, shop_from_url

MAX_VERIFY = 5


class SearchError(Exception):
    """All sources failed."""


def split_urls(raw: Any) -> list[str]:
    """Parse URLs from a multiline string or list."""
    if not raw:
        return []
    items = raw if isinstance(raw, list) else re.split(r"[\s,]+", str(raw))
    return [u.strip() for u in items if str(u).strip().startswith(("http://", "https://"))]


def split_terms(raw: Any) -> list[str]:
    """Parse comma separated exclude terms."""
    if not raw:
        return []
    items = raw if isinstance(raw, list) else str(raw).split(",")
    return [t.strip().lower() for t in items if str(t).strip()]


class PriceFinder:
    """Finds offers for one product from all configured sources."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Init."""
        self.hass = hass
        self.country: str = config.get(CONF_COUNTRY, "CH")
        self.currency: str = config.get(CONF_CURRENCY, "CHF").upper()
        self.serpapi_key: str | None = config.get(CONF_SERPAPI_KEY) or None
        self.verify: bool = config.get(CONF_VERIFY_PRICES, True)
        self.llm: LLMClient | None = llm_from_config(hass, config)
        self.session = async_get_clientsession(hass)

    @property
    def has_web_search(self) -> bool:
        """Whether a web search source is configured."""
        return self.llm is not None or self.serpapi_key is not None

    async def async_find(self, product: dict[str, Any]) -> list[Offer]:
        """Search all sources and return filtered offers sorted by price."""
        name = product[CONF_PRODUCT_NAME]
        query = product.get(CONF_QUERY) or name
        jobs: list[Awaitable[list[Offer]]] = [self._from_url(u, name) for u in split_urls(product.get(CONF_URLS))]
        if product.get(CONF_WEB_SEARCH, True):
            exclude = split_terms(product.get(CONF_EXCLUDE))
            if self.llm:
                rejected = [
                    f"ANY offer from the shop {b.get('display_shop')}" + (f" ({b['domain']})" if b.get("domain") else "")
                    if b.get("kind") == "shop"
                    else " – ".join(filter(None, (b.get("display_shop"), b.get("display_title"), b.get("url"))))
                    for b in (product.get(CONF_BLOCKED) or [])[-25:]
                ]
                jobs.append(self._from_llm(query, exclude, rejected))
            if self.serpapi_key:
                jobs.append(self._from_serpapi(query))
        if not jobs:
            raise SearchError("no_source")

        results = await asyncio.gather(*jobs, return_exceptions=True)
        offers: list[Offer] = []
        errors: list[str] = []
        for res in results:
            if isinstance(res, Exception):
                LOGGER.info("Deal Finder source failed for %s: %s", name, res)
                errors.append(str(res))
            elif isinstance(res, list):
                offers.extend(res)

        offers = self._filter(offers, product)
        if not offers and errors:
            raise SearchError("; ".join(errors)[:250])
        return offers

    def _filter(self, offers: list[Offer], product: dict[str, Any]) -> list[Offer]:
        min_price = product.get(CONF_MIN_PRICE)
        exclude = split_terms(product.get(CONF_EXCLUDE))
        blocked = product.get(CONF_BLOCKED) or []
        best_by_key: dict[str, Offer] = {}
        for offer in offers:
            if offer.price <= 0:
                continue
            if is_blocked(offer, blocked):
                LOGGER.debug("Skip offer blocked by user: %s", offer)
                continue
            if offer.currency and offer.currency.upper() != self.currency:
                LOGGER.debug("Skip offer in foreign currency: %s", offer)
                continue
            offer.currency = self.currency
            if min_price and offer.price < float(min_price):
                continue
            title = (offer.title or "").lower()
            if exclude and any(term in title for term in exclude):
                continue
            if offer.availability and "out" in offer.availability.lower():
                continue
            key = normalize_url(offer.url) or f"{offer.shop}|{offer.price}".lower()
            if key not in best_by_key or offer.price < best_by_key[key].price:
                best_by_key[key] = offer
        return sorted(best_by_key.values(), key=lambda o: (o.price, not o.verified))

    async def _from_url(self, url: str, product_name: str) -> list[Offer]:
        """Track an explicit product / comparison page URL."""
        html = await fetch_page(self.session, url, self.country)
        page = parse_page(url, html)
        matching = [p for p in page.prices if not p.currency or p.currency.upper() == self.currency]
        if matching:
            cand = min(matching, key=lambda p: p.price)
            return [
                Offer(
                    price=cand.price,
                    currency=(cand.currency or self.currency).upper(),
                    shop=cand.seller or shop_from_url(url),
                    url=url,
                    title=page.title or product_name,
                    source="url",
                    verified=True,
                    availability=cand.availability,
                )
            ]
        if self.llm and page.text:
            offer = await self.llm.async_extract_offer(product_name, url, self.currency, page.text, self.country)
            if offer:
                offer.title = offer.title or page.title
                return [offer]
        raise SearchError(f"no price found on {shop_from_url(url)}")

    async def _from_llm(self, query: str, exclude: list[str], rejected: list[str]) -> list[Offer]:
        assert self.llm is not None
        offers = await self.llm.async_search_offers(query, self.country, self.currency, exclude, rejected)
        LOGGER.debug("LLM offers for %s: %s", query, offers)
        if self.verify and offers:
            offers = await self._verify(offers)
        return offers

    async def _verify(self, offers: list[Offer]) -> list[Offer]:
        """Check the cheapest LLM offers against the real shop page."""
        offers = sorted(offers, key=lambda o: o.price)
        to_check = [o for o in offers if o.url][:MAX_VERIFY]

        async def check(offer: Offer) -> Offer | None:
            try:
                html = await fetch_page(self.session, offer.url, self.country)  # type: ignore[arg-type]
            except PageFetchError as err:
                if err.status in (404, 410):
                    LOGGER.debug("Dropping offer with dead URL %s", offer.url)
                    return None  # hallucinated or removed product page
                return offer  # blocked by bot protection etc. -> keep unverified
            page = parse_page(offer.url or "", html)
            prices = [p for p in page.prices if not p.currency or p.currency.upper() == self.currency]
            if prices:
                real = min(prices, key=lambda p: p.price)
                if abs(real.price - offer.price) > 0.01:
                    LOGGER.debug("Corrected %s price %s -> %s", offer.shop, offer.price, real.price)
                offer.price = real.price
                offer.verified = True
                if real.availability:
                    offer.availability = real.availability
            return offer

        checked = await asyncio.gather(*(check(o) for o in to_check))
        dropped = {id(o) for o, res in zip(to_check, checked, strict=True) if res is None}
        return [o for o in offers if id(o) not in dropped]

    async def _from_serpapi(self, query: str) -> list[Offer]:
        """Google Shopping results via SerpAPI."""
        params = {
            "engine": "google_shopping",
            "q": query,
            "gl": self.country.lower(),
            "hl": "de" if self.country in ("CH", "DE", "AT", "LI") else "en",
            "api_key": self.serpapi_key,
        }
        try:
            async with self.session.get(
                "https://serpapi.com/search.json", params=params, timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SearchError(f"SerpAPI: {err}") from err
        if "error" in data:
            raise SearchError(f"SerpAPI: {data['error']}")
        offers = []
        for item in data.get("shopping_results", [])[:20]:
            price = item.get("extracted_price") or parse_price(item.get("price"))
            if not price:
                continue
            url = item.get("link") or item.get("product_link")
            offers.append(
                Offer(
                    price=float(price),
                    currency=self.currency,
                    shop=item.get("source") or shop_from_url(url),
                    url=url,
                    title=item.get("title"),
                    source="serpapi",
                )
            )
        return offers
