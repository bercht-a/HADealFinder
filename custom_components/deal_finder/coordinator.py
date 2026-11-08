"""Coordinator: schedules searches, persists results and sends price alerts."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import timedelta
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_NOTIFY_ON_DROP,
    CONF_NOTIFY_SERVICES,
    CONF_PERSISTENT_NOTIFICATION,
    CONF_SCAN_INTERVAL,
    CONF_TARGET_PRICE,
    COORDINATOR_TICK_MINUTES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_PRICE_ALERT,
    LOGGER,
    SIGNAL_UPDATED,
    SUBENTRY_PRODUCT,
    merged_config,
)
from .models import Offer, ProductState
from .search import PriceFinder

STORAGE_VERSION = 1

type DealFinderConfigEntry = ConfigEntry[DealFinderCoordinator]


class DealFinderCoordinator(DataUpdateCoordinator[dict[str, ProductState]]):
    """Keeps the price state of all wishlist products."""

    config_entry: DealFinderConfigEntry

    def __init__(self, hass: HomeAssistant, entry: DealFinderConfigEntry) -> None:
        """Init."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=COORDINATOR_TICK_MINUTES),
        )
        self.config = merged_config(entry)
        self.finder = PriceFinder(hass, self.config)
        self.scan_interval = timedelta(hours=float(self.config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)))
        self.states: dict[str, ProductState] = {}
        self.searching: set[str] = set()
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._semaphore = asyncio.Semaphore(2)

    @property
    def products(self) -> dict[str, ConfigSubentry]:
        """All product subentries."""
        return {
            sid: sub
            for sid, sub in self.config_entry.subentries.items()
            if sub.subentry_type == SUBENTRY_PRODUCT
        }

    async def async_load(self) -> None:
        """Load cached results so a reload does not trigger new (paid) searches."""
        raw = await self._store.async_load() or {}
        self.states = {sid: ProductState.from_dict(raw.get(sid)) for sid in self.products}
        self.data = dict(self.states)
        if set(raw) - set(self.states):
            await self._async_save()  # prune removed products
        self.async_notify_ui()

    @callback
    def async_notify_ui(self) -> None:
        """Tell the sidebar panel that something changed."""
        async_dispatcher_send(self.hass, SIGNAL_UPDATED)

    async def _async_save(self) -> None:
        await self._store.async_save({sid: st.as_dict() for sid, st in self.states.items()})

    def is_due(self, sid: str) -> bool:
        """Whether a product needs a new search."""
        state = self.states.get(sid)
        if state is None or state.last_checked is None:
            return True
        return dt_util.utcnow() - state.last_checked >= self.scan_interval

    async def _async_update_data(self) -> dict[str, ProductState]:
        await self._async_search([sid for sid in self.products if self.is_due(sid)])
        return dict(self.states)

    async def async_search_now(self, sids: Iterable[str] | None = None) -> None:
        """Search immediately (button / service)."""
        await self._async_search(list(sids) if sids is not None else list(self.products))
        self.async_set_updated_data(dict(self.states))

    async def _async_search(self, sids: list[str]) -> None:
        targets = [sid for sid in sids if sid in self.products and sid not in self.searching]
        if not targets:
            return
        self.searching.update(targets)
        self.async_notify_ui()
        try:
            await asyncio.gather(*(self._async_search_one(sid) for sid in targets))
        finally:
            self.searching.difference_update(targets)
            await self._async_save()
            self.async_notify_ui()

    async def _async_search_one(self, sid: str) -> None:
        subentry = self.products[sid]
        state = self.states.setdefault(sid, ProductState())
        try:
            async with self._semaphore:
                LOGGER.debug("Searching prices for %s", subentry.title)
                try:
                    offers = await self.finder.async_find(dict(subentry.data))
                except Exception as err:  # noqa: BLE001 - one product must not break others
                    LOGGER.warning("Price search for '%s' failed: %s", subentry.title, err)
                    state.apply_error(str(err), dt_util.utcnow())
                    return
            state.apply_offers(offers, dt_util.utcnow())
            await self._async_check_alerts(subentry, state)
        finally:
            self.searching.discard(sid)
            self.async_notify_ui()

    async def _async_check_alerts(self, subentry: ConfigSubentry, state: ProductState) -> None:
        best = state.best
        if best is None or state.stale:
            return
        target = subentry.data.get(CONF_TARGET_PRICE)
        alerted = False
        if target is not None:
            if best.price <= float(target):
                if state.alerted_price is None or best.price < state.alerted_price - 0.001:
                    await self._async_notify(subentry, best, "below_target", float(target))
                    state.alerted_price = best.price
                    alerted = True
            else:
                state.alerted_price = None
        if (
            not alerted
            and self.config.get(CONF_NOTIFY_ON_DROP, False)
            and state.previous_price is not None
            and best.price < state.previous_price - 0.001
        ):
            await self._async_notify(subentry, best, "price_drop", target, state.previous_price)

    async def _async_notify(
        self,
        subentry: ConfigSubentry,
        offer: Offer,
        kind: str,
        target: float | None,
        previous: float | None = None,
    ) -> None:
        german = (self.hass.config.language or "").startswith("de")
        price = f"{offer.currency} {offer.price:.2f}"
        if kind == "below_target":
            title = f"💰 {subentry.title}: {price}"
            message = (
                f"Zielpreis {offer.currency} {target:.2f} unterschritten! Bestes Angebot bei {offer.shop}: {price}."
                if german
                else f"Below your target of {offer.currency} {target:.2f}! Best offer at {offer.shop}: {price}."
            )
        else:
            title = f"📉 {subentry.title}: {price}"
            message = (
                f"Preis gesunken von {offer.currency} {previous:.2f} auf {price} ({offer.shop})."
                if german
                else f"Price dropped from {offer.currency} {previous:.2f} to {price} ({offer.shop})."
            )
        if offer.url:
            message += f"\n{offer.url}"

        self.hass.bus.async_fire(
            EVENT_PRICE_ALERT,
            {
                "type": kind,
                "product": subentry.title,
                "subentry_id": subentry.subentry_id,
                "price": offer.price,
                "currency": offer.currency,
                "shop": offer.shop,
                "url": offer.url,
                "target_price": target,
                "previous_price": previous,
            },
        )
        if self.config.get(CONF_PERSISTENT_NOTIFICATION, True):
            persistent_notification.async_create(
                self.hass, message, title=title, notification_id=f"{DOMAIN}_{subentry.subentry_id}"
            )
        for service in self.config.get(CONF_NOTIFY_SERVICES) or []:
            domain, _, name = service.partition(".") if "." in service else ("notify", "", service)
            payload: dict[str, Any] = {"title": title, "message": message}
            if offer.url and domain == "notify" and name.startswith("mobile_app"):
                payload["data"] = {"url": offer.url, "clickAction": offer.url}
            try:
                await self.hass.services.async_call(domain, name, payload, blocking=True)
            except Exception as err:  # noqa: BLE001
                LOGGER.warning("Notification via %s failed: %s", service, err)
