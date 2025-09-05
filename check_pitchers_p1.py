#!/usr/bin/env python3
"""
Script to check every game and collect opposing pitcher names for teams with all 9 batters.
Writes results to a CSV file named with today's date.
"""

import json
import csv
import os
import boto3
import requests
from botocore.exceptions import ClientError
from datetime import datetime, timedelta


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
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    secret = get_secret_value_response["SecretString"]
    secret_dict = json.loads(secret)  # Parse the JSON string to get the actual secret value
    return secret_dict["ODDS_API_KEY"]  # Return just the API key value


def get_odds_api_events(date_str):
    """
    Get events from The Odds API for the specified date.
    Returns a list of events that can be used to find game IDs.
    """
    api_key = get_odds_api_key()
    
    # Determine if we need current or historical endpoint
    today = datetime.now().strftime("%Y-%m-%d")
    is_today = date_str == today
    
    if is_today:
        # Use current events endpoint
        url = "https://api.the-odds-api.com/v4/sports/baseball_mlb/events"
        params = {
            "apiKey": api_key,
            "regions": "us"
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()  # Returns list directly for current events
        except requests.exceptions.RequestException as e:
            print(f"Error fetching current events: {e}")
            return []
    else:
        # Use historical events endpoint
        url = "https://api.the-odds-api.com/v4/historical/sports/baseball_mlb/events"
        
        # For historical data, we need to provide a timestamp
        # We'll use the date at noon minus 10 minutes as a reasonable game time
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        game_time = date_obj.replace(hour=12, minute=0, second=0) - timedelta(minutes=10)
        iso_timestamp = game_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        params = {
            "apiKey": api_key,
            "regions": "us",
            "date": iso_timestamp
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])  # Extract data array from historical response
        except requests.exceptions.RequestException as e:
            print(f"Error fetching historical events for {date_str}: {e}")
            return []


def find_event_id_for_game(events, home_team, away_team):
    """
    Find the event ID for a specific game by matching home and away teams.
    
    Args:
        events: List of events from The Odds API
        home_team: Home team abbreviation (e.g., "NYY")
        away_team: Away team abbreviation (e.g., "BOS")
    
    Returns:
        Event ID string if found, None otherwise
    """
    # Team name mapping - The Odds API uses full team names
    TEAM_NAMES = {
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
        "MIA": "Miami Marlins",
        "HOU": "Houston Astros",
        "KC": "Kansas City Royals",
        "LAA": "Los Angeles Angels",
        "LAD": "Los Angeles Dodgers",
        "MIL": "Milwaukee Brewers",
        "MIN": "Minnesota Twins",
        "NYM": "New York Mets",
        "NYY": "New York Yankees",
        "ATH": "Athletics",
        "PHI": "Philadelphia Phillies",
        "PIT": "Pittsburgh Pirates",
        "SD": "San Diego Padres",
        "SF": "San Francisco Giants",
        "SEA": "Seattle Mariners",
        "STL": "St. Louis Cardinals",
        "TB": "Tampa Bay Rays",
        "TEX": "Texas Rangers",
        "TOR": "Toronto Blue Jays",
        "WSH": "Washington Nationals",
    }
    
    def get_possible_names(team_abbr):
        """Get possible team names for an abbreviation."""
        full_name = TEAM_NAMES.get(team_abbr, team_abbr)
        return [team_abbr, full_name]
    
    home_possible = get_possible_names(home_team)
    away_possible = get_possible_names(away_team)
    
    for event in events:
        event_home = event.get("home_team", "")
        event_away = event.get("away_team", "")
        
        # Check if either team name matches any of the possible names
        home_match = any(name in event_home or event_home in name for name in home_possible)
        away_match = any(name in event_away or event_away in name for name in away_possible)
        
        if home_match and away_match:
            return event.get("id")
    
    return None


def get_odds_events(date_str, game_start_time=None):
    """
    Get MLB events from The Odds API for the specified date.
    
    Args:
        date_str: Date in YYYY-MM-DD format
        game_start_time: Game start time in ISO8601 format (only needed for historical)
    
    Returns:
        List of events from The Odds API
    """
    api_key = get_odds_api_key()
    today = datetime.now().strftime("%Y-%m-%d")
    
    if date_str == today:
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
        print(f"Fetching events from Odds API for {date_str}...")
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        # The API returns a list directly, not a dict with 'data' field
        events = data if isinstance(data, list) else []
        print(f"Found {len(events)} events from Odds API")
        return events
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching events from Odds API: {e}")
        return []
    except Exception as e:
        print(f"Error processing Odds API response: {e}")
        return []


def get_pitcher_targets_from_odds(event_id, pitcher_name, date_str):
    """
    Get pitcher strikeouts and hits allowed targets from The Odds API.
    
    Args:
        event_id: The event ID from The Odds API
        pitcher_name: Name of the pitcher to find targets for
        date_str: Date string for historical data queries
    
    Returns:
        dict: {'target_ks': int, 'target_hits': int} or {'target_ks': None, 'target_hits': None}
    """
    if not event_id:
        return {'target_ks': None, 'target_hits': None}
    
    api_key = get_odds_api_key()
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Determine endpoint based on date
    if date_str == today:
        # Current odds endpoint
        url = f"https://api.the-odds-api.com/v4/sports/baseball_mlb/events/{event_id}/odds"
        params = {
            "apiKey": api_key,
            "markets": "pitcher_strikeouts_alternate,pitcher_hits_allowed_alternate",
            "regions": "us"
        }
    else:
        # Historical odds endpoint
        url = f"https://api.the-odds-api.com/v4/historical/sports/baseball_mlb/events/{event_id}/odds"
        
        # For historical, try different date format - using the date itself instead of a time
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        iso_date = date_obj.strftime("%Y-%m-%d")
        
        params = {
            "apiKey": api_key,
            "markets": "pitcher_strikeouts_alternate,pitcher_hits_allowed_alternate",
            "regions": "us",
            "date": iso_date
        }
    
    try:
        print(f"Fetching odds for event {event_id}, pitcher: {pitcher_name}")
        print(f"URL: {url}")
        print(f"Params: {params}")
        
        response = requests.get(url, params=params)
        
        # Print detailed error information
        if response.status_code != 200:
            print(f"API Error: {response.status_code} - {response.text}")
            return {'target_ks': None, 'target_hits': None}
        
        data = response.json()
        print(f"Response data type: {type(data)}")
        
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
        
        print(f"Processing {len(odds_data)} odds events")
        
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
        print(f"Found targets for {pitcher_name}: K's={targets['target_ks']}, Hits={targets['target_hits']}")
        return targets
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching odds for event {event_id}: {e}")
        return {'target_ks': None, 'target_hits': None}
    except Exception as e:
        print(f"Error processing odds data for {pitcher_name}: {e}")
        return {'target_ks': None, 'target_hits': None}


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
    # Create mapping from common abbreviations to possible Odds API team names
    team_name_mapping = {
        "WSH": ["Washington Nationals", "Washington", "Nationals"],
        "MIA": ["Miami Marlins", "Miami", "Marlins"],
        "NYY": ["New York Yankees", "Yankees", "NY Yankees"],
        "BOS": ["Boston Red Sox", "Boston", "Red Sox"],
        "TB": ["Tampa Bay Rays", "Tampa Bay", "Rays"],
        "TOR": ["Toronto Blue Jays", "Toronto", "Blue Jays"],
        "BAL": ["Baltimore Orioles", "Baltimore", "Orioles"],
        "CLE": ["Cleveland Guardians", "Cleveland", "Guardians"],
        "DET": ["Detroit Tigers", "Detroit", "Tigers"],
        "KC": ["Kansas City Royals", "Kansas City", "Royals"],
        "CWS": ["Chicago White Sox", "Chicago White Sox", "White Sox"],
        "MIN": ["Minnesota Twins", "Minnesota", "Twins"],
        "HOU": ["Houston Astros", "Houston", "Astros"],
        "LAA": ["Los Angeles Angels", "LA Angels", "Angels"],
        "OAK": ["Oakland Athletics", "Oakland", "Athletics", "A's"],
        "SEA": ["Seattle Mariners", "Seattle", "Mariners"],
        "TEX": ["Texas Rangers", "Texas", "Rangers"],
        "ATL": ["Atlanta Braves", "Atlanta", "Braves"],
        "PHI": ["Philadelphia Phillies", "Philadelphia", "Phillies"],
        "NYM": ["New York Mets", "Mets", "NY Mets"],
        "FLA": ["Miami Marlins", "Miami", "Marlins"],  # Alternative for Miami
        "CHC": ["Chicago Cubs", "Chicago Cubs", "Cubs"],
        "MIL": ["Milwaukee Brewers", "Milwaukee", "Brewers"],
        "STL": ["St. Louis Cardinals", "St Louis Cardinals", "Cardinals"],
        "CIN": ["Cincinnati Reds", "Cincinnati", "Reds"],
        "PIT": ["Pittsburgh Pirates", "Pittsburgh", "Pirates"],
        "LAD": ["Los Angeles Dodgers", "LA Dodgers", "Dodgers"],
        "SD": ["San Diego Padres", "San Diego", "Padres"],
        "SF": ["San Francisco Giants", "San Francisco", "Giants"],
        "COL": ["Colorado Rockies", "Colorado", "Rockies"],
        "AZ": ["Arizona Diamondbacks", "Arizona", "Diamondbacks"]
    }
    
    # Get possible names for home and away teams
    home_names = team_name_mapping.get(home_team, [home_team])
    away_names = team_name_mapping.get(away_team, [away_team])
    
    for event in events:
        event_home = event.get("home_team", "")
        event_away = event.get("away_team", "")
        
        # Check if any of the possible names match
        home_match = any(name.lower() in event_home.lower() or event_home.lower() in name.lower() 
                        for name in home_names)
        away_match = any(name.lower() in event_away.lower() or event_away.lower() in name.lower() 
                        for name in away_names)
        
        if home_match and away_match:
            print(f"Found matching event: {event_away} @ {event_home} (ID: {event['id']})")
            return event["id"]
    
    print(f"No matching event found for {away_team} @ {home_team}")
    return None


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
        return round(total_batters / game_count)

    except Exception as e:
        print(f"Error retrieving data for pitcher ID {pitcher_id}: {e}")
        return None


def has_all_nine_batters(team_data):
    """Check if a team has all 9 lineup positions (1-9)."""
    if not team_data or not team_data.get("batters"):
        return False

    lineup_positions = set()
    for batter in team_data["batters"]:
        lineup_positions.add(batter.get("lineup_position"))

    # Check if all positions 1-9 are present
    return lineup_positions == {1, 2, 3, 4, 5, 6, 7, 8, 9}


def process_json_file_with_teams(file_path):
    """Process a single JSON file and return list of opposing pitchers with team context."""
    opposing_pitchers_with_games = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "games" not in data:
            return opposing_pitchers_with_games

        for game in data["games"]:
            # Extract team abbreviations directly from the game data
            home_team = game.get("home_team", "")
            away_team = game.get("away_team", "")

            # Check home team vs away pitcher
            home_team_data = game.get("home_vs_away_pitcher", {})
            if has_all_nine_batters(home_team_data):
                pitcher_name = home_team_data.get("pitcher_name")
                pitcher_id = home_team_data.get("pitcher_id")
                if pitcher_name and pitcher_name != "Unknown" and pitcher_id:
                    pitcher_info = {
                        'pitcher_name': pitcher_name,
                        'pitcher_id': pitcher_id,
                        'home_team': home_team,
                        'away_team': away_team,
                        'is_home_pitcher': False  # This is the away pitcher facing home team
                    }
                    # Check for duplicates
                    if not any(p['pitcher_id'] == pitcher_id for p in opposing_pitchers_with_games):
                        opposing_pitchers_with_games.append(pitcher_info)

            # Check away team vs home pitcher
            away_team_data = game.get("away_vs_home_pitcher", {})
            if has_all_nine_batters(away_team_data):
                pitcher_name = away_team_data.get("pitcher_name")
                pitcher_id = away_team_data.get("pitcher_id")
                if pitcher_name and pitcher_name != "Unknown" and pitcher_id:
                    pitcher_info = {
                        'pitcher_name': pitcher_name,
                        'pitcher_id': pitcher_id,
                        'home_team': home_team,
                        'away_team': away_team,
                        'is_home_pitcher': True  # This is the home pitcher facing away team
                    }
                    # Check for duplicates
                    if not any(p['pitcher_id'] == pitcher_id for p in opposing_pitchers_with_games):
                        opposing_pitchers_with_games.append(pitcher_info)

    except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
        print(f"Error processing {file_path}: {e}")

    return opposing_pitchers_with_games


def process_json_file(file_path):
    """Process a single JSON file and return list of opposing pitchers for complete lineups."""
    opposing_pitchers = []  # Use list to store tuples of (name, id)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "games" not in data:
            return opposing_pitchers

        for game in data["games"]:
            # Check home team vs away pitcher
            home_team_data = game.get("home_vs_away_pitcher", {})
            if has_all_nine_batters(home_team_data):
                pitcher_name = home_team_data.get("pitcher_name")
                pitcher_id = home_team_data.get("pitcher_id")
                if pitcher_name and pitcher_name != "Unknown" and pitcher_id:
                    pitcher_tuple = (pitcher_name, pitcher_id)
                    if pitcher_tuple not in opposing_pitchers:  # Avoid duplicates
                        opposing_pitchers.append(pitcher_tuple)

            # Check away team vs home pitcher
            away_team_data = game.get("away_vs_home_pitcher", {})
            if has_all_nine_batters(away_team_data):
                pitcher_name = away_team_data.get("pitcher_name")
                pitcher_id = away_team_data.get("pitcher_id")
                if pitcher_name and pitcher_name != "Unknown" and pitcher_id:
                    pitcher_tuple = (pitcher_name, pitcher_id)
                    if pitcher_tuple not in opposing_pitchers:  # Avoid duplicates
                        opposing_pitchers.append(pitcher_tuple)

    except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
        print(f"Error processing {file_path}: {e}")

    return opposing_pitchers


def find_json_file(workspace_path, date_str):
    """Find JSON file for the specified date in the workspace."""
    json_filename = f"{date_str}.json"
    
    # Check for JSON file in the root directory first
    root_json_path = os.path.join(workspace_path, json_filename)
    if os.path.exists(root_json_path):
        return root_json_path
    
    # Check for JSON file in the json subdirectory
    json_dir_path = os.path.join(workspace_path, "json", json_filename)
    if os.path.exists(json_dir_path):
        return json_dir_path
    
    return None
def main(date_str=None):
    """Main function to process JSON file for the specified date and create CSV output."""
    # Use provided date or default to today
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    # Get the workspace path (current directory)
    workspace_path = os.path.dirname(os.path.abspath(__file__))

    # Find JSON file for the specified date
    json_file = find_json_file(workspace_path, date_str)

    if not json_file:
        print(f"No JSON file found for date: {date_str}.json")
        print("Checked both root directory and json/ subdirectory.")
        return

    print(f"Processing file: {os.path.basename(json_file)} for date {date_str}")

    # Get odds API events for this date
    print("Fetching MLB events from The Odds API...")
    odds_events = get_odds_api_events(date_str)
    print(f"Found {len(odds_events)} events from Odds API")

    # Collect all opposing pitchers and their game context from the games
    opposing_pitchers_with_games = process_json_file_with_teams(json_file)

    print(f"\nFound {len(opposing_pitchers_with_games)} unique opposing pitchers for teams with complete lineups.")
    print("Retrieving pitcher statistics from DynamoDB...")

    # Create CSV filename with the specified date
    csv_filename = f"{date_str}.csv"
    csv_path = os.path.join(workspace_path, csv_filename)

    # Write to CSV file
    try:
        with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)

            # Write header
            writer.writerow(["pitcher_name", "num_batters", "target_ks", "target_hits", "ks_odds", "hits_odds"])

            # Write each pitcher with empty columns and calculate num_batters
            pitchers_processed = 0
            for pitcher_info in sorted(opposing_pitchers_with_games, key=lambda x: x['pitcher_name']):
                pitcher_name = pitcher_info['pitcher_name']
                pitcher_id = pitcher_info['pitcher_id']
                home_team = pitcher_info['home_team']
                away_team = pitcher_info['away_team']
                
                # Get average batters faced
                avg_batters_faced = get_pitcher_avg_batters_faced(pitcher_id)
                num_batters = avg_batters_faced if avg_batters_faced is not None else ""
                
                # Find the event ID for this game
                event_id = find_matching_event(odds_events, home_team, away_team)
                
                # Get pitcher targets from odds
                targets = get_pitcher_targets_from_odds(event_id, pitcher_name, date_str)
                target_ks = targets['target_ks'] if targets['target_ks'] is not None else ""
                target_hits = targets['target_hits'] if targets['target_hits'] is not None else ""
                
                writer.writerow([pitcher_name, num_batters, target_ks, target_hits, "", ""])

                pitchers_processed += 1
                if pitchers_processed % 5 == 0:  # Progress indicator every 5 pitchers
                    print(f"Processed {pitchers_processed}/{len(opposing_pitchers_with_games)} pitchers...")

        print(f"\nCSV file created successfully: {csv_filename}")
        print(f"Total pitchers written: {len(opposing_pitchers_with_games)}")

        # Display first few entries for verification
        if opposing_pitchers_with_games:
            print(f"\nFirst few entries:")
            for i, pitcher_info in enumerate(sorted(opposing_pitchers_with_games, key=lambda x: x['pitcher_name'])[:5]):
                print(f"  {i+1}. {pitcher_info['pitcher_name']}")
            if len(opposing_pitchers_with_games) > 5:
                print(f"  ... and {len(opposing_pitchers_with_games) - 5} more")

    except Exception as e:
        print(f"Error writing CSV file: {e}")


if __name__ == "__main__":
    import sys
    
    # Check if date parameter was provided
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
        main(date_str)
    else:
        main()  # Use today's date by default
