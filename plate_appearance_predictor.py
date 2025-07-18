from functools import lru_cache

# Threshold to cut off foul recursion when it's negligible
FOUL_PROB_THRESHOLD = 0.001  # 0.1%


# Recursive function with memoization
@lru_cache(maxsize=None)
def V(b, s, hit_prob, foul_prob, out_prob, ball_prob, strike_prob):
    """
    Compute final at-bat outcome probabilities from count (balls b, strikes s),
    tracking cumulative foul probability to avoid infinite recursion.
    Returns dict with keys: Hit, Out, Walk, Strikeout
    """
    result = {"Hit": 0.0, "Out": 0.0, "Walk": 0.0, "Strikeout": 0.0}

    # Hit ends the at-bat
    result["Hit"] += hit_prob
    # Out ends the at-bat
    result["Out"] += out_prob

    # Ball
    if b == 3:
        result["Walk"] += ball_prob  # Walk
    else:
        next_state = V(
            b + 1,
            s,
            foul_prob=foul_prob,
            hit_prob=hit_prob,
            out_prob=out_prob,
            ball_prob=ball_prob,
            strike_prob=strike_prob,
        )
        for key in result:
            result[key] += ball_prob * next_state[key]

    # Strike
    if s == 2:
        result["Strikeout"] += strike_prob  # Strikeout
    else:
        next_state = V(
            b,
            s + 1,
            foul_prob=foul_prob,
            hit_prob=hit_prob,
            out_prob=out_prob,
            ball_prob=ball_prob,
            strike_prob=strike_prob,
        )
        for key in result:
            result[key] += strike_prob * next_state[key]

    # Foul
    if s < 2:
        next_state = V(
            b,
            s + 1,
            foul_prob=(foul_prob * foul_prob),
            hit_prob=hit_prob,
            out_prob=out_prob,
            ball_prob=ball_prob,
            strike_prob=strike_prob,
        )
        for key in result:
            result[key] += foul_prob * next_state[key]
    elif foul_prob * foul_prob > FOUL_PROB_THRESHOLD:
        # Continue recursion only if foul branch still contributes meaningfully
        next_state = V(
            b,
            s,
            foul_prob=(foul_prob * foul_prob),
            hit_prob=hit_prob,
            out_prob=out_prob,
            ball_prob=ball_prob,
            strike_prob=strike_prob,
        )
        for key in result:
            result[key] += foul_prob * next_state[key]
    # Else: cutoff, no contribution from further fouls

    return result


def calculate_plate_appearance_outcomes(
    ball_prob,
    strike_prob,
    foul_prob,
    hit_prob,
    out_prob,
):
    # Ensure the total probability sums to 1
    assert abs(ball_prob + strike_prob + foul_prob + hit_prob + out_prob) >= 0.995, "Probabilities must sum to 1."

    # Starting from count 0-0
    final_probs = V(0, 0, hit_prob=hit_prob, foul_prob=foul_prob, out_prob=out_prob, ball_prob=ball_prob, strike_prob=strike_prob)

    return final_probs
