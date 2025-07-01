import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
import statsapi

FUNKY_PLAYER_NAMES = {
    "Jose Ramirez": "José Ramírez",
    "Andres Gimenez": "Andrés Giménez",
    "Luis Garcia": "Luis García",
    "Jose Tena": "José Tena",
    "Andres Chaparro": "Andrés Chaparro",
    "Andy Ibanez": "Andy Ibáñez",
    "Javier Baez": "Javier Báez",
    "Yandy Diaz": "Yandy Díaz",
    "Michael Taylor": "Michael A. Taylor",
    "Ramon Urias": "Ramón Urías",
    "S. Arrighetti": "Spencer Arrighetti",
    "Jeremy Pena": "Jeremy Peña",
    "Mauricio Dubon": "Mauricio Dubón",
    "S. Schwellenbach": "Spencer Schwellenbach",
    "Ramon Laureano": "Ramón Laureano",
    "C. Sanchez": "Cristopher Sánchez",
    "Gary Sanchez": "Gary Sánchez",
    "Jose Caballero": "José Caballero",
    "Leo Jimenez": "Leo Jiménez",
    "Carlos Rodon": "Carlos Rodón",
    "Eugenio Suarez": "Eugenio Suárez",
    "Adolis Garcia": "Adolis García",
    "Jesus Sanchez": "Jesús Sánchez",
    "Julio Rodriguez": "Julio Rodríguez",
    "Teoscar Hernandez": "Teoscar Hernández",
    "Nasim Nunez": "Nasim Nuñez",
    "Enrique Hernandez": "Enrique Hernández",
    "Albert Suarez": "Albert Suárez",
    "Eloy Jimenez": "Eloy Jiménez",
    "Ali Sanchez": "Ali Sánchez",
    "Ranger Suarez": "Ranger Suárez",
    "Pablo Lopez": "Pablo López",
    "Vidal Brujan": "Vidal Bruján",
    "Pedro Pages": "Pedro Pagés",
    "Christian Vazquez": "Christian Vázquez",
    "Reynaldo Lopez": "Reynaldo López",
    "Luis Ortiz": "Luis L. Ortiz",
    "Martin Perez": "Martín Pérez",
    "Jose Berrios": "José Berríos",
    "Randy Vasquez": "Randy Vásquez",
    "Yariel Rodriguez": "Yariel Rodríguez",
    "S. Woods Richardson": "Simeon Woods Richardson",
    "Roddery Munoz": "Roddery Muñoz",
    "E. Rodriguez": "Eduardo Rodriguez",
    "Ivan Herrera": "Iván Herrera",
    "B. Williamson": "Brandon Williamson",
    "Jose Fermin": "José Fermín",
    "Jose Urena": "José Ureña",
    "Jose Devers": "José Devers",
    "Domingo German": "Domingo Germán",
    "Wenceel Perez": "Wenceel Pérez",
    "Angel Martinez": "Angel Martínez",
    "Jasson Dominguez": "Jasson Domínguez",
    "Jack Lopez": "Jack López",
    "Jose Suarez": "José Suarez",
    "Y. Yamamoto": "Yoshinobu Yamamoto",
}

def get_players(home_away_dict):
    rows = []
    for home_away, v in home_away_dict.items():
        players = v["players"]
        # print("\n{} - {}".format(v["team"], v["lineupStatus"]))
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

            if "title" in list(player.find("a").attrs.keys()):
                playerName = player.find("a")["title"].strip()
            else:
                playerName = player.find("a").text.strip()

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

def get_player_id(player_name: str) -> int | None:
    if player_name in FUNKY_PLAYER_NAMES:
        player_name = FUNKY_PLAYER_NAMES[player_name]

    matches = statsapi.lookup_player(player_name)
    
    if len(matches) == 0:
        print(f"Warning: No player found for name '{player_name}'")
        return 0
    return int(matches[0]["id"])


def get_team_lineups(game_day: str = "today"):
    rows = []
    url = f"https://www.rotowire.com/baseball/daily-lineups.php?date={game_day}"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    lineupBoxes = soup.find_all("div", {"class": "lineup__box"})

    for lineupBox in lineupBoxes:
        try:
            awayTeam = lineupBox.find("div", {"class": "lineup__team is-visit"}).text.strip()
            homeTeam = lineupBox.find("div", {"class": "lineup__team is-home"}).text.strip()

            # print(f"\n\n############\n  {awayTeam} @ {homeTeam}\n############")

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

    print("Adding Player ID column to lineups df...")
    player_ids = []
    for index, row in df.iterrows():
        player_name = row["Name"]
        player_id = int(get_player_id(player_name))
        player_ids.append(player_id)
    df["Player ID"] = player_ids

    # Drop all rows where Player ID is 0 (not found)
    df = df[df["Player ID"] != 0]

    return df
