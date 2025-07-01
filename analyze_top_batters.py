import os
import re
from typing import List, Dict, Tuple

def parse_game_file(file_path: str) -> List[Dict]:
    """Parse a game file and extract batter statistics."""
    batters = []
    
    with open(file_path, 'r') as file:
        content = file.read()
    
    # Split by sections (teams)
    sections = content.split('-----------------------------------')
    
    for section in sections[1:]:  # Skip the header section
        lines = section.strip().split('\n')
        if len(lines) < 2:
            continue
            
        # Extract team vs pitcher info
        team_pitcher_line = lines[0].strip()
        
        i = 1
        while i < len(lines):
            line = lines[i].strip()
            
            # Check if this is a player name line (not empty and not starting with Hit/Strike/etc.)
            if line and not line.startswith(('Hit:', 'Strike:', 'Foul:', 'Ball:', 'Out:', 'Total:', '-')):
                player_name = line
                
                # Look for stats in the next few lines
                stats = {}
                j = i + 1
                while j < len(lines) and j < i + 10:  # Look ahead max 10 lines
                    stat_line = lines[j].strip()
                    if stat_line.startswith('Hit:'):
                        hit_match = re.search(r'Hit: ([\d.]+)', stat_line)
                        if hit_match:
                            stats['hit'] = float(hit_match.group(1))
                    elif stat_line.startswith('Strike:'):
                        strike_match = re.search(r'Strike: ([\d.]+)', stat_line)
                        if strike_match:
                            stats['strike'] = float(strike_match.group(1))
                    elif stat_line.startswith('Foul:'):
                        foul_match = re.search(r'Foul: ([\d.]+)', stat_line)
                        if foul_match:
                            stats['foul'] = float(foul_match.group(1))
                    elif stat_line.startswith('Total:'):
                        break
                    j += 1
                
                # If we found all required stats, add the batter
                if 'hit' in stats and 'strike' in stats and 'foul' in stats:
                    stats['strike_foul_combined'] = stats['strike'] + stats['foul']
                    stats['player_name'] = player_name
                    stats['matchup'] = team_pitcher_line
                    stats['file'] = os.path.basename(file_path)
                    batters.append(stats)
                
                i = j
            else:
                i += 1
    
    return batters

def analyze_all_games() -> Tuple[List[Dict], List[Dict]]:
    """Analyze all game files and return top batters."""
    directory = "2025-05-03"
    all_batters = []
    
    # Get all game files
    for filename in os.listdir(directory):
        if filename.startswith('game_') and filename.endswith('.txt'):
            file_path = os.path.join(directory, filename)
            print(f"Analyzing {filename}...")
            batters = parse_game_file(file_path)
            all_batters.extend(batters)
    
    print(f"Found {len(all_batters)} total batter matchups")
    
    # Sort by strike + foul odds (descending)
    top_strike_foul = sorted(all_batters, key=lambda x: x['strike_foul_combined'], reverse=True)[:10]
    
    # Sort by hit odds (descending)
    top_hit = sorted(all_batters, key=lambda x: x['hit'], reverse=True)[:10]
    
    return top_strike_foul, top_hit

def print_results(top_strike_foul: List[Dict], top_hit: List[Dict]):
    """Print the results in a formatted way."""
    print("\n" + "="*80)
    print("TOP 10 BATTERS WITH HIGHEST STRIKE + FOUL ODDS")
    print("="*80)
    
    for i, batter in enumerate(top_strike_foul, 1):
        print(f"{i:2d}. {batter['player_name']:<25} - {batter['strike_foul_combined']:.1%}")
        print(f"    Strike: {batter['strike']:.1%} | Foul: {batter['foul']:.1%} | Hit: {batter['hit']:.1%}")
        print(f"    Matchup: {batter['matchup']}")
        print(f"    Game: {batter['file']}")
        print()
    
    print("\n" + "="*80)
    print("TOP 10 BATTERS WITH HIGHEST HIT ODDS")
    print("="*80)
    
    for i, batter in enumerate(top_hit, 1):
        print(f"{i:2d}. {batter['player_name']:<25} - {batter['hit']:.1%}")
        print(f"    Strike: {batter['strike']:.1%} | Foul: {batter['foul']:.1%} | Strike+Foul: {batter['strike_foul_combined']:.1%}")
        print(f"    Matchup: {batter['matchup']}")
        print(f"    Game: {batter['file']}")
        print()

if __name__ == "__main__":
    top_strike_foul, top_hit = analyze_all_games()
    print_results(top_strike_foul, top_hit)
