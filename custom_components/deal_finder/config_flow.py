"""Config, options and product (subentry) flows for Deal Finder."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CLAUDE_EFFORTS,
    CONF_BLOCKED,
    CONF_COUNTRY,
    CONF_CURRENCY,
    CONF_EXCLUDE,
    CONF_LLM_API_KEY,
    CONF_LLM_EFFORT,
    CONF_LLM_MODEL,
    CONF_LLM_PROVIDER,
    CONF_MIN_PRICE,
    CONF_NOTIFY_ON_DROP,
    CONF_NOTIFY_SERVICES,
    CONF_PERSISTENT_NOTIFICATION,
    CONF_PRODUCT_NAME,
    CONF_QUERY,
    CONF_SCAN_INTERVAL,
    CONF_SERPAPI_KEY,
    CONF_TARGET_PRICE,
    CONF_URLS,
    CONF_VERIFY_PRICES,
    CONF_WEB_SEARCH,
    COUNTRIES,
    CURRENCIES,
    DEFAULT_CLAUDE_EFFORT,
    DEFAULT_CLAUDE_MODEL,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LLM_CLAUDE,
    LLM_NONE,
    LLM_PROVIDERS,
    SUBENTRY_PRODUCT,
    merged_config,
)
from .llm import CannotConnect, InvalidAuth, LLMError, create_llm_client
from .product import normalize_product

PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def _general_schema(hass: HomeAssistant, cur: dict[str, Any]) -> vol.Schema:
    country = cur.get(CONF_COUNTRY) or (hass.config.country if hass.config.country in COUNTRIES else "CH")
    currency = cur.get(CONF_CURRENCY) or COUNTRIES[country][1]
    return vol.Schema(
        {
            vol.Required(CONF_COUNTRY, default=country): SelectSelector(
                SelectSelectorConfig(
                    options=[SelectOptionDict(value=k, label=f"{v[0]} ({k})") for k, v in COUNTRIES.items()],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_CURRENCY, default=currency): SelectSelector(
                SelectSelectorConfig(options=CURRENCIES, mode=SelectSelectorMode.DROPDOWN, custom_value=True)
            ),
            vol.Required(
                CONF_SCAN_INTERVAL, default=cur.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ): NumberSelector(NumberSelectorConfig(min=1, max=168, step=1, mode=NumberSelectorMode.BOX, unit_of_measurement="h")),
            vol.Optional(CONF_SERPAPI_KEY, description={"suggested_value": cur.get(CONF_SERPAPI_KEY)}): PASSWORD,
        }
    )


def _notify_schema(hass: HomeAssistant, cur: dict[str, Any]) -> vol.Schema:
    services = sorted(
        f"notify.{name}"
        for name in hass.services.async_services().get("notify", {})
        if name not in ("send_message", "persistent_notification")
    )
    return vol.Schema(
        {
            vol.Optional(CONF_NOTIFY_SERVICES, default=cur.get(CONF_NOTIFY_SERVICES, [])): SelectSelector(
                SelectSelectorConfig(options=services, multiple=True, custom_value=True, mode=SelectSelectorMode.DROPDOWN)
            ),
            vol.Required(
                CONF_PERSISTENT_NOTIFICATION, default=cur.get(CONF_PERSISTENT_NOTIFICATION, True)
            ): BooleanSelector(),
            vol.Required(CONF_NOTIFY_ON_DROP, default=cur.get(CONF_NOTIFY_ON_DROP, False)): BooleanSelector(),
        }
    )


class _LLMStepsMixin:
    """Shared LLM configuration steps for config and options flow."""

    hass: HomeAssistant
    _data: dict[str, Any]
    _models: list[str]

    def _current(self) -> dict[str, Any]:
        raise NotImplementedError

    async def _async_llm_done(self) -> ConfigFlowResult:
        raise NotImplementedError

    async def async_step_llm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose the LLM provider and enter the API key."""
        errors: dict[str, str] = {}
        cur = {**self._current(), **self._data}
        if user_input is not None:
            provider = user_input[CONF_LLM_PROVIDER]
            if provider == LLM_NONE:
                self._data.update({CONF_LLM_PROVIDER: LLM_NONE, CONF_LLM_API_KEY: None, CONF_LLM_MODEL: None})
                return await self._async_llm_done()
            api_key = (user_input.get(CONF_LLM_API_KEY) or "").strip()
            if not api_key:
                errors[CONF_LLM_API_KEY] = "api_key_required"
            else:
                client = create_llm_client(self.hass, provider, api_key)
                try:
                    self._models = await client.async_list_models() if client else []
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except LLMError:
                    errors["base"] = "unknown"
                else:
                    if provider != cur.get(CONF_LLM_PROVIDER):
                        self._data[CONF_LLM_MODEL] = None
                    self._data.update({CONF_LLM_PROVIDER: provider, CONF_LLM_API_KEY: api_key})
                    return await self.async_step_llm_model()  # type: ignore[attr-defined]
            cur.update(user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_LLM_PROVIDER, default=cur.get(CONF_LLM_PROVIDER) or LLM_NONE): SelectSelector(
                    SelectSelectorConfig(options=LLM_PROVIDERS, translation_key=CONF_LLM_PROVIDER, mode=SelectSelectorMode.LIST)
                ),
                vol.Optional(CONF_LLM_API_KEY, description={"suggested_value": cur.get(CONF_LLM_API_KEY)}): PASSWORD,
            }
        )
        return self.async_show_form(step_id="llm", data_schema=schema, errors=errors)  # type: ignore[attr-defined]

    async def async_step_llm_model(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose model (and effort for Claude)."""
        cur = {**self._current(), **self._data}
        provider = self._data[CONF_LLM_PROVIDER]
        if user_input is not None:
            self._data.update(user_input)
            return await self._async_llm_done()

        default_model = cur.get(CONF_LLM_MODEL) or (DEFAULT_CLAUDE_MODEL if provider == LLM_CLAUDE else DEFAULT_GEMINI_MODEL)
        models = list(self._models)
        if default_model not in models:
            models.insert(0, default_model)
        fields: dict[Any, Any] = {
            vol.Required(CONF_LLM_MODEL, default=default_model): SelectSelector(
                SelectSelectorConfig(options=models, custom_value=True, mode=SelectSelectorMode.DROPDOWN)
            ),
        }
        if provider == LLM_CLAUDE:
            fields[vol.Required(CONF_LLM_EFFORT, default=cur.get(CONF_LLM_EFFORT, DEFAULT_CLAUDE_EFFORT))] = SelectSelector(
                SelectSelectorConfig(options=CLAUDE_EFFORTS, translation_key=CONF_LLM_EFFORT, mode=SelectSelectorMode.LIST)
            )
        fields[vol.Required(CONF_VERIFY_PRICES, default=cur.get(CONF_VERIFY_PRICES, True))] = BooleanSelector()
        return self.async_show_form(step_id="llm_model", data_schema=vol.Schema(fields))  # type: ignore[attr-defined]


class DealFinderConfigFlow(_LLMStepsMixin, ConfigFlow, domain=DOMAIN):
    """Initial setup."""

    VERSION = 1

    def __init__(self) -> None:
        """Init."""
        self._data: dict[str, Any] = {}
        self._models: list[str] = []

    def _current(self) -> dict[str, Any]:
        return {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """General settings."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_llm()
        return self.async_show_form(step_id="user", data_schema=_general_schema(self.hass, self._data))

    async def _async_llm_done(self) -> ConfigFlowResult:
        return await self.async_step_notify()

    async def async_step_notify(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Notification settings."""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title="Deal Finder", data=self._data)
        return self.async_show_form(step_id="notify", data_schema=_notify_schema(self.hass, self._data))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> DealFinderOptionsFlow:
        """Options flow."""
        return DealFinderOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        """Products are subentries."""
        return {SUBENTRY_PRODUCT: ProductSubentryFlow}


class DealFinderOptionsFlow(_LLMStepsMixin, OptionsFlow):
    """Change settings after setup."""

    def __init__(self) -> None:
        """Init."""
        self._data: dict[str, Any] = {}
        self._models: list[str] = []

    def _current(self) -> dict[str, Any]:
        return merged_config(self.config_entry)

    def _save(self) -> ConfigFlowResult:
        return self.async_create_entry(data={**self.config_entry.options, **self._data})

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Menu."""
        return self.async_show_menu(step_id="init", menu_options=["general", "llm", "notify"])

    async def async_step_general(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """General settings."""
        if user_input is not None:
            self._data.update(user_input)
            # an emptied optional field is missing from user_input -> clear it explicitly
            self._data[CONF_SERPAPI_KEY] = user_input.get(CONF_SERPAPI_KEY)
            return self._save()
        return self.async_show_form(step_id="general", data_schema=_general_schema(self.hass, self._current()))

    async def _async_llm_done(self) -> ConfigFlowResult:
        return self._save()

    async def async_step_notify(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Notification settings."""
        if user_input is not None:
            self._data.update(user_input)
            return self._save()
        return self.async_show_form(step_id="notify", data_schema=_notify_schema(self.hass, self._current()))


def _product_schema(cur: dict[str, Any]) -> vol.Schema:
    money = NumberSelector(NumberSelectorConfig(min=0, max=1_000_000, step=0.05, mode=NumberSelectorMode.BOX))
    return vol.Schema(
        {
            vol.Required(CONF_PRODUCT_NAME, default=cur.get(CONF_PRODUCT_NAME, "")): TextSelector(),
            vol.Optional(CONF_QUERY, description={"suggested_value": cur.get(CONF_QUERY)}): TextSelector(),
            vol.Optional(CONF_TARGET_PRICE, description={"suggested_value": cur.get(CONF_TARGET_PRICE)}): money,
            vol.Optional(CONF_MIN_PRICE, description={"suggested_value": cur.get(CONF_MIN_PRICE)}): money,
            vol.Optional(CONF_URLS, description={"suggested_value": cur.get(CONF_URLS)}): TextSelector(
                TextSelectorConfig(multiline=True)
            ),
            vol.Optional(CONF_EXCLUDE, description={"suggested_value": cur.get(CONF_EXCLUDE)}): TextSelector(),
            vol.Required(CONF_WEB_SEARCH, default=cur.get(CONF_WEB_SEARCH, True)): BooleanSelector(),
        }
    )


class ProductSubentryFlow(ConfigSubentryFlow):
    """Add / edit a wishlist product."""

    def _validate(self, user_input: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        return normalize_product(user_input, merged_config(self._get_entry()))

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Add a product."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = self._validate(user_input)
            if not errors:
                return self.async_create_entry(title=data[CONF_PRODUCT_NAME], data=data)
        return self.async_show_form(step_id="user", data_schema=_product_schema(user_input or {}), errors=errors)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Edit a product."""
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = self._validate(user_input)
            if not errors:
                if subentry.data.get(CONF_BLOCKED):  # blocklist is managed in the panel
                    data[CONF_BLOCKED] = subentry.data[CONF_BLOCKED]
                return self.async_update_and_abort(
                    self._get_entry(), subentry, title=data[CONF_PRODUCT_NAME], data=data
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_product_schema(user_input or dict(subentry.data)),
            errors=errors,
        )
