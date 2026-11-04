"""The Twelve Data plugin, run against the library installed beside it: its windows of minutes read
from the documented answer, a pair's first minute, the errors its answers carry (and the key kept out
of them), the pairs' records, and the app loading it from this package with its own version and its
facts."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from importlib.metadata import version

import pytest
import requests

from liminal_lib import freshness
from liminal_lib.collector import history_floor
from liminal_lib.config import load_settings
from liminal_lib.errors import NotEntitled, RateLimited, SourceError
from liminal_lib.freshness import Delay
from liminal_lib.sources import feed_profiles, is_archive, markets, provider, rate_window, registry, supports
from liminal_lib.sources.registry import FeedPlugin
from liminal_lib.symbols import resolve

import liminal_plugin_twelvedata as twelvedata
from liminal_plugin_twelvedata import KEY, PER_DAY, PER_RUN, RATE, TIER, api_key
from liminal_plugin_twelvedata.client import (EPOCH, TwelveDataClient, TwelveDataSource, checked, stamp, stored_pair,
                                              twelvedata_pair, utc_ms)

from .conftest import FakeResponse, FakeSession

KEYS = {"TWELVEDATA_API_KEY": "k"}
PAIRS = {"data": [{"symbol": "EUR/USD", "currency_group": "Major", "currency_base": "Euro", "currency_quote": "US Dollar"},
                  {"symbol": "USD/JPY", "currency_group": "Major", "currency_base": "US Dollar",
                   "currency_quote": "Japanese Yen"}],
         "status": "ok"}
NOTHING = {"code": 400, "message": "No data is available on the specified dates. Try setting different start/end dates.",
           "status": "error"}


def _utc(*parts) -> int:
    return (datetime(*parts, tzinfo=timezone.utc) - EPOCH) // timedelta(milliseconds=1)


def _text(ms: int) -> str:
    return (EPOCH + timedelta(milliseconds=ms)).strftime("%Y-%m-%d %H:%M:%S")


class FakeTwelveData:
    """Answers as Twelve Data's reference shows (2026-11-02): /time_series with a bar every six hours
    of the span asked, the end included (newest first, prices as strings, no volume), its code 400
    for a span with nothing in it; /earliest_timestamp with the pair's first minute; /forex_pairs
    with two pairs."""

    def __init__(self, earliest: int = _utc(2010, 1, 4)):
        self.asked = []
        self.requests_made = 0
        self.earliest = earliest

    def get(self, path, params):
        self.asked.append((path, dict(params)))
        self.requests_made += 1
        if path == "/forex_pairs":
            return PAIRS
        if path == "/earliest_timestamp":
            return {"datetime": _text(self.earliest), "unix_time": self.earliest // 1000}
        lo, hi = utc_ms(params["start_date"]), utc_ms(params["end_date"])
        values = []
        t = lo
        while t <= hi:
            if t >= self.earliest:
                values.append({"datetime": _text(t), "open": "1.16170", "high": "1.16200", "low": "1.16150",
                               "close": "1.16180"})
            t += 6 * 3_600_000
        if not values:
            return dict(NOTHING)
        values.reverse()
        return {"meta": {"symbol": params["symbol"], "interval": params["interval"], "currency_base": "Euro",
                         "currency_quote": "US Dollar", "type": "Physical Currency"}, "values": values, "status": "ok"}


def _source(*responses, key="k-1"):
    session = FakeSession(list(responses))
    client = TwelveDataClient("https://x.test", key=key, session=session, sleep=lambda s: None)
    return TwelveDataSource(client, has_key=True), session


def test_a_pair_is_asked_three_whole_days_at_a_time_newest_first():
    client = FakeTwelveData()
    pages = list(TwelveDataSource(client, has_key=True).bar_pages(
        "C:EURUSD", date(2026, 10, 20), date(2026, 10, 27), "minute", descending=True, asset="fx"))
    assert [(p["start_date"], p["end_date"]) for _, p in client.asked] == [
        ("2026-10-26T00:00:00", "2026-10-28T00:00:00"), ("2026-10-23T00:00:00", "2026-10-26T00:00:00"),
        ("2026-10-20T00:00:00", "2026-10-23T00:00:00")]
    assert {path for path, _ in client.asked} == {"/time_series"}
    assert client.asked[0][1] == {"symbol": "EUR/USD", "interval": "1min", "start_date": "2026-10-26T00:00:00",
                                  "end_date": "2026-10-28T00:00:00", "outputsize": 5000, "timezone": "UTC"}
    assert [len(p) for p in pages] == [8, 12, 12]  # a window's end minute is the next window's (end_date read as inclusive)
    first = pages[0]
    assert first[0]["t"] == _utc(2026, 10, 27, 18) and first[-1]["t"] == _utc(2026, 10, 26)  # newest first
    assert (first[0]["o"], first[0]["h"], first[0]["l"], first[0]["c"], first[0]["v"]) == (1.1617, 1.162, 1.1615, 1.1618, None)
    assert first.window == (_utc(2026, 10, 26), _utc(2026, 10, 28))  # each window recorded, empty or not
    assert pages[-1].window == (_utc(2026, 10, 20), _utc(2026, 10, 23))
    assert client.requests_made == 3  # no window came back empty: the pair's first minute was not asked for
    oldest = list(TwelveDataSource(client, has_key=True).bar_pages("EURUSD", date(2026, 10, 20), date(2026, 10, 22), "minute"))
    assert len(oldest) == 1 and len(oldest[0]) == 12 and oldest[0][0]["t"] < oldest[0][-1]["t"]
    assert oldest[0].window == (_utc(2026, 10, 20), _utc(2026, 10, 23))


def test_bars_are_read_from_the_documented_answer_and_the_key_is_a_query_parameter():
    answer = {"meta": {"symbol": "EUR/USD", "interval": "1min", "currency_base": "Euro", "currency_quote": "US Dollar",
                       "type": "Physical Currency"},
              "values": [{"datetime": "2026-10-27 00:01:00", "open": "1.16170", "high": "1.16200", "low": "1.16150",
                          "close": "1.16180"},
                         {"datetime": "2026-10-27 00:00:00", "open": "1.16160", "high": "1.16190", "low": "1.16140",
                          "close": "1.16170"}],
              "status": "ok"}
    src, session = _source(FakeResponse(200, answer))
    page = next(src.bar_pages("C:EURUSD", date(2026, 10, 27), date(2026, 10, 27), "minute", asset="fx"))
    assert [(b["t"], b["o"], b["h"], b["l"], b["c"], b["v"], b["vw"], b["n"]) for b in page] == [
        (_utc(2026, 10, 27), 1.1616, 1.1619, 1.1614, 1.1617, None, None, None),
        (_utc(2026, 10, 27, 0, 1), 1.1617, 1.162, 1.1615, 1.1618, None, None, None)]
    url, params, headers = session.calls[0]
    assert url == "https://x.test/time_series" and params["apikey"] == "k-1" and params["symbol"] == "EUR/USD"
    assert "Authorization" not in headers and headers["User-Agent"].startswith("liminal/")
    assert page.window == (_utc(2026, 10, 27), _utc(2026, 10, 28)) and src.requests_made == 1
    assert utc_ms("2026-10-27 13:05:00") == _utc(2026, 10, 27, 13, 5) == utc_ms("2026-10-27T13:05:00Z")
    assert utc_ms("2026-10-27T09:05:00-04:00") == _utc(2026, 10, 27, 13, 5)
    assert stamp(_utc(2026, 10, 27, 13, 5)) == "2026-10-27T13:05:00"


def test_nothing_before_a_pairs_first_minute_is_asked_for_after_one_look():
    client = FakeTwelveData(earliest=_utc(2026, 10, 24, 12))
    src = TwelveDataSource(client, has_key=True)
    pages = list(src.bar_pages("C:EURUSD", date(2026, 10, 12), date(2026, 10, 27), "minute", descending=True, asset="fx"))
    assert [path for path, _ in client.asked] == ["/time_series", "/time_series", "/time_series", "/earliest_timestamp"]
    assert client.asked[3][1] == {"symbol": "EUR/USD", "interval": "1min", "timezone": "UTC"}
    assert [len(p) for p in pages] == [4, 10, 0, 0, 0, 0]  # two windows with minutes, the empty one asked, three answered here
    assert pages[1][-1]["t"] == _utc(2026, 10, 24, 12)  # the pair's first minute
    assert [p.window for p in pages[2:]] == [(_utc(2026, 10, 21), _utc(2026, 10, 24)), (_utc(2026, 10, 18), _utc(2026, 10, 21)),
                                             (_utc(2026, 10, 15), _utc(2026, 10, 18)), (_utc(2026, 10, 12), _utc(2026, 10, 15))]
    assert client.requests_made == 4
    # the rest of the run knows it: a span before the first minute costs nothing
    before = list(src.bar_pages("C:EURUSD", date(2026, 10, 1), date(2026, 10, 9), "minute", asset="fx"))
    assert client.requests_made == 4 and [len(p) for p in before] == [0, 0, 0]
    assert before[0].window == (_utc(2026, 10, 1), _utc(2026, 10, 4)) and before[-1].window == (_utc(2026, 10, 7), _utc(2026, 10, 10))
    # the window the first minute falls in is asked for whole, and answered from it on
    client2 = FakeTwelveData(earliest=_utc(2026, 10, 24, 12))
    src2 = TwelveDataSource(client2, has_key=True)
    src2._earliest["EUR/USD"] = _utc(2026, 10, 24, 12)
    page = next(src2.bar_pages("C:EURUSD", date(2026, 10, 23), date(2026, 10, 25), "minute", asset="fx"))
    assert client2.requests_made == 1 and page[0]["t"] == _utc(2026, 10, 24, 12) and len(page) == 6


def test_a_range_with_nothing_in_it_is_an_empty_window_and_an_error_is_raised():
    first = {"datetime": "2010-01-04 00:00:00", "unix_time": 1262563200}
    for status in (200, 400):  # the same body in a 200, or with its code as the HTTP status
        src, session = _source(FakeResponse(status, dict(NOTHING)), FakeResponse(200, first))
        page = next(src.bar_pages("C:EURUSD", date(2026, 10, 24), date(2026, 10, 25), "minute", asset="fx"))  # a weekend
        assert page == [] and page.window == (_utc(2026, 10, 24), _utc(2026, 10, 26))
        assert [u for u, _, _ in session.calls] == ["https://x.test/time_series", "https://x.test/earliest_timestamp"]
        assert src._earliest == {"EUR/USD": _utc(2010, 1, 4)}
    for code, kind in ((429, RateLimited), (401, NotEntitled), (403, NotEntitled), (400, SourceError), (500, SourceError)):
        with pytest.raises(kind):
            checked({"code": code, "message": f"error {code}", "status": "error"})
    with pytest.raises(RateLimited) as minute:
        checked({"code": 429, "message": "You have run out of API credits for the current minute. 9 API credits were "
                                         "used, with the current limit being 8. Wait for the next minute", "status": "error"})
    assert (minute.value.status, minute.value.retry_after) == (429, 60.0)
    assert checked({"status": "ok", "values": []}) == {"status": "ok", "values": []} and checked([1]) == [1]
    # through the source: raised, never an empty page
    src, _ = _source(FakeResponse(200, {"code": 429, "message": "You have run out of API credits for the day", "status": "error"}))
    with pytest.raises(RateLimited) as day:
        next(src.bar_pages("C:EURUSD", date(2026, 10, 26), date(2026, 10, 26), "minute"))
    assert day.value.retry_after is None
    src, _ = _source(FakeResponse(200, {"code": 401, "message": "**apikey** parameter is incorrect or not specified",
                                        "status": "error"}))
    with pytest.raises(NotEntitled):
        next(src.bar_pages("C:EURUSD", date(2026, 10, 26), date(2026, 10, 26), "minute"))
    src, _ = _source(FakeResponse(200, {"code": 400, "message": "**symbol** not found: ABC/XYZ", "status": "error"}))
    with pytest.raises(SourceError, match="not found"):
        next(src.bar_pages("C:ABCXYZ", date(2026, 10, 26), date(2026, 10, 26), "minute"))
    for body in ({"status": "ok"}, {"status": "ok", "values": "none"}, [], "x"):
        src, _ = _source(FakeResponse(200, body))
        with pytest.raises(SourceError, match="unexpected"):
            next(src.bar_pages("C:EURUSD", date(2026, 10, 26), date(2026, 10, 26), "minute"))
    src, _ = _source(FakeResponse(200, {"status": "ok", "values": [{"datetime": "2026-10-26 00:00:00", "open": "x"}]}))
    with pytest.raises(SourceError, match="unexpected Twelve Data value"):
        next(src.bar_pages("C:EURUSD", date(2026, 10, 26), date(2026, 10, 26), "minute"))
    # an HTTP 429 with a Retry-After: the client's own retries, then the wait the server asked for
    refused = FakeResponse(429, {"code": 429, "message": "slow down", "status": "error"}, headers={"Retry-After": "7"})
    src, session = _source(*[refused] * 5)
    with pytest.raises(RateLimited) as http:
        next(src.bar_pages("C:EURUSD", date(2026, 10, 26), date(2026, 10, 26), "minute"))
    assert (http.value.status, http.value.retry_after, len(session.calls)) == (429, 7.0, 5)


def test_the_key_never_shows_in_an_error():
    class NoAnswer:
        def get(self, url, params=None, headers=None, timeout=None):
            raise requests.exceptions.ConnectionError(
                f"Max retries exceeded with url: {url}?symbol=EUR%2FUSD&apikey={params['apikey']}")

    client = TwelveDataClient("https://x.test", key="SECRET", session=NoAnswer(), sleep=lambda s: None)
    with pytest.raises(SourceError) as info:
        client.get("/time_series", {"symbol": "EUR/USD"})
    assert "SECRET" not in str(info.value) and "<key>" in info.value.message and "no answer" in info.value.message
    e = RateLimited(429, "slow down", 7.0)
    assert client.scrubbed(e) is e  # an error without the key in it is raised as it is
    assert client.scrubbed(RateLimited(429, "SECRET refused", 7.0)).retry_after == 7.0  # a rate limit's wait kept
    assert client.scrubbed(NotEntitled(403, "the plan for SECRET")).message == "the plan for <key>"
    assert isinstance(client.scrubbed(NotEntitled(403, "SECRET")), NotEntitled)
    session = FakeSession([FakeResponse(200, {"status": "ok", "data": []})])
    keyless = TwelveDataClient("https://x.test", session=session, sleep=lambda s: None)
    keyless.get("/forex_pairs", {})
    assert session.calls[0][1] == {} and keyless.key is None  # no key: none sent


def test_a_pairs_record_and_whether_it_is_listed_come_from_one_request():
    assert twelvedata_pair("C:EURUSD") == "EUR/USD" == twelvedata_pair("eurusd") == twelvedata_pair("EUR/USD")
    assert twelvedata_pair(" eur-usd ") == "EUR/USD" and twelvedata_pair("C:USDJPY") == "USD/JPY"
    assert stored_pair("C:EURUSD") == "EURUSD" and twelvedata_pair("XAU/USD") == "XAU/USD"
    client = FakeTwelveData()
    src = TwelveDataSource(client, has_key=True)
    inst = src.instrument("C:EURUSD")
    assert (inst.ticker, inst.name, inst.currency, inst.primary_exchange, inst.active) == (
        "EURUSD", "Euro / US Dollar", "USD", None, True)
    assert inst.details["venue"] == "Twelve Data" and inst.details["currency_group"] == "Major" and inst.kind == "instrument"
    assert src.instrument("USDJPY", resolve_exchange=False).currency == "JPY"
    assert src.covers("C:EURUSD") and src.covers("usd/jpy") and not src.covers("C:EURGBP")
    assert client.requests_made == 1 and client.asked[0] == ("/forex_pairs", {})  # one request, kept for the run
    with pytest.raises(NotEntitled):
        src.instrument("C:EURGBP")
    assert src.exchanges() == []
    with pytest.raises(NotImplementedError):
        src.listings("XNAS")
    with pytest.raises(NotEntitled):
        TwelveDataSource(FakeTwelveData(), has_key=False).instrument("C:EURUSD")
    src, _ = _source(FakeResponse(200, {"status": "ok"}))
    with pytest.raises(SourceError, match="unexpected"):
        src.covers("C:EURUSD")


def test_only_minutes_and_only_with_a_key():
    client = FakeTwelveData()
    keyed = TwelveDataSource(client, has_key=True)
    with pytest.raises(NotEntitled):
        next(keyed.bar_pages("C:EURUSD", date(2026, 1, 5), date(2026, 1, 5), "hour"))
    with pytest.raises(NotEntitled):
        next(keyed.bar_pages("C:EURUSD", date(2026, 1, 5), date(2026, 1, 5), "minute", 5))
    keyless = TwelveDataSource(client, has_key=False)
    with pytest.raises(NotEntitled):
        next(keyless.bar_pages("C:EURUSD", date(2026, 1, 5), date(2026, 1, 5), "minute"))
    assert client.requests_made == 0 and not keyless.serves("fx") and keyless.resolutions("fx") == ()
    assert keyed.serves("fx") and not keyed.serves("stock") and keyed.resolutions("fx") == ("minute",)
    assert keyed.resolutions("stock") == () and keyed.native_frames("fx") == ()
    assert not keyed.archival and keyed.name == "twelvedata" and keyed.assets == ("fx",)
    assert keyed.is_entitled("minute", "C:EURUSD", "fx") and not keyed.is_entitled("day", "C:EURUSD", "fx")
    page = next(keyed.bar_pages("C:EURUSD", date(2026, 10, 20), date(2026, 10, 27), "minute", descending=True, limit=2))
    assert len(page) == 2 and page[0]["t"] == _utc(2026, 10, 27, 18) and client.requests_made == 1  # the newest page alone
    # exact times (the collector's spans): asked from the day's start, kept from the span's start
    at = datetime(2026, 10, 26, 10, 30, tzinfo=timezone.utc)
    client = FakeTwelveData()
    page = next(TwelveDataSource(client, has_key=True).bar_pages("C:EURUSD", at, at + timedelta(hours=14), "minute"))
    assert [b["t"] for b in page] == [_utc(2026, 10, 26, 12), _utc(2026, 10, 26, 18), _utc(2026, 10, 27)]
    assert page.window == (_utc(2026, 10, 26, 10, 30), _utc(2026, 10, 27, 0, 30))
    assert (client.asked[0][1]["start_date"], client.asked[0][1]["end_date"]) == ("2026-10-26T00:00:00", "2026-10-27T00:30:00")


def test_the_app_loads_it_from_this_package_with_its_own_version():
    registry.reload()
    assert twelvedata.PLUGIN.name == "twelvedata" and not hasattr(twelvedata, "PLUGINS")
    p = provider("twelvedata")
    assert p is not None, dict(registry.errors())
    assert p.origin in {"package: liminal-plugin-twelvedata (liminal_plugin_twelvedata)",
                        "plugins/liminal-plugin-twelvedata (liminal_plugin_twelvedata)"}  # its package, or its checkout in the workspace's plugin directory
    assert p.version == version("liminal-plugin-twelvedata") and p.api == "2.0"
    assert registry.api_refusal(p.api) is None and twelvedata.PLUGIN.version == ""
    assert not [why for where, why in registry.errors() if "twelvedata" in where or "twelvedata" in why]
    row = {r["name"]: r for r in registry.menu()}["twelvedata"]
    assert (row["version"], row["api"], row["archive"], row["assets"]) == (version("liminal-plugin-twelvedata"), "2.0", False, ["fx"])
    assert [k["name"] for k in row["keys"]] == [KEY] and row["keys"][0]["secret"] and row["feeds"] == []
    assert registry.plugin_feeds("twelvedata") == ["twelvedata"] and registry.plugin_of("twelvedata") == "twelvedata"
    assert KEY in registry.variables()


def test_it_keeps_its_facts(monkeypatch):
    registry.reload()
    s = load_settings(env=KEYS, env_file=None)
    view = s.for_source("twelvedata")
    assert (view.tier, view.max_requests_per_run, view.max_requests_per_day) == (TIER, PER_RUN, PER_DAY)
    assert rate_window("twelvedata", s) == RATE == (8, 62.0)  # the plan's 8 credits a minute, kept in 62 s
    assert PER_RUN <= PER_DAY <= 800 and TIER.requests_per_minute == 8 and TIER.history_years == 2
    assert not is_archive("twelvedata") and markets("twelvedata", s) == {"fx": "twelvedata"}
    assert supports("twelvedata", resolve("EURUSD")) and supports("twelvedata", resolve("EUR/USD"))
    assert supports("twelvedata", resolve("C:USDJPY")) and supports("twelvedata", resolve("JPYUSD"))  # shown inverted, asked as USD/JPY
    assert not supports("twelvedata", resolve("AAPL")) and not supports("twelvedata", resolve("2330.TW"))
    assert not supports("twelvedata", resolve("BTCUSD")) and not supports("twelvedata", resolve("I:VIX"))
    assert not supports("twelvedata", resolve("NQ1!"))
    assert history_floor(TIER, date(2026, 11, 2), "fx") == date(2024, 11, 3)  # two years, a day inside
    assert freshness.plan_delay(TIER, "fx").kind == "utc_day"  # the library knows the tier by name: whole UTC days
    profiles = feed_profiles(s)
    assert profiles["twelvedata"].venues == {"fx": "twelvedata"} and profiles["twelvedata"].assets == frozenset({"fx"})
    assert profiles["twelvedata"].tier == TIER and profiles["twelvedata"].capacity == 800.0
    assert not feed_profiles(load_settings(env={}, env_file=None))["twelvedata"].assets  # no key: serves nothing
    p = provider("twelvedata")
    assert (p.kind, p.archival, p.part_of, p.account, p.exchanges, p.title) == ("vendor", False, "", "", frozenset(), "Twelve Data")
    assert p.provides == {"fx": ("minute",)} and p.request_bars("minute") == 5000 and p.resolutions_for(TIER, "fx") == ("minute",)
    assert p.keys_set(s) is True and p.keys_set(load_settings(env={}, env_file=None)) is False and p.missing_keys_note
    assert api_key(load_settings(env={KEY: " k\n"}, env_file=None)) == "k"  # pasted with a newline
    assert api_key(load_settings(env={}, env_file=None)) is None
    # the window and the day's cap are held under its name, with its key, for the whole machine
    held = []
    monkeypatch.setattr(twelvedata, "limiter", lambda name, st, key: held.append(("window", name, key)))
    monkeypatch.setattr(twelvedata, "machine_caps", lambda client, name, st, key: held.append(("day", name, key)) or client)
    source = twelvedata.PLUGIN.build(s, 5)
    assert held == [("window", "twelvedata", "k"), ("day", "twelvedata", "k")] and source.name == "twelvedata" and source.has_key
    assert source.client.key == "k" and source.client.request_budget == 5 and source.client.base_url == "https://api.twelvedata.com"
    assert not twelvedata.PLUGIN.build(load_settings(env={}, env_file=None), 5).has_key


def test_it_is_a_class_on_plugin_api_2_0():
    """The plugin is an instance of its class (plugin API 2.0, liminal-lib 1.3.0): what it declares its class
    attributes, what it does its methods; the registry loads it as that class."""
    assert isinstance(twelvedata.PLUGIN, twelvedata.TwelveDataPlugin) and isinstance(twelvedata.PLUGIN, FeedPlugin)
    assert twelvedata.PLUGIN.api == "2.0" and not twelvedata.PLUGIN.is_record
    p = registry.reload()["twelvedata"]
    assert type(p) is twelvedata.TwelveDataPlugin and p.api == "2.0" and p.name == "twelvedata"
    # the hooks it gives, the rest the contract's defaults
    assert p.gives("build") and p.gives("has_keys") and p.gives("rate") and p.gives("markets")
    assert not p.gives("view") and not p.gives("scan") and not p.gives("carries") and not p.has_settings
    # it declares its plan's publication delay itself, the library's row for it still in place
    assert p.delays == {"twelvedata-free": {"fx": Delay("utc_day")}}
    assert p.delays["twelvedata-free"] == freshness.PLAN_DELAYS["twelvedata-free"]
