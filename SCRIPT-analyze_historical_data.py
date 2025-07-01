import datetime
import boto3
import pandas as pd
import requests
import statsapi
from decimal import Decimal

from lineups import get_team_lineups
from loaders.custom_data.app import get_games_by_date
from pitch_outcome_predictor import get_outcome_probabilities
from plate_appearance_predictor import analyze_plate_appearance

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


def get_preferred_bat_side(player_id: int) -> str:
    try:
        pitcher_stats_vlhb = requests.get(f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?group=pitching&season=2025&stats=statSplits&sitCodes=vl").json()
        pitcher_stats_vrhb = requests.get(f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?group=pitching&season=2025&stats=statSplits&sitCodes=vr").json()

        if pitcher_stats_vlhb and pitcher_stats_vrhb:
            kp_vlhb = round(pitcher_stats_vlhb["stats"][0]["splits"][-1]["stat"]["strikeOuts"] / pitcher_stats_vlhb["stats"][0]["splits"][-1]["stat"]["battersFaced"], 3)
            kp_vrhb = round(pitcher_stats_vrhb["stats"][0]["splits"][-1]["stat"]["strikeOuts"] / pitcher_stats_vrhb["stats"][0]["splits"][-1]["stat"]["battersFaced"], 3)

        if kp_vlhb > kp_vrhb:
            return "Left"
        else:
            return "Right"
    except Exception as e:
        print(f"Error fetching preferred bat side for player {player_id}: {e}")
        return "Unknown"


def analyze_games_for_date(date, games):
    """Analyze all games for a specific date and write to a single file."""
    date_str = date.strftime('%Y-%m-%d')

    lineups = get_team_lineups("today") if date.date() == datetime.date.today() else None

    # Collect all batter data for summary
    all_batters = []
    
    # Write all games for this date to a single file
    with open(f"{date_str}.txt", "w", encoding='utf-8') as file:
        file.write(f"GAME ANALYSIS FOR {date_str}\n")
        file.write(f"Total Games: {len(games)}\n")
        file.write("="*80 + "\n\n")
        
        for game_counter, game in enumerate(games, 1):
            game_pk = game["gamePk"]
            
            file.write(f"GAME {game_counter} of {len(games)}: {game_pk}\n")
            file.write(f"Game Link: www.mlb.com/gameday/{game_pk}/final/box\n")
            file.write("-"*60 + "\n")
            
            try:
                # Get box score
                box_score = statsapi.boxscore_data(game_pk)
                home_team = box_score["teamInfo"]["home"]["abbreviation"]
                away_team = box_score["teamInfo"]["away"]["abbreviation"]

                if lineups is not None:
                    # Try to get pitcher IDs from lineups, fallback to box score if not found
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
                file.write(f"\n{home_team} vs {away_pitcher_name}\n")
                if len(away_pitcher_data.get("past_games", [])) > 0:
                    if lineups is not None:
                        home_batter_ids = lineups.loc[(lineups["Team"] == home_team) & (lineups["Position"] != "P"), "Player ID"].tolist()
                        # convert list of strings to list of integers
                        home_batter_ids = [int(bid) for bid in home_batter_ids]
                    else:
                        home_batter_ids = box_score["home"]["battingOrder"]
                    for batter_id in home_batter_ids:
                        if lineups is not None:
                            batter_name = lineups.loc[lineups['Player ID'] == batter_id, 'Name'].values[0]
                            vs_pitcher = lineups.loc[lineups['Player ID'] == away_pitcher_id, 'Name'].values[0]
                        else:
                            # Check if they are a sub hitter
                            if int(box_score['home']['players'].get(f'ID{batter_id}', {}).get('battingOrder', "1")) % 100 != 0:
                                continue
                            batter_name = box_score['playerInfo'][f'ID{batter_id}']['fullName']
                            vs_pitcher = box_score['playerInfo'][f'ID{away_pitcher_id}']['fullName']
                        batter_data = get_player_data(batter_id)
                        if len(batter_data.get("past_games", [])) == 0:
                            continue
                        batter_hand = statsapi.player_stat_data(batter_id, "hitting")["bat_side"]

                        if batter_hand == "Switch":
                            batter_hand = get_preferred_bat_side(batter_id)

                        print(f"Game {game_counter}: Analyzing batter {batter_id} ({batter_hand}) against away pitcher {away_pitcher_id} ({away_pitcher_hand})...")
                        outcome_probabilities = get_outcome_probabilities(
                            pitcher_info=away_pitcher_data,
                            batter_info=batter_data,
                            pitcher_handedness=away_pitcher_hand[0].upper(),
                            batter_handedness=batter_hand[0].upper(),
                            date=game['gameDate'],
                        )

                        # Calculate PA outcome predictions
                        pa_analysis = analyze_plate_appearance(outcome_probabilities)
                        pa_outcomes = pa_analysis['plate_appearance_outcomes']
                        
                        # Store batter data for summary
                        batter_summary = {
                            'name': batter_name,
                            'team': home_team,
                            'vs_pitcher': vs_pitcher,
                            'hit_prob': pa_outcomes['hit'],
                            'strikeout_prob': pa_outcomes['strikeout'],
                            'walk_prob': pa_outcomes['walk'],
                            'other_out_prob': pa_outcomes['other'],
                            'est_pitches': pa_analysis['estimated_pitches_per_pa'],
                            'game': f"Game {game_counter}"
                        }
                        all_batters.append(batter_summary)
                        
                        file.write(f"{batter_name}\n")

                        # Handle unknown data (-1 values)
                        if pa_outcomes['hit'] == -1:
                            file.write("Hit: Unknown (insufficient data)\n")
                            file.write("Strikeout: Unknown (insufficient data)\n")
                            file.write("Walk: Unknown (insufficient data)\n")
                            file.write("Other Out: Unknown (insufficient data)\n")
                            file.write("Est. Pitches: Unknown (insufficient data)\n")
                        else:
                            file.write(f"Hit: {pa_outcomes['hit']:.3f} ({pa_outcomes['hit']*100:.1f}%)\n")
                            file.write(f"Strikeout: {pa_outcomes['strikeout']:.3f} ({pa_outcomes['strikeout']*100:.1f}%)\n")
                            file.write(f"Walk: {pa_outcomes['walk']:.3f} ({pa_outcomes['walk']*100:.1f}%)\n")
                            file.write(f"Other Out: {pa_outcomes['other']:.3f} ({pa_outcomes['other']*100:.1f}%)\n")
                            file.write(f"Est. Pitches: {pa_analysis['estimated_pitches_per_pa']:.1f}\n")
                        file.write("\n")

                # Away team vs Home pitcher
                file.write(f"\n{away_team} vs {home_pitcher_name}\n")
                if len(home_pitcher_data.get("past_games", [])) > 0:
                    if lineups is not None:
                        away_batter_ids = lineups.loc[(lineups["Team"] == away_team) & (lineups["Position"] != "P"), "Player ID"].tolist()
                    else:
                        away_batter_ids = box_score["away"]["battingOrder"]
                    for batter_id in away_batter_ids:
                        if lineups is not None:
                            batter_name = lineups.loc[lineups['Player ID'] == batter_id, 'Name'].values[0]
                            vs_pitcher = lineups.loc[lineups['Player ID'] == away_pitcher_id, 'Name'].values[0]
                        else:
                            # Check if they are a sub hitter
                            if int(box_score['away']['players'].get(f'ID{batter_id}', {}).get('battingOrder', "1")) % 100 != 0:
                                continue
                            batter_name = box_score['playerInfo'][f'ID{batter_id}']['fullName']
                            vs_pitcher = box_score['playerInfo'][f'ID{away_pitcher_id}']['fullName']
                        
                        batter_data = get_player_data(batter_id)
                        if len(batter_data.get("past_games", [])) == 0:
                            continue
                        batter_hand = statsapi.player_stat_data(batter_id, "hitting")["bat_side"]
                        
                        if batter_hand == "Switch":
                            batter_hand = get_preferred_bat_side(batter_id)
                        
                        print(f"Game {game_counter}: Analyzing batter {batter_id} ({batter_hand}) against home pitcher {home_pitcher_id} ({home_pitcher_hand})...")
                        outcome_probabilities = get_outcome_probabilities(
                            pitcher_info=home_pitcher_data,
                            batter_info=batter_data,
                            pitcher_handedness=home_pitcher_hand[0].upper(),
                            batter_handedness=batter_hand[0].upper(),
                            date=game['gameDate'],
                        )

                        # Calculate PA outcome predictions
                        pa_analysis = analyze_plate_appearance(outcome_probabilities)
                        pa_outcomes = pa_analysis['plate_appearance_outcomes']
                        
                        # Store batter data for summary
                        batter_summary = {
                            'name': batter_name,
                            'team': away_team,
                            'vs_pitcher': away_pitcher_name,
                            'hit_prob': pa_outcomes['hit'],
                            'strikeout_prob': pa_outcomes['strikeout'],
                            'walk_prob': pa_outcomes['walk'],
                            'other_out_prob': pa_outcomes['other'],
                            'est_pitches': pa_analysis['estimated_pitches_per_pa'],
                            'game': f"Game {game_counter}"
                        }
                        all_batters.append(batter_summary)

                        file.write(f"{batter_name}\n")

                        # Handle unknown data (-1 values)
                        if pa_outcomes['hit'] == -1:
                            file.write("Hit: Unknown (insufficient data)\n")
                            file.write("Strikeout: Unknown (insufficient data)\n")
                            file.write("Walk: Unknown (insufficient data)\n")
                            file.write("Other Out: Unknown (insufficient data)\n")
                            file.write("Est. Pitches: Unknown (insufficient data)\n")
                        else:
                            file.write(f"Hit: {pa_outcomes['hit']:.3f} ({pa_outcomes['hit']*100:.1f}%)\n")
                            file.write(f"Strikeout: {pa_outcomes['strikeout']:.3f} ({pa_outcomes['strikeout']*100:.1f}%)\n")
                            file.write(f"Walk: {pa_outcomes['walk']:.3f} ({pa_outcomes['walk']*100:.1f}%)\n")
                            file.write(f"Other Out: {pa_outcomes['other']:.3f} ({pa_outcomes['other']*100:.1f}%)\n")
                            file.write(f"Est. Pitches: {pa_analysis['estimated_pitches_per_pa']:.1f}\n")
                        file.write("\n")
                        
            except Exception as e:
                raise e
            
            # Add separator between games
            file.write("\n" + "="*80 + "\n\n")
        
        # Add summary section at the bottom
        if all_batters:
            file.write("\n\n")
            file.write("*** TOP PERFORMERS SUMMARY FOR " + date_str + " ***\n")
            file.write("="*80 + "\n\n")
            
            # Filter out batters with unknown data (-1 values)
            valid_batters = [b for b in all_batters if b['hit_prob'] != -1]
            unknown_count = len(all_batters) - len(valid_batters)
            
            if unknown_count > 0:
                file.write(f"Note: {unknown_count} batter matchups excluded due to insufficient data (<100 pitches vs handedness)\n\n")
            
            if valid_batters:
                # Top 10 most likely to get a hit
                file.write("TOP 10 MOST LIKELY TO GET A HIT:\n")
                file.write("-" * 50 + "\n")
                top_hits = sorted(valid_batters, key=lambda x: x['hit_prob'], reverse=True)[:10]
                for i, batter in enumerate(top_hits, 1):
                    file.write(f"{i:2d}. {batter['name']:<25} ({batter['team']}) - {batter['hit_prob']:.1%}\n")
                    file.write(f"    vs {batter['vs_pitcher']} | {batter['game']}\n")
                
                file.write(f"\nTOP 10 MOST LIKELY TO STRIKEOUT:\n")
                file.write("-" * 50 + "\n")
                top_strikeouts = sorted(valid_batters, key=lambda x: x['strikeout_prob'], reverse=True)[:10]
                for i, batter in enumerate(top_strikeouts, 1):
                    file.write(f"{i:2d}. {batter['name']:<25} ({batter['team']}) - {batter['strikeout_prob']:.1%}\n")
                    file.write(f"    vs {batter['vs_pitcher']} | {batter['game']}\n")
                
                file.write(f"\nTOP 10 MOST LIKELY TO WALK:\n")
                file.write("-" * 50 + "\n")
                top_walks = sorted(valid_batters, key=lambda x: x['walk_prob'], reverse=True)[:10]
                for i, batter in enumerate(top_walks, 1):
                    file.write(f"{i:2d}. {batter['name']:<25} ({batter['team']}) - {batter['walk_prob']:.1%}\n")
                    file.write(f"    vs {batter['vs_pitcher']} | {batter['game']}\n")
                
                # Overall stats (excluding unknown data)
                avg_hit = sum(b['hit_prob'] for b in valid_batters) / len(valid_batters)
                avg_k = sum(b['strikeout_prob'] for b in valid_batters) / len(valid_batters)
                avg_bb = sum(b['walk_prob'] for b in valid_batters) / len(valid_batters)
                avg_other = sum(b['other_out_prob'] for b in valid_batters) / len(valid_batters)
                avg_pitches = sum(b['est_pitches'] for b in valid_batters) / len(valid_batters)
                
                file.write(f"\nOVERALL AVERAGES ({len(valid_batters)} valid matchups):\n")
                file.write("-" * 50 + "\n")
                file.write(f"Average Hit Rate:        {avg_hit:.1%}\n")
                file.write(f"Average Strikeout Rate:  {avg_k:.1%}\n")
                file.write(f"Average Walk Rate:       {avg_bb:.1%}\n")
                file.write(f"Average Other Out Rate:  {avg_other:.1%}\n")
                file.write(f"Average Pitches/PA:      {avg_pitches:.1f}\n")
            else:
                file.write("No valid matchups with sufficient data for analysis.\n")
            file.write(f"Total Outcome Rate:      {avg_hit + avg_k + avg_bb + avg_other:.1%}\n")


for date in pd.date_range(start="2025-05-01", end="2025-06-17"):
    # If date is in June or later, analyze the data
    if date.month >= 5:
        games = get_games_by_date(date)
        if len(games) > 0:
            print(f"Analyzing {len(games)} total games for {date.strftime('%Y-%m-%d')}...")
            analyze_games_for_date(date, games)

    # load_daily_player_stats(date)
