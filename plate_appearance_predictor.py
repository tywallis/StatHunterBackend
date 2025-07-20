from functools import lru_cache

# Threshold to cut off foul recursion when it's negligible
FOUL_PROB_THRESHOLD = 0.001  # 0.1%


# Recursive function with memoization
@lru_cache(maxsize=None)
def V(b, s, hit_prob, foul_prob, out_prob, ball_prob, strike_prob):
    """
    Compute final at-bat outcome probabilities from count (balls b, strikes s).
    Returns tuple with (Hit, Out, Walk, Strikeout) probabilities
    """
    hit_result = 0.0
    out_result = 0.0
    walk_result = 0.0
    strikeout_result = 0.0

    # Hit ends the at-bat
    hit_result += hit_prob
    # Out ends the at-bat
    out_result += out_prob

    # Ball
    if b == 3:
        walk_result += ball_prob  # Walk
    else:
        next_hit, next_out, next_walk, next_strikeout = V(
            b + 1,
            s,
            hit_prob=hit_prob,
            foul_prob=foul_prob,
            out_prob=out_prob,
            ball_prob=ball_prob,
            strike_prob=strike_prob,
        )
        hit_result += ball_prob * next_hit
        out_result += ball_prob * next_out
        walk_result += ball_prob * next_walk
        strikeout_result += ball_prob * next_strikeout

    # Strike
    if s == 2:
        strikeout_result += strike_prob  # Strikeout
    else:
        next_hit, next_out, next_walk, next_strikeout = V(
            b,
            s + 1,
            hit_prob=hit_prob,
            foul_prob=foul_prob,
            out_prob=out_prob,
            ball_prob=ball_prob,
            strike_prob=strike_prob,
        )
        hit_result += strike_prob * next_hit
        out_result += strike_prob * next_out
        walk_result += strike_prob * next_walk
        strikeout_result += strike_prob * next_strikeout

    # Foul
    if s < 2:
        # Foul with less than 2 strikes adds a strike
        next_hit, next_out, next_walk, next_strikeout = V(
            b,
            s + 1,
            hit_prob=hit_prob,
            foul_prob=foul_prob,
            out_prob=out_prob,
            ball_prob=ball_prob,
            strike_prob=strike_prob,
        )
        hit_result += foul_prob * next_hit
        out_result += foul_prob * next_out
        walk_result += foul_prob * next_walk
        strikeout_result += foul_prob * next_strikeout
    elif s == 2 and foul_prob > 0:
        # Special case: 2 strikes and foul ball
        # This creates infinite recursion, so we solve it mathematically
        # The probability of eventually getting a non-foul outcome is 1/(1-foul_prob)
        # We multiply each non-foul outcome by this factor

        non_foul_prob = 1.0 - foul_prob
        if non_foul_prob > 0:
            # Scale the non-foul outcomes by the geometric series sum
            scaling_factor = 1.0 / non_foul_prob
            hit_result *= scaling_factor
            out_result *= scaling_factor
            walk_result *= scaling_factor
            strikeout_result *= scaling_factor

    return hit_result, out_result, walk_result, strikeout_result


def calculate_plate_appearance_outcomes(
    ball_prob,
    strike_prob,
    foul_prob,
    hit_prob,
    out_prob,
):
    # Normalize probabilities to sum to 1
    total_prob = ball_prob + strike_prob + foul_prob + hit_prob + out_prob

    if total_prob > 0:
        ball_prob /= total_prob
        strike_prob /= total_prob
        foul_prob /= total_prob
        hit_prob /= total_prob
        out_prob /= total_prob
    else:
        # Handle edge case where all probabilities are 0
        return {"Hit": 0.0, "Out": 0.0, "Walk": 0.0, "Strikeout": 0.0}

    # Starting from count 0-0
    hit_prob_final, out_prob_final, walk_prob_final, strikeout_prob_final = V(
        0, 0, 
        hit_prob=hit_prob, 
        foul_prob=foul_prob, 
        out_prob=out_prob, 
        ball_prob=ball_prob, 
        strike_prob=strike_prob
    )

    return {
        "Hit": hit_prob_final,
        "Out": out_prob_final,
        "Walk": walk_prob_final,
        "Strikeout": strikeout_prob_final
    }
