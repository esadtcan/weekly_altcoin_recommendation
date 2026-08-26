from typing import List, Sequence, Tuple

from .models import RankedCoin


def allocate_basket(
    ranked: Sequence[RankedCoin],
    budget_usd: float = 100.0,
    top_n: int = 5,
) -> List[Tuple[RankedCoin, float]]:
    """Allocate an exact-dollar weekly basket with a diversification floor."""
    picks = list(ranked[:top_n])
    budget_cents = round(budget_usd * 100)
    if not picks or budget_cents <= 0:
        return []

    # Half of the basket is equal-weighted; half follows risk-adjusted conviction.
    base_cents = budget_cents // (2 * len(picks))
    variable_cents = budget_cents - base_cents * len(picks)
    conviction = [max(item.score - 40.0, 1.0) for item in picks]
    total_conviction = sum(conviction)
    exact_shares = [variable_cents * value / total_conviction for value in conviction]
    variable_shares = [int(value) for value in exact_shares]
    remainder = variable_cents - sum(variable_shares)
    remainder_order = sorted(
        range(len(picks)),
        key=lambda index: (exact_shares[index] - variable_shares[index], -index),
        reverse=True,
    )
    for index in remainder_order[:remainder]:
        variable_shares[index] += 1

    return [
        (item, (base_cents + variable_shares[index]) / 100.0)
        for index, item in enumerate(picks)
    ]
