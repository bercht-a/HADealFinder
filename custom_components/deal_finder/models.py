"""Data models for Deal Finder."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from homeassistant.util import dt as dt_util


@dataclass
class Offer:
    """A single price offer found for a product."""

    price: float
    currency: str
    shop: str
    url: str | None = None
    title: str | None = None
    source: str = "unknown"  # url | gemini | claude | serpapi
    verified: bool = False
    availability: str | None = None
    # AI offers: True = URL appeared in the search results the AI saw,
    # False = URL not among them (likely made up), None = unknown
    grounded: bool | None = None

    def as_dict(self) -> dict[str, Any]:
        """Serialize."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Offer:
        """Deserialize."""
        return cls(
            price=float(data["price"]),
            currency=str(data.get("currency") or ""),
            shop=str(data.get("shop") or ""),
            url=data.get("url"),
            title=data.get("title"),
            source=data.get("source", "unknown"),
            verified=bool(data.get("verified", False)),
            availability=data.get("availability"),
            grounded=data.get("grounded"),
        )


def shop_from_url(url: str | None) -> str:
    """Derive a readable shop name from a URL."""
    if not url:
        return ""
    host = urlparse(url).netloc.lower()
    return host.removeprefix("www.")


_TRACKING_PARAMS = ("utm_", "gclid", "gbraid", "wbraid", "fbclid", "msclkid", "srsltid", "ref", "tag", "affid", "campaign")


def normalize_url(url: str | None) -> str | None:
    """Comparable form of a product URL (no scheme/www/fragment/tracking params)."""
    if not url:
        return None
    parsed = urlparse(url.strip())
    if not parsed.netloc:
        return None
    query = "&".join(
        sorted(
            part
            for part in parsed.query.split("&")
            if part and not part.split("=", 1)[0].lower().startswith(_TRACKING_PARAMS)
        )
    )
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    return f"{host}{path}" + (f"?{query}" if query else "")


_PRODUCT_ID = re.compile(r"(\d{5,})(?:\.html?)?/?$")


def _url_parts(url: str) -> tuple[str, str, str | None] | None:
    norm = normalize_url(url)
    if not norm:
        return None
    host, _, rest = norm.partition("/")
    path = "/" + rest.split("?", 1)[0]
    match = _PRODUCT_ID.search(path)
    return host, path, match.group(1) if match else None


def url_in_sources(url: str | None, sources: set[str] | list[str]) -> bool:
    """Whether a URL is one of the source URLs (same page or same product id on the same host)."""
    target = _url_parts(url) if url else None
    if target is None:
        return False
    for src in sources:
        parts = _url_parts(src)
        if parts is None or parts[0] != target[0]:
            continue
        if parts[1] == target[1] or (target[2] and parts[2] == target[2]):
            return True
    return False


def is_soft_404(requested: str, final: str) -> bool:
    """A product link that redirects to the home page, a search or another host is dead."""
    req, fin = _url_parts(requested), _url_parts(final)
    if req is None or fin is None:
        return False
    if req[0] != fin[0] and not fin[0].endswith("." + req[0]) and not req[0].endswith("." + fin[0]):
        return True
    if req[1] == fin[1] or (req[2] and req[2] == fin[2]):
        return False
    segments = [s for s in fin[1].split("/") if s]
    lowered = fin[1].lower()
    return len(segments) <= 1 or any(k in lowered for k in ("search", "suche", "/s?", "404", "not-found", "notfound"))


def _norm(text: str | None) -> str:
    return " ".join((text or "").lower().split())


_SECOND_LEVEL = {"co", "com", "net", "org", "ac", "gv"}
_SHOP_SUFFIXES = {"ag", "gmbh", "sa", "sarl", "ltd", "inc", "llc", "se", "kg", "ch", "de", "at", "shop", "online", "store"}


def shop_key(value: str | None) -> str:
    """Comparable shop identifier: 'Digitec', 'digitec.ch', 'https://www.digitec.ch/x' -> 'digitec'."""
    text = (value or "").strip().lower()
    if not text:
        return ""
    if "://" in text:
        text = urlparse(text).netloc
    if "." in text and " " not in text:  # looks like a domain
        labels = [p for p in text.removeprefix("www.").split(".") if p]
        if len(labels) >= 3 and labels[-2] in _SECOND_LEVEL:
            return re.sub(r"[^a-z0-9]", "", labels[-3])
        return re.sub(r"[^a-z0-9]", "", labels[-2] if len(labels) >= 2 else labels[0])
    words = [w for w in re.split(r"[^a-z0-9äöüé]+", text) if w and w not in _SHOP_SUFFIXES]
    return re.sub(r"[^a-z0-9]", "", "".join(words))


def _shop_keys(shop: str | None, url: str | None) -> set[str]:
    return {k for k in (shop_key(shop), shop_key(url)) if k}


def _keys_match(a: set[str], b: list[str] | set[str]) -> bool:
    # 'digitec' matches 'digitecgalaxus', 'mediamarkt' matches 'media markt'
    return any(x == y or (min(len(x), len(y)) >= 4 and (x.startswith(y) or y.startswith(x))) for x in a for y in b)


def block_entry(offer: dict[str, Any], now: datetime, kind: str = "offer") -> dict[str, Any]:
    """Create a blocklist entry from an offer dict (kind 'offer' or 'shop')."""
    url = normalize_url(offer.get("url"))
    shop = _norm(offer.get("shop"))
    title = _norm(offer.get("title"))
    if kind == "shop":
        keys = sorted(_shop_keys(offer.get("shop"), offer.get("url")))
        return {
            "id": "shop:" + (keys[0] if keys else shop),
            "kind": "shop",
            "shop_keys": keys,
            "shop": shop,
            "display_shop": offer.get("shop") or shop_from_url(offer.get("url")),
            "domain": shop_from_url(offer.get("url")) or None,
            "date": now.isoformat(),
        }
    return {
        "id": url or f"{shop}|{title}",
        "kind": "offer",
        "url": url,
        "shop": shop,
        "title": title or None,
        "display_shop": offer.get("shop"),
        "display_title": offer.get("title"),
        "price": offer.get("price"),
        "date": now.isoformat(),
    }


def is_blocked(offer: Offer | dict[str, Any], blocked: list[dict[str, Any]] | None) -> bool:
    """Whether an offer matches an entry of the blocklist."""
    if not blocked:
        return False
    get = offer.get if isinstance(offer, dict) else lambda k: getattr(offer, k, None)
    url = normalize_url(get("url"))
    shop = _norm(get("shop"))
    title = _norm(get("title"))
    keys: set[str] | None = None
    for entry in blocked:
        if entry.get("kind") == "shop":
            if keys is None:
                keys = _shop_keys(get("shop"), get("url"))
            if keys and _keys_match(keys, entry.get("shop_keys") or []):
                return True
            continue
        if url and entry.get("url") == url:
            return True
        # the AI may report the same offer with another URL -> also match shop + title
        if entry.get("title") and title and entry.get("shop") == shop and entry["title"] == title:
            return True
        # offers without URL and title are identified by shop only
        if not entry.get("url") and not entry.get("title") and entry.get("shop") == shop and not url and not title:
            return True
    return False


@dataclass
class ProductState:
    """Persisted search state of one wishlist product."""

    offers: list[Offer] = field(default_factory=list)
    last_checked: datetime | None = None
    last_error: str | None = None
    stale: bool = False
    previous_price: float | None = None
    lowest_ever: dict[str, Any] | None = None
    alerted_price: float | None = None

    @property
    def best(self) -> Offer | None:
        """Cheapest offer."""
        return self.offers[0] if self.offers else None

    def apply_offers(self, offers: list[Offer], now: datetime) -> None:
        """Apply new search results."""
        self.last_checked = now
        if not offers:
            # keep the last known offers so the sensor does not flap
            self.last_error = "no_offers"
            self.stale = bool(self.offers)
            return
        self.previous_price = self.best.price if self.best else None
        self.offers = sorted(offers, key=lambda o: o.price)[:15]
        self.last_error = None
        self.stale = False
        best = self.offers[0]
        if self.lowest_ever is None or best.price < float(self.lowest_ever["price"]):
            self.lowest_ever = {
                "price": best.price,
                "currency": best.currency,
                "shop": best.shop,
                "url": best.url,
                "date": now.isoformat(),
            }

    def remove_blocked(self, blocked: list[dict[str, Any]]) -> None:
        """Drop offers the user blocked (also from the all-time low)."""
        if not blocked:
            return
        self.offers = [o for o in self.offers if not is_blocked(o, blocked)]
        if self.lowest_ever and is_blocked(self.lowest_ever, blocked):
            best = self.best
            self.lowest_ever = (
                {
                    "price": best.price,
                    "currency": best.currency,
                    "shop": best.shop,
                    "url": best.url,
                    "date": self.last_checked.isoformat() if self.last_checked else None,
                }
                if best
                else None
            )
        if self.alerted_price is not None and (self.best is None or self.best.price > self.alerted_price):
            self.alerted_price = None

    def apply_error(self, error: str, now: datetime) -> None:
        """Record a failed search."""
        self.last_checked = now
        self.last_error = error
        self.stale = bool(self.offers)

    def as_dict(self) -> dict[str, Any]:
        """Serialize for storage."""
        return {
            "offers": [o.as_dict() for o in self.offers],
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "last_error": self.last_error,
            "stale": self.stale,
            "previous_price": self.previous_price,
            "lowest_ever": self.lowest_ever,
            "alerted_price": self.alerted_price,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ProductState:
        """Deserialize from storage."""
        if not data:
            return cls()
        offers = []
        for raw in data.get("offers") or []:
            try:
                offers.append(Offer.from_dict(raw))
            except (KeyError, TypeError, ValueError):
                continue
        last_checked = data.get("last_checked")
        return cls(
            offers=offers,
            last_checked=dt_util.parse_datetime(last_checked) if last_checked else None,
            last_error=data.get("last_error"),
            stale=bool(data.get("stale", False)),
            previous_price=data.get("previous_price"),
            lowest_ever=data.get("lowest_ever"),
            alerted_price=data.get("alerted_price"),
        )
