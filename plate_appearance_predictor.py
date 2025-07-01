import json
from typing import Dict, List, Tuple, Any
from collections import defaultdict
import math

def calculate_plate_appearance_outcomes(
    hit_prob: float,
    strike_prob: float, 
    foul_prob: float,
    ball_prob: float,
    out_prob: float
) -> Dict[str, float]:
    """
    Calculate complete plate appearance outcomes: Hit, Strikeout, Walk, Other
    
    Key rules:
    - Fouls advance count for first 2 strikes only
    - With 2 strikes, fouls keep at-bat alive but don't advance count
    - For strikeout predictions, only count called/swinging strikes (not fouls)
    - A strikeout requires 3 actual strikes (not fouls)
    
    Returns probabilities that sum to 1.0 for: Hit, Strikeout, Walk, Other
    """
    
    # Memoization to avoid infinite recursion and improve performance
    memo = {}
    
    def calculate_from_count(balls: int, strikes: int) -> Dict[str, float]:
        """Calculate outcome probabilities from a specific count"""
        
        # Check memo first
        if (balls, strikes) in memo:
            return memo[(balls, strikes)]
        
        # Terminal states
        if balls == 4:  # Walk
            result = {'hit': 0.0, 'strikeout': 0.0, 'walk': 1.0, 'other': 0.0}
            memo[(balls, strikes)] = result
            return result
            
        if strikes == 3:  # Strikeout  
            result = {'hit': 0.0, 'strikeout': 1.0, 'walk': 0.0, 'other': 0.0}
            memo[(balls, strikes)] = result
            return result
        
        # Two-strike scenarios: fouls don't advance count
        if strikes == 2:
            # From 2-strike counts, solve the recursive equation:
            # P = hit*hit + strike*strikeout + ball*P_next + other*other + foul*P
            # Rearranging: P(1-foul) = hit*hit + strike*strikeout + ball*P_next + other*other
            
            if balls == 3:  # Full count (3-2)
                # Next ball is a walk, next strike is strikeout
                denominator = 1 - foul_prob
                if denominator <= 0:
                    # Edge case: infinite fouls
                    result = {'hit': 0.0, 'strikeout': 0.0, 'walk': 0.0, 'other': 0.0}
                else:
                    result = {
                        'hit': hit_prob / denominator,
                        'strikeout': strike_prob / denominator,
                        'walk': ball_prob / denominator,
                        'other': out_prob / denominator
                    }
            else:
                # Not full count: ball advances to next count
                next_count = calculate_from_count(balls + 1, 2)
                denominator = 1 - foul_prob
                if denominator <= 0:
                    result = {'hit': 0.0, 'strikeout': 0.0, 'walk': 0.0, 'other': 0.0}
                else:
                    result = {
                        'hit': hit_prob / denominator,
                        'strikeout': strike_prob / denominator,
                        'walk': ball_prob * next_count['walk'] / denominator,
                        'other': out_prob / denominator
                    }
            
            memo[(balls, strikes)] = result
            return result
        
        # Zero or one strike: fouls advance the count
        else:
            # Calculate outcomes from possible next states
            hit_outcome = {'hit': 1.0, 'strikeout': 0.0, 'walk': 0.0, 'other': 0.0}
            other_outcome = {'hit': 0.0, 'strikeout': 0.0, 'walk': 0.0, 'other': 1.0}
            
            # Next states for strike/foul (both advance strike count)
            strike_next = calculate_from_count(balls, strikes + 1)
            foul_next = calculate_from_count(balls, strikes + 1)  # Foul advances strikes for first 2 strikes
            
            # Next state for ball
            if balls + 1 >= 4:
                ball_next = {'hit': 0.0, 'strikeout': 0.0, 'walk': 1.0, 'other': 0.0}
            else:
                ball_next = calculate_from_count(balls + 1, strikes)
            
            # Combine probabilities
            result = {
                'hit': (hit_prob * hit_outcome['hit'] + 
                       strike_prob * strike_next['hit'] + 
                       foul_prob * foul_next['hit'] + 
                       ball_prob * ball_next['hit'] + 
                       out_prob * other_outcome['hit']),
                       
                'strikeout': (hit_prob * hit_outcome['strikeout'] + 
                             strike_prob * strike_next['strikeout'] + 
                             # Note: fouls don't contribute to strikeouts
                             foul_prob * foul_next['strikeout'] + 
                             ball_prob * ball_next['strikeout'] + 
                             out_prob * other_outcome['strikeout']),
                             
                'walk': (hit_prob * hit_outcome['walk'] + 
                        strike_prob * strike_next['walk'] + 
                        foul_prob * foul_next['walk'] + 
                        ball_prob * ball_next['walk'] + 
                        out_prob * other_outcome['walk']),
                        
                'other': (hit_prob * hit_outcome['other'] + 
                         strike_prob * strike_next['other'] + 
                         foul_prob * foul_next['other'] + 
                         ball_prob * ball_next['other'] + 
                         out_prob * other_outcome['other'])
            }
            
            memo[(balls, strikes)] = result
            return result
    
    # Calculate from 0-0 count (start of at-bat)
    final_outcomes = calculate_from_count(0, 0)
    
    # Normalize to ensure probabilities sum to 1.0 (handle any floating point errors)
    total = sum(final_outcomes.values())
    if total > 0:
        for outcome in final_outcomes:
            final_outcomes[outcome] /= total
    
    return final_outcomes

def analyze_plate_appearance(batter_outcomes: Dict[str, float]) -> Dict[str, Any]:
    """
    Comprehensive plate appearance analysis for a batter matchup.
    
    Args:
        batter_outcomes: Dict with 'hit', 'strike', 'foul', 'ball', 'out' probabilities
                        Values may be "-1" for unknown data
    """
    
    # Check if any outcome is unknown (-1)
    if any(str(prob) == "-1" for prob in batter_outcomes.values()):
        # Return unknown/invalid results for all metrics
        return {
            'plate_appearance_outcomes': {
                'hit': -1,
                'strikeout': -1,
                'walk': -1,
                'other': -1
            },
            'hit_probability': -1,
            'strikeout_probability': -1,
            'walk_probability': -1,
            'other_out_probability': -1,
            'estimated_pitches_per_pa': -1,
            'strike_to_foul_ratio': -1,
            'batter_approach': {
                'aggressive': False,
                'patient': False,
                'contact_oriented': False
            }
        }
    
    # Convert string values to float for calculation
    hit_prob = float(batter_outcomes.get('hit', 0.0))
    strike_prob = float(batter_outcomes.get('strike', 0.0))
    foul_prob = float(batter_outcomes.get('foul', 0.0))
    ball_prob = float(batter_outcomes.get('ball', 0.0))
    out_prob = float(batter_outcomes.get('out', 0.0))
    
    # Calculate PA outcomes
    pa_outcomes = calculate_plate_appearance_outcomes(
        hit_prob, strike_prob, foul_prob, ball_prob, out_prob
    )
    
    # Additional analysis
    strike_to_foul_ratio = strike_prob / foul_prob if foul_prob > 0 else float('inf')
    
    # Estimate average pitches per PA (rough approximation)
    # More strikes/fouls = longer ABs, more balls = shorter ABs  
    base_pitches = 3.8  # MLB average is around 3.8 pitches per PA
    
    # Adjust based on rates
    if foul_prob > 0.25:  # High foul rate extends ABs
        estimated_pitches = base_pitches + (foul_prob - 0.25) * 10
    elif ball_prob > 0.45:  # High ball rate can shorten ABs  
        estimated_pitches = base_pitches - (ball_prob - 0.45) * 5
    else:
        estimated_pitches = base_pitches
    
    return {
        'plate_appearance_outcomes': pa_outcomes,
        'hit_probability': pa_outcomes['hit'],
        'strikeout_probability': pa_outcomes['strikeout'], 
        'walk_probability': pa_outcomes['walk'],
        'other_out_probability': pa_outcomes['other'],
        'estimated_pitches_per_pa': max(1.0, estimated_pitches),
        'strike_to_foul_ratio': strike_to_foul_ratio,
        'batter_approach': {
            'aggressive': hit_prob + strike_prob > 0.35,
            'patient': ball_prob > 0.42,
            'contact_focused': foul_prob > 0.22,
            'power_focused': hit_prob > 0.08 and out_prob > 0.08,
            'two_strike_battler': foul_prob > 0.20 and strike_prob < 0.25
        },
        'pitcher_dominance': {
            'strikeout_pitcher': pa_outcomes['strikeout'] > 0.25,
            'control_pitcher': ball_prob < 0.35, 
            'contact_inducer': out_prob > 0.12,
            'foul_inducer': foul_prob > 0.25
        }
    }

def create_pa_predictor_from_game_data(file_path: str) -> List[Dict]:
    """Parse game file and create PA predictions for all batters."""
    import re
    import os
    
    batters = []
    
    with open(file_path, 'r') as file:
        content = file.read()
    
    sections = content.split('-----------------------------------')
    
    for section in sections[1:]:
        lines = section.strip().split('\n')
        if len(lines) < 2:
            continue
            
        team_pitcher_line = lines[0].strip()
        
        i = 1
        while i < len(lines):
            line = lines[i].strip()
            
            if line and not line.startswith(('Hit:', 'Strike:', 'Foul:', 'Ball:', 'Out:', 'Total:', '-')):
                player_name = line
                
                stats = {}
                j = i + 1
                while j < len(lines) and j < i + 10:
                    stat_line = lines[j].strip()
                    if stat_line.startswith('Hit:'):
                        hit_match = re.search(r'Hit: ([\d.]+)', stat_line)
                        if hit_match:
                            stats['hit'] = float(hit_match.group(1))
                    elif stat_line.startswith('Strike:'):
                        strike_match = re.search(r'Strike: ([\d.]+)', stat_line)
                        if strike_match:
                            stats['strike'] = float(strike_match.group(1))
                    elif stat_line.startswith('Foul:'):
                        foul_match = re.search(r'Foul: ([\d.]+)', stat_line)
                        if foul_match:
                            stats['foul'] = float(foul_match.group(1))
                    elif stat_line.startswith('Ball:'):
                        ball_match = re.search(r'Ball: ([\d.]+)', stat_line)
                        if ball_match:
                            stats['ball'] = float(ball_match.group(1))
                    elif stat_line.startswith('Out:'):
                        out_match = re.search(r'Out: ([\d.]+)', stat_line)
                        if out_match:
                            stats['out'] = float(out_match.group(1))
                    elif stat_line.startswith('Total:'):
                        break
                    j += 1
                
                if all(key in stats for key in ['hit', 'strike', 'foul', 'ball', 'out']):
                    pa_analysis = analyze_plate_appearance(stats)
                    
                    batter_data = {
                        'player_name': player_name,
                        'matchup': team_pitcher_line, 
                        'file': os.path.basename(file_path),
                        'original_stats': stats,
                        'pa_analysis': pa_analysis
                    }
                    batters.append(batter_data)
                
                i = j
            else:
                i += 1
    
    return batters

def analyze_all_games_pa_outcomes() -> List[Dict]:
    """Analyze PA outcomes for all games in the current directory."""
    import os
    
    directory = "."  # Current directory
    all_batters = []
    
    for filename in os.listdir(directory):
        if filename.startswith('game_') and filename.endswith('.txt'):
            file_path = os.path.join(directory, filename)
            print(f"Analyzing PA outcomes for {filename}...")
            batters = create_pa_predictor_from_game_data(file_path)
            all_batters.extend(batters)
    
    print(f"Analyzed {len(all_batters)} complete plate appearance matchups")
    return all_batters

def print_pa_analysis_summary(all_batters: List[Dict]):
    """Print comprehensive PA outcome analysis."""
    
    print("\n" + "="*100)
    print("PLATE APPEARANCE OUTCOME ANALYSIS - MAY 1ST, 2025")
    print("="*100)
    
    # Overall averages
    avg_hit = sum(b['pa_analysis']['hit_probability'] for b in all_batters) / len(all_batters)
    avg_k = sum(b['pa_analysis']['strikeout_probability'] for b in all_batters) / len(all_batters)
    avg_bb = sum(b['pa_analysis']['walk_probability'] for b in all_batters) / len(all_batters)
    avg_other = sum(b['pa_analysis']['other_out_probability'] for b in all_batters) / len(all_batters)
    avg_pitches = sum(b['pa_analysis']['estimated_pitches_per_pa'] for b in all_batters) / len(all_batters)
    
    print(f"\nOVERALL AVERAGES ({len(all_batters)} matchups):")
    print("-" * 50)
    print(f"Hit Rate:        {avg_hit:.1%}")
    print(f"Strikeout Rate:  {avg_k:.1%}")  
    print(f"Walk Rate:       {avg_bb:.1%}")
    print(f"Other Out Rate:  {avg_other:.1%}")
    print(f"Avg Pitches/PA:  {avg_pitches:.1f}")
    print(f"Total:           {avg_hit + avg_k + avg_bb + avg_other:.1%}")
    
    # Top performers in each category
    print(f"\nTOP 10 HIT PROBABILITIES:")
    print("-" * 80) 
    print(f"{'Rank':<4} {'Player':<25} {'Matchup':<35} {'Hit%':<6}")
    print("-" * 80)
    
    top_hits = sorted(all_batters, key=lambda x: x['pa_analysis']['hit_probability'], reverse=True)[:10]
    for i, batter in enumerate(top_hits, 1):
        print(f"{i:<4} {batter['player_name']:<25} {batter['matchup']:<35} {batter['pa_analysis']['hit_probability']:<6.1%}")
    
    print(f"\nTOP 10 STRIKEOUT PROBABILITIES:")
    print("-" * 80)
    print(f"{'Rank':<4} {'Player':<25} {'Matchup':<35} {'K%':<6}")
    print("-" * 80)
    
    top_ks = sorted(all_batters, key=lambda x: x['pa_analysis']['strikeout_probability'], reverse=True)[:10]
    for i, batter in enumerate(top_ks, 1):
        print(f"{i:<4} {batter['player_name']:<25} {batter['matchup']:<35} {batter['pa_analysis']['strikeout_probability']:<6.1%}")
    
    print(f"\nTOP 10 WALK PROBABILITIES:")
    print("-" * 80)
    print(f"{'Rank':<4} {'Player':<25} {'Matchup':<35} {'BB%':<6}")
    print("-" * 80)
    
    top_walks = sorted(all_batters, key=lambda x: x['pa_analysis']['walk_probability'], reverse=True)[:10]
    for i, batter in enumerate(top_walks, 1):
        print(f"{i:<4} {batter['player_name']:<25} {batter['matchup']:<35} {batter['pa_analysis']['walk_probability']:<6.1%}")
    
    # Batter approach analysis
    print(f"\nBATTER APPROACH BREAKDOWN:")
    print("-" * 50)
    
    approaches = {
        'aggressive': len([b for b in all_batters if b['pa_analysis']['batter_approach']['aggressive']]),
        'patient': len([b for b in all_batters if b['pa_analysis']['batter_approach']['patient']]),
        'contact_focused': len([b for b in all_batters if b['pa_analysis']['batter_approach']['contact_focused']]),
        'power_focused': len([b for b in all_batters if b['pa_analysis']['batter_approach']['power_focused']]),
        'two_strike_battler': len([b for b in all_batters if b['pa_analysis']['batter_approach']['two_strike_battler']])
    }
    
    for approach, count in approaches.items():
        pct = count / len(all_batters)
        print(f"{approach.replace('_', ' ').title():<20}: {count:>3} batters ({pct:.1%})")
    
    # Pitcher style analysis  
    print(f"\nPITCHER DOMINANCE BREAKDOWN:")
    print("-" * 50)
    
    pitcher_styles = {
        'strikeout_pitcher': len([b for b in all_batters if b['pa_analysis']['pitcher_dominance']['strikeout_pitcher']]),
        'control_pitcher': len([b for b in all_batters if b['pa_analysis']['pitcher_dominance']['control_pitcher']]),
        'contact_inducer': len([b for b in all_batters if b['pa_analysis']['pitcher_dominance']['contact_inducer']]),
        'foul_inducer': len([b for b in all_batters if b['pa_analysis']['pitcher_dominance']['foul_inducer']])
    }
    
    for style, count in pitcher_styles.items():
        pct = count / len(all_batters)
        print(f"{style.replace('_', ' ').title():<20}: {count:>3} matchups ({pct:.1%})")

# Example usage and testing
if __name__ == "__main__":
    print("=== PLATE APPEARANCE OUTCOME PREDICTOR ===\n")
    
    # Test with sample data
    sample_batter = {
        'hit': 0.08,    # 8% hit rate
        'strike': 0.28, # 28% strike rate  
        'foul': 0.20,   # 20% foul rate
        'ball': 0.40,   # 40% ball rate
        'out': 0.04     # 4% other out rate
    }
    
    print("Sample Analysis:")
    analysis = analyze_plate_appearance(sample_batter)
    
    pa_outcomes = analysis['plate_appearance_outcomes']
    print(f"Hit:        {pa_outcomes['hit']:.1%}")
    print(f"Strikeout:  {pa_outcomes['strikeout']:.1%}")
    print(f"Walk:       {pa_outcomes['walk']:.1%}")
    print(f"Other Out:  {pa_outcomes['other']:.1%}")
    print(f"Total:      {sum(pa_outcomes.values()):.1%}")
    print(f"Est. Pitches/PA: {analysis['estimated_pitches_per_pa']:.1f}")
    
    print(f"\nBatter Approach: {analysis['batter_approach']}")
    print(f"Pitcher Style: {analysis['pitcher_dominance']}")
    
    # Analyze all games if directory exists
    try:
        all_batters = analyze_all_games_pa_outcomes()
        print_pa_analysis_summary(all_batters)
    except FileNotFoundError:
        print("\nGame directory not found - skipping full analysis")
