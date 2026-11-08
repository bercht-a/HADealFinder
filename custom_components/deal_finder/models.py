"""Data models for Deal Finder."""

from __future__ import annotations

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


def _norm(text: str | None) -> str:
    return " ".join((text or "").lower().split())


def block_entry(offer: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Create a blocklist entry from an offer dict."""
    url = normalize_url(offer.get("url"))
    shop = _norm(offer.get("shop"))
    title = _norm(offer.get("title"))
    return {
        "id": url or f"{shop}|{title}",
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
    for entry in blocked:
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
