"""What Twelve Data's plugin attaches to (plugin API 2.2, liminal_libs.sources.apis): Twelve Data's REST API, as its
pages said on 2026-11-11 (the documentation at twelvedata.com/docs, each section's page read that day with the credits
each call costs; its pricing page; its index, twelvedata.com/llms.txt, for the status page, the changelog and the
specification).

The user, 2026-11-11: "each plugin should reflect the the API its attached to, and present links that provide
documentation, the plugin interface should more or less contain what it already has, BUT, it should also expose more of
what the API is about". So every part of the API is named (`areas`: the documentation's sections), each said used here
or not, and the calls the plugin makes (`used`) beside the notable ones it does not, each with its credits."""
from __future__ import annotations

from liminal_libs.sources.apis import Api, Area, Call, Link

API = "https://api.twelvedata.com"
DOCS = "https://twelvedata.com/docs"
KEYS = "https://twelvedata.com/account/api-keys"  # where the key is (the plugin's `signup`)
MARKET, CATALOGS, DISCOVERY, MARKETS = "Market data", "Asset catalogs", "Discovery", "Markets"


def _docs(path: str = "") -> str:
    return f"{DOCS}/{path}" if path else DOCS


TWELVE_DATA = Api(
    name="Twelve Data REST API",
    maker="Twelve Data",
    about=("Twelve Data's REST API serves stocks, ETFs, funds, forex, crypto, commodities and bonds worldwide: time "
           "series from a minute to a month, quotes and prices, reference catalogs, fundamentals, analysis, regulatory "
           "data and about 100 technical indicators, with a WebSocket for live prices. Every request costs API credits (most "
           "a credit a symbol), counted a minute and, on the free plan, a day."),
    kind="rest",
    base=API,
    auth=("an API key (the account's API keys page), sent as the apikey query parameter (the plugin's way; an "
          "Authorization: apikey header is the one its docs recommend): the plugin takes it out of every error's text"),
    limits=("Basic (free): 8 API credits a minute and 800 a day; time_series, earliest_timestamp and forex_pairs cost 1 "
            "credit a request (a symbol); a paid plan has more credits a minute and no daily cap; over a limit: code "
            "429. Up to 5,000 values a time series request"),
    costs=("Basic is free; Grow, Pro, Ultra and Enterprise are sold by credits a minute, markets and WebSocket credits "
           "(its pricing page); the exchanges' data add-ons are sold apart"),
    links=(
        Link("Documentation", _docs(), "docs"),
        Link("Errors", _docs("introduction/errors"), "reference"),
        Link("Introduction", _docs("introduction"), "guide"),
        Link("API credits", "https://support.twelvedata.com/en/articles/5615854-credits", "limits"),
        Link("Pricing", "https://twelvedata.com/pricing", "pricing"),
        Link("System status", "https://twelvedata.isitup.cloud/", "status"),
        Link("News and changelog", "https://twelvedata.com/news", "changelog"),
        Link("OpenAPI specification", f"{API}/doc/swagger/openapi.json", "spec"),
        Link("API keys", KEYS, "console"),
        Link("Python SDK", "https://github.com/twelvedata/twelvedata-python", "sdk"),
        Link("Help center", "https://support.twelvedata.com/", "guide"),
        Link("Terms of use", "https://twelvedata.com/terms", "terms"),
    ),
    areas=(
        Area(MARKET, "time series, cross rates, quotes, the latest and end-of-day prices, market movers",
             _docs("market-data"),
             covered="currency pairs' 1-minute bars (time_series, three whole UTC days a request, in UTC)"),
        Area(CATALOGS, "the lists of stocks, forex pairs, crypto pairs, ETFs, funds, commodities and bonds",
             _docs("asset-catalogs"), covered="the forex pairs it lists (forex_pairs, once a run)"),
        Area(DISCOVERY, "symbol search, cross listings, a symbol's earliest timestamp", _docs("discovery"),
             covered="a pair's first minute (earliest_timestamp), asked once when a window comes back empty"),
        Area(MARKETS, "the exchanges, their schedules, the crypto exchanges, the markets' state", _docs("markets")),
        Area("Supporting metadata", "countries, instrument types, the technical indicators' interface",
             _docs("supporting-metadata")),
        Area("Currencies", "exchange rates and currency conversion", _docs("currencies")),
        Area("ETFs", "ETFs' directory, families, types, and their summary, performance, risk and composition",
             _docs("etfs")),
        Area("Mutual funds", "mutual funds' directory, families, types, and their summary, performance, risk, ratings, "
             "composition, purchase information and sustainability", _docs("mutual-funds")),
        Area("Money market funds", "money market funds' directory and data", _docs("money-market-funds")),
        Area("Fundamentals", "logos, profiles, dividends, splits, earnings, statistics, press releases, statements, "
             "calendars", _docs("fundamentals")),
        Area("Analysis", "earnings, revenue and growth estimates, EPS trends and revisions, recommendations, price "
             "targets, analyst ratings", _docs("analysis")),
        Area("Regulatory", "EDGAR filings, insider transactions, institutional, fund and direct holders, tax "
             "information, sanctions", _docs("regulatory")),
        Area("Technical indicators", "about 100 indicators computed by Twelve Data", _docs("technical-indicators")),
        Area("WebSocket", "live prices pushed over a WebSocket (wss://ws.twelvedata.com), a WebSocket credit a symbol: "
             "Pro and up (Basic and Grow: a trial of 8 symbols)", _docs("websocket")),
        Area("Advanced", "batch requests, the account's API usage", _docs("advanced")),
    ),
    calls=(
        Call("GET /time_series", "a symbol's bars at an interval (1min to 1month), up to 5,000 a request; 1 credit a "
             "symbol", MARKET,
             used="a pair's 1-minute bars, three whole UTC days a request (outputsize 5,000, timezone UTC)",
             docs=_docs("market-data/time-series")),
        Call("GET /forex_pairs", "the forex pairs it lists, with their currencies; 1 credit", CATALOGS,
             used="whether it lists a pair, and its currencies' names (once a run)",
             docs=_docs("asset-catalogs/forex-pairs-list")),
        Call("GET /earliest_timestamp", "a symbol's first datetime at an interval; 1 credit", DISCOVERY,
             used="a pair's first minute, once a run, when a window comes back empty",
             docs=_docs("discovery/earliest-timestamp")),
        Call("GET /time_series/cross", "a cross rate's series; 5 credits", MARKET,
             docs=_docs("market-data/time-series-cross")),
        Call("GET /quote", "a symbol's latest quote; 1 credit a symbol", MARKET, docs=_docs("market-data/quote")),
        Call("GET /price", "a symbol's latest price; 1 credit a symbol", MARKET, docs=_docs("market-data/real-time-price")),
        Call("GET /eod", "a symbol's end-of-day price; 1 credit a symbol", MARKET,
             docs=_docs("market-data/end-of-day-price")),
        Call("GET /market_movers/{market}", "a market's top gainers and losers; 100 credits", MARKET,
             docs=_docs("market-data/market-movers")),
        Call("GET /stocks", "the stocks it lists; 1 credit", CATALOGS, docs=_docs("asset-catalogs/stocks-list")),
        Call("GET /cryptocurrencies", "the crypto pairs it lists; 1 credit", CATALOGS,
             docs=_docs("asset-catalogs/cryptocurrencies-list")),
        Call("GET /symbol_search", "symbols matching a ticker, ISIN or FIGI; 1 credit", DISCOVERY,
             docs=_docs("discovery/symbol-search")),
        Call("GET /cross_listings", "a symbol's other listings (Grow and up); 40 credits", DISCOVERY,
             docs=_docs("discovery/cross-listings")),
        Call("GET /exchanges", "the exchanges; 1 credit", MARKETS, docs=_docs("markets/exchanges")),
        Call("GET /market_state", "whether each market is open; 1 credit", MARKETS, docs=_docs("markets/market-state")),
        Call("GET /exchange_rate", "a currency pair's latest rate; 1 credit a symbol", "Currencies",
             docs=_docs("currencies/exchange-rate")),
        Call("GET /currency_conversion", "an amount converted at the latest rate; 1 credit a symbol", "Currencies",
             docs=_docs("currencies/currency-conversion")),
        Call("GET /api_usage", "the requests made this minute and today, and the plan's limits; 1 credit", "Advanced",
             docs=_docs("advanced/api-usage")),
        Call("subscribe (WebSocket /v1/quotes/price)", "live prices of the symbols subscribed; a WebSocket credit a "
             "symbol", "WebSocket", docs=_docs("websocket/websocket-getting-started")),
    ),
    verified="2026-11-11",
)

APIS = (TWELVE_DATA,)
