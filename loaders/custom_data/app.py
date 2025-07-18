from datetime import date
import json
import boto3
import statsapi

import requests

table_name = "custom-player-data"
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(table_name)


def get_games_by_date(given_date: date = date.today()) -> dict:
    response = requests.get(f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={given_date.strftime('%Y-%m-%d')}").json()
    if response["totalGames"] == 0:
        return []
    return response["dates"][0]["games"]


def get_play_by_play(game_pk: int) -> dict:
    return requests.get(f"https://statsapi.mlb.com/api/v1/game/{game_pk}/playByPlay").json()


def get_boxscore(game_pk: int) -> dict:
    fields = (
        "gameData,game,teams,teamName,shortName,teamStats,batting,atBats,runs,hits,"
        "totalBases,homeRuns,rbi,plateAppearances,strikeOuts,baseOnBalls,pitching,"
        "inningsPitched,earnedRuns,players,boxscoreName,liveData,boxscore,teams,"
        "players,id,fullName,allPositions,abbreviation,seasonStats,batting,avg,ops,"
        "obp,slg,era,pitchesThrown,numberOfPitches,strikes,battingOrder,info,title,"
        "fieldList,note,label,value,wins,losses,holds,blownSaves"
    )
    return statsapi.get("game", params={"gamePk": game_pk, "fields": fields})


def save_player_data(player_stats: dict, game_pk: int, game_date: date):
    player_position = "pitching" if player_stats["position"]["abbreviation"] == "P" else "batting"
    if player_game_stats := player_stats["stats"][player_position]:
        dynamo_data = table.get_item(Key={"player_id": player_stats["person"]["id"]})
        if "Item" not in dynamo_data:
            item = {
                "player_id": player_stats["person"]["id"],
                "name": player_stats["person"]["fullName"],
                "past_games": [],
            }
        else:
            item = dynamo_data["Item"]

        item["past_games"].append(
            {
                "game_pk": game_pk,
                "date": game_date.strftime("%Y-%m-%d"),
                "stats": player_game_stats,
            }
        )

        table.put_item(Item=item)

def save_team_data(team_stats: dict, team_id: int, game_pk: int, game_date: date):
    dynamo_data = table.get_item(Key={"player_id": str(team_id)})
    if "Item" not in dynamo_data:
        item = {
            "player_id": str(team_id),
            "name": "",
            "past_games": {},
        }
    else:
        item = dynamo_data["Item"]

    item["past_games"][game_date.strftime("%Y-%m-%d")] = {
        "game_pk": game_pk,
        "team_stats": team_stats,
    }

def load_daily_player_stats(given_date: date = date.today()):
    games = get_games_by_date(given_date)
    print(f"Processing {len(games)} games for {given_date}")
    for game in games:
        game_pk = game["gamePk"]
        play_by_play = get_play_by_play(game_pk)
        boxscore = get_boxscore(game_pk)

        awayTeamId = boxscore["away"]["team"]["id"]
        awayIds = boxscore["away"]["battingOrder"][:9]
        awayData = {}
        awayCounter = 1

        for id in awayIds:
            assert f"ID{id}" in boxscore["away"]["players"][f"ID{id}"]["battingOrder"] == str(awayCounter*100)
            player_stats = boxscore["away"]["players"][f"ID{id}"]["stats"]["batting"]
            awayData[str(awayCounter)] = player_stats.get("atBats", 0) + player_stats.get("baseOnBalls", 0)
            awayCounter += 1
        save_team_data(awayData, awayTeamId, game_pk, given_date)

        homeTeamId = boxscore["home"]["team"]["id"]
        homeIds = boxscore["home"]["battingOrder"][:9]
        homeData = {}
        homeCounter = 1

        for id in homeIds:
            assert f"ID{id}" in boxscore["home"]["players"][f"ID{id}"]["battingOrder"] == str(homeCounter*100)
            player_stats = boxscore["home"]["players"][f"ID{id}"]["stats"]["batting"]
            homeData[str(homeCounter)] = player_stats.get("atBats", 0) + player_stats.get("baseOnBalls", 0)
            homeCounter += 1
        save_team_data(homeData, homeTeamId, game_pk, given_date)

        if not play_by_play or "allPlays" not in play_by_play:
            print(f"No play-by-play data found for game {game_pk} on {given_date}")
            continue
        print(f"Processing game {game_pk} on {given_date}")

        # Process each play, look for pitch events, and track how many pitches the pitcher threw of each type and zone
        stat_tracking = {}
        for play in play_by_play["allPlays"]:
            batter_id = play.get("matchup", {}).get("batter", {}).get("id")
            pitcher_id = play.get("matchup", {}).get("pitcher", {}).get("id")

            play_events = play.get("playEvents", [])
            for event in play_events:
                if event["isPitch"]:
                    pitch_data = event.get("pitchData", {})
                    pitch_zone = str(pitch_data.get("zone", "unknown"))
                    pitch_type = event.get("details", {}).get("type", {}).get("code", "unknown")
                    pitcher_split_code = str(play.get("matchup", {}).get("splits", {}).get("pitcher", "unknown"))
                    batter_split_code = str(play.get("matchup", {}).get("splits", {}).get("batter", "unknown"))

                    # Skip if essential data is missing
                    if pitch_zone == "unknown" or pitch_type == "unknown":
                        continue

                    if pitch_zone and pitch_type:
                        # Update pitcher data - create new dict for each level to avoid circular references
                        if pitcher_id not in stat_tracking:
                            stat_tracking[pitcher_id] = {}
                        if "pitching" not in stat_tracking[pitcher_id]:
                            stat_tracking[pitcher_id]["pitching"] = {"total": 0}
                        stat_tracking[pitcher_id]["pitching"]["total"] += 1

                        if pitcher_split_code not in stat_tracking[pitcher_id]["pitching"]:
                            stat_tracking[pitcher_id]["pitching"][pitcher_split_code] = {"total": 0}
                        stat_tracking[pitcher_id]["pitching"][pitcher_split_code]["total"] += 1

                        if pitch_type not in stat_tracking[pitcher_id]["pitching"][pitcher_split_code]:
                            stat_tracking[pitcher_id]["pitching"][pitcher_split_code][pitch_type] = {"total": 0}
                        stat_tracking[pitcher_id]["pitching"][pitcher_split_code][pitch_type]["total"] += 1

                        if pitch_zone not in stat_tracking[pitcher_id]["pitching"][pitcher_split_code][pitch_type]:
                            stat_tracking[pitcher_id]["pitching"][pitcher_split_code][pitch_type][pitch_zone] = {"total": 0}
                        stat_tracking[pitcher_id]["pitching"][pitcher_split_code][pitch_type][pitch_zone]["total"] += 1

                        # Update batter data - create new dict for each level to avoid circular references
                        if "Foul" in event["details"]["description"]:
                            stat_key = "fouls"
                        elif "Strike" in event["details"]["description"]:
                            stat_key = "strikes"
                        elif event["details"]["isInPlay"] and not event["details"]["isOut"]:
                            stat_key = "hits"
                        elif event["details"]["isBall"]:
                            stat_key = "balls"
                        else:
                            stat_key = "outs"

                        default = {"total": 0, "fouls": 0, "strikes": 0, "hits": 0, "balls": 0, "outs": 0}

                        if batter_id not in stat_tracking:
                            stat_tracking[batter_id] = {}
                        if "batting" not in stat_tracking[batter_id]:
                            stat_tracking[batter_id]["batting"] = default.copy()
                        stat_tracking[batter_id]["batting"]["total"] += 1
                        stat_tracking[batter_id]["batting"][stat_key] += 1

                        if batter_split_code not in stat_tracking[batter_id]["batting"]:
                            stat_tracking[batter_id]["batting"][batter_split_code] = default.copy()
                        stat_tracking[batter_id]["batting"][batter_split_code]["total"] += 1
                        stat_tracking[batter_id]["batting"][batter_split_code][stat_key] += 1

                        if pitch_type not in stat_tracking[batter_id]["batting"][batter_split_code]:
                            stat_tracking[batter_id]["batting"][batter_split_code][pitch_type] = default.copy()
                        stat_tracking[batter_id]["batting"][batter_split_code][pitch_type]["total"] += 1
                        stat_tracking[batter_id]["batting"][batter_split_code][pitch_type][stat_key] += 1

                        if pitch_zone not in stat_tracking[batter_id]["batting"][batter_split_code][pitch_type]:
                            stat_tracking[batter_id]["batting"][batter_split_code][pitch_type][pitch_zone] = default.copy()
                        stat_tracking[batter_id]["batting"][batter_split_code][pitch_type][pitch_zone]["total"] += 1
                        stat_tracking[batter_id]["batting"][batter_split_code][pitch_type][pitch_zone][stat_key] += 1

        # Save the pitch tracking data to DynamoDB
        for player_id, tracking_data in stat_tracking.items():
            try:
                dynamo_data = table.get_item(Key={"player_id": player_id})
                if "Item" not in dynamo_data:
                    item = {
                        "player_id": player_id,
                        "name": "",
                        "past_games": {},
                    }
                else:
                    item = dynamo_data["Item"]

                item["past_games"][given_date.strftime("%Y-%m-%d")] = {
                    "game_pk": game_pk,
                    "pitch_tracking": tracking_data,
                }

                table.put_item(Item=item)
            except Exception as e:
                print(f"Error saving data for player {player_id}: {e}")
                continue
