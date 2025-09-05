from datetime import date
import re
from bs4 import BeautifulSoup
import pandas as pd
import requests
import statsapi

from loaders.common.constants import TEAM_ABBREVIATIONS


def get_team_abbreviation(team_name):
    return TEAM_ABBREVIATIONS[team_name]

def get_player_id(player_name: str) -> int | None:
    url_string = player_name.replace(" ", "%20")
    response = requests.get(f"https://statsapi.mlb.com/api/v1/people/search?names={url_string}").json()
    return response["people"][0]["id"] if response["people"] else None


def get_players(home_away_dict):
    rows = []
    for home_away, v in home_away_dict.items():
        players = v["players"]
        for idx, player in enumerate(players):
            if home_away == "Home":
                team = home_away_dict["Home"]["team"]
                opp = home_away_dict["Away"]["team"]
            else:
                team = home_away_dict["Away"]["team"]
                opp = home_away_dict["Home"]["team"]
            if player.find("span", {"class": "lineup__throws"}):
                playerPosition = "P"
                handedness = player.find("span", {"class": "lineup__throws"}).text
            else:
                playerPosition = player.find("div", {"class": "lineup__pos"}).text
                handedness = player.find("span", {"class": "lineup__bats"}).text

            a_tag = player.find("a")
            title = a_tag.get("title")
            if title:
                playerName = title.strip()
            else:
                playerName = a_tag.text.strip()
            
            if playerPosition == "P" and '.' in playerName:
                href = a_tag.get("href")
                # e.g. "/baseball/player/john-doe-12345"
                playerNameId = href.split("/")[-1]
                # split playerNameId by "-" and take the first 2 elements
                playerNameId = playerNameId.split("-")[:2]
                # join the elements with a space and capitalize the first letter of each word
                playerName = " ".join([word.capitalize() for word in playerNameId])

            playerRow = {
                "Bat Order": idx,
                "Name": playerName,
                "Position": playerPosition,
                "Team": team,
                "Opponent": opp,
                "Home/Away": home_away,
                "Handedness": handedness,
                "Lineup Status": home_away_dict[home_away]["lineupStatus"],
            }

            rows.append(playerRow)
            # print("{} {}".format(playerRow["Position"], playerRow["Name"]))

    return rows

def get_lineups(game_day: str = "today"):
    ERRORS = 0
    rows = []
    url = f"https://www.rotowire.com/baseball/daily-lineups.php?date={game_day}"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    lineupBoxes = soup.find_all("div", {"class": "lineup__box"})

    for lineupBox in lineupBoxes:
        try:
            awayTeam = lineupBox.find("div", {"class": "lineup__team is-visit"}).text.strip()
            homeTeam = lineupBox.find("div", {"class": "lineup__team is-home"}).text.strip()

            awayLineup = lineupBox.find("ul", {"lineup__list is-visit"})
            homeLineup = lineupBox.find("ul", {"lineup__list is-home"})

            awayLineupStatus = awayLineup.find("li", {"class": re.compile("lineup__status.*")}).text.strip()
            homeLineupStatus = homeLineup.find("li", {"class": re.compile("lineup__status.*")}).text.strip()

            awayPlayers = awayLineup.find_all("li", {"class": re.compile("lineup__player.*")})
            homePlayers = homeLineup.find_all("li", {"class": re.compile("lineup__player.*")})

            home_away_dict = {
                "Home": {"team": homeTeam, "players": homePlayers, "lineupStatus": homeLineupStatus},
                "Away": {"team": awayTeam, "players": awayPlayers, "lineupStatus": awayLineupStatus},
            }

            playerRows = get_players(home_away_dict)
            rows += playerRows
        except:
            continue

    df = pd.DataFrame(rows)

    # Add player IDs
    player_ids = []
    for index, row in df.iterrows():
        player_name = row["Name"]
        player_id = get_player_id(player_name)
        player_ids.append(str(player_id))
    df["Player ID"] = player_ids

    return df


def get_games():
    params = {
        "sportId": 1,
        "date": date.today().strftime("%Y-%m-%d"),
    }
    games = statsapi.get("schedule", params)["dates"][0]["games"]
    return games