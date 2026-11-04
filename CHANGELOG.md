# Changelog

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
