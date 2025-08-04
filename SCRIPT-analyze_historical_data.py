import datetime
import boto3
import pandas as pd
import requests
import statsapi
import json
from decimal import Decimal
from collections import defaultdict

from lineups import get_team_lineups
from loaders.custom_data.app import get_games_by_date, load_daily_player_stats
from pitch_outcome_predictor import get_outcome_probabilities
from plate_appearance_predictor import calculate_plate_appearance_outcomes

table_name = "custom-player-data"
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(table_name)

PITCHER_SIT_CODES = {"Right": "vs_RHB", "Left": "vs_LHB"}

BATTER_SIT_CODES = {"Right": "vs_RHP", "Left": "vs_LHP"}

STAT_KEY_LIST = ["balls", "strikes", "fouls", "hits", "outs", "total"]


def convert_decimals(obj):
    """Recursively convert DynamoDB Decimal types to Python int/float types."""
    if isinstance(obj, dict):
        return {key: convert_decimals(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    elif isinstance(obj, Decimal):
        # Convert to int if it's a whole number, otherwise float
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    else:
        return obj


def get_player_data(player_id: int) -> dict:
    # Get stored pitch data from dynamoDB
    response = table.get_item(Key={"player_id": player_id})
    item = response.get("Item", {})
    # Convert DynamoDB Decimals to Python int/float types
    return convert_decimals(item)


def get_team_pa_data(team_id: int) -> dict:
    """Get stored PA data from DynamoDB for a specific team"""
    response = table.get_item(Key={"player_id": team_id})
    item = response.get("Item", {})
    return convert_decimals(item)


def aggregate_pa_probabilities_by_position(team_id: int, given_date: datetime.date) -> dict:
    """
    Aggregate historical PA data by lineup position for a team.
    Only includes games from dates before the given date.
    Returns a dictionary mapping lineup positions to PA probability distributions.
    """
    team_data = get_team_pa_data(team_id)
    
    if not team_data or "past_games" not in team_data:
        return {}

    past_games = team_data["past_games"]
    position_pa_probs = {}
    
    for position in range(1, 10):  # Positions 1-9
        position_str = str(position * 100)  # Convert to string like "100", "200", ..., "900"
        pa_counts = []
        
        # Loop through all date keys in past_games
        for date_str, game_data in past_games.items():
            try:
                # Parse the date string and compare to given_date
                game_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                if game_date >= given_date:
                    continue  # Skip games on or after the given date
                    
                # If this position has PA data for this game, add it
                if position_str in game_data["team_stats"]:
                    pa_counts.append(game_data["team_stats"][position_str])
            except ValueError as e:
                # Skip invalid date strings
                print(f"Error parsing date for game data: {e}")
                continue
        
        if not pa_counts:
            continue
            
        # Calculate probability distribution
        total_games = len(pa_counts)
        pa_distribution = defaultdict(int)
        
        for pa_count in pa_counts:
            pa_distribution[pa_count] += 1
        
        # Convert to probabilities
        pa_probabilities = {}
        for pa_count, frequency in pa_distribution.items():
            pa_probabilities[pa_count] = frequency / total_games
        
        position_pa_probs[position] = pa_probabilities
    
    return position_pa_probs


def calculate_per_game_outcome_probability(pa_outcome_prob: float, pa_distribution: dict) -> float:
    """
    Calculate the probability of a specific outcome occurring in a game,
    given the per-PA probability and the distribution of PAs.
    
    Args:
        pa_outcome_prob: Probability of outcome per plate appearance
        pa_distribution: Dictionary mapping PA counts to their probabilities
    
    Returns:
        Probability of the outcome occurring at least once in the game
    """
    if pa_outcome_prob == -1 or not pa_distribution:
        return -1
    
    # Calculate probability of NOT getting the outcome in the entire game
    prob_no_outcome = 0
    
    for pa_count, pa_count_prob in pa_distribution.items():
        if pa_count == 0:
            # If 0 PAs, probability of no outcome is 1
            prob_no_outcome += pa_count_prob * 1.0
        else:
            # Probability of no outcome in pa_count PAs = (1 - pa_outcome_prob)^pa_count
            prob_no_outcome_this_pa_count = (1 - pa_outcome_prob) ** pa_count
            prob_no_outcome += pa_count_prob * prob_no_outcome_this_pa_count
    
    # Probability of getting the outcome at least once = 1 - P(no outcome)
    return 1 - prob_no_outcome


def get_batter_lineup_position(batter_id: int, team: str, lineups: pd.DataFrame) -> int:
    """Get the lineup position for a batter from the lineups data"""
    batter_row = lineups.loc[(lineups["Player ID"] == batter_id) & (lineups["Team"] == team)]
    if len(batter_row) > 0:
        return int(batter_row["Bat Order"].values[0])
    return 5  # Default fallback


def analyze_games_for_date(date, games):
    """Analyze all games for a specific date and write to a JSON file."""
    date_str = date.strftime('%Y-%m-%d')

    lineups = get_team_lineups("today") if date.date() == datetime.date.today() else None

    # Main data structure for JSON output
    game_analysis = {
        "date": date_str,
        "total_games": len(games),
        "games": [],
        "summary": {
            "all_batters": []
        }
    }
    
    for game_counter, game in enumerate(games, 1):
        game_pk = game["gamePk"]
        
        game_data = {
            "game_number": game_counter,
            "game_pk": game_pk,
            "game_link": f"www.mlb.com/gameday/{game_pk}/final/box",
            "home_team": "",
            "away_team": "",
            "home_vs_away_pitcher": {
                "pitcher_name": "",
                "batters": []
            },
            "away_vs_home_pitcher": {
                "pitcher_name": "",
                "batters": []
            },
            "error": None
        }
        
        # Get box score
        box_score = statsapi.boxscore_data(game_pk)
        home_team = box_score["teamInfo"]["home"]["abbreviation"]
        away_team = box_score["teamInfo"]["away"]["abbreviation"]
        
        game_data["home_team"] = home_team
        game_data["away_team"] = away_team
        
        # Get PA probability distributions for both teams
        home_team_id = game["teams"]["home"]["team"]["id"]
        away_team_id = game["teams"]["away"]["team"]["id"]

        # Parse the game date
        try:
            game_date = datetime.datetime.strptime(game['gameDate'], '%Y-%m-%dT%H:%M:%S.%fZ').date()
        except ValueError:
            # Try without microseconds
            game_date = datetime.datetime.strptime(game['gameDate'], '%Y-%m-%dT%H:%M:%SZ').date()

        home_pa_probs = aggregate_pa_probabilities_by_position(home_team_id, game_date)
        away_pa_probs = aggregate_pa_probabilities_by_position(away_team_id, game_date)

        # Get pitcher information
        if lineups is not None:
            home_pitcher_data_lineup = lineups.loc[(lineups["Team"] == home_team) & (lineups["Position"] == "P"), "Player ID"]
            away_pitcher_data_lineup = lineups.loc[(lineups["Team"] == away_team) & (lineups["Position"] == "P"), "Player ID"]
            
            home_pitcher_id = 0
            away_pitcher_id = 0
            home_pitcher_name = "Unknown"
            away_pitcher_name = "Unknown"

            if len(home_pitcher_data_lineup) > 0:
                home_pitcher_id = int(home_pitcher_data_lineup.values[0])
                home_pitcher_name = lineups.loc[lineups["Player ID"] == home_pitcher_id, "Name"].values[0]
            if len(away_pitcher_data_lineup) > 0:
                away_pitcher_id = int(away_pitcher_data_lineup.values[0])
                away_pitcher_name = lineups.loc[lineups["Player ID"] == away_pitcher_id, "Name"].values[0]
        else:    
            home_pitcher_id = box_score["home"]["pitchers"][0] if len(box_score["home"]["pitchers"]) > 0 else 0
            away_pitcher_id = box_score["away"]["pitchers"][0] if len(box_score["away"]["pitchers"]) > 0 else 0
            home_pitcher_name = box_score['playerInfo'][f'ID{home_pitcher_id}']['fullName'] if home_pitcher_id > 0 else "Unknown"
            away_pitcher_name = box_score['playerInfo'][f'ID{away_pitcher_id}']['fullName'] if away_pitcher_id > 0 else "Unknown"

        # Get pitcher data
        if home_pitcher_id > 0:
            home_pitcher_data = get_player_data(home_pitcher_id)
            home_pitcher_hand = statsapi.player_stat_data(home_pitcher_id, "pitching")["pitch_hand"]
        else:
            home_pitcher_data = {"past_games": []}
            home_pitcher_hand = "Unknown"
        if away_pitcher_id > 0:    
            away_pitcher_data = get_player_data(away_pitcher_id)
            away_pitcher_hand = statsapi.player_stat_data(away_pitcher_id, "pitching")["pitch_hand"]
        else:
            away_pitcher_data = {"past_games": []}
            away_pitcher_hand = "Unknown"

        # Home team vs Away pitcher
        game_data["home_vs_away_pitcher"]["pitcher_name"] = away_pitcher_name
        
        if len(away_pitcher_data.get("past_games", [])) > 0:
            if lineups is not None:
                home_batter_ids = lineups.loc[(lineups["Team"] == home_team) & (lineups["Position"] != "P"), "Player ID"].tolist()
                home_batter_ids = [int(bid) for bid in home_batter_ids]
            else:
                home_batter_ids = box_score["home"]["battingOrder"]
            
            for batter_id in home_batter_ids:
                if lineups is not None:
                    batter_name = lineups.loc[lineups['Player ID'] == batter_id, 'Name'].values[0]
                else:
                    if int(box_score['home']['players'].get(f'ID{batter_id}', {}).get('battingOrder', "1")) % 100 != 0:
                        continue
                    batter_name = box_score['playerInfo'][f'ID{batter_id}']['fullName']
                
                vs_pitcher = away_pitcher_name
                batter_data = get_player_data(batter_id)
                if len(batter_data.get("past_games", [])) == 0:
                    continue
                batter_hand = statsapi.player_stat_data(batter_id, "hitting")["bat_side"]

                if batter_hand == "Switch":
                    batter_hand = "Left" if away_pitcher_hand == "Right" else "Right"

                print(f"Game {game_counter}: Analyzing batter {batter_id} ({batter_hand}) against away pitcher {away_pitcher_id} ({away_pitcher_hand})...")
                outcome_probabilities = get_outcome_probabilities(
                    pitcher_info=away_pitcher_data,
                    batter_info=batter_data,
                    pitcher_handedness=away_pitcher_hand[0].upper(),
                    batter_handedness=batter_hand[0].upper(),
                    cutoff_date_before=game['gameDate'],
                    cutoff_date_after=(game_date - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
                )

                if any(float(prob) == -1.0 for prob in outcome_probabilities.values()):
                    continue

                # Calculate PA outcome predictions
                pa_outcomes = calculate_plate_appearance_outcomes(
                    ball_prob=float(outcome_probabilities['ball']),
                    strike_prob=float(outcome_probabilities['strike']),
                    hit_prob=float(outcome_probabilities['hit']),
                    out_prob=float(outcome_probabilities['out']),
                    foul_prob=float(outcome_probabilities['foul']),
                )
                
                # Get batter's lineup position and PA distribution
                if lineups is not None:
                    lineup_position = get_batter_lineup_position(batter_id, home_team, lineups)
                else:
                    lineup_position = int(box_score['home']['players'][f'ID{batter_id}']['battingOrder']) / 100
                pa_distribution = home_pa_probs.get(lineup_position, {})
                
                # Calculate per-game probabilities
                if pa_distribution:
                    hit_prob_per_game = calculate_per_game_outcome_probability(pa_outcomes['Hit'], pa_distribution)
                    strikeout_prob_per_game = calculate_per_game_outcome_probability(pa_outcomes['Strikeout'], pa_distribution)
                    walk_prob_per_game = calculate_per_game_outcome_probability(pa_outcomes['Walk'], pa_distribution)
                else:
                    hit_prob_per_game = -1
                    strikeout_prob_per_game = -1
                    walk_prob_per_game = -1
                
                # Create batter data structure
                batter_data_entry = {
                    'batter_id': batter_id,
                    'name': batter_name,
                    'team': home_team,
                    'vs_pitcher': vs_pitcher,
                    'lineup_position': lineup_position,
                    'pa_distribution': pa_distribution,
                    'per_pa_probabilities': {
                        'hit': pa_outcomes['Hit'],
                        'strikeout': pa_outcomes['Strikeout'],
                        'walk': pa_outcomes['Walk'],
                        'other_out': pa_outcomes['Out']
                    },
                    'per_game_probabilities': {
                        'hit': hit_prob_per_game,
                        'strikeout': strikeout_prob_per_game,
                        'walk': walk_prob_per_game
                    },
                    'game': f"Game {game_counter}"
                }
                
                game_data["home_vs_away_pitcher"]["batters"].append(batter_data_entry)
                game_analysis["summary"]["all_batters"].append(batter_data_entry)

        # Away team vs Home pitcher
        game_data["away_vs_home_pitcher"]["pitcher_name"] = home_pitcher_name
        
        if len(home_pitcher_data.get("past_games", [])) > 0:
            if lineups is not None:
                away_batter_ids = lineups.loc[(lineups["Team"] == away_team) & (lineups["Position"] != "P"), "Player ID"].tolist()
                away_batter_ids = [int(bid) for bid in away_batter_ids]
            else:
                away_batter_ids = box_score["away"]["battingOrder"]
            
            for batter_id in away_batter_ids:
                if lineups is not None:
                    batter_name = lineups.loc[lineups['Player ID'] == batter_id, 'Name'].values[0]
                else:
                    if int(box_score['away']['players'].get(f'ID{batter_id}', {}).get('battingOrder', "1")) % 100 != 0:
                        continue
                    batter_name = box_score['playerInfo'][f'ID{batter_id}']['fullName']
                
                vs_pitcher = home_pitcher_name
                batter_data = get_player_data(batter_id)
                if len(batter_data.get("past_games", [])) == 0:
                    continue
                batter_hand = statsapi.player_stat_data(batter_id, "hitting")["bat_side"]
                
                if batter_hand == "Switch":
                    batter_hand = "Left" if away_pitcher_hand == "Right" else "Right"
                
                print(f"Game {game_counter}: Analyzing batter {batter_id} ({batter_hand}) against home pitcher {home_pitcher_id} ({home_pitcher_hand})...")
                outcome_probabilities = get_outcome_probabilities(
                    pitcher_info=home_pitcher_data,
                    batter_info=batter_data,
                    pitcher_handedness=home_pitcher_hand[0].upper(),
                    batter_handedness=batter_hand[0].upper(),
                    cutoff_date_before=game['gameDate'],
                    cutoff_date_after=(game_date - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
                )

                if any(float(prob) == -1.0 for prob in outcome_probabilities.values()):
                    continue

                # Calculate PA outcome predictions
                pa_outcomes = calculate_plate_appearance_outcomes(
                    ball_prob=float(outcome_probabilities['ball']),
                    strike_prob=float(outcome_probabilities['strike']),
                    hit_prob=float(outcome_probabilities['hit']),
                    out_prob=float(outcome_probabilities['out']),
                    foul_prob=float(outcome_probabilities['foul']),
                )
                
                # Get batter's lineup position and PA distribution
                if lineups is not None:
                    lineup_position = get_batter_lineup_position(batter_id, away_team, lineups)
                else:
                    lineup_position = int(box_score['away']['players'][f'ID{batter_id}']['battingOrder']) / 100
                pa_distribution = away_pa_probs.get(lineup_position, {})
                
                # Calculate per-game probabilities
                if pa_distribution:
                    hit_prob_per_game = calculate_per_game_outcome_probability(pa_outcomes['Hit'], pa_distribution)
                    strikeout_prob_per_game = calculate_per_game_outcome_probability(pa_outcomes['Strikeout'], pa_distribution)
                    walk_prob_per_game = calculate_per_game_outcome_probability(pa_outcomes['Walk'], pa_distribution)
                else:
                    hit_prob_per_game = -1
                    strikeout_prob_per_game = -1
                    walk_prob_per_game = -1

                # Create batter data structure
                batter_data_entry = {
                    'batter_id': batter_id,
                    'name': batter_name,
                    'team': away_team,
                    'vs_pitcher': vs_pitcher,
                    'lineup_position': lineup_position,
                    'pa_distribution': pa_distribution,
                    'per_pa_probabilities': {
                        'hit': pa_outcomes['Hit'],
                        'strikeout': pa_outcomes['Strikeout'],
                        'walk': pa_outcomes['Walk'],
                        'other_out': pa_outcomes['Out']
                    },
                    'per_game_probabilities': {
                        'hit': hit_prob_per_game,
                        'strikeout': strikeout_prob_per_game,
                        'walk': walk_prob_per_game
                    },
                    'game': f"Game {game_counter}"
                }
                
                game_data["away_vs_home_pitcher"]["batters"].append(batter_data_entry)
                game_analysis["summary"]["all_batters"].append(batter_data_entry)
        
        game_analysis["games"].append(game_data)

    # Write JSON file
    with open(f"{date_str}.json", "w", encoding='utf-8') as file:
        json.dump(game_analysis, file, indent=2, ensure_ascii=False)
    
    print(f"Analysis saved to {date_str}.json")

yesterday = datetime.date.today() - datetime.timedelta(days=1)
today = datetime.date.today()
start = datetime.date(2025, 5, 1) 
end = datetime.date(2025, 6, 30)
for date in pd.date_range(start=yesterday, end=today):
    # Skip July 15th (All-Star Game)
    if date.month == 7 and date.day == 15:
        continue

    if date.month == datetime.date.today().month and date.day == datetime.date.today().day:
        games = get_games_by_date(date)
        if len(games) > 0:
            print(f"Analyzing {len(games)} total games for {date.strftime('%Y-%m-%d')}...")
            analyze_games_for_date(date, games)

    else:
        load_daily_player_stats(date)
