"""The investable universe, grouped by asset class.

Each class is ranked independently in the dashboard, then merged.
Source of truth for these lists is `sector-rotation-methodology.md` §3.
"""

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
    "TAN",   # Solar
    "ICLN",  # Clean energy
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
}

ALL_TICKERS = (
    US_SECTORS
    + US_INDUSTRIES
    + COUNTRIES
    + FACTORS
    + DEFENSIVES
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
}
