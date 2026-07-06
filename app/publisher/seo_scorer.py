"""
SEO / engagement scorer for blog posts and X posts.

Scores content from 0-100. If below 80, returns feedback for Claude to revise.
Rules match the requirements in issue #92.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


_CRYPTO_ASSETS = {
    "bitcoin", "ethereum", "solana", "ripple", "xrp", "avalanche", "avax",
    "polkadot", "dot", "near", "uniswap", "uni", "aave", "compound",
    "synthetix", "curve", "litecoin", "ltc", "bitcoin cash", "bch",
    "arbitrum", "arb", "optimism", "op", "sui", "aptos", "apt",
    "injective", "inj", "polygon", "pol", "matic", "filecoin", "fil",
    "shiba inu", "shib", "pepe", "floki", "bonk", "dogwifhat", "wif",
}

_SEARCH_INTENT_PATTERNS = [
    r"why is .+ (going|up|down|rallying|falling|rising|dropping)",
    r"(price prediction|technical analysis|analysis|outlook)",
    r"is .+ (preparing|ready|set) for",
    r"(what is happening|what happened|what is moving)",
    r"(bullish|bearish|breakout|breakdown|signal|setup)",
    r"(today|this week|2026)",
    r"alphaforge",
]

_GENERIC_TITLES = [
    "daily crypto market update",
    "crypto market update",
    "market update",
    "daily update",
    "crypto news",
]

_ALPHAFORGE_KEYWORDS = [
    "alphaforge", "signal", "confidence", "regime", "confluence",
    "ml signal", "model",
]

_EVIDENCE_KEYWORDS = [
    "volume", "market cap", "price", "change", "exchange", "funding",
    "open interest", "on-chain", "onchain", "whale", "inflow", "outflow",
]

_RISK_KEYWORDS = [
    "risk", "resistance", "support", "caution", "monitor", "if",
    "could", "may", "potential", "watch",
]

_GENERIC_AI_PHRASES = [
    "it's important to note", "in conclusion", "in summary",
    "as an ai", "i cannot", "delve into", "certainly",
    "absolutely", "it is worth noting",
]


@dataclass
class ScoreResult:
    score: int
    passed: bool
    feedback: list[str]
    breakdown: dict[str, int]

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "passed": self.passed,
            "feedback": self.feedback,
            "breakdown": self.breakdown,
        }


def score_blog_post(title: str, content: str, has_alphaforge_data: bool = False) -> ScoreResult:
    """Score a blog post from 0-100. Threshold: 80."""
    feedback: list[str] = []
    breakdown: dict[str, int] = {}
    score = 0
    text_lower = (title + " " + content).lower()

    # 1. Title matches search intent (20 pts)
    title_lower = title.lower()
    if any(title_lower == g for g in _GENERIC_TITLES):
        feedback.append("Title is too generic — use a search-intent title like 'Why Is Bitcoin Going Up Today?' or 'Ethereum Technical Analysis: Is ETH Ready to Break Out?'")
        breakdown["title_search_intent"] = 0
    elif any(re.search(p, title_lower) for p in _SEARCH_INTENT_PATTERNS):
        score += 20
        breakdown["title_search_intent"] = 20
    elif any(asset in title_lower for asset in _CRYPTO_ASSETS):
        score += 12
        breakdown["title_search_intent"] = 12
        feedback.append("Title includes an asset name but could be more specific to a search query.")
    else:
        feedback.append("Title lacks search intent — include asset name and a specific question or keyword.")
        breakdown["title_search_intent"] = 0

    # 2. Includes asset name (10 pts)
    if any(asset in text_lower for asset in _CRYPTO_ASSETS):
        score += 10
        breakdown["asset_name"] = 10
    else:
        feedback.append("Content does not clearly name any crypto asset.")
        breakdown["asset_name"] = 0

    # 3. AlphaForge proprietary data (25 pts)
    af_hits = sum(1 for kw in _ALPHAFORGE_KEYWORDS if kw in text_lower)
    if has_alphaforge_data or af_hits >= 3:
        score += 25
        breakdown["alphaforge_data"] = 25
    elif af_hits >= 1:
        score += 12
        breakdown["alphaforge_data"] = 12
        feedback.append("Mention AlphaForge signal data more prominently (confidence, regime, confluence).")
    else:
        feedback.append("Missing AlphaForge proprietary data — include signal direction, confidence, and regime.")
        breakdown["alphaforge_data"] = 0

    # 4. External market/on-chain evidence (15 pts)
    ev_hits = sum(1 for kw in _EVIDENCE_KEYWORDS if kw in text_lower)
    if ev_hits >= 3:
        score += 15
        breakdown["evidence"] = 15
    elif ev_hits >= 1:
        score += 8
        breakdown["evidence"] = 8
        feedback.append("Include more market/on-chain evidence (volume, price change, exchange flows).")
    else:
        feedback.append("Missing market or on-chain evidence to support claims.")
        breakdown["evidence"] = 0

    # 5. Sources & Confidence section (10 pts)
    if "sources" in text_lower and "confidence" in text_lower:
        score += 10
        breakdown["sources_section"] = 10
    else:
        feedback.append("Add a 'Sources & Confidence' section at the end of the article.")
        breakdown["sources_section"] = 0

    # 6. Risk factors (10 pts)
    risk_hits = sum(1 for kw in _RISK_KEYWORDS if kw in text_lower)
    if risk_hits >= 3:
        score += 10
        breakdown["risk_factors"] = 10
    elif risk_hits >= 1:
        score += 5
        breakdown["risk_factors"] = 5
        feedback.append("Expand risk factor discussion.")
    else:
        feedback.append("Missing risk factors — directional claims must be qualified.")
        breakdown["risk_factors"] = 0

    # 7. Avoids generic AI language (-10 penalty)
    ai_hits = [p for p in _GENERIC_AI_PHRASES if p in text_lower]
    if ai_hits:
        score = max(0, score - 10)
        breakdown["ai_language_penalty"] = -10
        feedback.append(f"Remove generic AI phrases: {', '.join(ai_hits[:3])}")
    else:
        breakdown["ai_language_penalty"] = 0

    # 8. Strong hook / answers a real question (10 pts)
    first_200 = content[:200].lower()
    hook_score = 0
    if any(kw in first_200 for kw in ["bullish", "bearish", "signal", "confidence", "regime"]):
        hook_score += 5
    if any(asset in first_200 for asset in _CRYPTO_ASSETS):
        hook_score += 5
    score += hook_score
    breakdown["hook_strength"] = hook_score
    if hook_score < 5:
        feedback.append("Opening paragraph should immediately state the market view and lead asset.")

    score = min(100, max(0, score))
    return ScoreResult(
        score=score,
        passed=score >= 80,
        feedback=feedback,
        breakdown=breakdown,
    )


def score_x_post(text: str, has_alphaforge_data: bool = False) -> ScoreResult:
    """Score an X post from 0-100. Threshold: 80."""
    feedback: list[str] = []
    breakdown: dict[str, int] = {}
    score = 0
    text_lower = text.lower()

    # 1. Asset name / ticker (20 pts)
    has_ticker = bool(re.search(r'\$[A-Z]{2,5}\b', text))
    has_name = any(asset in text_lower for asset in _CRYPTO_ASSETS)
    if has_ticker or has_name:
        score += 20
        breakdown["asset_mention"] = 20
    else:
        feedback.append("Include asset name (Bitcoin, Ethereum) or ticker ($BTC, $ETH).")
        breakdown["asset_mention"] = 0

    # 2. AlphaForge data (25 pts)
    af_hits = sum(1 for kw in _ALPHAFORGE_KEYWORDS if kw in text_lower)
    if has_alphaforge_data or af_hits >= 2:
        score += 25
        breakdown["alphaforge_data"] = 25
    elif af_hits == 1:
        score += 12
        breakdown["alphaforge_data"] = 12
        feedback.append("Include more AlphaForge signal data (direction, confidence %).")
    else:
        feedback.append("X post must reference AlphaForge signal data.")
        breakdown["alphaforge_data"] = 0

    # 3. 0-2 hashtags (15 pts)
    hashtag_count = len(re.findall(r'#\w+', text))
    if hashtag_count <= 2:
        score += 15
        breakdown["hashtag_count"] = 15
    else:
        score += 5
        breakdown["hashtag_count"] = 5
        feedback.append(f"Use 0-2 hashtags maximum (found {hashtag_count}).")

    # 4. Evidence / market context (15 pts)
    ev_hits = sum(1 for kw in _EVIDENCE_KEYWORDS if kw in text_lower)
    if ev_hits >= 2:
        score += 15
        breakdown["evidence"] = 15
    elif ev_hits == 1:
        score += 8
        breakdown["evidence"] = 8
    else:
        feedback.append("Include one market evidence point (volume, funding, regime).")
        breakdown["evidence"] = 0

    # 5. Risk qualifier for directional claims (10 pts)
    directional = any(kw in text_lower for kw in ["long", "short", "buy", "bullish", "bearish"])
    has_risk = any(kw in text_lower for kw in ["risk", "if", "resistance", "caution", "but", "watch"])
    if directional and has_risk:
        score += 10
        breakdown["risk_qualifier"] = 10
    elif not directional:
        score += 10
        breakdown["risk_qualifier"] = 10
    else:
        feedback.append("Directional X posts must include a risk qualifier.")
        breakdown["risk_qualifier"] = 0

    # 6. Strong hook (15 pts)
    first_line = text.split("\n")[0].lower()
    hook_score = 0
    if any(kw in first_line for kw in ["bitcoin", "ethereum", "solana", "btc", "eth", "sol"]):
        hook_score += 8
    if any(kw in first_line for kw in ["signal", "confidence", "regime", "bullish", "bearish", "momentum"]):
        hook_score += 7
    score += hook_score
    breakdown["hook"] = hook_score
    if hook_score < 8:
        feedback.append("First line should name the asset and state the key insight.")

    # Penalty for generic AI phrases
    ai_hits = [p for p in _GENERIC_AI_PHRASES if p in text_lower]
    if ai_hits:
        score = max(0, score - 10)
        breakdown["ai_language_penalty"] = -10
        feedback.append(f"Remove generic phrases: {', '.join(ai_hits[:2])}")
    else:
        breakdown["ai_language_penalty"] = 0

    score = min(100, max(0, score))
    return ScoreResult(
        score=score,
        passed=score >= 80,
        feedback=feedback,
        breakdown=breakdown,
    )


def build_revision_prompt(original_content: str, score_result: ScoreResult, content_type: str = "blog post") -> str:
    """Build a Claude prompt asking it to revise content based on score feedback."""
    issues = "\n".join(f"- {f}" for f in score_result.feedback)
    return (
        f"The following {content_type} scored {score_result.score}/100 and did not meet the 80-point "
        f"publishing threshold. Revise it to address these issues:\n\n"
        f"{issues}\n\n"
        f"Rules:\n"
        f"- Do not add unsupported claims\n"
        f"- Keep AlphaForge signal data front and center\n"
        f"- Use natural keywords, not hashtag stuffing\n"
        f"- Add a Sources & Confidence section if missing\n\n"
        f"Original content:\n\n{original_content}"
    )
