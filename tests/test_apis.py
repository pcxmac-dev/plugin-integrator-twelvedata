"""What Twelve Data's plugin attaches to (plugin API 2.2, apis.py): a sound card, its calls the ones the plugin really
makes (a recording session answers every request; nothing is sent), and nothing asked to say what it learned
(api_facts). With LIMINAL_VENDOR_PAGES=1, every address on the card is asked once: the one test here that sends
anything (the plugins' page check)."""
from __future__ import annotations

import os
from datetime import date
from urllib.parse import urlparse

import pytest

from liminal_libs.sources import registry
from liminal_libs.sources.apis import dead_links, problems, urls
import plugin_integrator_twelvedata as twelvedata
from plugin_integrator_twelvedata.apis import API, APIS, KEYS, TWELVE_DATA
from plugin_integrator_twelvedata.client import TwelveDataClient, TwelveDataSource

from .conftest import FakeResponse

DAY = date(2026, 11, 10)
ANSWERS = {  # as its reference shows them: a window with nothing in it, a pair's first minute, the pairs it lists
    "/time_series": {"code": 400, "message": "No data is available on the specified dates.", "status": "error"},
    "/earliest_timestamp": {"datetime": "2010-01-04 00:00:00", "unix_time": 1262563200},
    "/forex_pairs": {"data": [{"symbol": "EUR/USD", "currency_group": "Major", "currency_base": "Euro",
                               "currency_quote": "US Dollar"}], "status": "ok"},
}


class Recording:
    """Answers every request as its reference shows and records it with its parameters."""

    def __init__(self):
        self.asked: list[tuple[str, str, dict]] = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.asked.append(("GET", url, dict(params or {})))
        return FakeResponse(200, ANSWERS[urlparse(url).path])


def test_its_card_names_every_call_it_makes_and_none_it_does_not():
    session = Recording()
    source = TwelveDataSource(TwelveDataClient(API, key="KEY", session=session, sleep=lambda s: None), has_key=True)
    list(source.bar_pages("C:EURUSD", DAY, DAY, "minute"))  # a window with nothing in it: the pair's first minute next
    source.instrument("EURUSD")  # the pairs it lists
    assert all(u.startswith(API + "/") and p.get("apikey") == "KEY" for _, u, p in session.asked)  # the card's base
    made = {f"{m} {urlparse(u).path}" for m, u, _ in session.asked}
    assert made <= {c.name for c in TWELVE_DATA.calls}  # every request it made is a call on the card
    assert made == {c.name for c in TWELVE_DATA.used} == {"GET /time_series", "GET /earliest_timestamp",
                                                           "GET /forex_pairs"}  # and every one it says, made


def test_a_sound_card():
    assert APIS == (TWELVE_DATA,) and twelvedata.PLUGIN.apis is APIS and problems(APIS, today=DAY) == []
    assert TWELVE_DATA.docs == "https://twelvedata.com/docs" and TWELVE_DATA.base == API == twelvedata.API
    assert twelvedata.PLUGIN.signup == KEYS == TWELVE_DATA.link("console")  # where the key is: its console page
    kinds = {x.kind for x in TWELVE_DATA.links}
    assert {"docs", "reference", "limits", "pricing", "status", "changelog", "spec", "console", "sdk", "terms"} <= kinds
    parts = {a.name for a in TWELVE_DATA.areas}
    assert {"Market data", "Asset catalogs", "Discovery", "Fundamentals", "Technical indicators", "WebSocket"} <= parts
    assert {a.name for a in TWELVE_DATA.covered} == {"Market data", "Asset catalogs", "Discovery"}
    assert all(c.area in parts for c in TWELVE_DATA.calls)
    assert not [c for c in TWELVE_DATA.calls if c.writes or c.costs]  # it only reads; nothing on it starts a charge
    assert all(u.startswith("https://") for u in urls(APIS)) and TWELVE_DATA.verified == "2026-11-11"
    assert "8 API credits a minute and 800 a day" in TWELVE_DATA.limits


def test_it_asks_nothing_to_say_what_it_learned():
    assert twelvedata.PLUGIN.api_facts() == {}  # the instance holds no run's state
    p = registry.reload()["twelvedata"]
    assert p.apis == APIS and p.interface()["apis"] == ["Twelve Data REST API"]


@pytest.mark.skipif(os.environ.get("LIMINAL_VENDOR_PAGES") != "1", reason="asks Twelve Data's pages (LIMINAL_VENDOR_PAGES=1)")
def test_every_address_on_its_card_answers():
    assert dead_links(APIS) == []
