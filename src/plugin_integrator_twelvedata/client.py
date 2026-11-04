"""Twelve Data's source (api.twelvedata.com): currency pairs' 1-minute bars in windows of three whole
UTC days (4,320 minutes: inside the 5,000 one request answers), on the library's client with the key
as the `apikey` query parameter of every request."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterator

from liminal_libs.errors import NotEntitled, RateLimited, SourceError
from liminal_libs.models import Instrument
from liminal_libs.sources.archive import Archive as _Archive, bounds as _bounds
from liminal_libs.sources.base import Page
from liminal_libs.sources.http import PublicClient

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
DAY_MS = 86_400_000
INTERVAL = "1min"
OUTPUTSIZE = 5000  # the most one request answers (its docs, 2026-11-02)
# Twelve Data's code 400 for a range with nothing in it (a weekend, the time before a pair's history):
# an empty window here, not a failure
NO_DATA = "no data is available"


def utc_ms(text: str) -> int:
    """A Twelve Data time ("2026-10-27 13:05:00", in UTC when asked with timezone=UTC; one with an
    offset is read as it says) in ms, by date arithmetic (no timestamp(): the same on every platform)."""
    t = datetime.fromisoformat(str(text).strip().replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (t - EPOCH) // timedelta(milliseconds=1)


def stamp(ms: int) -> str:
    """A time in ms as Twelve Data's start_date or end_date, in UTC: 2026-10-27T13:05:00."""
    return (EPOCH + timedelta(milliseconds=ms)).strftime("%Y-%m-%dT%H:%M:%S")


def twelvedata_pair(ticker: str) -> str:
    """Twelve Data's name for a currency pair (EUR/USD): the watch row keeps Massive's (C:EURUSD), the
    stored name is EURUSD; EUR/USD and EUR-USD are taken too."""
    t = ticker.strip().upper().removeprefix("C:").replace("/", "").replace("-", "")
    return f"{t[:3]}/{t[3:]}" if len(t) == 6 else t


def stored_pair(ticker: str) -> str:
    """The stored name of a pair: EURUSD."""
    return twelvedata_pair(ticker).replace("/", "")


def checked(body):
    """A Twelve Data answer, or the error it carries raised: a body with status "error" (one that comes
    with its code as the HTTP status is raised by the client's own rules first; this is the 200 form)
    is RateLimited for code 429 (the minute's credits gone: a minute to wait; the day's: the kill's
    own length), NotEntitled for 401 and 403 (the key refused, or the plan), SourceError otherwise
    (a symbol not found, a bad date): that request's failure, never an empty answer, which would
    count as no data there."""
    if isinstance(body, dict) and str(body.get("status") or "").lower() == "error":
        try:
            code = int(body.get("code") or 0)
        except (TypeError, ValueError):
            code = 0
        message = str(body.get("message") or "Twelve Data answered an error")
        if code == 429:
            raise RateLimited(429, message, 60.0 if "minute" in message.lower() else None)
        if code in (401, 403):
            raise NotEntitled(code, message)
        raise SourceError(code, message)
    return body


class TwelveDataClient(PublicClient):
    """The keyed client: the key goes as the `apikey` query parameter of every request (how the API
    takes it), to its host alone (the client follows no link elsewhere), and comes out of any error's
    message (a request that got no answer names the URL asked, query string included)."""

    def __init__(self, base_url: str, key: str | None = None, **kwargs):
        super().__init__(base_url, **kwargs)
        self.key = key

    def get(self, path_or_url: str, params: dict | None = None):
        sent = dict(params or {})
        if self.key:
            sent["apikey"] = self.key
        try:
            return super().get(path_or_url, sent)
        except SourceError as e:
            clean = self.scrubbed(e)
            if clean is e:
                raise
            raise clean from None

    def scrubbed(self, e: SourceError) -> SourceError:
        """The error with the key taken out of its message, when it is in it; else the error itself."""
        if not self.key or self.key not in e.message:
            return e
        message = e.message.replace(self.key, "<key>")
        if isinstance(e, RateLimited):
            return RateLimited(e.status, message, e.retry_after)
        return type(e)(e.status, message)


class TwelveDataSource(_Archive):
    """Twelve Data's forex: currency pairs' 1-minute bars (open, high, low, close; no volume), asked
    for WINDOW_DAYS whole UTC days at a time (4,320 minutes, inside the 5,000 a request answers),
    each window a Page that says what it covered, so a window with nothing in it (a weekend, the
    time before the pair's history) is recorded as looked at. A pair's first minute is asked for
    once a run (/earliest_timestamp, 1 credit), the first time one of its windows comes back empty:
    the windows before it are then answered here without a request. Still trading, so kept up to
    date (archival False), a UTC day at a time (the tier's delay)."""

    name = "twelvedata"
    assets = ("fx",)
    archival = False
    WINDOW_DAYS = 3

    def __init__(self, client: PublicClient, has_key: bool):
        super().__init__(client)
        self.has_key = has_key
        self._pairs: dict[str, dict] | None = None  # /forex_pairs, by Twelve Data's symbol (EUR/USD)
        self._earliest: dict[str, int] = {}  # pair -> ms of its first minute (/earliest_timestamp)

    def serves(self, asset: str) -> bool:
        return asset == "fx" and self.has_key

    def resolutions(self, asset: str) -> tuple[str, ...]:
        return ("minute",) if self.serves(asset) else ()

    def native_frames(self, asset: str) -> tuple[tuple[str, int], ...]:
        return ()  # its hours and days are built here from its minutes

    def _answer(self, path: str, params: dict):
        return checked(self.client.get(path, params))

    def pairs(self) -> dict[str, dict]:
        """Every pair Twelve Data lists (/forex_pairs: one request, kept for the run), by its symbol."""
        if self._pairs is None:
            body = self._answer("/forex_pairs", {})
            rows = body.get("data") if isinstance(body, dict) else body
            if not isinstance(rows, list):
                raise SourceError(0, "unexpected Twelve Data answer for its forex pairs")
            self._pairs = {str(r["symbol"]).strip().upper(): r for r in rows if isinstance(r, dict) and r.get("symbol")}
        return self._pairs

    def covers(self, ticker: str) -> bool:
        """Whether Twelve Data lists the pair (its list of pairs, one request a run)."""
        return twelvedata_pair(ticker) in self.pairs()

    def earliest(self, pair: str) -> int:
        """The ms of the pair's first minute Twelve Data holds (/earliest_timestamp, once a run)."""
        if pair not in self._earliest:
            body = self._answer("/earliest_timestamp", {"symbol": pair, "interval": INTERVAL, "timezone": "UTC"})
            if isinstance(body, dict) and body.get("unix_time") not in (None, ""):
                self._earliest[pair] = int(float(body["unix_time"])) * 1000
            elif isinstance(body, dict) and body.get("datetime"):
                self._earliest[pair] = utc_ms(body["datetime"])
            else:
                raise SourceError(0, f"unexpected Twelve Data answer for the first minute of {pair}")
        return self._earliest[pair]

    def _minutes(self, pair: str, lo: int, hi: int) -> list[dict]:
        """The pair's minutes in [lo, hi) from one request; empty when Twelve Data has none there."""
        params = {"symbol": pair, "interval": INTERVAL, "start_date": stamp(lo), "end_date": stamp(hi),
                  "outputsize": OUTPUTSIZE, "timezone": "UTC"}
        try:
            body = self._answer("/time_series", params)
        except SourceError as e:
            if e.status == 400 and NO_DATA in e.message.lower():
                return []
            raise
        values = body.get("values") if isinstance(body, dict) else None
        if not isinstance(values, list):
            raise SourceError(0, f"unexpected Twelve Data answer for {pair}")
        bars = []
        try:
            for r in values:
                t = utc_ms(r["datetime"])
                if lo <= t < hi:
                    v = r.get("volume")
                    bars.append({"t": t, "o": float(r["open"]), "h": float(r["high"]), "l": float(r["low"]),
                                 "c": float(r["close"]), "v": float(v) if v not in (None, "") else None,
                                 "vw": None, "n": None})
        except (KeyError, TypeError, ValueError) as e:
            raise SourceError(0, f"unexpected Twelve Data value for {pair}: {type(e).__name__}: {e}") from e
        return bars

    def bar_pages(self, ticker, start, end, timespan, multiplier=1, descending=False, asset="fx",
                  limit: int | None = None) -> Iterator[list[dict]]:
        if not self.has_key:
            raise NotEntitled(401, "TWELVEDATA_API_KEY not set; nothing sent")
        if (timespan, multiplier) != ("minute", 1):
            raise NotEntitled(0, "Twelve Data's forex is collected as 1-minute bars here")
        pair = twelvedata_pair(ticker)
        a, b = _bounds(start, end)
        step = self.WINDOW_DAYS * DAY_MS
        windows, t = [], a // DAY_MS * DAY_MS  # whole UTC days
        while t < b:
            windows.append((t, min(b, t + step)))
            t += step
        for lo, hi in (reversed(windows) if descending else windows):
            first = self._earliest.get(pair)
            if first is not None and hi <= first:
                bars = []  # before the pair's first minute: nothing to ask for
            else:
                bars = self._minutes(pair, lo, hi)
                if not bars and first is None:
                    self.earliest(pair)  # a stretch before its history, or a weekend: told apart once
            bars = [x for x in bars if max(lo, a) <= x["t"] < hi]
            bars.sort(key=lambda x: -x["t"] if descending else x["t"])
            yield Page(bars[:limit] if limit else bars, window=(max(lo, a), hi))
            if limit:
                return

    def instrument(self, ticker: str, resolve_exchange: bool = True) -> Instrument:
        """A pair's record from Twelve Data's list of pairs (one request a run): its name from the
        currencies' names, its price's currency the quote's."""
        if not self.has_key:
            raise NotEntitled(401, "TWELVEDATA_API_KEY not set; nothing sent")
        pair = twelvedata_pair(ticker)
        row = self.pairs().get(pair)
        if row is None:
            raise NotEntitled(0, f"Twelve Data lists no pair {pair}")
        base, _, quote = pair.partition("/")
        name = f"{row.get('currency_base') or base} / {row.get('currency_quote') or quote}"
        return Instrument(ticker=pair.replace("/", ""), name=name, currency=quote or "USD",
                          details={**row, "venue": "Twelve Data"})
