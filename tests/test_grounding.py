"""Tests against made-up links and bot-protected shop pages."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.deal_finder.const import CONF_COUNTRY, CONF_CURRENCY
from custom_components.deal_finder.extract import PageFetchError, looks_like_bot_challenge, parse_page
from custom_components.deal_finder.llm import _claude_source_urls
from custom_components.deal_finder.models import Offer, is_soft_404, url_in_sources
from custom_components.deal_finder.search import PriceFinder, SearchError

REAL = "https://www.digitec.ch/de/s1/product/ecovacs-winbot-w3-omni-fensterreinigungsroboter-38913573"
FAKE = "https://www.digitec.ch/de/s1/product/ecovacs-w3-omni-fensterputzroboter-27000000"
FETCH = "custom_components.deal_finder.search.fetch_page_with_url"
FETCH_URL_SRC = "custom_components.deal_finder.search.fetch_page"


def test_url_in_sources() -> None:
    """Same page or same product id on the same host counts; invented IDs do not."""
    sources = {REAL + "?utm_source=google", "https://www.brack.ch/ecovacs-w3-omni-123456"}
    assert url_in_sources(REAL, sources)
    # different slug, same product id
    assert url_in_sources("https://digitec.ch/de/s1/product/winbot-w3-38913573", sources)
    assert not url_in_sources(FAKE, sources)
    assert not url_in_sources("https://www.galaxus.ch/de/s1/product/x-38913573", sources)
    assert not url_in_sources(None, sources)


def test_soft_404() -> None:
    """Redirects to home / search / other host are dead links."""
    assert is_soft_404(FAKE, "https://www.digitec.ch/de")
    assert is_soft_404(FAKE, "https://www.digitec.ch/de/search?q=ecovacs")
    assert is_soft_404(FAKE, "https://www.other.ch/de/s1/product/x-27000000")
    assert not is_soft_404(REAL, REAL)
    assert not is_soft_404(REAL, "https://www.digitec.ch/de/s1/product/new-slug-38913573")


def test_bot_challenge_detection() -> None:
    """Challenge pages (toppreise 'Kurze Prüfung', Akamai 'Access Denied') are recognised."""
    assert looks_like_bot_challenge(parse_page("u", "<title>Access Denied</title><p>You don't have permission</p>"))
    assert looks_like_bot_challenge(parse_page("u", "<title>Toppreise.ch</title><h1>Kurze Prüfung</h1>"))
    real = '<title>Kurze Prüfung</title><meta property="product:price:amount" content="9.90">'
    assert not looks_like_bot_challenge(parse_page("u", real))
    assert not looks_like_bot_challenge(parse_page("u", "<title>Shop</title><p>Produktbeschreibung</p>"))


def test_claude_source_urls() -> None:
    """URLs from search results, fetch results and citations are collected; errors are ignored."""
    content = [
        SimpleNamespace(type="server_tool_use"),
        SimpleNamespace(
            type="web_search_tool_result",
            content=[SimpleNamespace(type="web_search_result", url=REAL), SimpleNamespace(type="web_search_result", url="https://b.ch/x")],
        ),
        SimpleNamespace(type="web_search_tool_result", content=SimpleNamespace(type="web_search_tool_result_error", error_code="max_uses_exceeded")),
        SimpleNamespace(type="web_fetch_tool_result", content=SimpleNamespace(type="web_fetch_result", url="https://c.ch/p")),
        SimpleNamespace(type="text", text="...", citations=[SimpleNamespace(url="https://d.ch/q")]),
        SimpleNamespace(type="text", text="...", citations=None),
    ]
    assert _claude_source_urls(content) == {REAL, "https://b.ch/x", "https://c.ch/p", "https://d.ch/q"}


@pytest.fixture
async def finder(hass: HomeAssistant) -> PriceFinder:
    """Finder with a mocked LLM."""
    f = PriceFinder(hass, {CONF_COUNTRY: "CH", CONF_CURRENCY: "CHF"})
    f.llm = AsyncMock()
    f.llm.name = "claude"
    return f


async def test_verify_drops_made_up_links(finder: PriceFinder) -> None:
    """Ungrounded links survive only if the page can be loaded and shows a price."""
    fake = Offer(price=499, currency="CHF", shop="Digitec", url=FAKE, source="claude", grounded=False)
    grounded_blocked = Offer(price=519, currency="CHF", shop="Digitec", url=REAL, source="claude", grounded=True)
    no_url = Offer(price=450, currency="CHF", shop="Irgendwo", source="claude", grounded=False)
    ok_html = '<script type="application/ld+json">{"@type":"Offer","price":"529.00","priceCurrency":"CHF"}</script>'
    ungrounded_ok = Offer(price=520, currency="CHF", shop="Brack", url="https://www.brack.ch/p-1234567", grounded=False)

    async def fake_fetch(session, url, country):
        if url == "https://www.brack.ch/p-1234567":
            return ok_html, url
        raise PageFetchError(url, 403, "HTTP 403")

    with patch(FETCH, side_effect=fake_fetch):
        result = await finder._verify([fake, grounded_blocked, no_url, ungrounded_ok])
    assert [(o.shop, o.price, o.verified) for o in result] == [("Digitec", 519, False), ("Brack", 529.0, True)]


async def test_verify_drops_soft_404(finder: PriceFinder) -> None:
    """A link redirecting to the shop's home page is dropped even if grounded."""
    offer = Offer(price=499, currency="CHF", shop="Digitec", url=FAKE, grounded=True)
    with patch(FETCH, AsyncMock(return_value=("<title>Digitec</title>", "https://www.digitec.ch/de"))):
        assert await finder._verify([offer]) == []


async def test_blocked_product_url_uses_ai(finder: PriceFinder) -> None:
    """A 403 / challenge page falls back to asking the AI for that exact URL."""
    url = "https://www.galaxus.ch/de/s2/product/ecovacs-w3-omni-fensterputzroboter-67290909"
    ai_offer = Offer(price=489.0, currency="CHF", shop="Galaxus", url=url, source="url+claude", grounded=True)
    finder.llm.async_price_for_url = AsyncMock(return_value=ai_offer)

    with patch(FETCH_URL_SRC, AsyncMock(side_effect=PageFetchError(url, 403, "HTTP 403"))):
        assert await finder._from_url(url, "Ecovacs W3 Omni") == [ai_offer]
    finder.llm.async_price_for_url.assert_awaited_once()

    challenge = "<title>Toppreise.ch</title><h1>Kurze Prüfung</h1>"
    with patch(FETCH_URL_SRC, AsyncMock(return_value=challenge)):
        assert await finder._from_url("https://www.toppreise.ch/preisvergleich/x-p123", "Ecovacs W3 Omni") == [ai_offer]

    # no AI configured -> understandable error
    finder.llm = None
    with (
        patch(FETCH_URL_SRC, AsyncMock(side_effect=PageFetchError(url, 403, "HTTP 403"))),
        pytest.raises(SearchError, match="galaxus.ch: blockiert automatische Abrufe"),
    ):
        await finder._from_url(url, "Ecovacs W3 Omni")
