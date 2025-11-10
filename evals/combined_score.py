"""Combined score calculation for evaluation"""

from config import (
    DEFAULT_SCORE_ALPHA,
    DEFAULT_SCORE_BETA,
    DEFAULT_SCORE_GAMMA,
    DEFAULT_TOKEN_NORMALIZATION_DIVISOR,
)


def calculate_combined_score(
    hit_rate: float,
    judge_score: float,
    num_tokens: int,
    alpha: float = DEFAULT_SCORE_ALPHA,
    beta: float = DEFAULT_SCORE_BETA,
    gamma: float = DEFAULT_SCORE_GAMMA,
    token_divisor: float = DEFAULT_TOKEN_NORMALIZATION_DIVISOR,
) -> float:
    """
    Calculate combined score balancing retrieval quality, answer quality, and token usage.

    Formula: score = (hit_rate^alpha * judge_score^gamma) / (num_tokens/token_divisor)^beta

    Args:
        hit_rate: Source hit rate (0.0 to 1.0)
        judge_score: Judge evaluation overall score (0.0 to 1.0)
        num_tokens: Total number of tokens used
        alpha: Exponent for hit rate (default: 2.0, prioritizes retrieval quality)
        beta: Exponent for token penalty (default: 0.5, penalizes high token usage)
        gamma: Exponent for judge score (default: 1.5, incorporates answer quality)
        token_divisor: Divisor for token normalization (default: 1000.0)

    Returns:
        Combined score (higher is better)
    """
    # Avoid division by zero
    if num_tokens <= 0:
        num_tokens = 1

    # Calculate normalized token usage
    normalized_tokens = num_tokens / token_divisor

    # Calculate combined score
    numerator = (hit_rate**alpha) * (judge_score**gamma)
    denominator = normalized_tokens**beta

    return numerator / denominator if denominator > 0 else 0.0
