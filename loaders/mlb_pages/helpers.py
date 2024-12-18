import boto3
import requests

dynamo = boto3.resource("dynamodb")
table = dynamo.Table("mlb-page-data")

def get_mlb_batter_stats(player_id, vs_hand=None):
    if vs_hand == "L":
        return requests.get(f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?group=batting&season=2024&stats=statSplits&sitCodes=vl").json()
    elif vs_hand == "R":
        return requests.get(f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?group=batting&season=2024&stats=statSplits&sitCodes=vr").json()
    else:
        return requests.get(f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?group=batting&season=2024&stats=season").json()


def get_mlb_pitcher_stats(player_id, vs_hand=None):
    if vs_hand == "L":
        return requests.get(f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?group=pitching&season=2024&stats=statSplits&sitCodes=vl").json()
    elif vs_hand == "R":
        return requests.get(f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?group=pitching&season=2024&stats=statSplits&sitCodes=vr").json()
    elif vs_hand == "All":
        return {
            "L": requests.get(f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?group=pitching&season=2024&stats=statSplits&sitCodes=vl").json(),
            "R": requests.get(f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?group=pitching&season=2024&stats=statSplits&sitCodes=vr").json(),
            "S": requests.get(f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?group=pitching&season=2024&stats=season").json(),
        }
    else:
        return requests.get(f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?group=pitching&season=2024&stats=season").json()

def get_batter_history(batter_id, num_games: int = 5, key: str = "hits"):
    player_data = table.get_item(Key={"player_id": batter_id})
    if "Item" not in player_data:
        return [0] * num_games
    past_games = player_data["Item"]["past_games"]
    l5_games = past_games[-5:]

    return list(map(lambda x: x[key], l5_games))
