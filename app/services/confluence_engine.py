"""
Multi-Timeframe Signal Confluence Engine.

Groups signals by symbol across timeframes (5m, 15m, 1h) and marks each
signal with its confluence level:

  "full"    — 3 or more timeframes agree on the same non-FLAT direction
  "partial" — exactly 2 timeframes agree
  None      — no confluence (single timeframe or all disagree)

Confidence is boosted for confluent signals so they sort higher on the feed:
  full    → +0.10  (capped at 0.95)
  partial → +0.05  (capped at 0.90)

The primary signal for each symbol (highest raw confidence among agreeing TFs)
is returned; its confluence_timeframes field lists the TFs that agreed.
Non-confluent symbols are returned unchanged with confluence=None.
"""

import logging
from collections import defaultdict
from app.domain.signals import Direction, Signal

log = logging.getLogger(__name__)

_CONFLUENCE_TFS = {"5m", "15m", "1h"}


def evaluate_confluence(signals: list[Signal]) -> list[Signal]:
    """
    Mark each signal with its confluence level and boost confidence.

    Signals for symbols that appear on only one timeframe pass through
    untouched. Signals outside the confluence timeframe set (e.g. 4h) pass
    through untouched.

    Returns a deduplicated list: one signal per symbol (the highest-confidence
    agreeing signal when confluent, the original signal otherwise).
    """
    by_symbol: dict[str, list[Signal]] = defaultdict(list)
    pass_through: list[Signal] = []

    for sig in signals:
        if sig.timeframe in _CONFLUENCE_TFS:
            by_symbol[sig.symbol].append(sig)
        else:
            pass_through.append(sig)

    result: list[Signal] = list(pass_through)

    for symbol, sym_sigs in by_symbol.items():
        elevated = _elevate(sym_sigs)
        result.extend(elevated)

    log.info(
        "event=confluence_evaluated symbol_count=%d elevated=%d pass_through=%d",
        len(by_symbol),
        len(result) - len(pass_through),
        len(pass_through),
    )
    return result


def filter_confluent(signals: list[Signal]) -> list[Signal]:
    """Return only signals that have a confluence tag (full or partial)."""
    return [s for s in signals if s.confluence is not None]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _elevate(sym_sigs: list[Signal]) -> list[Signal]:
    """
    Determine confluence for a group of same-symbol signals and return the
    elevated primary signal(s).

    Returns a list because non-confluent symbols keep all their signals,
    while confluent ones are collapsed to the single best signal.
    """
    if len(sym_sigs) == 1:
        return sym_sigs

    # Count agreement on non-FLAT directions only
    direction_groups: dict[str, list[Signal]] = defaultdict(list)
    for sig in sym_sigs:
        if sig.direction != Direction.FLAT:
            direction_groups[sig.direction].append(sig)

    if not direction_groups:
        # All FLAT — no confluence possible
        return sym_sigs

    best_direction = max(direction_groups, key=lambda d: len(direction_groups[d]))
    agreeing = direction_groups[best_direction]
    count = len(agreeing)

    if count >= 3:
        level, boost, cap = "full", 0.10, 0.95
    elif count == 2:
        level, boost, cap = "partial", 0.05, 0.90
    else:
        # Only one timeframe has this direction — no confluence
        return sym_sigs

    # Primary = highest raw confidence among agreeing signals
    primary = max(agreeing, key=lambda s: s.confidence)
    boosted = min(round(primary.confidence + boost, 2), cap)
    agreeing_tfs = sorted(s.timeframe for s in agreeing)

    elevated = primary.model_copy(update={
        "confidence": boosted,
        "confluence": level,
        "confluence_timeframes": agreeing_tfs,
    })

    log.debug(
        "event=signal_elevated symbol=%s direction=%s confluence=%s "
        "timeframes=%s confidence_raw=%.2f confidence_boosted=%.2f",
        primary.symbol,
        best_direction,
        level,
        agreeing_tfs,
        primary.confidence,
        boosted,
    )
    return [elevated]
