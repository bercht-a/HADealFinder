"""Fetch product pages and extract prices from structured data."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

import aiohttp

from .const import ACCEPT_LANGUAGE

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
MAX_HTML_BYTES = 3_000_000
MAX_TEXT_CHARS = 20_000


class PageFetchError(Exception):
    """Raised when a page could not be fetched."""

    def __init__(self, url: str, status: int | None, message: str) -> None:
        """Init."""
        super().__init__(message)
        self.url = url
        self.status = status


@dataclass
class PriceCandidate:
    """A price found in structured data."""

    price: float
    currency: str | None
    availability: str | None = None
    seller: str | None = None


@dataclass
class ParsedPage:
    """Result of parsing a product page."""

    url: str
    title: str = ""
    prices: list[PriceCandidate] = field(default_factory=list)
    text: str = ""


def parse_price(value: Any) -> float | None:
    """Parse prices like 1299, '1’299.90', '1.299,00 €' or '29.–'."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    text = re.sub(r"[^\d,.]", "", str(value).replace("'", "").replace("’", ""))
    if not text or not re.search(r"\d", text):
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        head, _, tail = text.rpartition(",")
        text = f"{head.replace(',', '')}.{tail}" if len(tail) in (1, 2) else text.replace(",", "")
    elif text.count(".") > 1:
        head, _, tail = text.rpartition(".")
        text = f"{head.replace('.', '')}.{tail}" if len(tail) in (1, 2) else text.replace(".", "")
    text = text.strip(".")
    try:
        price = float(text)
    except ValueError:
        return None
    return price if price > 0 else None


class _PageParser(HTMLParser):
    """Collect JSON-LD, price meta tags, microdata and visible text."""

    _SKIP = {"script", "style", "noscript", "svg", "template", "head"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ld_json: list[str] = []
        self.meta: dict[str, str] = {}
        self.itemprops: list[tuple[str, str]] = []
        self.title = ""
        self._text: list[str] = []
        self._text_len = 0
        self._skip_depth = 0
        self._in_ld = False
        self._in_title = False
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "script" and "ld+json" in a.get("type", "").lower():
            self._in_ld = True
            self._buf = []
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if key and "content" in a:
                self.meta.setdefault(key, a["content"])
        if "itemprop" in a and a["itemprop"].lower() in ("price", "lowprice", "pricecurrency"):
            value = a.get("content") or a.get("value") or ""
            if value:
                self.itemprops.append((a["itemprop"].lower(), value))
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_ld:
            self.ld_json.append("".join(self._buf))
            self._in_ld = False
        if tag == "title":
            self._in_title = False
        if tag in self._SKIP and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_ld:
            self._buf.append(data)
            return
        if self._in_title:
            self.title += data
            return
        if self._skip_depth or self._text_len > MAX_TEXT_CHARS:
            return
        chunk = data.strip()
        if chunk:
            self._text.append(chunk)
            self._text_len += len(chunk) + 1

    @property
    def text(self) -> str:
        return " ".join(self._text)[:MAX_TEXT_CHARS]


def _types(node: dict[str, Any]) -> set[str]:
    raw = node.get("@type")
    if isinstance(raw, str):
        return {raw.lower()}
    if isinstance(raw, list):
        return {str(t).lower() for t in raw}
    return set()


def _walk_ld(node: Any, out: list[PriceCandidate], depth: int = 0) -> None:
    if depth > 12:
        return
    if isinstance(node, list):
        for item in node:
            _walk_ld(item, out, depth + 1)
        return
    if not isinstance(node, dict):
        return
    types = _types(node)
    if types & {"offer", "aggregateoffer"}:
        price = parse_price(node.get("lowPrice")) or parse_price(node.get("price"))
        if price is None and isinstance(node.get("priceSpecification"), dict):
            price = parse_price(node["priceSpecification"].get("price"))
        if price is not None:
            seller = node.get("seller")
            out.append(
                PriceCandidate(
                    price=price,
                    currency=node.get("priceCurrency")
                    or (node.get("priceSpecification") or {}).get("priceCurrency"),
                    availability=str(node.get("availability") or "").rsplit("/", 1)[-1] or None,
                    seller=seller.get("name") if isinstance(seller, dict) else None,
                )
            )
    # Only follow keys that belong to *this* product; related/similar products
    # (isRelatedTo, isSimilarTo, itemListElement...) would yield foreign prices.
    for key in ("offers", "@graph", "mainEntity"):
        if key in node:
            _walk_ld(node[key], out, depth + 1)


_CHALLENGE_MARKERS = (
    "access denied",
    "kurze prüfung",
    "just a moment",
    "attention required",
    "are you a robot",
    "bist du ein mensch",
    "captcha",
    "verify you are human",
    "zugriff verweigert",
    "please enable javascript",
    "pardon our interruption",
)


def looks_like_bot_challenge(page: ParsedPage) -> bool:
    """Bot protection page instead of the real product page."""
    if page.prices:
        return False
    haystack = f"{page.title} {page.text[:2000]}".lower()
    return any(marker in haystack for marker in _CHALLENGE_MARKERS)


def parse_page(url: str, html: str) -> ParsedPage:
    """Parse HTML and extract price candidates."""
    parser = _PageParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # noqa: BLE001 - malformed HTML must not break extraction
        pass

    prices: list[PriceCandidate] = []
    for raw in parser.ld_json:
        try:
            data = json.loads(raw.strip())
        except ValueError:
            continue
        _walk_ld(data, prices)

    if not prices:
        meta_price = (
            parser.meta.get("product:price:amount")
            or parser.meta.get("og:price:amount")
            or parser.meta.get("price")
        )
        price = parse_price(meta_price)
        if price:
            prices.append(
                PriceCandidate(
                    price=price,
                    currency=parser.meta.get("product:price:currency")
                    or parser.meta.get("og:price:currency")
                    or parser.meta.get("pricecurrency"),
                )
            )

    if not prices and parser.itemprops:
        currency = next((v for k, v in parser.itemprops if k == "pricecurrency"), None)
        for key, value in parser.itemprops:
            if key in ("price", "lowprice") and (price := parse_price(value)):
                prices.append(PriceCandidate(price=price, currency=currency))

    return ParsedPage(url=url, title=parser.title.strip(), prices=prices, text=parser.text)


async def fetch_page(session: aiohttp.ClientSession, url: str, country: str) -> str:
    """Download a page and return its HTML."""
    html, _ = await fetch_page_with_url(session, url, country)
    return html


async def fetch_page_with_url(session: aiohttp.ClientSession, url: str, country: str) -> tuple[str, str]:
    """Download a page; return (HTML, final URL after redirects)."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": ACCEPT_LANGUAGE.get(country, "en;q=0.8"),
    }
    try:
        async with session.get(
            url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=25),
            allow_redirects=True,
        ) as resp:
            if resp.status >= 400:
                raise PageFetchError(url, resp.status, f"HTTP {resp.status} for {url}")
            raw = await resp.content.read(MAX_HTML_BYTES)
            return raw.decode(resp.charset or "utf-8", errors="replace"), str(resp.url)
    except (aiohttp.ClientError, TimeoutError) as err:
        raise PageFetchError(url, None, f"{type(err).__name__} for {url}") from err
