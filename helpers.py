import pandas as pd
import requests
import pybaseball

TEAM_ABBREVIATIONS = {
    "Arizona Diamondbacks": "ARI",
    "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",
    "Chicago White Sox": "CWS",
    "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL",
    "Detroit Tigers": "DET",
    "Miami Marlins": "MIA",
    "Houston Astros": "HOU",
    "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD",
    "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN",
    "New York Mets": "NYM",
    "New York Yankees": "NYY",
    "Oakland Athletics": "OAK",
    "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SD",
    "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA",
    "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WSH",
}


def get_team_abbreviation(team_name):
    return TEAM_ABBREVIATIONS[team_name]


def get_player_id(player_name: str) -> int | None:
    matches = pybaseball.playerid_lookup(player_name.split(" ")[1], player_name.split(" ")[0])

    if len(matches) == 0:
        raise ValueError(f"No players found for {player_name}: {matches}")

    return matches["key_mlbam"].values[0]


def get_lineups():
    mock_data = [
        {"Name": "Reese Olson", "Position": "P", "Hand": "R", "Team": "DET"},
        {"Name": "Parker Meadows", "Position": "CF", "Hand": "L", "Team": "DET"},
        {"Name": "Gio Urshela", "Position": "3B", "Hand": "R", "Team": "DET"},
        {"Name": "Riley Greene", "Position": "LF", "Hand": "L", "Team": "DET"},
        {"Name": "Spencer Torkelson", "Position": "1B", "Hand": "R", "Team": "DET"},
        {"Name": "Kerry Carpenter", "Position": "DH", "Hand": "L", "Team": "DET"},
        {"Name": "Mark Canha", "Position": "DH", "Hand": "R", "Team": "DET"},
        {"Name": "Colt Keith", "Position": "2B", "Hand": "L", "Team": "DET"},
        {"Name": "Matt Vierling", "Position": "RF", "Hand": "R", "Team": "DET"},
        {"Name": "Javier Báez", "Position": "SS", "Hand": "R", "Team": "DET"},
        {"Name": "Zach McKinstry", "Position": "3B", "Hand": "L", "Team": "DET"},
        {"Name": "Wenceel Pérez", "Position": "CF", "Hand": "S", "Team": "DET"},
        {"Name": "Jake Rogers", "Position": "C", "Hand": "R", "Team": "DET"},
        {"Name": "Oneil Cruz", "Position": "SS", "Hand": "L", "Team": "PIT"},
        {"Name": "Bryan Reynolds", "Position": "RF", "Hand": "S", "Team": "PIT"},
        {"Name": "Ke'Bryan Hayes", "Position": "3B", "Hand": "R", "Team": "PIT"},
        {"Name": "Jack Suwinski", "Position": "LF", "Hand": "L", "Team": "PIT"},
        {"Name": "Andrew McCutchen", "Position": "DH", "Hand": "R", "Team": "PIT"},
        {"Name": "Rowdy Tellez", "Position": "1B", "Hand": "L", "Team": "PIT"},
        {"Name": "Connor Joe", "Position": "RF", "Hand": "R", "Team": "PIT"},
        {"Name": "Michael Taylor", "Position": "CF", "Hand": "R", "Team": "PIT"},
        {"Name": "Jared Triolo", "Position": "2B", "Hand": "R", "Team": "PIT"},
        {"Name": "Joey Bart", "Position": "C", "Hand": "R", "Team": "PIT"},
        {"Name": "Ryder Ryan", "Position": "P", "Hand": "R", "Team": "PIT"},
    ]

    df = pd.DataFrame(mock_data)

    # Add player IDs
    player_ids = []
    for index, row in df.iterrows():
        player_name = row["Name"]
        player_id = get_player_id(player_name)
        player_ids.append(player_id)
    df["Player ID"] = player_ids

    return df


def get_games():
    mock_data = [
        {
            "gamePk": 745520,
            "gameGuid": "d9c5c674-418e-40b4-aecb-94cdd81e1e96",
            "link": "/api/v1.1/game/745520/feed/live",
            "gameType": "R",
            "season": "2024",
            "gameDate": "2024-04-08T22:40:00Z",
            "officialDate": "2024-04-08",
            "status": {
                "abstractGameState": "Final",
                "codedGameState": "F",
                "detailedState": "Final",
                "statusCode": "F",
                "startTimeTBD": False,
                "abstractGameCode": "F",
            },
            "teams": {
                "away": {
                    "leagueRecord": {"wins": 6, "losses": 4, "pct": ".600"},
                    "score": 4,
                    "team": {"id": 116, "name": "Detroit Tigers", "link": "/api/v1/teams/116"},
                    "isWinner": False,
                    "splitSquad": False,
                    "seriesNumber": 4,
                },
                "home": {
                    "leagueRecord": {"wins": 9, "losses": 2, "pct": ".818"},
                    "score": 7,
                    "team": {"id": 134, "name": "Pittsburgh Pirates", "link": "/api/v1/teams/134"},
                    "isWinner": True,
                    "splitSquad": False,
                    "seriesNumber": 4,
                },
            },
            "venue": {"id": 31, "name": "PNC Park", "link": "/api/v1/venues/31"},
            "content": {"link": "/api/v1/game/745520/content"},
            "isTie": False,
            "gameNumber": 1,
            "publicFacing": True,
            "doubleHeader": "N",
            "gamedayType": "P",
            "tiebreaker": "N",
            "calendarEventID": "14-745520-2024-04-08",
            "seasonDisplay": "2024",
            "dayNight": "night",
            "scheduledInnings": 9,
            "reverseHomeAwayStatus": False,
            "inningBreakLength": 120,
            "gamesInSeries": 2,
            "seriesGameNumber": 1,
            "seriesDescription": "Regular Season",
            "recordSource": "S",
            "ifNecessary": "N",
            "ifNecessaryDescription": "Normal Game",
        }
    ]
    return mock_data


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
