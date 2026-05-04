"""
Signal domain model.

Defines the core concept of a trading signal as a typed, validated object.
Signal generation is handled separately (ML engine, not yet wired in).
This module exists to establish a clean contract for what a signal looks like
before the data pipeline and API surface are built.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Direction(str, Enum):
    LONG  = "LONG"
    SHORT = "SHORT"
    FLAT  = "FLAT"


class Timeframe(str, Enum):
    M5  = "5m"
    M15 = "15m"
    H1  = "1h"
    H4  = "4h"


class Signal(BaseModel):
    """
    A single model-generated trade signal.

    Fields
    ------
    symbol               : Asset ticker, e.g. "ETH"
    direction            : LONG, SHORT, or FLAT (no trade)
    timeframe            : Candle resolution the signal was generated on
    confidence           : Model confidence score, 0.0–1.0
    regime               : Market regime label at signal time
    thesis               : Plain-language explanation of why this signal was generated
    top_features         : Optional list of (feature_name, importance) pairs from the model
    confluence           : "full" (3+ TFs agree) | "partial" (2 TFs agree) | None
    confluence_timeframes: Timeframes that agreed on the same direction
    """

    symbol:                str               = Field(..., examples=["ETH"])
    direction:             Direction         = Field(..., examples=[Direction.LONG])
    timeframe:             Timeframe         = Field(Timeframe.M15)
    confidence:            float             = Field(..., ge=0.0, le=1.0, examples=[0.72])
    regime:                str               = Field(..., examples=["uptrend"])
    thesis:                str               = Field(..., examples=["RSI reset from oversold, OI expanding, L/S ratio turning bullish."])
    top_features:          Optional[list[tuple[str, float]]] = Field(None)
    confluence:            Optional[str]     = Field(None)
    confluence_timeframes: Optional[list[str]] = Field(None)

    class Config:
        use_enum_values = True
