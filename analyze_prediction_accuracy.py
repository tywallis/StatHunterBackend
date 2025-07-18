#!/usr/bin/env python3
"""
Script to analyze the accuracy of prediction percentages across different probability bins.
Converts per-plate-appearance percentages to game-level probabilities assuming 4 PA per game,
then checks if predicted odds actually match real-world outcomes for calibration analysis.
"""

import os
import re
import glob
from datetime import datetime, date
from typing import List, Dict, Tuple, Optional
import statsapi
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict

class PredictionAccuracyAnalyzer:
    def __init__(self):
        self.prediction_files = []
        self.results = []
        # Track predictions by bins (0-5%, 5-10%, etc.)
        self.accuracy_bins = {
            'hitters': defaultdict(lambda: {'predicted': [], 'actual': [], 'actual_2plus': []}),
            'strikers': defaultdict(lambda: {'predicted': [], 'actual': [], 'actual_2plus': []}),
            'walkers': defaultdict(lambda: {'predicted': [], 'actual': [], 'actual_2plus': []})
        }
        # Track high confidence (50%+) predictions for 2+ analysis
        self.high_confidence_stats = {
            'hitters': {'total': 0, 'achieved_1plus': 0, 'achieved_2plus': 0},
            'strikers': {'total': 0, 'achieved_1plus': 0, 'achieved_2plus': 0},
            'walkers': {'total': 0, 'achieved_1plus': 0, 'achieved_2plus': 0}
        }
        
    def convert_pa_to_game_probability(self, pa_percentage: float, num_pa: int = 4) -> float:
        """
        Convert per-plate-appearance percentage to whole-game probability.
        
        For a given probability p per PA and n plate appearances:
        P(at least 1 success) = 1 - P(no successes) = 1 - (1-p)^n
        
        Args:
            pa_percentage: Percentage chance per plate appearance (0-100)
            num_pa: Number of plate appearances (default 4)
            
        Returns:
            Whole game probability as percentage (0-100)
        """
        if pa_percentage <= 0:
            return 0.0
        if pa_percentage >= 100:
            return 100.0
            
        p = pa_percentage / 100.0  # Convert to probability
        game_prob = 1 - (1 - p) ** num_pa  # Probability of at least 1 success
        result = game_prob * 100.0  # Convert back to percentage
        
        # Debug: Print conversion for first few calls
        if hasattr(self, '_debug_count'):
            self._debug_count += 1
        else:
            self._debug_count = 1
            
        if self._debug_count <= 5:
            print(f"DEBUG Convert: {pa_percentage:.1f}% per PA, {num_pa} PA -> {result:.1f}% game prob")
            
        return result
    
    def convert_pa_to_game_probability_2plus(self, pa_percentage: float, num_pa: int = 4) -> float:
        """
        Convert per-plate-appearance percentage to whole-game probability of 2+ successes.
        
        For a given probability p per PA and n plate appearances:
        P(2+ successes) = 1 - P(0 successes) - P(1 success)
        P(0 successes) = (1-p)^n
        P(1 success) = n * p * (1-p)^(n-1)
        
        Args:
            pa_percentage: Percentage chance per plate appearance (0-100)
            num_pa: Number of plate appearances (default 4)
            
        Returns:
            Whole game probability of 2+ successes as percentage (0-100)
        """
        if pa_percentage <= 0:
            return 0.0
        if pa_percentage >= 100:
            return 100.0
            
        p = pa_percentage / 100.0  # Convert to probability
        prob_0 = (1 - p) ** num_pa
        prob_1 = num_pa * p * ((1 - p) ** (num_pa - 1))
        prob_2plus = 1 - prob_0 - prob_1
        return max(0.0, prob_2plus * 100.0)  # Ensure non-negative
    
    def find_prediction_files(self, directory: str = ".") -> List[str]:
        """Find all prediction files in the directory."""
        pattern = os.path.join(directory, "2025-*.txt")
        files = glob.glob(pattern)
        # Sort by date
        return sorted(files)
    
    def get_percentage_bin(self, percentage: float) -> str:
        """Get the bin label for a given percentage (game-level probability)."""
        if percentage < 5:
            return "0-5%"
        elif percentage < 10:
            return "5-10%"
        elif percentage < 15:
            return "10-15%"
        elif percentage < 20:
            return "15-20%"
        elif percentage < 25:
            return "20-25%"
        elif percentage < 30:
            return "25-30%"
        elif percentage < 35:
            return "30-35%"
        elif percentage < 40:
            return "35-40%"
        elif percentage < 45:
            return "40-45%"
        elif percentage < 50:
            return "45-50%"
        elif percentage < 55:
            return "50-55%"
        elif percentage < 60:
            return "55-60%"
        elif percentage < 65:
            return "60-65%"
        elif percentage < 70:
            return "65-70%"
        elif percentage < 75:
            return "70-75%"
        elif percentage < 80:
            return "75-80%"
        elif percentage < 85:
            return "80-85%"
        elif percentage < 90:
            return "85-90%"
        elif percentage < 95:
            return "90-95%"
        else:
            return "95-100%"
    
    def parse_prediction_file(self, file_path: str) -> Dict:
        """Parse a prediction file and extract ALL performers with percentages."""
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
        
        # Try to extract from both summary section AND individual game sections
        all_hitters = []
        all_strikers = []
        all_walkers = []
        
        # First, try the summary section
        if "*** TOP PERFORMERS SUMMARY FOR" in content:
            summary_section = content.split("*** TOP PERFORMERS SUMMARY FOR")[1]
            all_hitters.extend(self._extract_all_performers(summary_section, "TOP 10 MOST LIKELY TO GET A HIT:"))
            all_strikers.extend(self._extract_all_performers(summary_section, "TOP 10 MOST LIKELY TO STRIKEOUT:"))
            all_walkers.extend(self._extract_all_performers(summary_section, "TOP 10 MOST LIKELY TO WALK:"))
        
        # If summary didn't yield enough players, try extracting from individual game sections
        if len(all_hitters) < 20 or len(all_strikers) < 20 or len(all_walkers) < 20:
            # Look for individual game predictions
            game_sections = re.split(r'GAME \d+ of \d+:', content)[1:]  # Split by game headers
            
            for game_section in game_sections:
                if "MOST LIKELY TO GET A HIT:" in game_section:
                    all_hitters.extend(self._extract_players_from_game_section(game_section, "MOST LIKELY TO GET A HIT:"))
                if "MOST LIKELY TO STRIKEOUT:" in game_section:
                    all_strikers.extend(self._extract_players_from_game_section(game_section, "MOST LIKELY TO STRIKEOUT:"))
                if "MOST LIKELY TO WALK:" in game_section:
                    all_walkers.extend(self._extract_players_from_game_section(game_section, "MOST LIKELY TO WALK:"))
        
        # Remove duplicates based on player name and team
        all_hitters = self._remove_duplicate_players(all_hitters)
        all_strikers = self._remove_duplicate_players(all_strikers)
        all_walkers = self._remove_duplicate_players(all_walkers)
        
        return {
            'date': date_str,
            'games': games,
            'top_hitters': all_hitters,
            'top_strikers': all_strikers,
            'top_walkers': all_walkers
        }
    
    def _extract_all_performers(self, summary_section: str, section_header: str) -> List[Dict]:
        """Extract ALL performers from a specific section, not just top 10."""
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
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Look for numbered entries (extract all, not just 1-10)
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
                
                # Continue extracting all players (removed the rank >= 10 break)
            
            i += 1
        
        return performers
    
    def _extract_players_from_game_section(self, game_section: str, section_header: str) -> List[Dict]:
        """Extract players from individual game sections."""
        performers = []
        
        if section_header not in game_section:
            return performers
        
        section_start = game_section.find(section_header)
        # Find the end of this section (next section or end of game)
        section_end = len(game_section)
        for next_header in ["MOST LIKELY TO", "*** GAME", "Game Link:"]:
            next_pos = game_section.find(next_header, section_start + len(section_header))
            if next_pos != -1:
                section_end = min(section_end, next_pos)
        
        section_content = game_section[section_start:section_end]
        lines = section_content.split('\n')
        
        for line in lines:
            line = line.strip()
            # Look for player entries with percentages
            match = re.match(r'\s*(\d+)\.\s+([^(]+)\s+\(([^)]+)\)\s+-\s+([\d.]+)%', line)
            if match:
                rank = int(match.group(1))
                name = match.group(2).strip()
                team = match.group(3).strip()
                percentage = float(match.group(4))
                
                performers.append({
                    'name': name,
                    'team': team,
                    'percentage': percentage,
                    'game_info': '',
                    'rank': rank
                })
        
        return performers
    
    def _remove_duplicate_players(self, players: List[Dict]) -> List[Dict]:
        """Remove duplicate players based on name and team, keeping the first occurrence."""
        seen = set()
        unique_players = []
        
        for player in players:
            player_key = (player['name'].lower().strip(), player['team'].lower().strip())
            if player_key not in seen:
                seen.add(player_key)
                unique_players.append(player)
        
        return unique_players
    
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
                        achieved_1plus = False
                        achieved_2plus = False
                        
                        if stat_type == 'hit':
                            if hits >= 1:
                                achieved_1plus = True
                                result['achieved'] = True
                                result['details'] = f"Got {hits} hit(s)"
                            if hits >= 2:
                                achieved_2plus = True
                        elif stat_type == 'strikeout':
                            if strikeouts >= 1:
                                achieved_1plus = True
                                result['achieved'] = True
                                result['details'] = f"Had {strikeouts} strikeout(s)"
                            if strikeouts >= 2:
                                achieved_2plus = True
                        elif stat_type == 'walk':
                            if walks >= 1:
                                achieved_1plus = True
                                result['achieved'] = True
                                result['details'] = f"Had {walks} walk(s)"
                            if walks >= 2:
                                achieved_2plus = True
                        
                        if not achieved_1plus:
                            result['details'] = f"Stats: {hits}H, {strikeouts}K, {walks}BB"
                        
                        # Store both 1+ and 2+ achievements for analysis
                        result['achieved_2plus'] = achieved_2plus
                    else:
                        result['details'] = "No batting stats found"
                    
                    break
        
        if not result['found']:
            result['details'] = f"Player '{player_name}' not found in boxscore"
            result['achieved_2plus'] = False
        
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
    
    def process_single_date(self, file_path: str) -> Dict:
        """Process predictions for a single date and track accuracy by percentage bins."""
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
        
        # Process all categories of players
        categories = [
            ('hitters', parsed_data['top_hitters'], 'hit'),
            ('strikers', parsed_data['top_strikers'], 'strikeout'),
            ('walkers', parsed_data['top_walkers'], 'walk')
        ]
        
        for category_name, players, stat_type in categories:
            for player in players:
                found = False
                performance = None
                
                # Check across all games for this player
                for game_id, boxscore in game_boxscores.items():
                    performance = self.check_player_performance(
                        player['name'], player['team'], boxscore, stat_type
                    )
                    if performance['found']:
                        found = True
                        break
                
                if found and performance:
                    # Add to results
                    results[category_name].append({
                        'player': player,
                        'performance': performance,
                        'game_id': game_id
                    })
                    
                    # Track for accuracy analysis
                    pa_percentage = player['percentage']  # Per-PA percentage from prediction
                    
                    # Use fixed 4 PA assumption (since we don't know actual PA before the game)
                    assumed_pa = 4
                    
                    # Convert per-PA percentage to game probability using assumed PA
                    game_probability_1plus = self.convert_pa_to_game_probability(pa_percentage, assumed_pa)
                    game_probability_2plus = self.convert_pa_to_game_probability_2plus(pa_percentage, assumed_pa)
                    
                    bin_label = self.get_percentage_bin(game_probability_1plus)
                    achieved_1plus = performance['achieved']
                    achieved_2plus = performance.get('achieved_2plus', False)
                    
                    self.accuracy_bins[category_name][bin_label]['predicted'].append(game_probability_1plus)
                    self.accuracy_bins[category_name][bin_label]['actual'].append(1 if achieved_1plus else 0)
                    self.accuracy_bins[category_name][bin_label]['actual_2plus'].append(1 if achieved_2plus else 0)
                    
                    # Track high confidence (50%+) predictions for 2+ analysis (using game probability)
                    if game_probability_1plus >= 50.0:
                        self.high_confidence_stats[category_name]['total'] += 1
                        if achieved_1plus:
                            self.high_confidence_stats[category_name]['achieved_1plus'] += 1
                        if achieved_2plus:
                            self.high_confidence_stats[category_name]['achieved_2plus'] += 1
        
        return results
    
    def calculate_bin_accuracy(self) -> Dict:
        """Calculate accuracy statistics for each percentage bin."""
        bin_stats = {}
        
        for category in ['hitters', 'strikers', 'walkers']:
            bin_stats[category] = {}
            
            for bin_label in ["0-5%", "5-10%", "10-15%", "15-20%", "20-25%", "25-30%", 
                             "30-35%", "35-40%", "40-45%", "45-50%", "50-55%", "55-60%",
                             "60-65%", "65-70%", "70-75%", "75-80%", "80-85%", "85-90%", 
                             "90-95%", "95-100%"]:
                
                bin_data = self.accuracy_bins[category][bin_label]
                
                if len(bin_data['actual']) > 0:
                    actual_success_rate = sum(bin_data['actual']) / len(bin_data['actual']) * 100
                    actual_2plus_rate = sum(bin_data['actual_2plus']) / len(bin_data['actual_2plus']) * 100
                    avg_predicted_rate = sum(bin_data['predicted']) / len(bin_data['predicted'])
                    sample_size = len(bin_data['actual'])
                    
                    # Calculate difference between predicted and actual
                    difference = actual_success_rate - avg_predicted_rate
                    
                    bin_stats[category][bin_label] = {
                        'sample_size': sample_size,
                        'avg_predicted_rate': avg_predicted_rate,
                        'actual_success_rate': actual_success_rate,
                        'actual_2plus_rate': actual_2plus_rate,
                        'difference': difference,
                        'predictions': bin_data['predicted'],
                        'outcomes': bin_data['actual'],
                        'outcomes_2plus': bin_data['actual_2plus']
                    }
                else:
                    bin_stats[category][bin_label] = {
                        'sample_size': 0,
                        'avg_predicted_rate': 0,
                        'actual_success_rate': 0,
                        'actual_2plus_rate': 0,
                        'difference': 0,
                        'predictions': [],
                        'outcomes': [],
                        'outcomes_2plus': []
                    }
        
        return bin_stats
    
    def print_accuracy_analysis(self, bin_stats: Dict):
        """Print detailed accuracy analysis by bins."""
        print(f"\n{'='*100}")
        print(f"PREDICTION ACCURACY ANALYSIS (Converted to Game-Level Probabilities)")
        print(f"Note: Per-PA percentages converted assuming 4 plate appearances per game")
        print(f"{'='*100}")
        
        for category in ['hitters', 'strikers', 'walkers']:
            category_display = category.upper()
            print(f"\n{category_display} ACCURACY BY GAME-LEVEL PREDICTION CONFIDENCE:")
            print(f"{'-'*90}")
            print(f"{'Bin':<12} {'Sample':<8} {'Avg Pred':<10} {'1+ Rate':<10} {'2+ Rate':<10} {'Difference':<12} {'Calibration'}")
            print(f"{'-'*90}")
            
            total_predictions = 0
            total_correct = 0
            
            for bin_label in ["0-5%", "5-10%", "10-15%", "15-20%", "20-25%", "25-30%", 
                             "30-35%", "35-40%", "40-45%", "45-50%", "50-55%", "55-60%",
                             "60-65%", "65-70%", "70-75%", "75-80%", "80-85%", "85-90%", 
                             "90-95%", "95-100%"]:
                
                stats = bin_stats[category][bin_label]
                
                if stats['sample_size'] > 0:
                    calibration = "Well Calibrated" if abs(stats['difference']) <= 5 else \
                                 "Overconfident" if stats['difference'] < -5 else "Underconfident"
                    
                    print(f"{bin_label:<12} {stats['sample_size']:<8} "
                          f"{stats['avg_predicted_rate']:<10.1f} "
                          f"{stats['actual_success_rate']:<10.1f} "
                          f"{stats['actual_2plus_rate']:<10.1f} "
                          f"{stats['difference']:+<12.1f} {calibration}")
                    
                    total_predictions += stats['sample_size']
                    total_correct += sum(stats['outcomes'])
                else:
                    print(f"{bin_label:<12} {'0':<8} {'N/A':<10} {'N/A':<10} {'N/A':<10} {'N/A':<12} {'No Data'}")
            
            if total_predictions > 0:
                overall_accuracy = total_correct / total_predictions * 100
                print(f"{'-'*90}")
                print(f"OVERALL {category_display}: {total_correct}/{total_predictions} = {overall_accuracy:.1f}% accuracy")
    
    def create_calibration_plot(self, bin_stats: Dict, save_path: str = "calibration_plot.png"):
        """Create calibration plots showing predicted vs actual success rates."""
        fig, axes = plt.subplots(1, 3, figsize=(18, 6))
        fig.suptitle('Prediction Calibration Analysis (Game-Level Probabilities)', fontsize=16, fontweight='bold')
        
        categories = ['hitters', 'strikers', 'walkers']
        category_titles = ['Hitters (Getting a Hit)', 'Strikers (Getting a Strikeout)', 'Walkers (Getting a Walk)']
        
        bin_centers = [2.5, 7.5, 12.5, 17.5, 22.5, 27.5, 32.5, 37.5, 42.5, 47.5,
                      52.5, 57.5, 62.5, 67.5, 72.5, 77.5, 82.5, 87.5, 92.5, 97.5]  # Center of each 5% bin
        perfect_line = [2.5, 7.5, 12.5, 17.5, 22.5, 27.5, 32.5, 37.5, 42.5, 47.5,
                       52.5, 57.5, 62.5, 67.5, 72.5, 77.5, 82.5, 87.5, 92.5, 97.5]  # Perfect calibration line
        
        for idx, (category, title) in enumerate(zip(categories, category_titles)):
            ax = axes[idx]
            
            predicted_rates = []
            actual_rates = []
            sample_sizes = []
            
            for bin_label in ["0-5%", "5-10%", "10-15%", "15-20%", "20-25%", "25-30%", 
                             "30-35%", "35-40%", "40-45%", "45-50%", "50-55%", "55-60%",
                             "60-65%", "65-70%", "70-75%", "75-80%", "80-85%", "85-90%", 
                             "90-95%", "95-100%"]:
                
                stats = bin_stats[category][bin_label]
                if stats['sample_size'] > 0:
                    predicted_rates.append(stats['avg_predicted_rate'])
                    actual_rates.append(stats['actual_success_rate'])
                    sample_sizes.append(stats['sample_size'])
                else:
                    predicted_rates.append(None)
                    actual_rates.append(None)
                    sample_sizes.append(0)
            
            # Filter out None values for plotting
            valid_data = [(p, a, s, c) for p, a, s, c in zip(predicted_rates, actual_rates, sample_sizes, bin_centers) 
                         if p is not None and a is not None and s > 0]
            
            if valid_data:
                pred_vals, actual_vals, sizes, centers = zip(*valid_data)
                
                # Create scatter plot with size based on sample size
                scatter = ax.scatter(pred_vals, actual_vals, s=[s*10 for s in sizes], 
                                   alpha=0.7, c='blue', edgecolors='black')
                
                # Add perfect calibration line
                ax.plot(perfect_line, perfect_line, 'r--', alpha=0.8, linewidth=2, label='Perfect Calibration')
                
                # Add labels for each point
                for p, a, s in zip(pred_vals, actual_vals, sizes):
                    ax.annotate(f'n={s}', (p, a), xytext=(5, 5), textcoords='offset points', 
                              fontsize=8, alpha=0.8)
            
            ax.set_xlim(0, 100)
            ax.set_ylim(0, 100)
            ax.set_xlabel('Predicted Game Success Rate (%)')
            ax.set_ylabel('Actual Game Success Rate (%)')
            ax.set_title(title)
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # Add diagonal reference lines
            ax.plot([0, 100], [0, 100], 'k--', alpha=0.3, linewidth=1)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"\nCalibration plot saved as: {save_path}")
        
        try:
            plt.show()
        except:
            print("Note: Could not display plot interactively. Graph saved to file.")
        
        plt.close()
    
    def run_analysis(self, specific_date: str = None, days_back: int = 63):
        """Run the complete accuracy analysis."""
        print("MLB Prediction Accuracy Analysis")
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
        
        # Process all files
        for file_path in prediction_files:
            try:
                self.process_single_date(file_path)
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                continue
        
        # Calculate and display accuracy statistics
        bin_stats = self.calculate_bin_accuracy()
        self.print_accuracy_analysis(bin_stats)
        
        # Create calibration plot
        self.create_calibration_plot(bin_stats)
        
        # Print summary insights
        self.print_calibration_insights(bin_stats)
        
        # Print high confidence 2+ analysis
        self.print_high_confidence_2plus_analysis()
    
    def print_calibration_insights(self, bin_stats: Dict):
        """Print insights about model calibration."""
        print(f"\n{'='*100}")
        print(f"CALIBRATION INSIGHTS")
        print(f"{'='*100}")
        
        for category in ['hitters', 'strikers', 'walkers']:
            print(f"\n{category.upper()} MODEL INSIGHTS:")
            print(f"{'-'*50}")
            
            # Find most overconfident and underconfident bins
            max_overconfident = None
            max_underconfident = None
            best_calibrated = None
            
            for bin_label in ["0-5%", "5-10%", "10-15%", "15-20%", "20-25%", "25-30%", 
                             "30-35%", "35-40%", "40-45%", "45-50%", "50-55%", "55-60%",
                             "60-65%", "65-70%", "70-75%", "75-80%", "80-85%", "85-90%", 
                             "90-95%", "95-100%"]:
                
                stats = bin_stats[category][bin_label]
                if stats['sample_size'] >= 5:  # Only consider bins with meaningful sample size
                    
                    if max_overconfident is None or stats['difference'] < max_overconfident[1]:
                        max_overconfident = (bin_label, stats['difference'], stats['sample_size'])
                    
                    if max_underconfident is None or stats['difference'] > max_underconfident[1]:
                        max_underconfident = (bin_label, stats['difference'], stats['sample_size'])
                    
                    if best_calibrated is None or abs(stats['difference']) < abs(best_calibrated[1]):
                        best_calibrated = (bin_label, stats['difference'], stats['sample_size'])
            
            if max_overconfident and max_overconfident[1] < -2:
                print(f"• Most Overconfident: {max_overconfident[0]} bin (predicted {max_overconfident[1]:+.1f}% too high, n={max_overconfident[2]})")
            
            if max_underconfident and max_underconfident[1] > 2:
                print(f"• Most Underconfident: {max_underconfident[0]} bin (predicted {max_underconfident[1]:+.1f}% too low, n={max_underconfident[2]})")
            
            if best_calibrated:
                print(f"• Best Calibrated: {best_calibrated[0]} bin (off by {best_calibrated[1]:+.1f}%, n={best_calibrated[2]})")
            
            # Check high-confidence predictions (95-100% bin)
            high_conf_stats = bin_stats[category]["95-100%"]
            if high_conf_stats['sample_size'] > 0:
                print(f"• High Confidence (95-100%): {high_conf_stats['actual_success_rate']:.1f}% actual success rate "
                      f"(n={high_conf_stats['sample_size']})")
                if high_conf_stats['actual_success_rate'] < 90:
                    print(f"  ⚠️  WARNING: High confidence predictions are significantly overconfident!")
                elif high_conf_stats['actual_success_rate'] >= 95:
                    print(f"  ✅ High confidence predictions are well-calibrated")
            
            # Also check very high confidence (90-95% bin)
            very_high_conf_stats = bin_stats[category]["90-95%"]
            if very_high_conf_stats['sample_size'] > 0:
                print(f"• Very High Confidence (90-95%): {very_high_conf_stats['actual_success_rate']:.1f}% actual success rate "
                      f"(n={very_high_conf_stats['sample_size']})")
                if very_high_conf_stats['actual_success_rate'] < 87:
                    print(f"  ⚠️  WARNING: Very high confidence predictions are overconfident!")
                elif very_high_conf_stats['actual_success_rate'] >= 90:
                    print(f"  ✅ Very high confidence predictions are well-calibrated")
    
    def print_high_confidence_2plus_analysis(self):
        """Print analysis of how often high confidence (50%+) predictions achieve 2+ of their stat."""
        print(f"\n{'='*100}")
        print(f"HIGH CONFIDENCE (50%+) GAME-LEVEL PREDICTIONS: 2+ ACHIEVEMENT ANALYSIS")
        print(f"Note: Based on game-level probabilities assuming 4 plate appearances per game")
        print(f"{'='*100}")
        
        for category in ['hitters', 'strikers', 'walkers']:
            stats = self.high_confidence_stats[category]
            
            if stats['total'] > 0:
                rate_1plus = stats['achieved_1plus'] / stats['total'] * 100
                rate_2plus = stats['achieved_2plus'] / stats['total'] * 100
                
                # Of those who achieved 1+, what fraction achieved 2+?
                fraction_2plus_given_1plus = 0
                if stats['achieved_1plus'] > 0:
                    fraction_2plus_given_1plus = stats['achieved_2plus'] / stats['achieved_1plus'] * 100
                
                category_display = category.upper()
                stat_name = "hits" if category == 'hitters' else "strikeouts" if category == 'strikers' else "walks"
                
                print(f"\n{category_display} (50%+ confidence predictions):")
                print(f"{'-'*60}")
                print(f"Total high confidence predictions: {stats['total']}")
                print(f"Achieved 1+ {stat_name}: {stats['achieved_1plus']}/{stats['total']} ({rate_1plus:.1f}%)")
                print(f"Achieved 2+ {stat_name}: {stats['achieved_2plus']}/{stats['total']} ({rate_2plus:.1f}%)")
                print(f"")
                print(f"Of those who got 1+ {stat_name}, {stats['achieved_2plus']}/{stats['achieved_1plus']} got 2+ ({fraction_2plus_given_1plus:.1f}%)")
                
                # Provide insights
                if fraction_2plus_given_1plus > 40:
                    print(f"✅ High rate of 2+ achievements among successful predictions")
                elif fraction_2plus_given_1plus > 25:
                    print(f"📊 Moderate rate of 2+ achievements among successful predictions")
                else:
                    print(f"📉 Low rate of 2+ achievements among successful predictions")
            else:
                print(f"\n{category.upper()}: No high confidence predictions found")


def main():
    """Main function to run the accuracy analysis."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze prediction accuracy across confidence levels')
    parser.add_argument('--date', help='Specific date to analyze (YYYY-MM-DD format)')
    parser.add_argument('--days', type=int, default=61, help='Number of recent days to analyze (default: 61)')
    
    args = parser.parse_args()
    
    analyzer = PredictionAccuracyAnalyzer()
    analyzer.run_analysis(specific_date=args.date, days_back=args.days)


if __name__ == "__main__":
    main()
