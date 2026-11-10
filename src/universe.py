"""The investable universe, grouped by asset class.

Each class is ranked independently in the dashboard, then merged.
Source of truth for these lists is `sector-rotation-methodology.md` §3.
"""
import json
from pathlib import Path

US_SECTORS = [
    "XLK",   # Technology
    "XLF",   # Financials
    "XLE",   # Energy
    "XLV",   # Health Care
    "XLI",   # Industrials
    "XLY",   # Consumer Discretionary
    "XLP",   # Consumer Staples
    "XLU",   # Utilities
    "XLB",   # Materials
    "XLRE",  # Real Estate
    "XLC",   # Communication Services
]

US_INDUSTRIES = [
    "SOXX",  # Semiconductors (iShares)
    "SMH",   # Semiconductors (VanEck)
    "IGV",   # Software
    "IHI",   # Medical devices
    "IHF",   # Healthcare providers
    "KRE",   # Regional banks
    "KIE",   # Insurance
    "ITB",   # Home construction
    "XHB",   # Homebuilders (SPDR)
    "XRT",   # Retail
    "XOP",   # Oil & gas E&P
    "OIH",   # Oil services
    "GDX",   # Gold miners
    "KWEB",  # China internet
    "FDN",   # Internet
    "ITA",   # Aerospace & defense
    "JETS",  # Airlines
    "IBB",   # Biotech (iShares)
    "XBI",   # Biotech (SPDR)
]

COUNTRIES = [
    "VEU",   # FTSE All-World ex-US
    "VWO",   # Emerging markets (Vanguard)
    "EFA",   # EAFE developed
    "EEM",   # Emerging markets (iShares)
    "EWJ",   # Japan
    "EWG",   # Germany
    "EWU",   # UK
    "INDA",  # India
    "MCHI",  # China
    "FXI",   # China large-cap
    "EWZ",   # Brazil
    "EWA",   # Australia
    "EWC",   # Canada
    "EWW",   # Mexico
    "EZA",   # South Africa
    "EWY",   # South Korea
    "EWT",   # Taiwan
    "EWS",   # Singapore
    "EIDO",  # Indonesia
    "KSA",   # Saudi Arabia
]

FACTORS = [
    "MTUM",  # Momentum
    "QUAL",  # Quality
    "USMV",  # Min volatility
    "VLUE",  # Value
    "SIZE",  # Size (small-cap tilt)
    "IWF",   # Russell 1000 Growth
    "IWD",   # Russell 1000 Value
    "IJR",   # S&P 600 small-cap
    "IJH",   # S&P 400 mid-cap
    "IWB",   # Russell 1000
]

THEMES = [
    "ARKK",  # Disruptive innovation
    "HACK",  # Cybersecurity
    "MOO",   # Agribusiness
    "URA",   # Uranium
    "LIT",   # Lithium and battery technology
    "TAN",   # Solar
    "ICLN",  # Clean energy
    "BOTZ",  # Robotics and artificial intelligence
]

CRYPTO = [
    "BITO",  # Bitcoin futures
    "IBIT",  # Spot bitcoin
    "ETHE",  # Ethereum exposure
]

MEGA_CAP_STOCKS = [
    "NVDA",   # NVIDIA
    "AAPL",   # Apple
    "MSFT",   # Microsoft
    "AMZN",   # Amazon
    "GOOGL",  # Alphabet
    "META",   # Meta Platforms
    "TSLA",   # Tesla
]

DEFENSIVES = ["TLT", "IEF", "GLD", "UUP", "DBC"]  # for risk-off pivot

BENCH = {
    "US": "SPY",
    "GLOBAL": "ACWI",
    "TBILL": "BIL",
}

UNIVERSE_BY_CLASS = {
    "US Sectors":   US_SECTORS,
    "US Industries": US_INDUSTRIES,
    "Countries":    COUNTRIES,
    "Factors":      FACTORS,
    "Themes":       THEMES,
    "Crypto":       CRYPTO,
    "Mega-Cap Stocks": MEGA_CAP_STOCKS,
}

SCORED_TICKERS = (
    US_SECTORS
    + US_INDUSTRIES
    + COUNTRIES
    + FACTORS
    + THEMES
    + CRYPTO
    + MEGA_CAP_STOCKS
    + DEFENSIVES
)

ALL_TICKERS = (
    SCORED_TICKERS
    + list(BENCH.values())
)


def class_of(ticker: str) -> str:
    """Return the universe class for a ticker, or 'Other'."""
    for name, tickers in UNIVERSE_BY_CLASS.items():
        if ticker in tickers:
            return name
    if ticker in BENCH.values():
        return "Benchmark"
    if ticker in DEFENSIVES:
        return "Defensive"
    return "Other"


# Top-N target holdings per class (drives the ranking output)
TOP_N = {
    "US Sectors":   4,
    "US Industries": 3,
    "Countries":    3,
    "Factors":      2,
    "Themes":       3,
    "Crypto":       1,
    "Mega-Cap Stocks": 3,
}


# --- User names -------------------------------------------------------------
# Tickers from saved portfolios and watchlists are fetched and scored as their
# own class, so the fixed methodology lists (and calibration baselines) stay
# unchanged. The class has no top-N target, so these names are never selected.
USER_CLASS = "User Names"
_SAVED_INPUTS_PATH = Path(__file__).resolve().parents[1] / "data" / "saved_inputs.json"


def user_tickers(path: Path = _SAVED_INPUTS_PATH) -> list[str]:
    """Unique tickers from saved portfolios and watchlists (empty if unreadable)."""
    try:
        items = json.loads(Path(path).read_text(encoding="utf-8")).get("items", [])
    except (OSError, ValueError):
        return []
    seen: list[str] = []
    for item in items:
        if item.get("kind") == "watchlist":
            raw = item.get("tickers") or []
        elif item.get("kind") == "portfolio":
            raw = [h.get("ticker") for h in (item.get("holdings") or []) if isinstance(h, dict)]
        else:
            raw = []
        for ticker in raw:
            ticker = str(ticker or "").strip().upper()
            if ticker and ticker not in seen:
                seen.append(ticker)
    return seen


def user_class_overrides(path: Path = _SAVED_INPUTS_PATH) -> dict[str, str]:
    """Map user tickers that are not already in a methodology class to USER_CLASS."""
    return {t: USER_CLASS for t in user_tickers(path) if class_of(t) == "Other"}

