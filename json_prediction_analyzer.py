#!/usr/bin/env python3
"""
Script to analyze prediction accuracy from JSON prediction files.
Bins predictions by 5% increments and compares to actual game results.
"""

import json
import os
import glob
import statsapi
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict
from datetime import datetime
import argparse

class JSONPredictionAnalyzer:
    def __init__(self):
        self.accuracy_bins = {
            'hit': defaultdict(lambda: {'predicted': [], 'actual': []}),
            'strikeout': defaultdict(lambda: {'predicted': [], 'actual': []}),
            'walk': defaultdict(lambda: {'predicted': [], 'actual': []})
        }
        
    def get_percentage_bin(self, percentage: float) -> str:
        """Get the bin label for a given percentage."""
        # Convert to 0-100 scale if needed
        if percentage <= 1.0:
            percentage *= 100
            
        # Create 2% bins
        bin_number = int(percentage // 2) * 2
        if bin_number >= 100:
            return "98-100%"
        elif bin_number < 2:
            return "0-2%"
        else:
            return f"{bin_number}-{bin_number + 2}%"
    
    def get_game_boxscore(self, game_id: str) -> dict:
        """Get boxscore data for a specific game."""
        try:
            print(f"  Fetching boxscore for game {game_id}...")
            boxscore = statsapi.boxscore_data(game_id)
            return boxscore
        except Exception as e:
            print(f"Error fetching boxscore for game {game_id}: {e}")
            return None
    
    def clean_player_name(self, name: str) -> str:
        """Clean player name for matching."""
        # Remove extra spaces, convert to lowercase
        cleaned = name.strip().lower()
        # Remove common suffixes
        cleaned = cleaned.replace(' jr.', '').replace(' sr.', '').replace(' jr', '').replace(' sr', '')
        cleaned = cleaned.replace(' ii', '').replace(' iii', '')
        return cleaned
    
    def names_match(self, name1: str, name2: str) -> bool:
        """Check if two player names match using various approaches."""
        clean1 = self.clean_player_name(name1)
        clean2 = self.clean_player_name(name2)
        
        if clean1 == clean2:
            return True
        
        # Try last name matching
        name1_parts = clean1.split()
        name2_parts = clean2.split()
        
        if len(name1_parts) >= 2 and len(name2_parts) >= 2:
            # Compare last names
            if name1_parts[-1] == name2_parts[-1]:
                # If last names match, check if first names start with same letter
                if name1_parts[0][0] == name2_parts[0][0]:
                    return True
        
        # Try partial matching (in case of nicknames)
        if clean1 in clean2 or clean2 in clean1:
            return True
        
        return False
    
    def check_player_performance(self, player_name: str, team: str, boxscore: dict) -> dict:
        """Check if a player achieved their projected stats in the game."""
        if not boxscore:
            return {'found': False, 'stats': {}}
        
        result = {
            'found': False,
            'stats': {'hits': 0, 'strikeouts': 0, 'walks': 0}
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
                
                # Try various name matching approaches
                if self.names_match(player_name, api_name):
                    result['found'] = True
                    
                    # Get batting stats if available
                    if 'stats' in player_data and 'batting' in player_data['stats']:
                        batting_stats = player_data['stats']['batting']
                        
                        result['stats'] = {
                            'hits': batting_stats.get('hits', 0),
                            'strikeouts': batting_stats.get('strikeOuts', 0),
                            'walks': batting_stats.get('baseOnBalls', 0)
                        }
                    
                    return result
        
        return result
    
    def process_json_file(self, file_path: str):
        """Process a single JSON prediction file."""
        print(f"Processing {os.path.basename(file_path)}...")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return
        
        # Get boxscores for all games
        game_boxscores = {}
        for game_data in data['games']:
            if game_data.get('error') is None:
                game_id = str(game_data['game_pk'])
                boxscore = self.get_game_boxscore(game_id)
                if boxscore:
                    game_boxscores[game_id] = boxscore
        
        # Process all batters from the summary
        for batter_data in data['summary']['all_batters']:
            if 'per_game_probabilities' not in batter_data:
                continue
                
            player_name = batter_data['name']
            team = batter_data['team']
            
            # Find the game this batter was in
            game_id = None
            for game_data in data['games']:
                if game_data['home_team'] == team or game_data['away_team'] == team:
                    game_id = str(game_data['game_pk'])
                    break
            
            if game_id not in game_boxscores:
                continue
            
            # Check player performance
            performance = self.check_player_performance(player_name, team, game_boxscores[game_id])
            
            if not performance['found']:
                continue
            
            # Process each prediction type
            per_game_probs = batter_data['per_game_probabilities']
            stats = performance['stats']
            
            # Hit predictions
            if 'hit' in per_game_probs and per_game_probs['hit'] > 0:
                hit_prob = per_game_probs['hit']
                bin_label = self.get_percentage_bin(hit_prob)
                achieved_hit = 1 if stats['hits'] >= 1 else 0
                
                self.accuracy_bins['hit'][bin_label]['predicted'].append(hit_prob * 100 if hit_prob <= 1 else hit_prob)
                self.accuracy_bins['hit'][bin_label]['actual'].append(achieved_hit)
            
            # Strikeout predictions
            if 'strikeout' in per_game_probs and per_game_probs['strikeout'] > 0:
                strikeout_prob = per_game_probs['strikeout']
                bin_label = self.get_percentage_bin(strikeout_prob)
                achieved_strikeout = 1 if stats['strikeouts'] >= 1 else 0
                
                self.accuracy_bins['strikeout'][bin_label]['predicted'].append(strikeout_prob * 100 if strikeout_prob <= 1 else strikeout_prob)
                self.accuracy_bins['strikeout'][bin_label]['actual'].append(achieved_strikeout)
            
            # Walk predictions
            if 'walk' in per_game_probs and per_game_probs['walk'] > 0:
                walk_prob = per_game_probs['walk']
                bin_label = self.get_percentage_bin(walk_prob)
                achieved_walk = 1 if stats['walks'] >= 1 else 0
                
                self.accuracy_bins['walk'][bin_label]['predicted'].append(walk_prob * 100 if walk_prob <= 1 else walk_prob)
                self.accuracy_bins['walk'][bin_label]['actual'].append(achieved_walk)
    
    def calculate_bin_statistics(self):
        """Calculate statistics for each bin."""
        bin_stats = {}
        
        for stat_type in ['hit', 'strikeout', 'walk']:
            bin_stats[stat_type] = {}
            
            # Create 2% bins from 0-100%
            bin_labels = []
            for i in range(0, 100, 2):
                if i == 98:
                    bin_labels.append("98-100%")
                else:
                    bin_labels.append(f"{i}-{i+2}%")
            
            for bin_label in bin_labels:
                bin_data = self.accuracy_bins[stat_type][bin_label]
                
                if len(bin_data['actual']) > 0:
                    actual_success_rate = sum(bin_data['actual']) / len(bin_data['actual']) * 100
                    avg_predicted_rate = sum(bin_data['predicted']) / len(bin_data['predicted'])
                    sample_size = len(bin_data['actual'])
                    
                    bin_stats[stat_type][bin_label] = {
                        'sample_size': sample_size,
                        'avg_predicted_rate': avg_predicted_rate,
                        'actual_success_rate': actual_success_rate,
                        'difference': actual_success_rate - avg_predicted_rate
                    }
                else:
                    bin_stats[stat_type][bin_label] = {
                        'sample_size': 0,
                        'avg_predicted_rate': 0,
                        'actual_success_rate': 0,
                        'difference': 0
                    }
        
        return bin_stats
    
    def combine_small_bins(self, bin_stats, min_sample_size=50):
        """Combine bins with less than min_sample_size members into neighboring bins."""
        combined_stats = {}
        
        for stat_type in ['hit', 'strikeout', 'walk']:
            combined_stats[stat_type] = {}
            
            # Create ordered list of bins with their centers
            bin_data = []
            for i in range(0, 100, 2):
                if i == 98:
                    bin_label = "98-100%"
                    bin_center = 99.0
                else:
                    bin_label = f"{i}-{i+2}%"
                    bin_center = i + 1.0
                
                stats = bin_stats[stat_type][bin_label]
                bin_data.append({
                    'label': bin_label,
                    'center': bin_center,
                    'start': i,
                    'end': i + 2 if i < 98 else 100,
                    'sample_size': stats['sample_size'],
                    'predicted_sum': stats['avg_predicted_rate'] * stats['sample_size'] if stats['sample_size'] > 0 else 0,
                    'actual_sum': stats['actual_success_rate'] * stats['sample_size'] / 100 if stats['sample_size'] > 0 else 0
                })
            
            # Combine small bins
            i = 0
            while i < len(bin_data):
                current_bin = bin_data[i]
                
                if current_bin['sample_size'] >= min_sample_size:
                    # Bin is large enough, keep as is
                    combined_stats[stat_type][current_bin['label']] = bin_stats[stat_type][current_bin['label']]
                    i += 1
                else:
                    # Bin is too small, combine with neighbors
                    combine_group = [current_bin]
                    total_samples = current_bin['sample_size']
                    
                    # Look ahead to include consecutive small bins
                    j = i + 1
                    while j < len(bin_data) and total_samples < min_sample_size:
                        next_bin = bin_data[j]
                        combine_group.append(next_bin)
                        total_samples += next_bin['sample_size']
                        j += 1
                    
                    # If we still don't have enough samples and there are more bins ahead,
                    # keep adding until we reach min_sample_size or run out of bins
                    while j < len(bin_data) and total_samples < min_sample_size:
                        next_bin = bin_data[j]
                        combine_group.append(next_bin)
                        total_samples += next_bin['sample_size']
                        j += 1
                    
                    # Create combined bin
                    if total_samples > 0:
                        combined_predicted_sum = sum(bin['predicted_sum'] for bin in combine_group)
                        combined_actual_sum = sum(bin['actual_sum'] for bin in combine_group)
                        
                        # Create label for combined bin
                        start_val = combine_group[0]['start']
                        end_val = combine_group[-1]['end']
                        if end_val == 100:
                            combined_label = f"{start_val}-100%"
                        else:
                            combined_label = f"{start_val}-{end_val}%"
                        
                        combined_stats[stat_type][combined_label] = {
                            'sample_size': total_samples,
                            'avg_predicted_rate': combined_predicted_sum / total_samples,
                            'actual_success_rate': combined_actual_sum / total_samples * 100,
                            'difference': (combined_actual_sum / total_samples * 100) - (combined_predicted_sum / total_samples)
                        }
                    
                    i = j
        
        return combined_stats
    
    def print_accuracy_analysis(self, bin_stats):
        """Print detailed accuracy analysis."""
        print(f"\n{'='*100}")
        print(f"PREDICTION ACCURACY ANALYSIS")
        print(f"{'='*100}")
        
        # Combine small bins first
        combined_stats = self.combine_small_bins(bin_stats, min_sample_size=50)
        
        for stat_type in ['hit', 'strikeout', 'walk']:
            print(f"\n{stat_type.upper()} ACCURACY BY PREDICTION CONFIDENCE (Combined bins with <50 samples):")
            print(f"{'-'*90}")
            print(f"{'Bin':<15} {'Sample':<8} {'Avg Pred':<10} {'Actual':<10} {'Difference':<12} {'Calibration'}")
            print(f"{'-'*90}")
            
            total_predictions = 0
            total_correct = 0
            
            # Sort bins by their starting value for proper ordering
            sorted_bins = []
            for bin_label in combined_stats[stat_type].keys():
                start_val = int(bin_label.split('-')[0])
                sorted_bins.append((start_val, bin_label))
            sorted_bins.sort()
            
            for start_val, bin_label in sorted_bins:
                stats = combined_stats[stat_type][bin_label]
                
                if stats['sample_size'] > 0:
                    calibration = "Well Calibrated" if abs(stats['difference']) <= 3 else \
                                 "Overconfident" if stats['difference'] < -3 else "Underconfident"
                    
                    print(f"{bin_label:<15} {stats['sample_size']:<8} "
                          f"{stats['avg_predicted_rate']:<10.1f} "
                          f"{stats['actual_success_rate']:<10.1f} "
                          f"{stats['difference']:+<12.1f} {calibration}")
                    
                    total_predictions += stats['sample_size']
                    total_correct += stats['sample_size'] * stats['actual_success_rate'] / 100
                else:
                    print(f"{bin_label:<15} {'0':<8} {'N/A':<10} {'N/A':<10} {'N/A':<12} {'No Data'}")
            
            if total_predictions > 0:
                overall_accuracy = total_correct / total_predictions * 100
                print(f"{'-'*90}")
                print(f"OVERALL {stat_type.upper()}: {total_correct:.0f}/{total_predictions} = {overall_accuracy:.1f}% accuracy")
    
    def create_calibration_plots(self, bin_stats, save_path: str = "json_calibration_plots.png"):
        """Create calibration plots showing predicted vs actual success rates."""
        # Combine small bins first
        combined_stats = self.combine_small_bins(bin_stats, min_sample_size=50)
        
        fig, axes = plt.subplots(1, 3, figsize=(18, 6))
        fig.suptitle('Prediction Calibration Analysis (JSON Data - Combined Bins)', fontsize=16, fontweight='bold')
        
        stat_types = ['hit', 'strikeout', 'walk']
        titles = ['Hits (Getting a Hit)', 'Strikeouts (Getting a Strikeout)', 'Walks (Getting a Walk)']
        
        for idx, (stat_type, title) in enumerate(zip(stat_types, titles)):
            ax = axes[idx]
            
            predicted_rates = []
            actual_rates = []
            sample_sizes = []
            bin_centers = []
            
            # Sort bins by their starting value for proper ordering
            sorted_bins = []
            for bin_label in combined_stats[stat_type].keys():
                start_val = int(bin_label.split('-')[0])
                end_val = int(bin_label.split('-')[1].rstrip('%'))
                bin_center = (start_val + end_val) / 2
                sorted_bins.append((start_val, bin_label, bin_center))
            sorted_bins.sort()
            
            for start_val, bin_label, bin_center in sorted_bins:
                stats = combined_stats[stat_type][bin_label]
                if stats['sample_size'] > 0:
                    predicted_rates.append(stats['avg_predicted_rate'])
                    actual_rates.append(stats['actual_success_rate'])
                    sample_sizes.append(stats['sample_size'])
                    bin_centers.append(bin_center)
            
            if predicted_rates:
                # Create scatter plot with size based on sample size
                scatter = ax.scatter(predicted_rates, actual_rates, s=[s*3 for s in sample_sizes], 
                                   alpha=0.7, c='blue', edgecolors='black')
                
                # Add perfect calibration line
                ax.plot([0, 100], [0, 100], 'r--', alpha=0.8, linewidth=2, label='Perfect Calibration')
                
                # Calculate and plot linear fit
                if len(predicted_rates) >= 2:
                    # Use sample sizes as weights for the linear fit
                    weights = np.array(sample_sizes)
                    
                    # Fit weighted linear regression
                    coeffs = np.polyfit(predicted_rates, actual_rates, 1, w=weights)
                    slope, intercept = coeffs
                    
                    # Generate fit line
                    x_fit = np.linspace(0, 100, 100)
                    y_fit = slope * x_fit + intercept
                    
                    # Plot fit line
                    ax.plot(x_fit, y_fit, 'g-', alpha=0.8, linewidth=2, 
                           label=f'Linear Fit (y = {slope:.2f}x + {intercept:.1f})')
                    
                    # Calculate R-squared
                    y_pred = slope * np.array(predicted_rates) + intercept
                    ss_res = np.sum(weights * (np.array(actual_rates) - y_pred) ** 2)
                    ss_tot = np.sum(weights * (np.array(actual_rates) - np.average(actual_rates, weights=weights)) ** 2)
                    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
                    
                    # Add R-squared to the plot
                    ax.text(0.05, 0.95, f'R² = {r_squared:.3f}', transform=ax.transAxes, 
                           bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
                           verticalalignment='top')
                
                # Add labels for each point
                for p, a, s, bin_label in zip(predicted_rates, actual_rates, sample_sizes, [label for _, label, _ in sorted_bins]):
                    if s > 0:
                        ax.annotate(f'{bin_label}\nn={s}', (p, a), xytext=(5, 5), textcoords='offset points', 
                                  fontsize=6, alpha=0.8)
            
            ax.set_xlim(0, 100)
            ax.set_ylim(0, 100)
            ax.set_xlabel('Predicted Success Rate (%)')
            ax.set_ylabel('Actual Success Rate (%)')
            ax.set_title(title)
            ax.grid(True, alpha=0.3)
            ax.legend()
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"\nCalibration plots saved as: {save_path}")
        
        try:
            plt.show()
        except:
            print("Note: Could not display plots interactively. Graphs saved to file.")
        
        plt.close()
    
    def run_analysis(self, directory: str = ".", pattern: str = "*.json"):
        """Run the complete analysis on JSON files."""
        print("JSON Prediction Accuracy Analysis")
        print("="*50)
        
        # Find all JSON files
        json_files = glob.glob(os.path.join(directory, pattern))
        json_files = [f for f in json_files if os.path.basename(f).startswith('202')]  # Only date files
        json_files.sort()
        
        if not json_files:
            print(f"No JSON files found matching pattern: {pattern}")
            return
        
        print(f"Found {len(json_files)} JSON files to process")
        
        # Process all files
        for file_path in json_files:
            try:
                self.process_json_file(file_path)
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                continue
        
        # Calculate and display statistics
        bin_stats = self.calculate_bin_statistics()
        self.print_accuracy_analysis(bin_stats)
        
        # Create calibration plots
        self.create_calibration_plots(bin_stats)
        
        print("\nAnalysis complete!")


def main():
    """Main function to run the JSON prediction accuracy analysis."""
    parser = argparse.ArgumentParser(description='Analyze JSON prediction accuracy')
    parser.add_argument('--directory', '-d', default='.', help='Directory to search for JSON files')
    parser.add_argument('--pattern', '-p', default='*.json', help='File pattern to match')
    
    args = parser.parse_args()
    
    analyzer = JSONPredictionAnalyzer()
    analyzer.run_analysis(args.directory, args.pattern)


if __name__ == "__main__":
    main()