"""LLM backends (Google Gemini, Anthropic Claude) used for web price search."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from functools import partial
from typing import TYPE_CHECKING, Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_LLM_API_KEY,
    CONF_LLM_EFFORT,
    CONF_LLM_MODEL,
    CONF_LLM_PROVIDER,
    COUNTRIES,
    DEFAULT_CLAUDE_EFFORT,
    DEFAULT_CLAUDE_MODEL,
    DEFAULT_GEMINI_MODEL,
    LLM_CLAUDE,
    LLM_GEMINI,
    LOGGER,
)
from .extract import parse_price
from .models import Offer, shop_from_url

if TYPE_CHECKING:
    import anthropic


class LLMError(Exception):
    """Generic LLM failure."""


class InvalidAuth(LLMError):
    """API key rejected."""


class CannotConnect(LLMError):
    """Network / service problem."""


SYSTEM_PROMPT = (
    "You are a meticulous price research assistant. You search the web for current "
    "retail offers of one specific product and report only offers you actually saw in "
    "search results or on shop pages. Never invent shops, prices or URLs. "
    "Answer with JSON only, no prose."
)

OUTPUT_SPEC = (
    'Return exactly this JSON structure: {"offers": [{"shop": "shop name", '
    '"price": 123.45, "currency": "CHF", "url": "https://direct-product-page", '
    '"title": "product title as listed", "availability": "in_stock|out_of_stock|unknown"}]}. '
    "price is a number incl. VAT without currency symbols. Sort by price ascending, "
    'at most 10 offers. If you found nothing reliable return {"offers": []}.'
)


def build_search_prompt(query: str, country: str, currency: str, exclude: list[str]) -> str:
    """Build the user prompt for a web price search."""
    name, _, sites = COUNTRIES.get(country, (country, currency, []))
    parts = [
        f'Find the lowest current prices for this product: "{query}".',
        f"Market: online shops selling and delivering to {name} ({country}); prices in {currency}.",
    ]
    if sites:
        parts.append(f"Good sources to check: {', '.join(sites)}, plus manufacturer and major shops.")
    parts.append(
        "Only the exact same product (same model, variant, capacity, colour if specified), "
        "new condition, no used/refurbished items, no accessories, no bundles unless asked. "
        "Prefer offers that are in stock. Use the direct shop product URL, not a search page."
    )
    if exclude:
        parts.append(f"Exclude offers whose title contains any of: {', '.join(exclude)}.")
    parts.append(OUTPUT_SPEC)
    return "\n".join(parts)


def build_extract_prompt(product: str, url: str, currency: str, page_text: str) -> str:
    """Prompt to extract a price from page text."""
    return (
        f'The following is the visible text of the web page {url}. Find the current price of the product "{product}" '
        f"(expected currency {currency}). If the page lists several offers, return the cheapest one for exactly this product. "
        f"{OUTPUT_SPEC}\n\n--- PAGE TEXT ---\n{page_text}"
    )


def parse_json_block(text: str) -> Any:
    """Parse JSON from an LLM answer that might contain fences or prose."""
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(cleaned)
    except ValueError:
        pass
    for open_c, close_c in (("{", "}"), ("[", "]")):
        start, end = cleaned.find(open_c), cleaned.rfind(close_c)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except ValueError:
                continue
    raise LLMError(f"LLM answer was not valid JSON: {text[:200]!r}")


def offers_from_json(data: Any, currency: str, source: str) -> list[Offer]:
    """Convert LLM JSON into Offer objects."""
    items = data.get("offers", []) if isinstance(data, dict) else data
    offers: list[Offer] = []
    if not isinstance(items, list):
        return offers
    for item in items:
        if not isinstance(item, dict):
            continue
        price = parse_price(item.get("price"))
        if price is None:
            continue
        url = item.get("url") or None
        if url and not str(url).startswith(("http://", "https://")):
            url = None
        offers.append(
            Offer(
                price=price,
                currency=str(item.get("currency") or currency).upper(),
                shop=str(item.get("shop") or shop_from_url(url) or "?"),
                url=url,
                title=item.get("title"),
                source=source,
                availability=item.get("availability"),
            )
        )
    return offers


class LLMClient(ABC):
    """Base class for LLM backends."""

    name: str

    def __init__(self, hass: HomeAssistant, api_key: str, model: str) -> None:
        """Init."""
        self.hass = hass
        self.api_key = api_key
        self.model = model

    @abstractmethod
    async def async_list_models(self) -> list[str]:
        """Return available model ids (also validates the API key)."""

    @abstractmethod
    async def _async_generate(self, prompt: str, *, web_search: bool, country: str) -> str:
        """Run a prompt and return the answer text."""

    async def async_search_offers(
        self, query: str, country: str, currency: str, exclude: list[str]
    ) -> list[Offer]:
        """Search the web for offers."""
        text = await self._async_generate(
            build_search_prompt(query, country, currency, exclude), web_search=True, country=country
        )
        return offers_from_json(parse_json_block(text), currency, self.name)

    async def async_extract_offer(
        self, product: str, url: str, currency: str, page_text: str, country: str
    ) -> Offer | None:
        """Extract the price from page text."""
        text = await self._async_generate(
            build_extract_prompt(product, url, currency, page_text), web_search=False, country=country
        )
        offers = offers_from_json(parse_json_block(text), currency, self.name)
        if not offers:
            return None
        offer = min(offers, key=lambda o: o.price)
        offer.url = url
        offer.shop = shop_from_url(url)
        offer.source = f"url+{self.name}"
        return offer


class GeminiClient(LLMClient):
    """Google Gemini via REST with Google Search grounding."""

    name = "gemini"
    BASE = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, hass: HomeAssistant, api_key: str, model: str) -> None:
        """Init."""
        super().__init__(hass, api_key, model.removeprefix("models/"))
        self._session = async_get_clientsession(hass)

    async def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        try:
            async with self._session.request(
                method,
                f"{self.BASE}/{path}",
                json=payload,
                headers={"x-goog-api-key": self.api_key},
                timeout=aiohttp.ClientTimeout(total=180),
            ) as resp:
                data = await resp.json(content_type=None)
                if resp.status in (401, 403) or (
                    resp.status == 400 and "API_KEY_INVALID" in json.dumps(data)
                ):
                    raise InvalidAuth(data.get("error", {}).get("message", "invalid API key"))
                if resp.status >= 400:
                    raise LLMError(data.get("error", {}).get("message", f"HTTP {resp.status}"))
                return data
        except (aiohttp.ClientError, TimeoutError) as err:
            raise CannotConnect(str(err)) from err

    async def async_list_models(self) -> list[str]:
        """List generateContent-capable models."""
        data = await self._request("GET", "models?pageSize=1000")
        models = [
            m["name"].removeprefix("models/")
            for m in data.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
            and m.get("name", "").startswith("models/gemini")
        ]
        return sorted(models, reverse=True)

    async def _async_generate(self, prompt: str, *, web_search: bool, country: str) -> str:
        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1},
        }
        if web_search:
            payload["tools"] = [{"google_search": {}}]
        data = await self._request("POST", f"models/{self.model}:generateContent", payload)
        candidates = data.get("candidates") or []
        if not candidates:
            raise LLMError(f"Gemini returned no candidates: {data.get('promptFeedback')}")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        if not text:
            raise LLMError(f"Gemini returned no text (finishReason={candidates[0].get('finishReason')})")
        return text


# Models supporting the dynamic-filtering web search tool version.
_CLAUDE_NEW_SEARCH = (
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-opus-4-6",
    "claude-opus-4-7",
    "claude-opus-4-8",
    "claude-sonnet-4-6",
)
# Models accepting output_config.effort.
_CLAUDE_EFFORT = (*_CLAUDE_NEW_SEARCH, "claude-fable", "claude-haiku-5", "claude-opus-4-5")
# Models supporting server-side refusal fallbacks ("default" routing).
_CLAUDE_FALLBACK = ("claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5")


class ClaudeClient(LLMClient):
    """Anthropic Claude with the server-side web search tool."""

    name = "claude"

    def __init__(self, hass: HomeAssistant, api_key: str, model: str, effort: str) -> None:
        """Init."""
        super().__init__(hass, api_key, model)
        self.effort = effort
        self._client: anthropic.AsyncAnthropic | None = None

    async def _get_client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            import anthropic  # noqa: PLC0415

            # Client construction loads SSL certs -> do it in the executor.
            # The SDK brings its own HTTP client (httpx or httpx2 depending on
            # the installed SDK major), so we don't pass HA's shared client.
            self._client = await self.hass.async_add_executor_job(
                partial(anthropic.AsyncAnthropic, api_key=self.api_key, max_retries=2)
            )
        return self._client

    async def async_list_models(self) -> list[str]:
        """List models (validates the key)."""
        import anthropic  # noqa: PLC0415

        client = await self._get_client()
        try:
            page = await client.models.list(limit=100)
        except anthropic.AuthenticationError as err:
            raise InvalidAuth(str(err)) from err
        except anthropic.PermissionDeniedError as err:
            raise InvalidAuth(str(err)) from err
        except anthropic.APIConnectionError as err:
            raise CannotConnect(str(err)) from err
        except anthropic.APIStatusError as err:
            raise LLMError(str(err)) from err
        return [m.id for m in page.data]

    async def _async_generate(self, prompt: str, *, web_search: bool, country: str) -> str:
        import anthropic  # noqa: PLC0415

        client = await self._get_client()
        model = self.model
        kwargs: dict[str, Any] = {"model": model, "max_tokens": 16000, "system": SYSTEM_PROMPT}
        extra_body: dict[str, Any] = {}
        extra_headers: dict[str, str] = {}
        if model.startswith(_CLAUDE_EFFORT):
            extra_body["output_config"] = {"effort": self.effort}
        if model.startswith(_CLAUDE_FALLBACK):
            # On a safety-classifier refusal, let the API retry on a fallback model.
            extra_headers["anthropic-beta"] = "server-side-fallback-2026-07-01"
            extra_body["fallbacks"] = "default"
        if web_search:
            tool: dict[str, Any] = {
                "type": "web_search_20260209" if model.startswith(_CLAUDE_NEW_SEARCH) else "web_search_20250305",
                "name": "web_search",
                "max_uses": 8,
            }
            if len(country) == 2:
                tool["user_location"] = {"type": "approximate", "country": country.upper()}
            kwargs["tools"] = [tool]

        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        response = None
        for _ in range(4):  # resume long server-tool turns (pause_turn)
            try:
                response = await client.messages.create(
                    messages=messages, extra_body=extra_body or None, extra_headers=extra_headers or None, **kwargs
                )
            except anthropic.AuthenticationError as err:
                raise InvalidAuth(str(err)) from err
            except anthropic.RateLimitError as err:
                raise LLMError(f"Claude rate limit: {err.message}") from err
            except anthropic.APIConnectionError as err:
                raise CannotConnect(str(err)) from err
            except anthropic.APIStatusError as err:
                raise LLMError(f"Claude API error {err.status_code}: {err.message}") from err
            if response.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": response.content})

        assert response is not None
        if response.stop_reason == "refusal":
            raise LLMError("Claude declined the request")
        text = "".join(getattr(b, "text", "") for b in response.content if b.type == "text")
        if not text:
            raise LLMError(f"Claude returned no text (stop_reason={response.stop_reason})")
        LOGGER.debug("Claude answer: %s", text[:2000])
        return text


def create_llm_client(
    hass: HomeAssistant,
    provider: str | None,
    api_key: str | None,
    model: str | None = None,
    effort: str | None = None,
) -> LLMClient | None:
    """Create an LLM client for the given provider."""
    if not api_key:
        return None
    if provider == LLM_GEMINI:
        return GeminiClient(hass, api_key, model or DEFAULT_GEMINI_MODEL)
    if provider == LLM_CLAUDE:
        return ClaudeClient(hass, api_key, model or DEFAULT_CLAUDE_MODEL, effort or DEFAULT_CLAUDE_EFFORT)
    return None


def llm_from_config(hass: HomeAssistant, config: dict[str, Any]) -> LLMClient | None:
    """Create the configured LLM client (or None)."""
    return create_llm_client(
        hass,
        config.get(CONF_LLM_PROVIDER),
        config.get(CONF_LLM_API_KEY),
        config.get(CONF_LLM_MODEL),
        config.get(CONF_LLM_EFFORT),
    )

