# liminal-plugin-twelvedata

Twelve Data for [Liminal](https://github.com/pcxmac-dev/liminal-app): currency pairs' 1-minute bars
(`EURUSD`, `USDJPY`, `XAUUSD`: open, high, low, close, no volume) from Twelve Data's `/time_series`, on
a free account key. One feed, `twelvedata`, its own market: its data is Twelve Data's own, not a copy of
another feed's. It is live: pairs are kept up to date a whole UTC day at a time (the plan's publication
delay), two years back (the free plan's floor here), and no earlier than the first minute Twelve Data
holds of a pair (`/earliest_timestamp`, asked once a run when a window comes back empty).

The free plan (Basic) allows 8 API credits a minute and 800 a day; a request of one symbol is 1 credit.
The feed keeps 8 requests in 62 seconds, 100 a run and 800 a day, counted for the whole machine. Each
request asks for three whole UTC days of minutes (4,320, inside the 5,000 one request answers), so a
pair's two years take about 240 requests, and a day's upkeep one.

A Liminal provider plugin released on its own. The app finds it through the entry point group
`liminal.providers` and lists it on the Plugins view and in `liminal plugins`
as `package: liminal-plugin-twelvedata`, with this package's version.

## Install

Into the app's environment, from the app's folder:

```powershell
.venv\Scripts\python.exe -m pip install "liminal-plugin-twelvedata @ git+https://github.com/pcxmac-dev/liminal-plugin-twelvedata@v0.2.0"
```

or with the app's plugins (`pip install -e ".[plugins]"` in liminal-app). The app loads it on its next
start.

## Key

`TWELVEDATA_API_KEY`: a free twelvedata.com account's API key (made on its dashboard). Save it from the
app's Plugins view or with `tools/set-key.ps1`: it is read from your user environment variables only,
never written to a file, and sent to api.twelvedata.com alone, as the `apikey` query parameter. Without
it the feed serves nothing and sends nothing.

## Compatibility

It is written for plugin API 2.0, the class contract (`PLUGIN`, an instance of `TwelveDataPlugin`, a
`FeedPlugin`; liminal-lib 1.3.0 or later: `sources.http`, `sources.archive`, `sources.base.Page`, and the
plan's publication delay the feed declares itself, `delays`: `twelvedata-free`, whole UTC days). An app
offering 2.0 or a later 2.x loads it; an app of another major leaves it out and says why on the Plugins
view.

## Develop

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install "liminal-lib @ git+https://github.com/pcxmac-dev/liminal-lib@main"
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m pytest -q
```

Tests never send requests (a fake client answers, shaped as Twelve Data's reference shows) and never
read your keys. What the reference confirmed and what it did not is in the module's docstring.
