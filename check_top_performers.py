#!/usr/bin/env python3
"""
Script to check top performers' actual performance against predictions.
Finds the top 2 hitters, top 3 strikers, and top 3 walkers for each day
and verifies if they achieved at least 1 of their projected stat using statsapi.
"""

import os
import re
import glob
from datetime import datetime, date
from typing import List, Dict, Tuple, Optional
import statsapi
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

class PerformanceChecker:
    def __init__(self):
        self.prediction_files = []
        self.results = []
        self.generate_graph = None  # Auto-decide
        # Profit tracking
        self.profit_tracking = {
            'hitters': 0.0,
            'strikers': 0.0,
            'walkers': 0.0,
            'daily_results': []
        }
        
    def find_prediction_files(self, directory: str = ".") -> List[str]:
        """Find all prediction files in the directory."""
        pattern = os.path.join(directory, "2025-*.txt")
        files = glob.glob(pattern)
        # Sort by date
        return sorted(files)
    
    def parse_prediction_file(self, file_path: str) -> Dict:
        """Parse a prediction file and extract game information and top performers."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract date from filename
        filename = os.path.basename(file_path)
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
        if not date_match:
            return None
        
        date_str = date_match.group(1)
        
        # Extract game IDs and links
        games = []
        game_matches = re.findall(r'GAME \d+ of \d+: (\d+)\nGame Link: www\.mlb\.com/gameday/(\d+)/final/box', content)
        for game_id, link_id in game_matches:
            games.append({
                'game_id': game_id,
                'link_id': link_id
            })
        
        # Parse top performers from the summary section
        summary_section = content.split("*** TOP PERFORMERS SUMMARY FOR")[1] if "*** TOP PERFORMERS SUMMARY FOR" in content else ""
        
        top_hitters = self._extract_top_performers(summary_section, "TOP 10 MOST LIKELY TO GET A HIT:", 2)
        top_strikers = self._extract_top_performers(summary_section, "TOP 10 MOST LIKELY TO STRIKEOUT:", 3)
        top_walkers = self._extract_top_performers(summary_section, "TOP 10 MOST LIKELY TO WALK:", 3)
        
        return {
            'date': date_str,
            'games': games,
            'top_hitters': top_hitters,
            'top_strikers': top_strikers,
            'top_walkers': top_walkers
        }
    
    def _extract_top_performers(self, summary_section: str, section_header: str, count: int) -> List[Dict]:
        """Extract top performers from a specific section."""
        performers = []
        
        if section_header not in summary_section:
            return performers
        
        section_start = summary_section.find(section_header)
        section_end = summary_section.find("TOP 10", section_start + 1)
        if section_end == -1:
            section_end = summary_section.find("OVERALL AVERAGES", section_start)
        if section_end == -1:
            section_end = len(summary_section)
        
        section_content = summary_section[section_start:section_end]
        lines = section_content.split('\n')
        
        current_count = 0
        i = 0
        while i < len(lines) and current_count < count:
            line = lines[i].strip()
            
            # Look for numbered entries
            match = re.match(r'\s*(\d+)\.\s+([^(]+)\s+\(([^)]+)\)\s+-\s+([\d.]+)%', line)
            if match:
                rank = int(match.group(1))
                name = match.group(2).strip()
                team = match.group(3).strip()
                percentage = float(match.group(4))
                
                # Get game info from next line if available
                game_info = ""
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if "vs" in next_line and "Game" in next_line:
                        game_info = next_line
                
                performers.append({
                    'name': name,
                    'team': team,
                    'percentage': percentage,
                    'game_info': game_info,
                    'rank': rank
                })
                current_count += 1
            
            i += 1
        
        return performers
    
    def get_game_boxscore(self, game_id: str) -> Dict:
        """Get boxscore data for a specific game."""
        try:
            boxscore = statsapi.boxscore_data(game_id)
            return boxscore
        except Exception as e:
            print(f"Error fetching boxscore for game {game_id}: {e}")
            return None
    
    def check_player_performance(self, player_name: str, team: str, boxscore: Dict, stat_type: str) -> Dict:
        """Check if a player achieved their projected stat in the game."""
        if not boxscore:
            return {'found': False, 'achieved': False, 'details': 'No boxscore data'}
        
        # Clean player name for matching
        clean_name = self._clean_player_name(player_name)
        
        result = {
            'found': False,
            'achieved': False,
            'details': '',
            'stats': {}
        }
        
        # Search both teams' batting stats
        for team_key in ['home', 'away']:
            if team_key not in boxscore:
                continue
                
            team_data = boxscore[team_key]
            if 'players' not in team_data:
                continue
            
            # Check each player
            for player_id, player_data in team_data['players'].items():
                if 'person' not in player_data:
                    continue
                
                api_name = player_data['person'].get('fullName', '')
                clean_api_name = self._clean_player_name(api_name)
                
                # Try various name matching approaches
                if self._names_match(clean_name, clean_api_name):
                    result['found'] = True
                    
                    # Get batting stats if available
                    if 'stats' in player_data and 'batting' in player_data['stats']:
                        batting_stats = player_data['stats']['batting']
                        
                        hits = batting_stats.get('hits', 0)
                        strikeouts = batting_stats.get('strikeOuts', 0)
                        walks = batting_stats.get('baseOnBalls', 0)
                        
                        result['stats'] = {
                            'hits': hits,
                            'strikeouts': strikeouts,
                            'walks': walks,
                            'at_bats': batting_stats.get('atBats', 0),
                            'plate_appearances': batting_stats.get('plateAppearances', 0)
                        }
                        
                        # Check if achieved the projected stat
                        if stat_type == 'hit' and hits >= 1:
                            result['achieved'] = True
                            result['details'] = f"Got {hits} hit(s)"
                        elif stat_type == 'strikeout' and strikeouts >= 1:
                            result['achieved'] = True
                            result['details'] = f"Had {strikeouts} strikeout(s)"
                        elif stat_type == 'walk' and walks >= 1:
                            result['achieved'] = True
                            result['details'] = f"Had {walks} walk(s)"
                        else:
                            result['details'] = f"Stats: {hits}H, {strikeouts}K, {walks}BB"
                    else:
                        result['details'] = "No batting stats found"
                    
                    break
        
        if not result['found']:
            result['details'] = f"Player '{player_name}' not found in boxscore"
        
        return result
    
    def _clean_player_name(self, name: str) -> str:
        """Clean player name for matching."""
        # Remove extra spaces, convert to lowercase
        cleaned = re.sub(r'\s+', ' ', name.strip().lower())
        # Remove common suffixes
        cleaned = re.sub(r'\s+(jr\.?|sr\.?|ii|iii)$', '', cleaned)
        return cleaned
    
    def _names_match(self, name1: str, name2: str) -> bool:
        """Check if two player names match using various approaches."""
        if name1 == name2:
            return True
        
        # Try last name matching
        name1_parts = name1.split()
        name2_parts = name2.split()
        
        if len(name1_parts) >= 2 and len(name2_parts) >= 2:
            # Compare last names
            if name1_parts[-1] == name2_parts[-1]:
                # If last names match, check if first names start with same letter
                if name1_parts[0][0] == name2_parts[0][0]:
                    return True
        
        # Try partial matching (in case of nicknames)
        if name1 in name2 or name2 in name1:
            return True
        
        return False
    
    def calculate_daily_profit(self, results: Dict) -> Dict:
        """Calculate profit for a single day based on betting strategy."""
        daily_profit = {
            'date': results['date'],
            'hitters': 0.0,
            'strikers': 0.0,
            'walkers': 0.0
        }
        
        # HITTERS: Both top hitters must get a hit (+1.5), otherwise (-1)
        hitter_successes = sum(1 for entry in results['hitters'] if entry['performance']['achieved'])
        if hitter_successes == len(results['hitters']) and len(results['hitters']) >= 2:
            daily_profit['hitters'] = 1.5
        else:
            daily_profit['hitters'] = -1.0
        
        # STRIKERS: All three top strikers must get a strikeout (+1.0), otherwise (-1)
        striker_successes = sum(1 for entry in results['strikers'] if entry['performance']['achieved'])
        if striker_successes == len(results['strikers']) and len(results['strikers']) >= 3:
            daily_profit['strikers'] = 1.0
        else:
            daily_profit['strikers'] = -1.0
        
        # WALKERS: Individual scoring + bonus
        walker_successes = sum(1 for entry in results['walkers'] if entry['performance']['achieved'])
        walker_failures = len(results['walkers']) - walker_successes
        
        # Individual walker scoring: +0.5 for each success, -0.3 for each failure
        daily_profit['walkers'] = (walker_successes * 0.5) - (walker_failures * 0.3)
        
        # Bonus/penalty: If all walkers succeed +1.5, if any fail additional -0.1
        if walker_successes == len(results['walkers']) and len(results['walkers']) > 0:
            daily_profit['walkers'] += 1.5
        elif walker_failures > 0:
            daily_profit['walkers'] -= 0.1
        
        # Calculate if this is a perfect day (all markets at 100%)
        hitter_success_rate = hitter_successes / max(len(results['hitters']), 1)
        striker_success_rate = striker_successes / max(len(results['strikers']), 1)
        walker_success_rate = walker_successes / max(len(results['walkers']), 1)
        
        is_perfect_day = (hitter_success_rate == 1.0 and 
                         striker_success_rate == 1.0 and 
                         walker_success_rate == 1.0)
        
        daily_profit['perfect_day'] = is_perfect_day
        
        return daily_profit
    
    def update_profit_tracking(self, daily_profit: Dict):
        """Update overall profit tracking with daily results."""
        self.profit_tracking['hitters'] += daily_profit['hitters']
        self.profit_tracking['strikers'] += daily_profit['strikers']
        self.profit_tracking['walkers'] += daily_profit['walkers']
        self.profit_tracking['daily_results'].append(daily_profit)
    
    def process_single_date(self, file_path: str) -> Dict:
        """Process predictions for a single date."""
        print(f"Processing {os.path.basename(file_path)}...")
        
        parsed_data = self.parse_prediction_file(file_path)
        if not parsed_data:
            return None
        
        date_str = parsed_data['date']
        results = {
            'date': date_str,
            'games_processed': 0,
            'hitters': [],
            'strikers': [],
            'walkers': []
        }
        
        # Get all game boxscores first
        game_boxscores = {}
        for game in parsed_data['games']:
            game_id = game['game_id']
            print(f"  Fetching boxscore for game {game_id}...")
            boxscore = self.get_game_boxscore(game_id)
            if boxscore:
                game_boxscores[game_id] = boxscore
                results['games_processed'] += 1
        
        # Check top hitters across all games
        for hitter in parsed_data['top_hitters']:
            found = False
            for game_id, boxscore in game_boxscores.items():
                performance = self.check_player_performance(
                    hitter['name'], hitter['team'], boxscore, 'hit'
                )
                if performance['found']:
                    results['hitters'].append({
                        'player': hitter,
                        'performance': performance,
                        'game_id': game_id
                    })
                    found = True
                    break
            
            if not found:
                # Add with "not found" status
                results['hitters'].append({
                    'player': hitter,
                    'performance': {'found': False, 'achieved': False, 'details': 'Player not found in any game', 'stats': {}},
                    'game_id': 'N/A'
                })
        
        # Check top strikers across all games
        for striker in parsed_data['top_strikers']:
            found = False
            for game_id, boxscore in game_boxscores.items():
                performance = self.check_player_performance(
                    striker['name'], striker['team'], boxscore, 'strikeout'
                )
                if performance['found']:
                    results['strikers'].append({
                        'player': striker,
                        'performance': performance,
                        'game_id': game_id
                    })
                    found = True
                    break
            
            if not found:
                results['strikers'].append({
                    'player': striker,
                    'performance': {'found': False, 'achieved': False, 'details': 'Player not found in any game', 'stats': {}},
                    'game_id': 'N/A'
                })
        
        # Check top walkers across all games
        for walker in parsed_data['top_walkers']:
            found = False
            for game_id, boxscore in game_boxscores.items():
                performance = self.check_player_performance(
                    walker['name'], walker['team'], boxscore, 'walk'
                )
                if performance['found']:
                    results['walkers'].append({
                        'player': walker,
                        'performance': performance,
                        'game_id': game_id
                    })
                    found = True
                    break
            
            if not found:
                results['walkers'].append({
                    'player': walker,
                    'performance': {'found': False, 'achieved': False, 'details': 'Player not found in any game', 'stats': {}},
                    'game_id': 'N/A'
                })
        
        return results
    
    def print_results(self, results: Dict, daily_profit: Dict = None):
        """Print formatted results for a single date."""
        print(f"\n{'='*80}")
        print(f"RESULTS FOR {results['date']}")
        print(f"Games Processed: {results['games_processed']}")
        print(f"{'='*80}")
        
        # Print hitters results
        print(f"\nTOP 2 HITTERS:")
        print(f"{'-'*50}")
        for i, entry in enumerate(results['hitters'], 1):
            player = entry['player']
            perf = entry['performance']
            status = "✓ HIT!" if perf['achieved'] else "✗ No hit"
            print(f"{i}. {player['name']} ({player['team']}) - {player['percentage']:.1f}%")
            print(f"   {status} - {perf['details']}")
            if perf['stats']:
                stats = perf['stats']
                print(f"   Game Stats: {stats['hits']}H, {stats['strikeouts']}K, {stats['walks']}BB in {stats['at_bats']}AB")
        
        # Print strikers results
        print(f"\nTOP 3 STRIKERS:")
        print(f"{'-'*50}")
        for i, entry in enumerate(results['strikers'], 1):
            player = entry['player']
            perf = entry['performance']
            status = "✓ STRUCK OUT!" if perf['achieved'] else "✗ No strikeout"
            print(f"{i}. {player['name']} ({player['team']}) - {player['percentage']:.1f}%")
            print(f"   {status} - {perf['details']}")
            if perf['stats']:
                stats = perf['stats']
                print(f"   Game Stats: {stats['hits']}H, {stats['strikeouts']}K, {stats['walks']}BB in {stats['at_bats']}AB")
        
        # Print walkers results
        print(f"\nTOP 3 WALKERS:")
        print(f"{'-'*50}")
        for i, entry in enumerate(results['walkers'], 1):
            player = entry['player']
            perf = entry['performance']
            status = "✓ WALKED!" if perf['achieved'] else "✗ No walk"
            print(f"{i}. {player['name']} ({player['team']}) - {player['percentage']:.1f}%")
            print(f"   {status} - {perf['details']}")
            if perf['stats']:
                stats = perf['stats']
                print(f"   Game Stats: {stats['hits']}H, {stats['strikeouts']}K, {stats['walks']}BB in {stats['at_bats']}AB")
        
        # Calculate success rates
        hitter_success = sum(1 for entry in results['hitters'] if entry['performance']['achieved'])
        striker_success = sum(1 for entry in results['strikers'] if entry['performance']['achieved'])
        walker_success = sum(1 for entry in results['walkers'] if entry['performance']['achieved'])
        
        print(f"\nSUCCESS SUMMARY:")
        print(f"{'-'*50}")
        print(f"Hitters: {hitter_success}/{len(results['hitters'])} ({hitter_success/max(len(results['hitters']), 1)*100:.1f}%)")
        print(f"Strikers: {striker_success}/{len(results['strikers'])} ({striker_success/max(len(results['strikers']), 1)*100:.1f}%)")
        print(f"Walkers: {walker_success}/{len(results['walkers'])} ({walker_success/max(len(results['walkers']), 1)*100:.1f}%)")
        
        # Print daily profit if available
        if daily_profit:
            print(f"\nDAILY PROFIT ESTIMATE:")
            print(f"{'-'*50}")
            hitter_result = "PROFIT" if daily_profit['hitters'] > 0 else "LOSS"
            striker_result = "PROFIT" if daily_profit['strikers'] > 0 else "LOSS"
            walker_result = "PROFIT" if daily_profit['walkers'] > 0 else "LOSS"
            
            print(f"Hitters: {daily_profit['hitters']:+.1f} units ({hitter_result})")
            print(f"Strikers: {daily_profit['strikers']:+.1f} units ({striker_result})")
            print(f"Walkers: {daily_profit['walkers']:+.1f} units ({walker_result})")
            print(f"TOTAL: {sum(daily_profit[k] for k in ['hitters', 'strikers', 'walkers']):+.1f} units")
    
    def run_analysis(self, specific_date: str = None, days_back: int = 7):
        """Run the complete analysis."""
        print("MLB Top Performers Analysis")
        print("="*50)
        
        # Find all prediction files
        prediction_files = self.find_prediction_files()
        
        if specific_date:
            # Filter for specific date
            prediction_files = [f for f in prediction_files if specific_date in f]
            if not prediction_files:
                print(f"No prediction file found for date: {specific_date}")
                return
        else:
            # Use last N days
            prediction_files = prediction_files[-days_back:]
        
        print(f"Found {len(prediction_files)} prediction files to process")
        
        all_results = []
        
        for file_path in prediction_files:
            try:
                results = self.process_single_date(file_path)
                if results:
                    # Calculate daily profit
                    daily_profit = self.calculate_daily_profit(results)
                    self.update_profit_tracking(daily_profit)
                    
                    all_results.append(results)
                    self.print_results(results, daily_profit)
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                continue
        
        # Print overall summary
        if len(all_results) > 1:
            self.print_overall_summary(all_results)
        
        # Print profit summary
        self.print_profit_summary()
        
        # Create profit line graph
        should_generate_graph = (
            self.generate_graph is True or 
            (self.generate_graph is None and len(self.profit_tracking['daily_results']) > 1)
        )
        
        if should_generate_graph and self.generate_graph is not False:
            self.create_profit_line_graph()
    
    def print_overall_summary(self, all_results: List[Dict]):
        """Print overall summary across all dates."""
        print(f"\n{'='*80}")
        print(f"OVERALL SUMMARY ({len(all_results)} days)")
        print(f"{'='*80}")
        
        total_hitters = sum(len(r['hitters']) for r in all_results)
        total_strikers = sum(len(r['strikers']) for r in all_results)
        total_walkers = sum(len(r['walkers']) for r in all_results)
        
        successful_hitters = sum(sum(1 for entry in r['hitters'] if entry['performance']['achieved']) for r in all_results)
        successful_strikers = sum(sum(1 for entry in r['strikers'] if entry['performance']['achieved']) for r in all_results)
        successful_walkers = sum(sum(1 for entry in r['walkers'] if entry['performance']['achieved']) for r in all_results)
        
        print(f"Hitters Overall: {successful_hitters}/{total_hitters} ({successful_hitters/max(total_hitters, 1)*100:.1f}%)")
        print(f"Strikers Overall: {successful_strikers}/{total_strikers} ({successful_strikers/max(total_strikers, 1)*100:.1f}%)")
        print(f"Walkers Overall: {successful_walkers}/{total_walkers} ({successful_walkers/max(total_walkers, 1)*100:.1f}%)")
    
    def print_profit_summary(self):
        """Print profit summary across all analyzed dates."""
        if not self.profit_tracking['daily_results']:
            return
        
        print(f"\n{'='*80}")
        print(f"PROFIT SUMMARY ({len(self.profit_tracking['daily_results'])} days)")
        print(f"{'='*80}")
        
        # Overall profit by category
        print(f"\nOVERALL PROFIT BY MARKET:")
        print(f"{'-'*50}")
        total_profit = (self.profit_tracking['hitters'] + 
                       self.profit_tracking['strikers'] + 
                       self.profit_tracking['walkers'])
        
        print(f"Hitters Market:  {self.profit_tracking['hitters']:+.1f} units")
        print(f"Strikers Market: {self.profit_tracking['strikers']:+.1f} units")
        print(f"Walkers Market:  {self.profit_tracking['walkers']:+.1f} units")
        print(f"{'='*30}")
        print(f"TOTAL PROFIT:    {total_profit:+.1f} units")
        
        # Daily breakdown
        print(f"\nDAILY BREAKDOWN:")
        print(f"{'-'*50}")
        for daily in self.profit_tracking['daily_results']:
            daily_total = daily['hitters'] + daily['strikers'] + daily['walkers']
            result_indicator = "📈" if daily_total > 0 else "📉" if daily_total < 0 else "➖"
            print(f"{daily['date']}: {result_indicator} {daily_total:+.1f} units "
                  f"(H:{daily['hitters']:+.1f}, S:{daily['strikers']:+.1f}, W:{daily['walkers']:+.1f})")
        
        # Performance statistics
        profitable_days = sum(1 for d in self.profit_tracking['daily_results'] 
                             if (d['hitters'] + d['strikers'] + d['walkers']) > 0)
        perfect_days = sum(1 for d in self.profit_tracking['daily_results'] 
                          if d.get('perfect_day', False))
        total_days = len(self.profit_tracking['daily_results'])
        
        print(f"\nPROFIT STATISTICS:")
        print(f"{'-'*50}")
        print(f"Profitable Days: {profitable_days}/{total_days} ({profitable_days/max(total_days, 1)*100:.1f}%)")
        print(f"Perfect Days (100% hit rate all markets): {perfect_days}/{total_days} ({perfect_days/max(total_days, 1)*100:.1f}%)")
        print(f"Average Daily P&L: {total_profit/max(total_days, 1):+.2f} units")
        
        # Market-specific win rates
        hitter_wins = sum(1 for d in self.profit_tracking['daily_results'] if d['hitters'] > 0)
        striker_wins = sum(1 for d in self.profit_tracking['daily_results'] if d['strikers'] > 0)
        walker_wins = sum(1 for d in self.profit_tracking['daily_results'] if d['walkers'] > 0)
        
        print(f"\nMARKET WIN RATES:")
        print(f"{'-'*50}")
        print(f"Hitters:  {hitter_wins}/{total_days} ({hitter_wins/max(total_days, 1)*100:.1f}%)")
        print(f"Strikers: {striker_wins}/{total_days} ({striker_wins/max(total_days, 1)*100:.1f}%)")
        print(f"Walkers:  {walker_wins}/{total_days} ({walker_wins/max(total_days, 1)*100:.1f}%)")
    
    def create_profit_line_graph(self, save_path: str = "profit_trends.png"):
        """Create a line graph showing profit trends over time."""
        if not self.profit_tracking['daily_results']:
            print("No data available for creating graph")
            return
        
        # Prepare data
        dates = []
        hitters_cumulative = []
        strikers_cumulative = []
        walkers_cumulative = []
        total_cumulative = []
        daily_totals = []
        
        hitters_running = 0
        strikers_running = 0
        walkers_running = 0
        
        for daily in self.profit_tracking['daily_results']:
            # Parse date
            date_obj = datetime.strptime(daily['date'], '%Y-%m-%d').date()
            dates.append(date_obj)
            
            # Update running totals
            hitters_running += daily['hitters']
            strikers_running += daily['strikers']
            walkers_running += daily['walkers']
            
            hitters_cumulative.append(hitters_running)
            strikers_cumulative.append(strikers_running)
            walkers_cumulative.append(walkers_running)
            total_cumulative.append(hitters_running + strikers_running + walkers_running)
            daily_totals.append(daily['hitters'] + daily['strikers'] + daily['walkers'])
        
        # Create the plot
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        fig.suptitle('MLB Betting Strategy Performance', fontsize=16, fontweight='bold')
        
        # Plot 1: Cumulative Profit Lines
        ax1.plot(dates, total_cumulative, 'k-', linewidth=2.5, label='Total Profit', marker='o', markersize=4)
        ax1.plot(dates, hitters_cumulative, 'b-', linewidth=2, label='Hitters Market', marker='s', markersize=3)
        ax1.plot(dates, strikers_cumulative, 'r-', linewidth=2, label='Strikers Market', marker='^', markersize=3)
        ax1.plot(dates, walkers_cumulative, 'g-', linewidth=2, label='Walkers Market', marker='d', markersize=3)
        
        # Add horizontal line at y=0
        ax1.axhline(y=0, color='gray', linestyle='--', alpha=0.7)
        
        ax1.set_title('Cumulative Profit by Market', fontsize=14, pad=20)
        ax1.set_ylabel('Cumulative Profit (Units)', fontsize=12)
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)
        
        # Format x-axis for first subplot
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        ax1.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates)//10)))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
        
        # Plot 2: Daily Profit/Loss
        colors = ['green' if x > 0 else 'red' if x < 0 else 'gray' for x in daily_totals]
        bars = ax2.bar(dates, daily_totals, color=colors, alpha=0.7, edgecolor='black', linewidth=0.5)
        
        # Add horizontal line at y=0
        ax2.axhline(y=0, color='black', linestyle='-', alpha=0.8)
        
        ax2.set_title('Daily Profit/Loss', fontsize=14, pad=20)
        ax2.set_xlabel('Date', fontsize=12)
        ax2.set_ylabel('Daily P&L (Units)', fontsize=12)
        ax2.grid(True, alpha=0.3, axis='y')
        
        # Format x-axis for second subplot
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        ax2.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates)//10)))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
        
        # Add value labels on bars for daily P&L
        for bar, value in zip(bars, daily_totals):
            if abs(value) > 0.1:  # Only label non-zero values
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height + (0.1 if height > 0 else -0.2),
                        f'{value:+.1f}', ha='center', va='bottom' if height > 0 else 'top', 
                        fontsize=8, fontweight='bold')
        
        # Adjust layout
        plt.tight_layout()
        
        # Add summary statistics as text
        total_profit = total_cumulative[-1] if total_cumulative else 0
        profitable_days = sum(1 for x in daily_totals if x > 0)
        total_days = len(daily_totals)
        win_rate = profitable_days / max(total_days, 1) * 100
        
        summary_text = f'Summary: Total Profit: {total_profit:+.1f} units | Win Rate: {win_rate:.1f}% ({profitable_days}/{total_days})'
        fig.text(0.5, 0.02, summary_text, ha='center', fontsize=11, 
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray", alpha=0.8))
        
        # Save the plot
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"\nProfit line graph saved as: {save_path}")
        
        # Try to display the plot
        try:
            plt.show()
        except:
            print("Note: Could not display plot interactively. Graph saved to file.")
        
        plt.close()


def main():
    """Main function to run the analysis."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Check top performers against actual game results')
    parser.add_argument('--date', help='Specific date to analyze (YYYY-MM-DD format)')
    parser.add_argument('--days', type=int, default=7, help='Number of recent days to analyze (default: 7)')
    parser.add_argument('--graph', action='store_true', help='Generate profit line graph (default: auto for multi-day analysis)')
    parser.add_argument('--no-graph', action='store_true', help='Skip generating profit line graph')
    
    args = parser.parse_args()
    
    checker = PerformanceChecker()
    
    # Set graph generation preference
    if args.no_graph:
        checker.generate_graph = False
    elif args.graph:
        checker.generate_graph = True
    else:
        checker.generate_graph = None  # Auto-decide based on data
    
    checker.run_analysis(specific_date=args.date, days_back=args.days)


if __name__ == "__main__":
    main()
