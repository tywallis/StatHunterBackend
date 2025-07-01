from loaders.common.utils import get_games, get_lineups, get_team_abbreviation
from loaders.mlb_pages.helpers import get_batter_history, get_mlb_batter_stats, get_mlb_pitcher_stats
import boto3
from datetime import date


def process_batters(batters, vs_pitcher_stats, team, vs_pitcher, results):
    for index, row in batters.iterrows():
        stats = get_mlb_batter_stats(row["Player ID"], "All")
        if "stats" not in stats or len(stats["stats"]) == 0 or "splits" not in stats["stats"][0]:
            continue
        batter_mlb_stats = stats["stats"][0]["splits"][0]["stat"]
        batter_l5 = get_batter_history(row["Player ID"])
        batter_name = row["Name"]
        batter_hand = row["Handedness"]
        pitcher_ba = vs_pitcher_stats[row["Handedness"]]["stats"][0]["splits"][0]["stat"]["avg"] if vs_pitcher_stats[row["Handedness"]]["stats"] and vs_pitcher_stats[row["Handedness"]]["stats"][0]["splits"] else 0
        batter_stats_dynamo_row = {
            "batter_id": row["Player ID"],
            "pitcher_id": vs_pitcher["Player ID"].values[0],
            "batter_team": get_team_abbreviation(team),
            "batter_name": f"{batter_name} ({batter_hand})",
            "batter_ba": batter_mlb_stats["avg"],
            "pitcher_ba": pitcher_ba,
            "pitcher_name": f"{vs_pitcher['Name'].values[0]} ({vs_pitcher['Handedness'].values[0]})",
            "L5": batter_l5,
        }
        results.append(batter_stats_dynamo_row)


def load_mlb_page_data():
    games_to_analyze = get_games()

    if len(games_to_analyze) > 0:
        df = get_lineups()
        print(df.to_markdown())

        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table("mlb-page-data")

        # Check the table to see if lineups have changed
        response = table.get_item(Key={"date": date.today().strftime("%Y-%m-%d"), "page": "daily-lineups"})
        if "Item" in response:
            existing_data = response["Item"]["data"]
            if existing_data == df.to_dict(orient="records"):
                print("Lineups have not changed. No need to update.")
                return
        print("Lineups have changed. Updating with new lineups.")
        table.put_item(
            Item={
                "date": date.today().strftime("%Y-%m-%d"),
                "page": "daily-lineups",
                "data": df.to_dict(orient="records"),
            }
        )

        hits_results = []

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

            process_batters(away_batters, home_pitcher_stats, away_team, home_pitcher, hits_results)
            process_batters(home_batters, away_pitcher_stats, home_team, away_pitcher, hits_results)

        table.put_item(
            Item={
                "date": date.today().strftime("%Y-%m-%d"),
                "page": "batter-hits",
                "data": hits_results,
            }
        )
