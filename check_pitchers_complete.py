#!/usr/bin/env python3
"""
Complete Pitcher Analysis Script

This script combines the functionality of check_pitchers_p1.py and check_pitchers_p2.py
into a single comprehensive pitcher analysis tool that:

1. Processes daily JSON game data
2. Retrieves pitcher statistics from DynamoDB
3. Fetches odds data from The Odds API to set targets
4. Calculates probability outcomes
5. Generates a complete CSV file with all analysis

Usage:
    python check_pitchers_complete.py [date]
    
    date: Optional date in YYYY-MM-DD format (defaults to today)
"""

import json
import csv
import math
import boto3
import requests
from datetime import datetime, timedelta
from itertools import combinations_with_replacement
from typing import List, Dict, Tuple, Any, Optional


# Team name mapping for The Odds API
TEAM_MAPPING = {
    "ARI": "Arizona Diamondbacks",
    "ATL": "Atlanta Braves", 
    "BAL": "Baltimore Orioles",
    "BOS": "Boston Red Sox",
    "CHC": "Chicago Cubs",
    "CWS": "Chicago White Sox",
    "CIN": "Cincinnati Reds",
    "CLE": "Cleveland Guardians",
    "COL": "Colorado Rockies",
    "DET": "Detroit Tigers",
    "HOU": "Houston Astros",
    "KC": "Kansas City Royals",
    "LAA": "Los Angeles Angels",
    "LAD": "Los Angeles Dodgers",
    "MIA": "Miami Marlins",
    "MIL": "Milwaukee Brewers",
    "MIN": "Minnesota Twins",
    "NYM": "New York Mets",
    "NYY": "New York Yankees",
    "OAK": "Oakland Athletics",
    "PHI": "Philadelphia Phillies",
    "PIT": "Pittsburgh Pirates",
    "SD": "San Diego Padres",
    "SF": "San Francisco Giants",
    "SEA": "Seattle Mariners",
    "STL": "St. Louis Cardinals",
    "TB": "Tampa Bay Rays",
    "TEX": "Texas Rangers",
    "TOR": "Toronto Blue Jays",
    "WSH": "Washington Nationals"
}

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("custom-player-data")


def get_odds_api_key():
    """Retrieve API key from AWS Secrets Manager."""
    secret_name = "apiKeys/the-odds-api"
    region_name = "us-east-1"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except Exception as e:
        print(f"CRITICAL ERROR: Could not retrieve API key from Secrets Manager: {e}")
        raise SystemExit("Script terminated: Odds API key is required for accurate analysis")

    secret = get_secret_value_response["SecretString"]
    secret_dict = json.loads(secret)  # Parse the JSON string to get the actual secret value
    return secret_dict["ODDS_API_KEY"]  # Return just the API key value


def get_mlb_events(date_str: str, game_start_time: str = None):
    """
    Fetch MLB events from The Odds API for the given date.
    
    Args:
        date_str: Date string in YYYY-MM-DD format
        game_start_time: Optional specific game start time for historical queries
    
    Returns:
        List of events from The Odds API
    """
    api_key = get_odds_api_key()
    if not api_key:
        print("CRITICAL ERROR: No Odds API key available")
        raise SystemExit("Script terminated: Odds API key is required for accurate analysis")
    
    # Determine if this is a current or historical request
    today = datetime.now().strftime("%Y-%m-%d")
    is_current = (date_str == today)
    
    if is_current:
        # Use current events endpoint for today
        url = "https://api.the-odds-api.com/v4/sports/baseball_mlb/events"
        params = {
            "apiKey": api_key,
            "regions": "us"
        }
    else:
        # Use historical events endpoint for past dates
        url = "https://api.the-odds-api.com/v4/historical/sports/baseball_mlb/events"
        
        # If game_start_time is provided, subtract 10 minutes for the query
        if game_start_time:
            query_time = datetime.fromisoformat(game_start_time.replace('Z', '+00:00'))
            query_time = query_time - timedelta(minutes=10)
            date_param = query_time.isoformat()
        else:
            # Default to start of the day for the given date
            date_param = f"{date_str}T00:00:00Z"
        
        params = {
            "apiKey": api_key,
            "regions": "us",
            "date": date_param
        }
    
    try:
        print("Fetching MLB events from The Odds API...")
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        # The API returns a list directly, not a dict with 'data' field
        events = data if isinstance(data, list) else []
        print(f"Found {len(events)} events from Odds API")
        return events
        
    except requests.exceptions.RequestException as e:
        print(f"CRITICAL ERROR: Failed to fetch events from Odds API: {e}")
        raise SystemExit("Script terminated: Odds API request failed")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to process Odds API response: {e}")
        raise SystemExit("Script terminated: Odds API response processing failed")


def find_matching_event(events, home_team, away_team):
    """
    Find the matching event from Odds API events based on team names.
    
    Args:
        events: List of events from Odds API
        home_team: Home team abbreviation (e.g., "WSH")
        away_team: Away team abbreviation (e.g., "MIA")
    
    Returns:
        Event ID if found, None otherwise
    """
    home_team_full = TEAM_MAPPING.get(home_team)
    away_team_full = TEAM_MAPPING.get(away_team)
    
    if not home_team_full or not away_team_full:
        return None
    
    for event in events:
        event_home = event.get("home_team")
        event_away = event.get("away_team")
        
        if event_home == home_team_full and event_away == away_team_full:
            return event.get("id")
    
    return None


def get_pitcher_odds_targets(event_id: str, pitcher_name: str):
    """
    Get target strikeouts and hits for a pitcher from The Odds API.
    
    Args:
        event_id: The Odds API event ID
        pitcher_name: Name of the pitcher
    
    Returns:
        Dictionary with target_ks and target_hits
    """
    api_key = get_odds_api_key()
    if not api_key:
        print("CRITICAL ERROR: No Odds API key available for target extraction")
        raise SystemExit("Script terminated: Odds API key is required for target extraction")
    
    url = f"https://api.the-odds-api.com/v4/sports/baseball_mlb/events/{event_id}/odds"
    params = {
        "apiKey": api_key,
        "markets": "pitcher_strikeouts_alternate,pitcher_hits_allowed_alternate",
        "regions": "us"
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        # Handle different response formats
        if isinstance(data, dict) and "data" in data:
            # Historical format
            odds_data = data["data"]
        elif isinstance(data, list):
            # Current format
            odds_data = data
        else:
            # Single event object
            odds_data = [data] if isinstance(data, dict) else []
        
        # Extract pitcher targets using best odds logic
        targets = {'target_ks': None, 'target_hits': None}
        
        for odds_event in odds_data:
            bookmakers = odds_event.get("bookmakers", [])
            
            # Process each market type
            for market_type in ["pitcher_strikeouts_alternate", "pitcher_hits_allowed_alternate"]:
                target_key = 'target_ks' if market_type == "pitcher_strikeouts_alternate" else 'target_hits'
                
                # Collect all lines and their best odds across all bookmakers
                line_odds = {}  # {point: best_price}
                
                for bookmaker in bookmakers:
                    markets = bookmaker.get("markets", [])
                    
                    for market in markets:
                        if market.get("key") != market_type:
                            continue
                            
                        outcomes = market.get("outcomes", [])
                        
                        for outcome in outcomes:
                            outcome_name = outcome.get("name", "")
                            outcome_desc = outcome.get("description", "")
                            point = outcome.get("point")
                            price = outcome.get("price")
                            
                            # Check if this outcome is for our pitcher (name is in description)
                            if pitcher_name.lower() not in outcome_desc.lower():
                                continue
                            
                            # For pitcher markets, we want "Over" outcomes with points
                            if outcome_name == "Over" and point is not None and price is not None:
                                # Convert point to float for comparison
                                point_float = float(point)
                                
                                # Track the best (highest) price for this line
                                if point_float not in line_odds or price > line_odds[point_float]:
                                    line_odds[point_float] = price
                
                if line_odds:
                    # Find the line closest to even odds (price closest to 2.0 in decimal odds)
                    closest_to_even = None
                    closest_distance = float('inf')
                    
                    for point_float, price in line_odds.items():
                        # Calculate distance from even odds (2.0 = +100 American odds)
                        distance = abs(price - 2.0)
                        
                        if distance < closest_distance:
                            closest_distance = distance
                            closest_to_even = point_float
                    
                    if closest_to_even is not None:
                        # Round up to nearest integer
                        target_value = int(closest_to_even + 0.5)  # This rounds X.5 up to X+1
                        targets[target_key] = target_value
        
        # Ensure we found at least one target, otherwise fail
        if targets['target_ks'] is None and targets['target_hits'] is None:
            print(f"CRITICAL ERROR: No odds data found for pitcher {pitcher_name} in event {event_id}")
            raise SystemExit(f"Script terminated: No odds markets available for {pitcher_name}")
        
        print(f"Found targets for {pitcher_name}: K's={targets['target_ks']}, Hits={targets['target_hits']}")
        return targets
        
    except requests.exceptions.RequestException as e:
        print(f"CRITICAL ERROR: Failed to fetch odds for event {event_id}: {e}")
        raise SystemExit(f"Script terminated: Odds API request failed for {pitcher_name}")
    except SystemExit:
        raise  # Re-raise SystemExit exceptions
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to process odds data for {pitcher_name}: {e}")
        raise SystemExit(f"Script terminated: Odds processing failed for {pitcher_name}")


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


def get_pitcher_avg_batters_faced(pitcher_id, days_back=30):
    """Get the average number of batters faced by a pitcher in the last N days."""
    try:
        # Calculate the date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        # Get pitcher data directly by player_id
        response = table.get_item(Key={"player_id": pitcher_id})

        if "Item" not in response:
            return None

        # Get the pitcher's data
        pitcher_data = response["Item"]
        past_games = pitcher_data.get("past_games", {})

        total_batters = 0
        game_count = 0

        # Process each game within the date range
        for date_str, game_data in past_games.items():
            try:
                game_date = datetime.strptime(date_str, "%Y-%m-%d")
                if start_date <= game_date <= end_date:
                    pitch_tracking = game_data.get("pitch_tracking", {})
                    pitching_data = pitch_tracking.get("pitching", {})
                    batters_faced = pitching_data.get("total_batters_faced", 0)

                    if batters_faced > 0:
                        total_batters += batters_faced
                        game_count += 1
            except (ValueError, KeyError):
                continue

        if game_count == 0:
            return None

        # Return average rounded to nearest integer
        return round(total_batters / game_count)

    except Exception as e:
        print(f"Error retrieving data for pitcher ID {pitcher_id}: {e}")
        return None


def get_pitcher_stats_from_dynamo(pitcher_ids: List[str]) -> Dict[str, Dict]:
    """
    Retrieve pitcher statistics from DynamoDB for multiple pitcher IDs.
    
    Args:
        pitcher_ids: List of pitcher IDs to look up
    
    Returns:
        Dictionary mapping pitcher_id to their stats
    """
    try:
        pitcher_stats = {}
        
        for pitcher_id in pitcher_ids:
            try:
                response = table.get_item(Key={'player_id': pitcher_id})
                if 'Item' in response:
                    pitcher_stats[pitcher_id] = response['Item']
                else:
                    print(f"CRITICAL ERROR: No DynamoDB entry found for pitcher ID: {pitcher_id}")
                    raise SystemExit(f"Script terminated: Missing pitcher data for ID {pitcher_id}")
            except Exception as e:
                print(f"CRITICAL ERROR: Could not retrieve stats for pitcher {pitcher_id}: {e}")
                raise SystemExit(f"Script terminated: DynamoDB access failed for pitcher {pitcher_id}")
        
        return pitcher_stats
        
    except SystemExit:
        raise  # Re-raise SystemExit exceptions
    except Exception as e:
        print(f"CRITICAL ERROR: Could not connect to DynamoDB: {e}")
        raise SystemExit("Script terminated: DynamoDB connection failed")


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
                              data: Dict[str, Any]) -> float:
    """
    Calculate the probability for a pitcher achieving a target.
    
    Args:
        pitcher_name: Name of the pitcher to analyze
        total_batters_faced: Total number of batters the pitcher will face
        stat_type: Either 'hit' or 'strikeout'
        target: Target number of occurrences
        data: The loaded JSON data
    
    Returns:
        Probability as a float (0.0 to 1.0), or 0.0 if no matchups found
    """
    # Find pitcher matchups
    matchups = find_pitcher_matchups(data, pitcher_name)
    
    if not matchups:
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


def main(date_str: str = None):
    """
    Main function that processes the complete pitcher analysis.
    
    Args:
        date_str: Date string in YYYY-MM-DD format (defaults to today)
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    print(f"Processing complete pitcher analysis for date: {date_str}")
    print("=" * 60)
    
    # Step 1: Load JSON data
    try:
        print(f"Processing file: {date_str}.json for date {date_str}")
        with open(f"{date_str}.json", "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File {date_str}.json not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in file {date_str}.json")
        return
    
    # Step 2: Get Odds API events
    mlb_events = get_mlb_events(date_str)
    
    # Step 3: Process games and find opposing pitchers
    opposing_pitchers = {}
    
    for game in data.get("games", []):
        home_team = game.get("home_team")
        away_team = game.get("away_team")
        
        # Process home vs away matchup
        home_vs_away = game.get("home_vs_away_pitcher")
        if home_vs_away and "batters" in home_vs_away:
            pitcher_name = home_vs_away.get("pitcher_name")
            pitcher_id = home_vs_away.get("pitcher_id")
            if pitcher_name and pitcher_id and len(home_vs_away["batters"]) >= 9:
                opposing_pitchers[pitcher_name] = {
                    "pitcher_id": pitcher_id,
                    "home_team": home_team,
                    "away_team": away_team
                }
        
        # Process away vs home matchup
        away_vs_home = game.get("away_vs_home_pitcher")
        if away_vs_home and "batters" in away_vs_home:
            pitcher_name = away_vs_home.get("pitcher_name")
            pitcher_id = away_vs_home.get("pitcher_id")
            if pitcher_name and pitcher_id and len(away_vs_home["batters"]) >= 9:
                opposing_pitchers[pitcher_name] = {
                    "pitcher_id": pitcher_id,
                    "home_team": home_team,
                    "away_team": away_team
                }
    
    print(f"Found {len(opposing_pitchers)} unique opposing pitchers for teams with complete lineups.")
    
    # Step 4: Process each pitcher and get odds data
    processed_count = 0
    pitcher_data = []
    
    for pitcher_name, info in opposing_pitchers.items():
        pitcher_id = info["pitcher_id"]
        home_team = info["home_team"]
        away_team = info["away_team"]
        
        # Get num_batters using the average calculation function
        num_batters = get_pitcher_avg_batters_faced(pitcher_id)
        
        if num_batters is None or num_batters == 0:
            print(f"CRITICAL ERROR: No batters faced data for pitcher {pitcher_name} (ID: {pitcher_id})")
            raise SystemExit(f"Script terminated: Missing critical data for {pitcher_name}")
        
        # Find matching event and get targets from Odds API
        event_id = find_matching_event(mlb_events, home_team, away_team)
        targets = {'target_ks': None, 'target_hits': None}
        
        if event_id:
            print(f"Found matching event: {TEAM_MAPPING.get(away_team, away_team)} @ {TEAM_MAPPING.get(home_team, home_team)} (ID: {event_id})")
            targets = get_pitcher_odds_targets(event_id, pitcher_name)
        else:
            print(f"CRITICAL ERROR: No matching event found for {TEAM_MAPPING.get(away_team, away_team)} @ {TEAM_MAPPING.get(home_team, home_team)}")
            raise SystemExit(f"Script terminated: No odds event found for game {away_team} @ {home_team}")
        
        # Ensure we have targets - this is now guaranteed by get_pitcher_odds_targets
        
        # Calculate probabilities - both must be calculated for valid analysis
        ks_odds = ""
        hits_odds = ""
        
        if targets['target_ks']:
            ks_probability = analyze_pitcher_probability(
                pitcher_name, num_batters, 'strikeout', targets['target_ks'], data
            )
            if ks_probability == 0.0:
                print(f"CRITICAL ERROR: Could not calculate strikeout probability for {pitcher_name}")
                raise SystemExit(f"Script terminated: Probability calculation failed for {pitcher_name}")
            ks_odds = f"{ks_probability * 100:.2f}%"
        
        if targets['target_hits']:
            hits_probability = analyze_pitcher_probability(
                pitcher_name, num_batters, 'hit', targets['target_hits'], data
            )
            if hits_probability == 0.0:
                print(f"CRITICAL ERROR: Could not calculate hits probability for {pitcher_name}")
                raise SystemExit(f"Script terminated: Probability calculation failed for {pitcher_name}")
            hits_odds = f"{hits_probability * 100:.2f}%"
        
        pitcher_data.append({
            'pitcher_name': pitcher_name,
            'num_batters': num_batters,
            'target_ks': targets['target_ks'] if targets['target_ks'] else '',
            'target_hits': targets['target_hits'] if targets['target_hits'] else '',
            'ks_odds': ks_odds,
            'hits_odds': hits_odds
        })
        
        processed_count += 1
        if processed_count % 5 == 0:
            print(f"Processed {processed_count}/{len(opposing_pitchers)} pitchers...")
    
    # Step 6: Create CSV file
    csv_filename = f"{date_str}.csv"
    
    with open(csv_filename, 'w', newline='') as csvfile:
        fieldnames = ['pitcher_name', 'num_batters', 'target_ks', 'target_hits', 'ks_odds', 'hits_odds']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(pitcher_data)
    
    print(f"\nCSV file created successfully: {csv_filename}")
    print(f"Total pitchers written: {len(pitcher_data)}")
    
    # Display first few entries
    print("\nFirst few entries:")
    for i, pitcher in enumerate(pitcher_data[:5]):
        print(f"  {i+1}. {pitcher['pitcher_name']}")
    if len(pitcher_data) > 5:
        print(f"  ... and {len(pitcher_data) - 5} more")
    
    print("\n✓ Complete pitcher analysis finished!")


if __name__ == "__main__":
    import sys
    
    # Check if date parameter was provided
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
        main(date_str)
    else:
        main()  # Use today's date by default
