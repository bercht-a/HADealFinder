"""Tests for price extraction."""

from __future__ import annotations

import pytest

from custom_components.deal_finder.extract import parse_page, parse_price
from custom_components.deal_finder.llm import offers_from_json, parse_json_block


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (1299, 1299.0),
        ("1299.90", 1299.90),
        ("1'299.90", 1299.90),
        ("1’299.–", 1299.0),
        ("1.299,00 €", 1299.0),
        ("1,299.00", 1299.0),
        ("CHF 49.95", 49.95),
        ("29,5", 29.5),
        ("1.234.567", 1234567.0),
        ("", None),
        ("gratis", None),
        (0, None),
        (None, None),
    ],
)
def test_parse_price(raw, expected) -> None:
    """Prices in various formats."""
    assert parse_price(raw) == expected


def test_parse_page_json_ld_product() -> None:
    """Product with Offer, related product must be ignored."""
    html = """<html><head><title>Kopfhörer XY</title>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Product","name":"XY",
     "offers":{"@type":"Offer","price":"279.00","priceCurrency":"CHF",
               "availability":"https://schema.org/InStock","seller":{"@type":"Organization","name":"Shop AG"}},
     "isRelatedTo":{"@type":"Product","offers":{"@type":"Offer","price":"9.90","priceCurrency":"CHF"}}}
    </script></head><body><p>Hallo</p><script>var x=1;</script></body></html>"""
    page = parse_page("https://shop.example/xy", html)
    assert page.title == "Kopfhörer XY"
    assert len(page.prices) == 1
    cand = page.prices[0]
    assert cand.price == 279.0
    assert cand.currency == "CHF"
    assert cand.availability == "InStock"
    assert cand.seller == "Shop AG"
    assert "Hallo" in page.text
    assert "var x" not in page.text


def test_parse_page_aggregate_offer_graph() -> None:
    """Comparison sites usually expose an AggregateOffer (in @graph)."""
    html = """<script type="application/ld+json">{"@graph":[{"@type":"WebPage"},
      {"@type":["Product"],"offers":{"@type":"AggregateOffer","lowPrice":219.5,"highPrice":299,"priceCurrency":"EUR"}}]}</script>"""
    page = parse_page("https://geizhals.example/p", html)
    assert [(p.price, p.currency) for p in page.prices] == [(219.5, "EUR")]


def test_parse_page_meta_and_microdata() -> None:
    """Fallbacks: OpenGraph meta and microdata."""
    meta = '<meta property="product:price:amount" content="59.90"><meta property="product:price:currency" content="CHF">'
    page = parse_page("https://a.example", meta)
    assert [(p.price, p.currency) for p in page.prices] == [(59.9, "CHF")]

    micro = '<div itemscope><span itemprop="price" content="12.50"></span><meta itemprop="priceCurrency" content="EUR"></div>'
    page = parse_page("https://b.example", micro)
    assert [(p.price, p.currency) for p in page.prices] == [(12.5, "EUR")]


def test_llm_json_parsing() -> None:
    """LLM answers with fences and prose."""
    text = 'Here you go:\n```json\n{"offers":[{"shop":"A","price":"1\'099.00","currency":"chf","url":"https://a.ch/p"},' \
        '{"shop":"B","price":null},{"shop":"C","price":999,"url":"not-a-url"}]}\n```'
    offers = offers_from_json(parse_json_block(text), "CHF", "claude")
    assert [(o.shop, o.price, o.currency, o.url) for o in offers] == [
        ("A", 1099.0, "CHF", "https://a.ch/p"),
        ("C", 999.0, "CHF", None),
    ]
