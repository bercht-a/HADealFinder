"""Sidebar panel registration."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PANEL_COMPONENT, PANEL_URL_PATH, STATIC_URL

FRONTEND_DIR = Path(__file__).parent / "frontend"
PANEL_FILE = "deal-finder-panel.js"
_DATA_STATIC = f"{DOMAIN}_static_registered"
_DATA_PANEL = f"{DOMAIN}_panel_registered"


async def async_register_panel(hass: HomeAssistant) -> None:
    """Serve the panel JS and add the sidebar entry (idempotent)."""
    if not hass.data.get(_DATA_STATIC):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), cache_headers=False)]
        )
        hass.data[_DATA_STATIC] = True

    if hass.data.get(_DATA_PANEL):
        return
    # cache buster: changes whenever the file changes (e.g. after an HACS update)
    mtime = await hass.async_add_executor_job(lambda: int((FRONTEND_DIR / PANEL_FILE).stat().st_mtime))
    german = (hass.config.language or "").startswith("de")
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_COMPONENT,
        sidebar_title="Wunschliste" if german else "Wishlist",
        sidebar_icon="mdi:tag-heart",
        module_url=f"{STATIC_URL}/{PANEL_FILE}?v={mtime}",
        require_admin=False,
    )
    hass.data[_DATA_PANEL] = True


def async_remove_panel(hass: HomeAssistant) -> None:
    """Remove the sidebar entry."""
    if hass.data.pop(_DATA_PANEL, False):
        frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
