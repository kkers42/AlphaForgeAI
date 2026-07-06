"""
EvidenceBuilder — collect structured evidence before any content is generated.

Source priority:
  Tier 1: AlphaForge proprietary (signals, confidence, regime, confluence)
  Tier 2: On-chain / exchange intelligence (future — stubs provided)
  Tier 3: Market data (CoinGecko free, no API key required)
  Tier 4: News / macro context (passed in from n8n pipeline)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

log = logging.getLogger(__name__)

_COINGECKO_BASE = "https://api.coingecko.com/api/v3"
_CMC_IDS = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
    "XRP": "ripple", "AVAX": "avalanche-2", "DOT": "polkadot",
    "NEAR": "near", "UNI": "uniswap", "AAVE": "aave",
    "COMP": "compound-governance-token", "SNX": "synthetix-network-token",
    "CRV": "curve-dao-token", "LTC": "litecoin", "BCH": "bitcoin-cash",
    "ARB": "arbitrum", "OP": "optimism", "SUI": "sui", "APT": "aptos",
    "INJ": "injective-protocol", "POL": "matic-network",
    "FIL": "filecoin", "SHIB": "shiba-inu", "PEPE": "pepe",
    "FLOKI": "floki", "BONK": "bonk", "WIF": "dogwifcoin",
}


@dataclass
class MarketSnapshot:
    symbol: str
    price: Optional[float] = None
    change_24h: Optional[float] = None
    volume_24h: Optional[float] = None
    market_cap: Optional[float] = None
    source: str = "coingecko"


@dataclass
class AlphaForgeSignal:
    symbol: str
    direction: str
    confidence: float
    regime: str
    timeframe: str
    thesis: str
    confluence: Optional[str] = None


@dataclass
class Evidence:
    """Structured evidence object for one asset or market-wide."""
    asset: Optional[str]
    direction: Optional[str]
    alphaforge_signals: list[AlphaForgeSignal] = field(default_factory=list)
    market_data: dict[str, MarketSnapshot] = field(default_factory=dict)
    onchain_data: dict = field(default_factory=dict)
    risk_factors: list[str] = field(default_factory=list)
    sources_used: list[str] = field(default_factory=list)
    market_tone: str = "neutral"
    top_assets_by_confidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "asset": self.asset,
            "direction": self.direction,
            "alphaforge_signals": [
                {
                    "symbol": s.symbol,
                    "direction": s.direction,
                    "confidence": s.confidence,
                    "regime": s.regime,
                    "timeframe": s.timeframe,
                    "thesis": s.thesis,
                    "confluence": s.confluence,
                }
                for s in self.alphaforge_signals
            ],
            "market_data": {
                sym: {
                    "price": m.price,
                    "change_24h": m.change_24h,
                    "volume_24h": m.volume_24h,
                    "market_cap": m.market_cap,
                }
                for sym, m in self.market_data.items()
            },
            "onchain_data": self.onchain_data,
            "risk_factors": self.risk_factors,
            "sources": self.sources_used,
            "market_tone": self.market_tone,
            "top_assets_by_confidence": self.top_assets_by_confidence,
        }


def build_evidence(
    signals_snapshot: Optional[dict] = None,
    fetch_market_data: bool = True,
    symbols: Optional[list[str]] = None,
) -> Evidence:
    """
    Build structured evidence from all available sources.

    Parameters
    ----------
    signals_snapshot : pre-fetched /api/signals/snapshot payload (or None to skip)
    fetch_market_data: whether to call CoinGecko
    symbols          : override which symbols to fetch market data for
    """
    evidence = Evidence(asset=None, direction=None)

    # --- Tier 1: AlphaForge signals ---
    if signals_snapshot and not signals_snapshot.get("is_stale", True):
        raw_signals = signals_snapshot.get("signals", [])
        af_signals = [
            AlphaForgeSignal(
                symbol=s["symbol"],
                direction=s["direction"],
                confidence=s["confidence"],
                regime=s.get("regime", "unknown"),
                timeframe=s.get("timeframe", "?"),
                thesis=s.get("thesis", ""),
                confluence=s.get("confluence"),
            )
            for s in raw_signals
        ]
        evidence.alphaforge_signals = af_signals
        evidence.sources_used.append("AlphaForge ML signal engine")

        if af_signals:
            long_count = sum(1 for s in af_signals if s.direction == "LONG")
            short_count = sum(1 for s in af_signals if s.direction == "SHORT")
            total = len(af_signals)
            if total > 0:
                long_pct = long_count / total
                short_pct = short_count / total
                if long_pct >= 0.55:
                    evidence.market_tone = "bullish"
                elif short_pct >= 0.55:
                    evidence.market_tone = "bearish"
                elif abs(long_pct - short_pct) <= 0.10:
                    evidence.market_tone = "mixed"
                else:
                    evidence.market_tone = "neutral"

            # Top assets by confidence
            directional = [s for s in af_signals if s.direction in ("LONG", "SHORT")]
            directional.sort(key=lambda s: s.confidence, reverse=True)
            evidence.top_assets_by_confidence = [s.symbol for s in directional[:5]]

            # Determine primary direction from top signals
            if directional:
                top = directional[0]
                evidence.asset = top.symbol
                evidence.direction = top.direction.lower()

    # --- Tier 3: Market data ---
    if fetch_market_data:
        target_symbols = symbols or evidence.top_assets_by_confidence or ["BTC", "ETH", "SOL"]
        mkt = _fetch_coingecko(target_symbols[:8])  # cap to avoid rate limits
        if mkt:
            evidence.market_data = mkt
            evidence.sources_used.append("CoinGecko market data")

    # --- Risk factors ---
    evidence.risk_factors = _infer_risk_factors(evidence)

    return evidence


def _fetch_coingecko(symbols: list[str]) -> dict[str, MarketSnapshot]:
    """Fetch price/volume/market cap from CoinGecko for given symbols."""
    ids = [_CMC_IDS[s] for s in symbols if s in _CMC_IDS]
    if not ids:
        return {}

    url = (
        f"{_COINGECKO_BASE}/simple/price"
        f"?ids={','.join(ids)}"
        f"&vs_currencies=usd"
        f"&include_market_cap=true"
        f"&include_24hr_vol=true"
        f"&include_24hr_change=true"
    )

    try:
        resp = httpx.get(url, timeout=8.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("event=coingecko_fetch_failed error=%s", exc)
        return {}

    result: dict[str, MarketSnapshot] = {}
    id_to_sym = {v: k for k, v in _CMC_IDS.items()}
    for cg_id, vals in data.items():
        sym = id_to_sym.get(cg_id)
        if not sym:
            continue
        result[sym] = MarketSnapshot(
            symbol=sym,
            price=vals.get("usd"),
            change_24h=vals.get("usd_24h_change"),
            volume_24h=vals.get("usd_24h_vol"),
            market_cap=vals.get("usd_market_cap"),
        )
    return result


def _infer_risk_factors(evidence: Evidence) -> list[str]:
    risks: list[str] = []

    # High-confidence signals near extreme values may indicate overextension
    high_conf = [s for s in evidence.alphaforge_signals if s.confidence > 0.85]
    if high_conf:
        risks.append(
            f"High-confidence signals ({len(high_conf)}) may indicate crowded positioning — "
            "monitor for mean reversion if funding overheats."
        )

    # Mixed market tone with directional signals
    if evidence.market_tone == "mixed":
        risks.append(
            "Mixed directional signals suggest elevated uncertainty — "
            "prefer high-confluence setups only."
        )

    # Market data risks
    for sym, mkt in evidence.market_data.items():
        if mkt.change_24h is not None and abs(mkt.change_24h) > 8:
            direction = "upside" if mkt.change_24h > 0 else "downside"
            risks.append(
                f"{sym} has moved {mkt.change_24h:+.1f}% in 24h — "
                f"extended {direction} move increases reversal risk."
            )

    if not risks:
        risks.append(
            "Standard market risks apply: position sizing, stop management, "
            "and monitoring for regime change."
        )

    return risks
