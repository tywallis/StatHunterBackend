#!/usr/bin/env python3
"""
Script to find days when a specified player had a high chance of getting a specific stat
(strikeouts or hits) in per_game_probabilities by analyzing all JSON files in the ./json/ directory.
Now includes boxscore verification to check actual performance.
"""

import json
import os
import sys
import argparse
import statsapi
from datetime import datetime
from typing import List, Dict, Any

# Default player name - can be changed here or via command line argument
DEFAULT_PLAYER_NAME = "Joey Ortiz"



def get_game_boxscore(game_id: str) -> dict:
    """Get boxscore data for a specific game."""
    try:
        print(f"  Fetching boxscore for game {game_id}...")
        boxscore = statsapi.boxscore_data(game_id)
        return boxscore
    except Exception as e:
        print(f"Error fetching boxscore for game {game_id}: {e}")
        return None


def clean_player_name(name: str) -> str:
    """Clean player name for matching."""
    cleaned = name.strip().lower()
    cleaned = cleaned.replace(' jr.', '').replace(' sr.', '').replace(' jr', '').replace(' sr', '')
    cleaned = cleaned.replace(' ii', '').replace(' iii', '')
    return cleaned


def names_match(name1: str, name2: str) -> bool:
    """Check if two player names match using various approaches."""
    clean1 = clean_player_name(name1)
    clean2 = clean_player_name(name2)
    
    if clean1 == clean2:
        return True
    
    # Try last name matching
    name1_parts = clean1.split()
    name2_parts = clean2.split()
    
    if len(name1_parts) >= 2 and len(name2_parts) >= 2:
        if name1_parts[-1] == name2_parts[-1]:
            if name1_parts[0][0] == name2_parts[0][0]:
                return True
    
    # Try partial matching
    if clean1 in clean2 or clean2 in clean1:
        return True
    
    return False


def check_player_performance(player_name: str, team: str, boxscore: dict) -> dict:
    """Check if a player achieved their projected stats in the game."""
    if not boxscore:
        return {'found': False, 'stats': {}}
    
    result = {
        'found': False,
        'stats': {'hits': 0, 'strikeouts': 0, 'walks': 0}
    }
    
    # Search both teams' batting stats
    for team_key in ['home', 'away']:
        if team_key not in boxscore:
            continue
            
        team_data = boxscore[team_key]
        if 'players' not in team_data:
            continue
        
        for player_id, player_data in team_data['players'].items():
            if 'person' not in player_data:
                continue
            
            api_name = player_data['person'].get('fullName', '')
            
            if names_match(player_name, api_name):
                result['found'] = True
                
                if 'stats' in player_data and 'batting' in player_data['stats']:
                    batting_stats = player_data['stats']['batting']
                    
                    result['stats'] = {
                        'hits': batting_stats.get('hits', 0),
                        'strikeouts': batting_stats.get('strikeOuts', 0),
                        'walks': batting_stats.get('baseOnBalls', 0)
                    }
                
                return result
    
    return result


def find_player_high_probability_days(player_name: str, stat_type: str = "strikeout", json_dir: str = "./json/", threshold: float = 0.9, verify_boxscores: bool = False) -> List[Dict[str, Any]]:
    """
    Find days when a specified player had a stat probability >= threshold.
    
    Args:
        player_name: Name of the player to search for
        stat_type: Type of stat to analyze ("strikeout" or "hit")
        json_dir: Directory containing JSON files
        threshold: Minimum probability threshold (default 0.9 for 90%)
        verify_boxscores: Whether to fetch and verify actual game results
    
    Returns:
        List of dictionaries containing date, probability, and game info
    """
    high_probability_days = []
    
    # Validate stat_type
    if stat_type not in ["strikeout", "hit"]:
        raise ValueError("stat_type must be either 'strikeout' or 'hit'")
    
    # Get all JSON files in the directory
    json_files = [f for f in os.listdir(json_dir) if f.endswith('.json')]
    json_files.sort()  # Sort by filename (which should be dates)
    
    print(f"Analyzing {len(json_files)} JSON files for player: {player_name} ({stat_type}s)...")
    if verify_boxscores:
        print("Boxscore verification enabled - this will take longer but provide actual results")
    
    for filename in json_files:
        filepath = os.path.join(json_dir, filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
            continue
        
        date = data.get('date', filename.replace('.json', ''))
        
        # First pass: find games where player has high probability
        high_prob_games = []
        
        # Search through all games for the specified player
        for game in data.get('games', []):
            # Check both home and away teams
            for team_key in ['home_vs_away_pitcher', 'away_vs_home_pitcher']:
                if team_key not in game:
                    continue
                
                pitcher_data = game[team_key]
                batters = pitcher_data.get('batters', [])
                
                for batter in batters:
                    if batter.get('name') == player_name:
                        per_game_probs = batter.get('per_game_probabilities', {})
                        stat_prob = per_game_probs.get(stat_type, 0)
                        
                        if stat_prob >= threshold:
                            # Store this game and batter info for processing
                            high_prob_games.append({
                                'game': game,
                                'batter': batter,
                                'stat_prob': stat_prob,
                                'per_game_probs': per_game_probs
                            })
        
        # Second pass: only fetch boxscores for high-probability games if verification is enabled
        game_boxscores = {}
        if verify_boxscores and high_prob_games:
            print(f"  Found {len(high_prob_games)} high-probability game(s) on {date}, fetching boxscores...")
            for high_prob_game in high_prob_games:
                game = high_prob_game['game']
                if game.get('error') is None:
                    game_id = str(game['game_pk'])
                    if game_id not in game_boxscores:  # Avoid duplicate fetches
                        boxscore = get_game_boxscore(game_id)
                        if boxscore:
                            game_boxscores[game_id] = boxscore
        
        # Third pass: process the high-probability games and add verification data
        for high_prob_game in high_prob_games:
            game = high_prob_game['game']
            batter = high_prob_game['batter']
            per_game_probs = high_prob_game['per_game_probs']
            stat_prob = high_prob_game['stat_prob']
            
            game_entry = {
                'date': date,
                'stat_type': stat_type,
                f'{stat_type}_probability': stat_prob,
                'vs_pitcher': batter.get('vs_pitcher', 'Unknown'),
                'team': batter.get('team', 'Unknown'),
                'lineup_position': batter.get('lineup_position', 'Unknown'),
                'game_number': game.get('game_number', 'Unknown'),
                'home_team': game.get('home_team', 'Unknown'),
                'away_team': game.get('away_team', 'Unknown'),
                'hit_probability': per_game_probs.get('hit', 0),
                'strikeout_probability': per_game_probs.get('strikeout', 0),
                'walk_probability': per_game_probs.get('walk', 0)
            }
            
            # Add boxscore verification if enabled
            if verify_boxscores:
                game_id = str(game['game_pk'])
                if game_id in game_boxscores:
                    performance = check_player_performance(
                        player_name, 
                        batter.get('team', 'Unknown'), 
                        game_boxscores[game_id]
                    )
                    
                    if performance['found']:
                        stats = performance['stats']
                        actual_stat_count = stats[stat_type + 's']  # 'strikeouts' or 'hits'
                        
                        game_entry.update({
                            'verified': True,
                            'actual_hits': stats['hits'],
                            'actual_strikeouts': stats['strikeouts'],
                            'actual_walks': stats['walks'],
                            f'actual_{stat_type}s': actual_stat_count,
                            'achieved_1_plus': actual_stat_count >= 1,
                            'achieved_2_plus': actual_stat_count >= 2,
                            'achieved_3_plus': actual_stat_count >= 3
                        })
                    else:
                        game_entry.update({
                            'verified': False,
                            'verification_error': 'Player not found in boxscore'
                        })
                else:
                    game_entry.update({
                        'verified': False,
                        'verification_error': 'Boxscore not available'
                    })
            else:
                game_entry['verified'] = False
            
            high_probability_days.append(game_entry)
    
    return high_probability_days


def display_results(results: List[Dict[str, Any]], player_name: str, threshold: float = 0.9, stat_type: str = 'strikeout'):
    """Display the results in a formatted way."""
    if not results:
        print(f"\nNo days found where {player_name} had a {threshold*100}%+ {stat_type} probability.")
        return
    
    print(f"\nFound {len(results)} instance(s) where {player_name} had a {threshold*100}%+ {stat_type} probability:")
    print("=" * 120)
    
    # Count verified results
    verified_count = sum(1 for r in results if r.get('verified', False))
    if verified_count > 0:
        print(f"Boxscore verification available for {verified_count}/{len(results)} games")
        print("=" * 120)
    
    for result in results:
        print(f"Date: {result['date']}")
        
        # Display the probability for the requested stat type
        stat_prob_key = f'{stat_type}_probability'
        print(f"  {stat_type.title()} Probability: {result[stat_prob_key]:.1%}")
        
        print(f"  vs Pitcher: {result['vs_pitcher']}")
        print(f"  Team: {result['team']}")
        print(f"  Lineup Position: {result['lineup_position']}")
        print(f"  Game: {result['home_team']} vs {result['away_team']} (Game {result['game_number']})")
        
        # Display other probabilities
        if stat_type == 'strikeout':
            print(f"  Hit Probability: {result['hit_probability']:.1%}")
            print(f"  Walk Probability: {result['walk_probability']:.1%}")
        else:  # hit
            print(f"  Strikeout Probability: {result['strikeout_probability']:.1%}")
            print(f"  Walk Probability: {result['walk_probability']:.1%}")
        
        # Show verification results if available
        if result.get('verified', False):
            actual_stat_count = result[f'actual_{stat_type}s']
            print(f"  📊 ACTUAL RESULTS:")
            print(f"    Hits: {result['actual_hits']}, Strikeouts: {result['actual_strikeouts']}, Walks: {result['actual_walks']}")
            
            # Show achievement status with emojis
            status_1 = "✅" if result['achieved_1_plus'] else "❌"
            status_2 = "✅" if result['achieved_2_plus'] else "❌"
            status_3 = "✅" if result['achieved_3_plus'] else "❌"
            
            print(f"    Achievement Status:")
            print(f"      1+ {stat_type.title()}s: {status_1} ({'YES' if result['achieved_1_plus'] else 'NO'})")
            print(f"      2+ {stat_type.title()}s: {status_2} ({'YES' if result['achieved_2_plus'] else 'NO'})")
            print(f"      3+ {stat_type.title()}s: {status_3} ({'YES' if result['achieved_3_plus'] else 'NO'})")
            
        elif 'verification_error' in result:
            print(f"  ⚠️  Verification failed: {result['verification_error']}")
        
        print("-" * 80)


def print_verification_summary(results: List[Dict[str, Any]], player_name: str, threshold: float, stat_type: str):
    """Print summary statistics for verified results."""
    verified_results = [r for r in results if r.get('verified', False)]
    
    if not verified_results:
        print(f"\n⚠️  No verified results available for analysis")
        return
    
    print(f"\n{'='*100}")
    print(f"VERIFICATION SUMMARY FOR {player_name.upper()}")
    print(f"{'='*100}")
    
    total_verified = len(verified_results)
    
    # Count achievements
    achieved_1_plus = sum(1 for r in verified_results if r['achieved_1_plus'])
    achieved_2_plus = sum(1 for r in verified_results if r['achieved_2_plus'])
    achieved_3_plus = sum(1 for r in verified_results if r['achieved_3_plus'])
    
    # Calculate percentages
    pct_1_plus = (achieved_1_plus / total_verified * 100) if total_verified > 0 else 0
    pct_2_plus = (achieved_2_plus / total_verified * 100) if total_verified > 0 else 0
    pct_3_plus = (achieved_3_plus / total_verified * 100) if total_verified > 0 else 0
    
    print(f"Total verified high-probability days: {total_verified}")
    print(f"Threshold used: {threshold*100}%")
    print(f"Stat type: {stat_type}")
    print()
    print(f"ACTUAL ACHIEVEMENT RATES:")
    print(f"  1+ {stat_type.title()}s: {achieved_1_plus}/{total_verified} ({pct_1_plus:.1f}%)")
    print(f"  2+ {stat_type.title()}s: {achieved_2_plus}/{total_verified} ({pct_2_plus:.1f}%)")
    print(f"  3+ {stat_type.title()}s: {achieved_3_plus}/{total_verified} ({pct_3_plus:.1f}%)")
    
    # Show prediction accuracy
    print(f"\nPREDICTION ACCURACY:")
    print(f"  High probability predictions that achieved 1+ {stat_type}s: {pct_1_plus:.1f}%")
    
    # Calculate average actual stats on high-probability days
    total_stat_count = sum(r[f'actual_{stat_type}s'] for r in verified_results)
    avg_stat_count = total_stat_count / total_verified if total_verified > 0 else 0
    
    print(f"\n{stat_type.upper()} PERFORMANCE ON HIGH-PROBABILITY DAYS:")
    print(f"  Average {stat_type}s per game: {avg_stat_count:.2f}")
    print(f"  Total {stat_type}s across all games: {total_stat_count}")
    
    # Show distribution of actual stats
    stat_distribution = {}
    for r in verified_results:
        stat_count = r[f'actual_{stat_type}s']
        stat_distribution[stat_count] = stat_distribution.get(stat_count, 0) + 1
    
    print(f"\n{stat_type.upper()} DISTRIBUTION:")
    for stat_count in sorted(stat_distribution.keys()):
        count = stat_distribution[stat_count]
        pct = count / total_verified * 100
        print(f"  {stat_count} {stat_type}s: {count} games ({pct:.1f}%)")
    
    # Show best performances (3+ of the stat)
    triple_plus_games = [r for r in verified_results if r['achieved_3_plus']]
    if triple_plus_games:
        print(f"\n🔥 EXCEPTIONAL PERFORMANCES (3+ {stat_type}s):")
        for game in triple_plus_games:
            actual_count = game[f'actual_{stat_type}s']
            prob_key = f'{stat_type}_probability'
            print(f"  {game['date']}: {actual_count} {stat_type}s vs {game['vs_pitcher']} ({game[prob_key]:.1%} predicted)")
    else:
        # Show best performances that did occur
        best_games = sorted(verified_results, key=lambda x: x[f'actual_{stat_type}s'], reverse=True)[:3]
        if best_games and best_games[0][f'actual_{stat_type}s'] > 0:
            print(f"\n🔥 EXCEPTIONAL PERFORMANCES (3+ {stat_type}s):")
            for game in best_games:
                actual_count = game[f'actual_{stat_type}s']
                prob_key = f'{stat_type}_probability'
                if actual_count > 0:  # Only show games with actual achievements
                    print(f"  {game['date']}: {actual_count} {stat_type}s vs {game['vs_pitcher']} ({game[prob_key]:.1%} predicted)")
    
    # Calculate probability ranges and their success rates
    print(f"\nSUCCESS RATES BY PROBABILITY RANGE:")
    
    # Group by probability ranges
    ranges = [
        (0.90, 0.92, "90-92%"),
        (0.92, 0.94, "92-94%"),
        (0.94, 0.96, "94-96%"),
        (0.96, 1.00, "96%+")
    ]
    
    for min_prob, max_prob, range_label in ranges:
        prob_key = f'{stat_type}_probability'
        range_results = [r for r in verified_results 
                        if min_prob <= r[prob_key] < max_prob]
        
        if range_results:
            range_total = len(range_results)
            range_1_plus = sum(1 for r in range_results if r['achieved_1_plus'])
            range_2_plus = sum(1 for r in range_results if r['achieved_2_plus'])
            
            pct_1 = (range_1_plus / range_total * 100) if range_total > 0 else 0
            pct_2 = (range_2_plus / range_total * 100) if range_total > 0 else 0
            
            print(f"  {range_label}: {range_total} games → 1+: {pct_1:.1f}%, 2+: {pct_2:.1f}%")


def main():
    """Main function to run the analysis."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Find days when a player had high stat probability")
    parser.add_argument('--player', '-p', type=str, default=DEFAULT_PLAYER_NAME,
                        help=f"Player name to analyze (default: {DEFAULT_PLAYER_NAME})")
    parser.add_argument('--stat-type', '-s', type=str, default='strikeout', choices=['strikeout', 'hit'],
                        help="Type of stat to analyze (default: strikeout)")
    parser.add_argument('--threshold', '-t', type=float, default=0.9,
                        help="Minimum probability threshold (default: 0.9)")
    parser.add_argument('--json-dir', '-d', type=str, default="./json/",
                        help="Directory containing JSON files (default: ./json/)")
    parser.add_argument('--verify', '-v', action='store_true',
                        help="Verify predictions against actual boxscore results (slower but more accurate)")
    
    args = parser.parse_args()
    
    player_name = args.player
    stat_type = args.stat_type
    threshold = args.threshold
    json_dir = args.json_dir
    verify_boxscores = args.verify
    
    print(f"High {stat_type.title()} Probability Finder for {player_name}")
    print("=" * 80)
    print(f"Stat type: {stat_type}")
    print(f"Threshold: {threshold*100}%")
    print(f"Boxscore verification: {'ENABLED' if verify_boxscores else 'DISABLED'}")
    print("=" * 80)
    
    # Find days with high probability
    results = find_player_high_probability_days(player_name, stat_type, json_dir, threshold, verify_boxscores)
    display_results(results, player_name, threshold, stat_type)
    
    # Show summary statistics if verification was enabled
    if verify_boxscores and results:
        print_verification_summary(results, player_name, threshold, stat_type)
    
    # Show basic summary statistics
    if results:
        stat_prob_key = f'{stat_type}_probability'
        stat_probs = [r[stat_prob_key] for r in results]
        print(f"\n{'='*80}")
        print(f"BASIC SUMMARY STATISTICS")
        print(f"{'='*80}")
        print(f"Total high-probability days found: {len(results)}")
        print(f"Highest {stat_type} probability: {max(stat_probs):.1%}")
        print(f"Average {stat_type} probability: {sum(stat_probs)/len(stat_probs):.1%}")
        
        # Group by pitcher
        pitcher_counts = {}
        for result in results:
            pitcher = result['vs_pitcher']
            if pitcher not in pitcher_counts:
                pitcher_counts[pitcher] = []
            pitcher_counts[pitcher].append(result[stat_prob_key])
        
        print(f"\nPitchers faced on high {stat_type} probability days:")
        for pitcher, probs in pitcher_counts.items():
            avg_prob = sum(probs) / len(probs)
            print(f"  {pitcher}: {len(probs)} game(s), avg {avg_prob:.1%}")


if __name__ == "__main__":
    main()
