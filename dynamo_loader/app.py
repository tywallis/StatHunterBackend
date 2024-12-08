from helpers import get_games, get_lineups, get_mlb_batter_stats, get_mlb_pitcher_stats, get_team_abbreviation
import boto3
from datetime import date


def lambda_handler(event, context):
    games_to_analyze = get_games()

    if len(games_to_analyze) > 0:
        df = get_lineups()
        results = []

        print(f"Analyzing {len(games_to_analyze)} total games...")
        counter = 1
        for game in games_to_analyze:
            print(f"Analyzing game {counter} of {len(games_to_analyze)}...")
            counter += 1

            away_team = game["teams"]["away"]["team"]["name"]
            away_pitcher = df.loc[(df["Team"] == get_team_abbreviation(away_team)) & (df["Position"] == "P")]
            away_batters = df.loc[(df["Team"] == get_team_abbreviation(away_team)) & (df["Position"] != "P")]
            away_pitcher_stats = get_mlb_pitcher_stats(away_pitcher["Player ID"].values[0], "All")

            home_team = game["teams"]["home"]["team"]["name"]
            home_pitcher = df.loc[(df["Team"] == get_team_abbreviation(home_team)) & (df["Position"] == "P")]
            home_batters = df.loc[(df["Team"] == get_team_abbreviation(home_team)) & (df["Position"] != "P")]
            home_pitcher_stats = get_mlb_pitcher_stats(home_pitcher["Player ID"].values[0], "All")

            for index, row in away_batters.iterrows():
                batter_mlb_stats = get_mlb_batter_stats(row["Player ID"], "All")["stats"][0]["splits"][0]["stat"]
                batter_l5 = ""  # get_batter_l5()
                batter_stats_dynamo_row = {
                    "batter_team": get_team_abbreviation(away_team),
                    "batter_name": f"{row["Name"]} ({row["Hand"]})",
                    "batter_ba": batter_mlb_stats["avg"],
                    "pitcher_ba": home_pitcher_stats[row["Hand"]]["stats"][0]["splits"][0]["stat"]["avg"],
                    "pitcher_name": f"{home_pitcher['Name'].values[0]} ({home_pitcher['Hand'].values[0]})",
                    "L5": batter_l5,
                }
                results.append(batter_stats_dynamo_row)

            for index, row in home_batters.iterrows():
                batter_mlb_stats = get_mlb_batter_stats(row["Player ID"], "All")["stats"][0]["splits"][0]["stat"]
                batter_l5 = ""  # get_batter_l5()
                batter_stats_dynamo_row = {
                    "batter_team": get_team_abbreviation(home_team),
                    "batter_name": f"{row["Name"]} ({row["Hand"]})",
                    "batter_ba": batter_mlb_stats["avg"],
                    "pitcher_ba": away_pitcher_stats[row["Hand"]]["stats"][0]["splits"][0]["stat"]["avg"],
                    "pitcher_name": f"{away_pitcher['Name'].values[0]} ({away_pitcher['Hand'].values[0]})",
                    "L5": batter_l5,
                }
                results.append(batter_stats_dynamo_row)

        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table("mlb-page-data")
        table.put_item(
            Item={
                "date": date.today().strftime("%Y-%m-%d"),
                "page": "batter-hits",
                "data": results,
            }
        )


lambda_handler(None, None)
