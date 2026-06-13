"""Ticker display names and concise identity labels."""
from __future__ import annotations

from .universe import COUNTRIES, CRYPTO, FACTORS, MEGA_CAP_STOCKS, THEMES, US_INDUSTRIES, US_SECTORS


TICKER_DISPLAY_NAMES = {
    **dict(zip(US_SECTORS, [
        "Technology sector", "Financials sector", "Energy sector", "Health care sector",
        "Industrials sector", "Consumer discretionary sector", "Consumer staples sector",
        "Utilities sector", "Materials sector", "Real estate sector", "Communication services sector",
    ])),
    **dict(zip(US_INDUSTRIES, [
        "Semiconductors", "Semiconductors", "Software", "Medical devices", "Healthcare providers",
        "Regional banks", "Insurance", "Home construction", "Homebuilders", "Retail",
        "Oil and gas exploration", "Oil services", "Gold miners", "China internet", "Internet",
        "Aerospace and defense", "Airlines", "Biotech", "Biotech",
    ])),
    **dict(zip(COUNTRIES, [
        "All-world ex-US", "Emerging markets", "Developed ex-US", "Emerging markets",
        "Japan", "Germany", "United Kingdom", "India", "China", "China large-cap",
        "Brazil", "Australia", "Canada", "Mexico", "South Africa", "South Korea",
        "Taiwan", "Singapore", "Indonesia", "Saudi Arabia",
    ])),
    **dict(zip(FACTORS, [
        "Momentum factor", "Quality factor", "Minimum volatility factor", "Value factor",
        "Small-size factor", "Large-cap growth factor", "Large-cap value factor",
        "Small-cap factor", "Mid-cap factor", "Large-cap core factor",
    ])),
    **dict(zip(THEMES, [
        "Innovation theme", "Cybersecurity theme", "Agribusiness theme", "Uranium theme",
        "Lithium and batteries theme", "Solar theme", "Clean energy theme", "Robotics and AI theme",
    ])),
    **dict(zip(CRYPTO, ["Bitcoin futures", "Spot bitcoin", "Ethereum exposure"])),
    **dict(zip(MEGA_CAP_STOCKS, [
        "NVIDIA", "Apple", "Microsoft", "Amazon", "Alphabet", "Meta Platforms", "Tesla",
    ])),
}


def ticker_display_name(ticker: str) -> str:
    normalized = str(ticker or "").strip().upper()
    return TICKER_DISPLAY_NAMES.get(normalized, normalized)


def ticker_display_label(ticker: str) -> str:
    normalized = str(ticker or "").strip().upper()
    name = ticker_display_name(normalized)
    return normalized if not name or name == normalized else f"{normalized} | {name}"
