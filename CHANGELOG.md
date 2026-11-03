# Changelog

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
Plugin API 1.12; requires liminal-lib 1.2.0.
