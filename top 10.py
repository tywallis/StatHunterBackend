import json
import pandas as pd
from typing import List, Dict, Any

def load_json_data(filename: str) -> Dict[str, Any]:
    """Load JSON data from file"""
    with open(filename, 'r') as f:
        return json.load(f)

def extract_batter_data(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract all batter data from the JSON structure"""
    all_batters = []
    
    for game in data['games']:
        # Process home team batters vs away pitcher
        if 'home_vs_away_pitcher' in game:
            pitcher_name = game['home_vs_away_pitcher']['pitcher_name']
            for batter in game['home_vs_away_pitcher']['batters']:
                batter_record = {
                    'batter_name': batter['name'],
                    'pitcher_name': pitcher_name,
                    'team': batter['team'],
                    'hit_prob': batter['per_game_probabilities']['hit'],
                    'strikeout_prob': batter['per_game_probabilities']['strikeout'],
                    'walk_prob': batter['per_game_probabilities']['walk'],
                    'game_number': game['game_number']
                }
                all_batters.append(batter_record)
        
        # Process away team batters vs home pitcher
        if 'away_vs_home_pitcher' in game:
            pitcher_name = game['away_vs_home_pitcher']['pitcher_name']
            for batter in game['away_vs_home_pitcher']['batters']:
                batter_record = {
                    'batter_name': batter['name'],
                    'pitcher_name': pitcher_name,
                    'team': batter['team'],
                    'hit_prob': batter['per_game_probabilities']['hit'],
                    'strikeout_prob': batter['per_game_probabilities']['strikeout'],
                    'walk_prob': batter['per_game_probabilities']['walk'],
                    'game_number': game['game_number']
                }
                all_batters.append(batter_record)
    
    return all_batters

def find_top_10_outcomes(batters: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Find top 10 batters for each outcome"""
    
    # Sort by each outcome and get top 10
    top_hits = sorted(batters, key=lambda x: x['hit_prob'], reverse=True)[:10]
    top_strikeouts = sorted(batters, key=lambda x: x['strikeout_prob'], reverse=True)[:10]
    top_walks = sorted(batters, key=lambda x: x['walk_prob'], reverse=True)[:10]
    
    return {
        'Hit': top_hits,
        'Strikeout': top_strikeouts,
        'Walk': top_walks
    }

def print_results(results: Dict[str, List[Dict[str, Any]]]):
    """Print formatted results to terminal"""
    print("=" * 80)
    print("BASEBALL OUTCOME PROBABILITIES - TOP 10 ANALYSIS")
    print("=" * 80)
    
    outcome_mapping = {
        'Hit': 'hit_prob',
        'Strikeout': 'strikeout_prob',
        'Walk': 'walk_prob'
    }
    
    for outcome_type, batters in results.items():
        print(f"\n🏆 TOP 10 MOST LIKELY TO {outcome_type.upper()}")
        print("-" * 80)
        
        if not batters:
            print(f"No data found for {outcome_type}")
            continue
        
        prob_key = outcome_mapping[outcome_type]
        
        for i, batter in enumerate(batters, 1):
            name = batter['batter_name']
            pitcher = batter['pitcher_name']
            prob = batter[prob_key]
            team = batter['team']
            game_num = batter['game_number']
            
            # Format probability as percentage
            prob_str = f"{prob:.1%}"
            
            print(f"{i:2d}. {name:<20} ({team}) vs {pitcher:<20} | {prob_str} | Game {game_num}")
    
    print("\n" + "=" * 80)

def main():
    try:
        # Load JSON data
        filename = '2025-07-19.json'  # Your JSON filename
        data = load_json_data(filename)
        
        print(f"Data loaded successfully from {filename}!")
        print(f"Date: {data['date']}")
        print(f"Total games: {data['total_games']}")
        
        # Extract all batter data
        all_batters = extract_batter_data(data)
        print(f"Total batter matchups: {len(all_batters)}")
        
        # Find top 10 for each outcome
        results = find_top_10_outcomes(all_batters)
        
        # Print results
        print_results(results)
        
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found. Please check the filename and path.")
    except KeyError as e:
        print(f"Error: Missing key in JSON data: {e}")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()