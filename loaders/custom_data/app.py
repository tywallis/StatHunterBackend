from datetime import date
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
            item = (
                {
                    "player_id": player_stats["person"]["id"],
                    "name": player_stats["person"]["fullName"],
                    "past_games": [],
                },
            )
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


def load_daily_player_stats(given_date: date = date.today()):
    games = get_games_by_date(given_date)
    print(f"Processing {len(games)} games for {given_date}")
    for game in games:
        game_pk = game["gamePk"]
        # play_by_play = get_play_by_play(game_pk)
        boxscore = get_boxscore(game_pk)

        for player_key in boxscore["home"]["players"].keys():
            player_stats = boxscore["home"]["players"][player_key]
            save_player_data(player_stats, game_pk, given_date)

        for player_key in boxscore["away"]["players"].keys():
            player_stats = boxscore["away"]["players"][player_key]
            save_player_data(player_stats, game_pk, given_date)
