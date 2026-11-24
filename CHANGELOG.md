# Changelog

## 0.3.1 (2026-11-24)

The review of 2026-11-21 (Monday list item 26), a P1: the key is taken out of the vendor's own words in an answer (`unkeyed`) before any of them become an error's
message. The scrub covered only errors of the transport; a 200 answer's error message reached the run's log and the kill's reason as it came.

## 0.3.0 (2026-11-11)

Its API on its page (plugin API 2.2, liminal-libs 1.49.0; the user: "each plugin should reflect the the API its
attached to, and present links that provide documentation, the plugin interface should more or less contain what it
already has, BUT, it should also expose more of what the API is about"). The feed declares a card (`apis`, from
`apis.py`: `TWELVE_DATA`), Twelve Data's REST API as its pages said on 2026-11-11: what it is and for, its address,
the key's form, its limits (Basic: 8 API credits a minute and 800 a day) and plans, and its pages (the documentation,
errors, introduction, API credits, pricing, the status page, the news and changelog, the OpenAPI specification, the
API keys page, the Python SDK, the help center, the terms). Its 15 parts, the documentation's sections, say which 3
are used here; its 18 calls the 3 made here (`/time_series`, `/forex_pairs`, `/earliest_timestamp`), each with what
for and what it costs in credits, beside the notable others. `API` is the card's base. `signup` is the API keys
page's address (a link on the Plugins view). `api_facts` says nothing (the contract's): the plugin holds no run's
state. Tests: the card names every call the plugin makes and none it does not; every address on it answers (with
`LIMINAL_VENDOR_PAGES=1`). Nothing it fetches changed. Requires liminal-libs 1.49.0.

## 0.2.0 (2026-11-03)

Renamed `plugin-integrator-twelvedata` (the package `plugin_integrator_twelvedata`; it was `liminal-plugin-twelvedata`) on 2026-11-03: the naming by system (plugins are `plugin-<app>-<name>`), on liminal-libs 1.4.0 (`liminal_libs`, the library renamed with it).

The plugin is a class on plugin API 2.0 (the class contract, liminal-libs 1.3.0; the user: "all the plugins under
liminal should basically follow inheritance/oop paradigm"): `PLUGIN` is an instance of `TwelveDataPlugin`, a
`FeedPlugin`, what it declares its class attributes (its key, its free plan and caps, its own market ...) and what
it does its methods (`build`, `has_keys`, `rate`, `markets`). It declares its plan's publication delay itself
(`delays`: `twelvedata-free`, whole UTC days; the library's row stays). Every fact, limit and string is as in
1.0.0. Its version is the release's, 0.2.0, as every Liminal plugin's on `release/0.2.0`; requires liminal-libs
1.3.0.

## 1.0.0 (2026-11-02)

The first release (the user: "if new sources, create a new plugin"; Twelve Data is the FX addition): one feed,
`twelvedata`, currency pairs' 1-minute bars from Twelve Data's `/time_series` on a free account key
(`TWELVEDATA_API_KEY`, sent as the `apikey` query parameter), its own market (`twelvedata`), kept up to date a
UTC day at a time. Windows of three whole UTC days (4,320 minutes, inside the 5,000 a request answers), each
recorded as looked at even when empty; a pair's first minute from `/earliest_timestamp` (asked once a run, the
first time a window of the pair comes back empty), the windows before it answered without a request; a pair's
record and whether it is listed from `/forex_pairs` (one request a run). The free plan's limits kept: 8 requests
in 62 seconds, 100 a run, 800 a day on the whole machine, two years of history. A 200 answer carrying an error is
raised (code 429 rate limited, 401 and 403 not entitled, others that request's failure), never read as no data.
Plugin API 1.12; requires liminal-libs 1.2.0.
