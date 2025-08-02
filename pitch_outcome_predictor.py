import json
from typing import Dict, List, Tuple, Any
from collections import defaultdict

def load_json_data(file_path: str) -> Dict:
    """Load JSON data from file."""
    with open(file_path, 'r') as f:
        return json.load(f)

def calculate_pitcher_tendencies(pitcher_data: Dict, cutoff_date_before: str = None, cutoff_date_after: str = None) -> Dict[str, Dict[str, Dict[str, float]]]:
    """
    Calculate pitcher tendencies (probability of throwing each pitch type in each zone).
    
    Args:
        pitcher_data: Pitcher data dictionary
        cutoff_date: Only consider games before this date (YYYY-MM-DD format)
    
    Returns: {handedness: {pitch_type: {zone: probability}}}
    """
    tendencies = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    
    # Aggregate all games
    total_pitches_by_handedness = defaultdict(int)  # {handedness: total_count}
    zone_pitches = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))  # {handedness: {pitch_type: {zone: count}}}
    
    for game_date, game_data in pitcher_data['past_games'].items():
        # Filter games by date if cutoff_date is provided
        if cutoff_date_before and game_date >= cutoff_date_before:
            continue
        if cutoff_date_after and game_date <= cutoff_date_after:
            continue
        pitching_data = game_data['pitch_tracking'].get('pitching', {})
        if not pitching_data:
            continue
        
        for handedness in ['vs_LHB', 'vs_RHB']:
            if handedness not in pitching_data:
                continue
                
            handedness_data = pitching_data[handedness]
            
            # Add to total pitch count for this handedness
            total_pitches_by_handedness[handedness] += handedness_data.get('total', 0)
            
            for pitch_type, pitch_data in handedness_data.items():
                if pitch_type == 'total':
                    continue
                    
                # Add zone-specific counts
                for zone, zone_data in pitch_data.items():
                    if zone == 'total':
                        continue
                    if isinstance(zone_data, dict) and 'total' in zone_data:
                        zone_pitches[handedness][pitch_type][zone] += zone_data['total']
    
    # Calculate probabilities as fraction of ALL pitches to that handedness
    for handedness in zone_pitches:
        total_count = total_pitches_by_handedness[handedness]
        if total_count > 0:
            for pitch_type in zone_pitches[handedness]:
                for zone in zone_pitches[handedness][pitch_type]:
                    zone_count = zone_pitches[handedness][pitch_type][zone]
                    tendencies[handedness][pitch_type][zone] = zone_count / total_count
    
    return dict(tendencies)

def calculate_batter_outcomes(batter_data: Dict, cutoff_date_before: str = None, cutoff_date_after: str = None) -> Dict[str, Dict[str, Dict[str, Dict[str, float]]]]:
    """
    Calculate batter outcome probabilities for each pitch type and zone.
    
    Args:
        batter_data: Batter data dictionary
        cutoff_date: Only consider games before this date (YYYY-MM-DD format)
    
    Returns: {handedness: {pitch_type: {zone: {outcome: probability}}}}
    """
    outcomes = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(float))))
    
    # First pass: collect all data
    zone_data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))
    pitch_type_totals = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    # Separate totals for inside and outside strike zone
    inside_zone_totals = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))  # zones < 10
    outside_zone_totals = defaultdict(lambda: defaultdict(lambda: defaultdict(int))) # zones >= 10
    
    for game_date, game_data in batter_data['past_games'].items():
        # Filter games by date if cutoff_date is provided
        if cutoff_date_before and game_date >= cutoff_date_before:
            continue
        if cutoff_date_after and game_date <= cutoff_date_after:
            continue
        batting_data = game_data['pitch_tracking'].get('batting', {})

        if not batting_data:
            continue
        
        for handedness in ['vs_LHP', 'vs_RHP']:
            if handedness not in batting_data:
                continue
                
            handedness_data = batting_data[handedness]
            
            for pitch_type, pitch_data in handedness_data.items():
                if pitch_type in ['balls', 'fouls', 'hits', 'outs', 'strikes', 'total']:
                    continue
                    
                # Aggregate pitch type totals across all zones
                for outcome in ['balls', 'fouls', 'hits', 'outs', 'strikes']:
                    if outcome in pitch_data:
                        pitch_type_totals[handedness][pitch_type][outcome] += pitch_data[outcome]
                
                # Aggregate zone-specific data
                for zone, zone_info in pitch_data.items():
                    if zone in ['balls', 'fouls', 'hits', 'outs', 'strikes', 'total']:
                        continue
                    if isinstance(zone_info, dict):
                        # Convert zone to integer for comparison
                        try:
                            zone_num = int(zone)
                        except ValueError:
                            continue  # Skip non-numeric zones
                        
                        for outcome in ['balls', 'fouls', 'hits', 'outs', 'strikes']:
                            if outcome in zone_info:
                                count = zone_info[outcome]
                                zone_data[handedness][pitch_type][zone][outcome] += count
                                
                                # Add to appropriate zone category totals
                                if zone_num < 10:  # Inside strike zone
                                    inside_zone_totals[handedness][pitch_type][outcome] += count
                                else:  # Outside strike zone
                                    outside_zone_totals[handedness][pitch_type][outcome] += count
    
    # Calculate probabilities
    for handedness in zone_data:
        for pitch_type in zone_data[handedness]:
            for zone in zone_data[handedness][pitch_type]:
                zone_total = sum(zone_data[handedness][pitch_type][zone].values())
                
                # Convert zone to integer for comparison
                try:
                    zone_num = int(zone)
                except ValueError:
                    continue  # Skip non-numeric zones

                # Use zone-specific data if we have enough samples (>=10), otherwise use zone-category averages
                if zone_total >= 10:
                    for outcome in ['balls', 'fouls', 'hits', 'outs', 'strikes']:
                        count = zone_data[handedness][pitch_type][zone][outcome]
                        outcomes[handedness][pitch_type][zone][outcome] = count / zone_total if zone_total > 0 else 0
                else:
                    # Use appropriate zone category averages (inside vs outside strike zone)
                    if zone_num < 10:  # Inside strike zone
                        zone_category_totals = inside_zone_totals[handedness][pitch_type]
                    else:  # Outside strike zone
                        zone_category_totals = outside_zone_totals[handedness][pitch_type]
                    
                    zone_category_total = sum(zone_category_totals.values())
                    
                    if zone_category_total > 0:
                        # Use zone category averages
                        for outcome in ['balls', 'fouls', 'hits', 'outs', 'strikes']:
                            count = zone_category_totals[outcome]
                            outcomes[handedness][pitch_type][zone][outcome] = count / zone_category_total
                    else:
                        # Fall back to overall pitch type averages if no zone category data
                        pitch_type_total = sum(pitch_type_totals[handedness][pitch_type].values())
                        for outcome in ['balls', 'fouls', 'hits', 'outs', 'strikes']:
                            count = pitch_type_totals[handedness][pitch_type][outcome]
                            outcomes[handedness][pitch_type][zone][outcome] = count / pitch_type_total if pitch_type_total > 0 else 0
    
    return dict(outcomes)

def predict_pitch_outcomes(pitcher_info: Dict[str, Any], batter_info: Dict[str, Any], pitcher_handedness: str, batter_handedness: str, cutoff_date_before: str = None, cutoff_date_after: str = None) -> Dict[str, Dict[str, float]]:
    """
    Predict outcomes for all possible pitch type/zone combinations.
    
    Args:
        pitcher_info: Information about the pitcher
        batter_info: Information about the batter
        pitcher_handedness: 'L' for left-handed pitcher, 'R' for right-handed pitcher
        batter_handedness: 'L' for left-handed batter, 'R' for right-handed batter
        cutoff_date: Only consider games before this date (YYYY-MM-DD format)
    
    Returns:
        Dictionary with pitch_type_zone as keys and outcome probabilities as values
    """
    # Calculate tendencies and outcomes
    pitcher_tendencies = calculate_pitcher_tendencies(pitcher_info, cutoff_date_before, cutoff_date_after)
    batter_outcomes = calculate_batter_outcomes(batter_info, cutoff_date_before, cutoff_date_after)

    # Determine handedness keys - pitcher throws to LHB/RHB, batter faces LHP/RHP
    pitcher_vs = 'vs_LHB' if batter_handedness == 'L' else 'vs_RHB'
    batter_vs = 'vs_LHP' if pitcher_handedness == 'L' else 'vs_RHP'
    
    predictions = {}
    
    # For each pitch type the pitcher throws
    if pitcher_vs in pitcher_tendencies:
        for pitch_type in pitcher_tendencies[pitcher_vs]:
            for zone in pitcher_tendencies[pitcher_vs][pitch_type]:
                # Probability pitcher throws this pitch in this zone
                pitch_prob = pitcher_tendencies[pitcher_vs][pitch_type][zone]
                
                # Batter's expected outcomes for this pitch/zone combination
                zone_outcomes = batter_outcomes.get(batter_vs, {}).get(pitch_type, {}).get(zone, {})
                
                # If no zone-specific data, fall back to pitch type averages
                if not zone_outcomes:
                    # Calculate pitch type averages across all zones for this batter vs this pitcher handedness
                    pitch_type_outcomes = {}
                    if batter_vs in batter_outcomes and pitch_type in batter_outcomes[batter_vs]:
                        # Sum all outcomes for this pitch type across all zones
                        total_counts = {'hits': 0, 'strikes': 0, 'fouls': 0, 'balls': 0, 'outs': 0}
                        for zone_key in batter_outcomes[batter_vs][pitch_type]:
                            if isinstance(batter_outcomes[batter_vs][pitch_type][zone_key], dict):
                                for outcome in total_counts:
                                    total_counts[outcome] += batter_outcomes[batter_vs][pitch_type][zone_key].get(outcome, 0)
                        
                        # Convert to probabilities
                        total_pitches = sum(total_counts.values())
                        if total_pitches > 0:
                            zone_outcomes = {outcome: count / total_pitches for outcome, count in total_counts.items()}
                
                # Only proceed if we have some outcome data (either zone-specific or pitch-type average)
                if zone_outcomes and pitch_prob > 0:
                    key = f"{pitch_type}_zone_{zone}"
                    predictions[key] = {
                        'pitch_probability': pitch_prob,
                        'outcome_probabilities': {
                            'hit': zone_outcomes.get('hits', 0),
                            'strike': zone_outcomes.get('strikes', 0), 
                            'foul': zone_outcomes.get('fouls', 0),
                            'ball': zone_outcomes.get('balls', 0),
                            'out': zone_outcomes.get('outs', 0)
                        },
                        'expected_outcome_weighted': {
                            'hit': pitch_prob * zone_outcomes.get('hits', 0),
                            'strike': pitch_prob * zone_outcomes.get('strikes', 0),
                            'foul': pitch_prob * zone_outcomes.get('fouls', 0), 
                            'ball': pitch_prob * zone_outcomes.get('balls', 0),
                            'out': pitch_prob * zone_outcomes.get('outs', 0)
                        }
                    }
    else:
        print(f"Warning: No pitcher data found for {pitcher_vs}")
    
    return predictions

def calculate_overall_outcome_odds(predictions: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    """
    Calculate overall odds for each outcome type across all pitch/zone combinations.
    The probabilities are normalized to sum to 100%.
    """
    overall_odds = {
        'hit': 0,
        'strike': 0,
        'foul': 0,
        'ball': 0,
        'out': 0
    }
    
    for prediction in predictions.values():
        weighted_outcomes = prediction['expected_outcome_weighted']
        for outcome in overall_odds:
            overall_odds[outcome] += weighted_outcomes[outcome]
    
    # Normalize probabilities to sum to 1 (100%)
    total_probability = sum(overall_odds.values())
    if total_probability > 0:
        for outcome in overall_odds:
            overall_odds[outcome] = overall_odds[outcome] / total_probability
    
    return overall_odds

def print_predictions_summary(predictions: Dict, overall_odds: Dict[str, float]):
    """Print a formatted summary of predictions."""
    print("=== PITCH OUTCOME PREDICTIONS ===\n")
    
    print("Overall Expected Outcome Probabilities:")
    print("-" * 40)
    total_outcome_prob = 0
    for outcome, probability in overall_odds.items():
        print(f"{outcome.capitalize()}: {probability:.3f} ({probability*100:.1f}%)")
        total_outcome_prob += probability
    print(f"Total: {total_outcome_prob:.3f} ({total_outcome_prob*100:.1f}%)")
    
    print(f"\n\nDetailed Predictions by Pitch Type and Zone:")
    print("-" * 60)
    
    # Sort by pitch probability (most likely pitches first)
    sorted_predictions = sorted(predictions.items(), 
                              key=lambda x: x[1]['pitch_probability'], 
                              reverse=True)
    
    total_pitch_prob = sum(data['pitch_probability'] for _, data in sorted_predictions)
    print(f"Total pitch probabilities: {total_pitch_prob:.3f} ({total_pitch_prob*100:.1f}%)")
    print(f"Number of pitch/zone combinations: {len(sorted_predictions)}")
    
    for pitch_zone, data in sorted_predictions:  # Show ALL combinations
        pitch_prob = data['pitch_probability']
        outcomes = data['outcome_probabilities']
        
        print(f"\n{pitch_zone} (Pitch Probability: {pitch_prob:.3f})")
        print("  Outcome probabilities if this pitch is thrown:")
        outcome_total = 0
        for outcome, prob in outcomes.items():
            print(f"    {outcome.capitalize()}: {prob:.3f} ({prob*100:.1f}%)")
            outcome_total += prob
        print(f"    Total: {outcome_total:.3f} ({outcome_total*100:.1f}%)")

def count_batter_pitches_vs_handedness(batter_data: Dict, pitcher_handedness: str, cutoff_date_before: str = None, cutoff_date_after: str = None) -> int:
    """
    Count total number of pitches a batter has faced from a specific pitcher handedness.
    
    Args:
        batter_data: Batter data dictionary
        pitcher_handedness: 'L' or 'R' for left/right-handed pitcher
        cutoff_date: Only consider games before this date (YYYY-MM-DD format)
    
    Returns:
        Total number of pitches faced
    """
    # Determine handedness key based on pitcher handedness
    batter_vs = 'vs_LHP' if pitcher_handedness == 'L' else 'vs_RHP'
    
    total_pitches = 0
    
    for game_date, game_data in batter_data['past_games'].items():
        # Filter games by date if cutoff_date is provided
        if cutoff_date_before and game_date >= cutoff_date_before:
            continue
        if cutoff_date_after and game_date <= cutoff_date_after:
            continue

        batting_data = game_data['pitch_tracking'].get('batting', {})
        if not batting_data:
            continue
        
        if batter_vs not in batting_data:
            continue
            
        handedness_data = batting_data[batter_vs]
        
        # Use the direct "total" field for this handedness in this game
        if 'total' in handedness_data and isinstance(handedness_data['total'], int):
            total_pitches += handedness_data['total']
    
    return total_pitches

def get_outcome_probabilities(pitcher_info: Dict[str, Any], batter_info: Dict[str, Any], pitcher_handedness: str, batter_handedness: str, cutoff_date_before: str, cutoff_date_after: str) -> Dict[str, Any]:
    """
    Get outcome probabilities for a batter vs pitcher matchup.
    Returns -1 for all outcomes if batter has faced fewer than 100 pitches from this pitcher handedness.
    """
    # Count total pitches faced by batter from this pitcher handedness
    total_pitches = count_batter_pitches_vs_handedness(batter_info, pitcher_handedness, cutoff_date_before, cutoff_date_after)

    # If insufficient data (< 100 pitches), return unknown for all outcomes
    if total_pitches < 100:
        return {
            'hit': "-1",
            'strike': "-1",
            'foul': "-1",
            'ball': "-1",
            'out': "-1"
        }
    
    # Predict outcomes (specify both pitcher and batter handedness)
    predictions = predict_pitch_outcomes(
        pitcher_info, 
        batter_info, 
        pitcher_handedness,
        batter_handedness,
        cutoff_date_before,
        cutoff_date_after
    )
    
    # Calculate overall odds
    overall_odds = calculate_overall_outcome_odds(predictions)
    
    # Convert to strings with proper formatting
    formatted_odds = {}
    for outcome, probability in overall_odds.items():
        formatted_odds[outcome] = f"{probability:.3f}"
    
    return formatted_odds
