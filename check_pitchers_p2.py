#!/usr/bin/env python3
"""
Pitcher Probability Analyzer

This script analyzes the probability of a pitcher achieving a target number 
of hits or strikeouts against an opposing lineup for a given number of total batters faced.

The script distributes plate appearances across the opposing lineup based on the 
total batters faced parameter, then calculates cumulative probabilities.
"""

import json
import csv
import math
from datetime import datetime
from itertools import combinations_with_replacement
from typing import List, Dict, Tuple, Any


def load_todays_data(date_str: str = None) -> Dict[str, Any]:
    """Load today's JSON data file."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    filename = f"{date_str}.json"
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find file {filename}")
        raise
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in file {filename}")
        raise


def find_pitcher_matchups(data: Dict[str, Any], pitcher_name: str) -> List[Dict[str, Any]]:
    """Find all matchups for the given pitcher."""
    matchups = []
    
    for game in data.get('games', []):
        # Check home pitcher vs away batters
        home_matchup = game.get('home_vs_away_pitcher', {})
        if home_matchup.get('pitcher_name') == pitcher_name:
            matchups.append({
                'pitcher_name': pitcher_name,
                'opposing_team': game.get('away_team'),
                'batters': home_matchup.get('batters', []),
                'game_info': f"Game {game.get('game_number', '?')} - {game.get('home_team')} vs {game.get('away_team')}"
            })
        
        # Check away pitcher vs home batters
        away_matchup = game.get('away_vs_home_pitcher', {})
        if away_matchup.get('pitcher_name') == pitcher_name:
            matchups.append({
                'pitcher_name': pitcher_name,
                'opposing_team': game.get('home_team'),
                'batters': away_matchup.get('batters', []),
                'game_info': f"Game {game.get('game_number', '?')} - {game.get('away_team')} vs {game.get('home_team')}"
            })
    
    return matchups


def distribute_plate_appearances(total_batters_faced: int, lineup_size: int = 9) -> List[int]:
    """
    Distribute total batters faced across a 9-batter lineup.
    
    Args:
        total_batters_faced: Total number of batters the pitcher will face
        lineup_size: Size of the batting lineup (default 9)
    
    Returns:
        List of plate appearances for each batter in the lineup
    """
    if lineup_size == 0:
        return []
    
    # Calculate base plate appearances for each batter
    base_pa = total_batters_faced // lineup_size
    remainder = total_batters_faced % lineup_size
    
    # Distribute plate appearances
    pa_distribution = [base_pa] * lineup_size
    
    # Add extra plate appearances to the first 'remainder' batters
    for i in range(remainder):
        pa_distribution[i] += 1
    
    return pa_distribution


def calculate_binomial_probability(n: int, k: int, p: float) -> float:
    """Calculate binomial probability P(X = k) where X ~ Binomial(n, p)."""
    if k > n or k < 0:
        return 0.0
    if p == 0:
        return 1.0 if k == 0 else 0.0
    if p == 1:
        return 1.0 if k == n else 0.0
    
    # Use math.comb for binomial coefficient
    try:
        return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))
    except (OverflowError, ValueError):
        return 0.0


def calculate_total_probability(batters: List[Dict[str, Any]], 
                              pa_distribution: List[int], 
                              stat_type: str, 
                              target: int) -> float:
    """
    Calculate the probability of achieving >= target occurrences of stat_type
    across all batters in the lineup.
    
    Args:
        batters: List of batter data with per_pa_probabilities
        pa_distribution: Number of plate appearances for each batter
        stat_type: Either 'hit' or 'strikeout'
        target: Target number of occurrences
    
    Returns:
        Probability of achieving >= target occurrences
    """
    if stat_type not in ['hit', 'strikeout']:
        raise ValueError("stat_type must be 'hit' or 'strikeout'")
    
    # Get probabilities for each batter
    batter_probabilities = []
    batter_pas = []
    
    for i, batter in enumerate(batters):
        if i < len(pa_distribution):
            pas = pa_distribution[i]
            if pas > 0:
                prob = batter.get('per_pa_probabilities', {}).get(stat_type, 0.0)
                batter_probabilities.append(prob)
                batter_pas.append(pas)
    
    if not batter_probabilities:
        return 0.0
    
    # Calculate probability distribution for total occurrences
    # We'll use dynamic programming to calculate P(total = k) for k = 0 to total_pa
    total_pa = sum(batter_pas)
    
    # dp[i][j] = probability of getting exactly j occurrences from first i batters
    dp = [[0.0 for _ in range(total_pa + 1)] for _ in range(len(batter_probabilities) + 1)]
    dp[0][0] = 1.0  # Base case: 0 batters, 0 occurrences
    
    for i in range(1, len(batter_probabilities) + 1):
        prob = batter_probabilities[i - 1]
        pas = batter_pas[i - 1]
        
        for j in range(total_pa + 1):
            # For each possible number of occurrences from this batter
            for k in range(min(pas, j) + 1):
                if j - k >= 0:
                    binom_prob = calculate_binomial_probability(pas, k, prob)
                    dp[i][j] += dp[i - 1][j - k] * binom_prob
    
    # Calculate P(total >= target)
    prob_ge_target = sum(dp[len(batter_probabilities)][j] for j in range(target, total_pa + 1))
    
    return prob_ge_target


def analyze_pitcher_probability(pitcher_name: str, 
                              total_batters_faced: int, 
                              stat_type: str, 
                              target: int,
                              date_str: str = None) -> float:
    """
    Main analysis function that returns the probability.
    
    Args:
        pitcher_name: Name of the pitcher to analyze
        total_batters_faced: Total number of batters the pitcher will face
        stat_type: Either 'hit' or 'strikeout'
        target: Target number of occurrences
        date_str: Date string in YYYY-MM-DD format (defaults to today)
    
    Returns:
        Probability as a float (0.0 to 1.0), or 0.0 if no matchups found
    """
    # Load data
    data = load_todays_data(date_str)
    
    # Find pitcher matchups
    matchups = find_pitcher_matchups(data, pitcher_name)
    
    if not matchups:
        print(f"No matchups found for pitcher '{pitcher_name}' in today's games.")
        return 0.0
    
    total_probability = 0.0
    matchup_count = 0
    
    for matchup in matchups:
        batters = matchup['batters']
        if not batters:
            continue
        
        # Sort batters by lineup position
        sorted_batters = sorted(batters, key=lambda x: x.get('lineup_position', 999))
        
        # Distribute plate appearances
        pa_distribution = distribute_plate_appearances(total_batters_faced, len(sorted_batters))
        
        # Calculate probability
        try:
            probability = calculate_total_probability(sorted_batters, pa_distribution, stat_type, target)
            total_probability += probability
            matchup_count += 1
        except Exception as e:
            print(f"Error calculating probability for {pitcher_name}: {e}")
    
    # Return average probability across all matchups
    return total_probability / matchup_count if matchup_count > 0 else 0.0


def process_csv_file(date_str=None):
    """
    Process CSV file for the specified date and calculate probabilities for each pitcher.
    Updates the CSV file with calculated odds.
    """
    # Use provided date or default to today
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    csv_filename = f"{date_str}.csv"
    
    try:
        # Read the CSV file with UTF-8-sig encoding to handle BOM
        rows = []
        with open(csv_filename, 'r', newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
        
        print(f"Processing {len(rows)} pitchers from {csv_filename}")
        print("=" * 60)
        
        # Process each row
        for row in rows:
            try:
                pitcher_name = row['pitcher_name']
                num_batters = int(row['num_batters']) if row['num_batters'] else 0
                target_ks = int(row['target_ks']) if row['target_ks'] else 0
                target_hits = int(row['target_hits']) if row['target_hits'] else 0
                
                # Skip if no targets are set
                if target_ks == 0 and target_hits == 0:
                    print(f"Skipping {pitcher_name} - no targets set")
                    continue
                
                print(f"\nProcessing {pitcher_name}...")
                
                # Calculate strikeout probability
                if target_ks > 0:
                    ks_probability = analyze_pitcher_probability(
                        pitcher_name, num_batters, 'strikeout', target_ks, date_str
                    )
                    row['ks_odds'] = f"{ks_probability * 100:.2f}%"
                    print(f"  Strikeouts: {ks_probability * 100:.2f}% (>= {target_ks} strikeouts)")
                
                # Calculate hits probability
                if target_hits > 0:
                    hits_probability = analyze_pitcher_probability(
                        pitcher_name, num_batters, 'hit', target_hits, date_str
                    )
                    row['hits_odds'] = f"{hits_probability * 100:.2f}%"
                    print(f"  Hits: {hits_probability * 100:.2f}% (>= {target_hits} hits)")
                
            except Exception as e:
                print(f"Error processing row for {row.get('pitcher_name', 'unknown')}: {e}")
                continue
        
        # Write back to CSV file
        with open(csv_filename, 'w', newline='') as csvfile:
            fieldnames = ['pitcher_name', 'num_batters', 'target_ks', 'target_hits', 'ks_odds', 'hits_odds']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"\n✓ Updated {csv_filename} with calculated probabilities")
        
    except FileNotFoundError:
        print(f"Error: Could not find file {csv_filename}")
    except Exception as e:
        print(f"Error processing CSV file: {e}")


def main(date_str=None):
    """Main entry point - process CSV file for the specified date."""
    process_csv_file(date_str)


if __name__ == "__main__":
    import sys
    
    # Check if date parameter was provided
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
        main(date_str)
    else:
        main()  # Use today's date by default
