"""
Publisher routes — evidence endpoint for n8n and internal use.

GET /api/publisher/evidence
  Returns structured evidence (AlphaForge signals + market data) that n8n
  injects into the Claude prompt before generating blog posts.

This endpoint is unauthenticated for internal VPS use; it only returns
already-public signal data plus market data from CoinGecko.
"""

import logging
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.publisher.evidence_builder import build_evidence
from app.services.signal_service import get_signals
from app.services.signal_staleness import evaluate_signal_staleness

router = APIRouter()
log = logging.getLogger(__name__)


@router.get("/api/publisher/evidence")
async def get_publisher_evidence(
    symbols: str = Query(
        default="",
        description="Comma-separated list of symbols to include market data for (e.g. BTC,ETH,SOL). "
                    "Defaults to top-confidence signals.",
    ),
):
    """
    Return structured evidence for the publisher pipeline.

    n8n calls this before generating each blog post so Claude has
    AlphaForge signal data, market context, and inferred risk factors.
    """
    # Pull AlphaForge signals
    snapshot = get_signals()
    staleness = evaluate_signal_staleness(snapshot.generated_at)

    signal_payload = None
    if not (staleness.is_stale and staleness.action == "filter"):
        signal_payload = {
            "generated_at": snapshot.generated_at,
            "signal_count": len(snapshot.signals),
            "is_stale": staleness.is_stale,
            "signals": [
                {
                    "symbol": s.symbol,
                    "direction": s.direction,
                    "confidence": round(s.confidence, 4),
                    "regime": s.regime,
                    "timeframe": s.timeframe,
                    "thesis": s.thesis,
                    "confluence": s.confluence,
                }
                for s in sorted(snapshot.signals, key=lambda s: getattr(s, "confidence", 0), reverse=True)
            ],
        }

    target_symbols = [s.strip().upper() for s in symbols.split(",") if s.strip()] or None

    evidence = build_evidence(
        signals_snapshot=signal_payload,
        fetch_market_data=True,
        symbols=target_symbols,
    )

    log.info(
        "event=publisher_evidence_built signals=%d market_data=%d tone=%s",
        len(evidence.alphaforge_signals),
        len(evidence.market_data),
        evidence.market_tone,
    )

    return JSONResponse(evidence.to_dict())
