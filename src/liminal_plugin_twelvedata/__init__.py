"""Twelve Data (twelvedata.com) for Liminal: currency pairs' 1-minute bars with a free account key
(its Basic plan: 8 API credits a minute, 800 a day), two years back, kept up to date a UTC day at a
time.

A Liminal plugin released on its own (liminal_lib.sources.registry: Provider), registered under the
entry point group `liminal.providers` as `twelvedata`: one feed, `twelvedata`, a forex feed on its own
key and limits like Tiingo's forex feed, its own market (`twelvedata`: its data is Twelve Data's own,
not a copy of another feed's). It relies on plugin API 1.12 and nothing of the app outside it; its
version is this distribution's (pyproject.toml), so the record's version is left empty.

What Twelve Data's public reference says (twelvedata.com/docs/market-data/time-series, read
2026-11-02, the one page read while building this; no keyed request was sent): `interval=1min`;
`outputsize` 1 to 5,000 (30 by default without dates, the maximum with them); the values come newest
first (`order` defaults to desc); `timezone` defaults to the exchange's and takes `UTC`; `start_date`
and `end_date` as `2006-01-02` or `2006-01-02T15:04:05` (whether `end_date` is inclusive is not said:
the source asks to a window's end and keeps what is before it); each value has `datetime`
("2021-09-16 15:59:00"), `open`, `high`, `low`, `close` as strings (`volume` for stocks); `status`
is "ok"; a request of one symbol costs 1 credit; the key goes as the `apikey` query parameter.
Not confirmed there (from the API as known before; the first real answers on a key will tell):
forex values carry no volume; `/earliest_timestamp` answers `datetime` and `unix_time`;
`/forex_pairs` answers `data` rows with `symbol`, `currency_group`, `currency_base`,
`currency_quote`; an error is a body with `code`, `message` and `status` "error" (handled whether
it comes with HTTP 200 or with its code as the HTTP status), and a range with nothing in it a
code 400 "No data is available on the specified dates" (read as an empty window)."""
from __future__ import annotations

from liminal_lib.config import Tier
from liminal_lib.sources.registry import KeyVar, Provider, limiter, machine_caps
from .client import TwelveDataClient, TwelveDataSource

API = "https://api.twelvedata.com"
KEY = "TWELVEDATA_API_KEY"  # a free twelvedata.com account's API key, a user environment variable (the Plugins view, the key script)
# Its free plan, Basic (twelvedata.com/pricing, 2026-11-02): 8 API credits a minute and 800 a day; a
# time_series request of one symbol is 1 credit (its docs), so requests are counted as credits here.
# The window kept is the plan's 8 in 62 seconds (two seconds' margin, as registry.minute_window keeps
# for a few a minute); a run takes 100 at most (about 13 minutes at 8 a minute, so most of the day's
# 800 is left for the later runs); the day's cap is the plan's 800, counted for the whole machine.
# Its history: two years back (the plan's floor here, freshness.PLAN_DELAYS knowing the tier's name:
# whole UTC days), and no earlier than each pair's first minute, which the source asks for
# (/earliest_timestamp) the first time one of the pair's windows comes back empty.
TIER = Tier("twelvedata-free", requests_per_minute=8, history_years=2)
PER_RUN, PER_DAY = 100, 800
RATE = (8, 62.0)


def api_key(settings) -> str | None:
    """The Twelve Data key among the settings' plugin variables (Settings.env), spaces around it taken
    off (one pasted with a newline would make every request fail), or None."""
    return (settings.env.get(KEY) or "").strip() or None


def build(settings, request_budget):
    key = api_key(settings)
    client = TwelveDataClient(API, key=key, request_budget=request_budget,
                              rate_limiter=limiter("twelvedata", settings, key))
    return TwelveDataSource(machine_caps(client, "twelvedata", settings, key), has_key=bool(key))


PLUGIN = Provider(
    api="1.12",  # the contract it needs (sources.http, sources.archive, sources.base.Page); its version: the distribution's
    name="twelvedata", title="Twelve Data", build=build, assets=frozenset({"fx"}), order=120,
    about="currency pairs' 1-minute bars from Twelve Data, two years back (a free account key: 8 requests a minute, 800 a day)",
    keys=(KeyVar(KEY),), signup="twelvedata.com: a free account's API key (its dashboard)",
    kind="vendor", archival=False, tier=TIER, per_run=PER_RUN, per_day=PER_DAY,
    limits="Basic (free): 8 API credits a minute, 800 a day; a time_series request of one symbol is 1 credit",
    provides={"fx": ("minute",)}, per_request={"minute": 5000},  # outputsize's most: up to 5,000 minutes a request
    missing_keys_note="key not set: Twelve Data's forex comes with TWELVEDATA_API_KEY",
    has_keys=lambda s: bool(api_key(s)),
    rate=lambda settings: RATE,  # the plan's 8 a minute, kept in 62 s
    markets=lambda settings: {"fx": "twelvedata"},  # its own market: its data is its own, not a copy of another feed's
)
