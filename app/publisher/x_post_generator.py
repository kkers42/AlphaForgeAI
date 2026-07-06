"""
X post generator — produces 3 post variants from evidence + article.

Templates follow issue #92:
  - Signal Card:  structured data block with AlphaForge signal
  - Hook Post:    narrative contrast hook, then signal data
  - Risk-Aware:   directional claim + explicit risk factors

All variants use 0-2 hashtags and natural crypto keywords.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from app.publisher.evidence_builder import Evidence, AlphaForgeSignal


@dataclass
class XPostSet:
    signal_card: str
    hook: str
    risk_aware: str

    def all_variants(self) -> list[str]:
        return [self.signal_card, self.hook, self.risk_aware]

    def to_dict(self) -> dict:
        return {
            "signal_card": self.signal_card,
            "hook": self.hook,
            "risk_aware": self.risk_aware,
        }


def generate_x_posts(
    evidence: Evidence,
    article_title: str,
    article_slug: str,
    primary_signal: Optional[AlphaForgeSignal] = None,
) -> XPostSet:
    """
    Generate 3 X post variants from evidence and article metadata.

    Uses the primary signal (highest confidence) if available,
    falls back to market tone if no signal data.
    """
    sig = primary_signal or _pick_primary_signal(evidence)

    if sig:
        return _posts_from_signal(sig, evidence, article_title, article_slug)
    else:
        return _posts_from_tone(evidence, article_title, article_slug)


# ── Signal-backed posts ───────────────────────────────────────────────────────

def _posts_from_signal(
    sig: AlphaForgeSignal,
    evidence: Evidence,
    title: str,
    slug: str,
) -> XPostSet:
    conf_pct = int(round(sig.confidence * 100))
    direction_label = "BUY" if sig.direction == "LONG" else ("SELL" if sig.direction == "SHORT" else "FLAT")
    asset_name = _asset_full_name(sig.symbol)
    ticker = f"${sig.symbol}"

    mkt = evidence.market_data.get(sig.symbol)
    price_line = ""
    if mkt and mkt.price:
        price_str = f"${mkt.price:,.0f}" if mkt.price > 100 else f"${mkt.price:.4f}"
        change_str = f" ({mkt.change_24h:+.1f}% 24h)" if mkt.change_24h is not None else ""
        price_line = f"\nPrice: {price_str}{change_str}"

    volume_line = ""
    if mkt and mkt.volume_24h:
        vol = mkt.volume_24h
        vol_str = f"${vol/1e9:.1f}B" if vol >= 1e9 else f"${vol/1e6:.0f}M"
        volume_line = f"\nVolume 24h: {vol_str}"

    risk_line = evidence.risk_factors[0] if evidence.risk_factors else "Monitor for regime change."
    # Shorten risk for tweet
    if len(risk_line) > 100:
        risk_line = risk_line[:97] + "..."

    confluence_line = ""
    if sig.confluence == "full":
        confluence_line = "\nConfluence: Full (3+ timeframes)"
    elif sig.confluence == "partial":
        confluence_line = "\nConfluence: Partial (2 timeframes)"

    hashtag = f"#{sig.symbol}" if sig.symbol in ("BTC", "ETH", "SOL") else ""

    # Signal Card
    short_risk = risk_line[:80].rstrip(".") + "." if len(risk_line) > 80 else risk_line
    signal_card = (
        f"{asset_name} Signal Update\n\n"
        f"AlphaForge: {direction_label}\n"
        f"Confidence: {conf_pct}%\n"
        f"Regime: {sig.regime}"
        f"{confluence_line}"
        f"{price_line}"
        f"{volume_line}\n\n"
        f"{sig.thesis[:100] + '...' if len(sig.thesis) > 100 else sig.thesis}\n\n"
        f"Risk: {short_risk}\n\n"
        f"{ticker}"
        + (f" {hashtag}" if hashtag else "")
    )

    # Hook Post
    hook = (
        f"Most traders are watching {asset_name} price.\n\n"
        f"AlphaForge is watching regime, volume, and model conviction.\n\n"
        f"Current signal:\n"
        f"{direction_label}\n"
        f"Confidence: {conf_pct}%\n"
        f"Regime: {sig.regime}\n\n"
        f"The key: {sig.thesis[:100].rstrip('.')}.\n\n"
        f"{ticker}"
    )

    # Risk-Aware
    tone_word = "improving" if sig.direction == "LONG" else "weakening"
    risk_aware = (
        f"{asset_name} momentum is {tone_word}, but this is not a blind {'long' if sig.direction == 'LONG' else 'short'}.\n\n"
        f"AlphaForge signal:\n"
        f"{direction_label}\n"
        f"Confidence: {conf_pct}%\n\n"
        f"Main risk:\n"
        f"{risk_line}\n\n"
        f"{'Bullish' if sig.direction == 'LONG' else 'Bearish'} setup — but risk still matters.\n\n"
        f"{ticker}"
        + (f" #{asset_name.split()[0]}" if " " in asset_name else f" #{asset_name}")
    )

    return XPostSet(
        signal_card=_trim_tweet(signal_card),
        hook=_trim_tweet(hook),
        risk_aware=_trim_tweet(risk_aware),
    )


# ── Tone-based posts (no signal data) ────────────────────────────────────────

def _posts_from_tone(evidence: Evidence, title: str, slug: str) -> XPostSet:
    tone = evidence.market_tone.capitalize()
    risk_line = evidence.risk_factors[0] if evidence.risk_factors else "Standard market risks apply."

    signal_card = (
        f"AlphaForge Market Read\n\n"
        f"Tone: {tone}\n"
        f"Signals available: {len(evidence.alphaforge_signals)}\n\n"
        f"Top assets watched: {', '.join(evidence.top_assets_by_confidence[:4]) or 'BTC, ETH, SOL'}\n\n"
        f"Full analysis: alphaforgeai.io/blog/{slug}\n\n"
        f"#AlphaForgeAI"
    )

    hook = (
        f"The crypto market is giving a {tone.lower()} read today.\n\n"
        f"AlphaForge is tracking {len(evidence.alphaforge_signals)} active signals.\n\n"
        f"Full breakdown with evidence: alphaforgeai.io/blog/{slug}\n\n"
        f"$BTC $ETH"
    )

    risk_aware = (
        f"Market tone: {tone}\n\n"
        f"AlphaForge signal count: {len(evidence.alphaforge_signals)}\n\n"
        f"Risk to watch: {risk_line[:100]}\n\n"
        f"Full analysis at alphaforgeai.io/blog/{slug}\n\n"
        f"#AlphaForgeAI"
    )

    return XPostSet(
        signal_card=_trim_tweet(signal_card),
        hook=_trim_tweet(hook),
        risk_aware=_trim_tweet(risk_aware),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

_ASSET_NAMES = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana",
    "XRP": "XRP", "AVAX": "Avalanche", "DOT": "Polkadot",
    "NEAR": "NEAR Protocol", "UNI": "Uniswap", "AAVE": "Aave",
    "COMP": "Compound", "SNX": "Synthetix", "CRV": "Curve",
    "LTC": "Litecoin", "BCH": "Bitcoin Cash", "ARB": "Arbitrum",
    "OP": "Optimism", "SUI": "Sui", "APT": "Aptos",
    "INJ": "Injective", "POL": "Polygon", "FIL": "Filecoin",
    "SHIB": "Shiba Inu", "PEPE": "Pepe", "FLOKI": "Floki",
    "BONK": "Bonk", "WIF": "Dogwifhat",
}


def _asset_full_name(symbol: str) -> str:
    return _ASSET_NAMES.get(symbol, symbol)


def _pick_primary_signal(evidence: Evidence) -> Optional[AlphaForgeSignal]:
    directional = [s for s in evidence.alphaforge_signals if s.direction in ("LONG", "SHORT")]
    if not directional:
        return None
    return max(directional, key=lambda s: s.confidence)


def _trim_tweet(text: str, limit: int = 280) -> str:
    """Trim post to Twitter limit, breaking at word boundary."""
    if len(text) <= limit:
        return text
    trimmed = text[:limit - 3].rsplit(" ", 1)[0]
    return trimmed + "..."
