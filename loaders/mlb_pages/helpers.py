import requests

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
