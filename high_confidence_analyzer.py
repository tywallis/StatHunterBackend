#!/usr/bin/env python3
"""
Script to analyze the accuracy of high confidence (90%+) predictions from JSON prediction files.
Analyzes how often players with 90%+ probability predictions actually achieve their predicted stats.
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

class HighConfidencePredictionAnalyzer:
    def __init__(self):
        self.high_confidence_predictions = {
            'hit': [],      # Store all 90%+ hit predictions
            'strikeout': [] # Store all 90%+ strikeout predictions
        }
        self.daily_details = []
        self.results_summary = {
            'hit': {
                'total_predictions': 0,
                'achieved_1_plus': 0,
                'achieved_2_plus': 0,
                'achieved_3_plus': 0
            },
            'strikeout': {
                'total_predictions': 0,
                'achieved_1_plus': 0,
                'achieved_2_plus': 0,
                'achieved_3_plus': 0
            }
        }
        
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
        cleaned = name.strip().lower()
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
            if name1_parts[-1] == name2_parts[-1]:
                if name1_parts[0][0] == name2_parts[0][0]:
                    return True
        
        # Try partial matching
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
            
            for player_id, player_data in team_data['players'].items():
                if 'person' not in player_data:
                    continue
                
                api_name = player_data['person'].get('fullName', '')
                
                if self.names_match(player_name, api_name):
                    result['found'] = True
                    
                    if 'stats' in player_data and 'batting' in player_data['stats']:
                        batting_stats = player_data['stats']['batting']
                        
                        result['stats'] = {
                            'hits': batting_stats.get('hits', 0),
                            'strikeouts': batting_stats.get('strikeOuts', 0),
                            'walks': batting_stats.get('baseOnBalls', 0)
                        }
                    
                    return result
        
        return result
    
    def get_high_confidence_predictions(self, data: dict, threshold: float = 0.90) -> dict:
        """Extract players with 90%+ probability for hits and strikeouts."""
        high_confidence = {
            'hit': [],
            'strikeout': []
        }
        
        # Get all batters with their probabilities
        for batter_data in data['summary']['all_batters']:
            if 'per_game_probabilities' not in batter_data:
                continue
            
            probs = batter_data['per_game_probabilities']
            
            # Check hit probability
            hit_prob = probs.get('hit', 0)
            if hit_prob >= threshold:
                high_confidence['hit'].append({
                    'name': batter_data['name'],
                    'team': batter_data['team'],
                    'probability': hit_prob
                })
            
            # Check strikeout probability
            strikeout_prob = probs.get('strikeout', 0)
            if strikeout_prob >= threshold:
                high_confidence['strikeout'].append({
                    'name': batter_data['name'],
                    'team': batter_data['team'],
                    'probability': strikeout_prob
                })
        
        return high_confidence
    
    def process_json_file(self, file_path: str):
        """Process a single JSON prediction file."""
        print(f"Processing {os.path.basename(file_path)}...")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return
        
        date_str = os.path.basename(file_path).replace('.json', '')
        
        # Get boxscores for all games
        game_boxscores = {}
        for game_data in data['games']:
            if game_data.get('error') is None:
                game_id = str(game_data['game_pk'])
                boxscore = self.get_game_boxscore(game_id)
                if boxscore:
                    game_boxscores[game_id] = boxscore
        
        # Get high confidence predictions
        high_confidence = self.get_high_confidence_predictions(data)
        
        daily_detail = {
            'date': date_str,
            'predictions': {
                'hit': [],
                'strikeout': []
            }
        }
        
        # Process high confidence predictions for each stat type
        for stat_type in ['hit', 'strikeout']:
            predictions = high_confidence[stat_type]
            
            print(f"  Found {len(predictions)} high confidence {stat_type} predictions")
            
            for prediction in predictions:
                player_name = prediction['name']
                team = prediction['team']
                probability = prediction['probability']
                
                # Find the game this player was in
                game_id = None
                for game_data in data['games']:
                    if game_data['home_team'] == team or game_data['away_team'] == team:
                        game_id = str(game_data['game_pk'])
                        break
                
                prediction_result = {
                    'name': player_name,
                    'team': team,
                    'probability': probability,
                    'achieved_1_plus': False,
                    'achieved_2_plus': False,
                    'achieved_3_plus': False,
                    'actual_count': 0,
                    'found': False,
                    'reason': None
                }
                
                if game_id not in game_boxscores:
                    prediction_result['reason'] = 'No boxscore data'
                    daily_detail['predictions'][stat_type].append(prediction_result)
                    continue
                
                # Check player performance
                performance = self.check_player_performance(player_name, team, game_boxscores[game_id])
                
                if not performance['found']:
                    prediction_result['reason'] = 'Player not found'
                    daily_detail['predictions'][stat_type].append(prediction_result)
                    continue
                
                # Check if prediction was correct
                stats = performance['stats']
                stat_count = 0
                
                if stat_type == 'hit':
                    stat_count = stats['hits']
                elif stat_type == 'strikeout':
                    stat_count = stats['strikeouts']
                
                prediction_result['found'] = True
                prediction_result['actual_count'] = stat_count
                prediction_result['achieved_1_plus'] = stat_count >= 1
                prediction_result['achieved_2_plus'] = stat_count >= 2
                prediction_result['achieved_3_plus'] = stat_count >= 3
                prediction_result['actual_stats'] = stats
                
                # Update summary statistics
                self.results_summary[stat_type]['total_predictions'] += 1
                if stat_count >= 1:
                    self.results_summary[stat_type]['achieved_1_plus'] += 1
                if stat_count >= 2:
                    self.results_summary[stat_type]['achieved_2_plus'] += 1
                if stat_count >= 3:
                    self.results_summary[stat_type]['achieved_3_plus'] += 1
                
                daily_detail['predictions'][stat_type].append(prediction_result)
                
                status = "✓" if stat_count >= 1 else "✗"
                prob_display = f"{probability*100:.1f}%" if probability <= 1 else f"{probability:.1f}%"
                print(f"    {status} {player_name} ({team}) - {prob_display} -> {stat_count} {stat_type}s")
        
        self.daily_details.append(daily_detail)
    
    def print_summary_analysis(self):
        """Print summary of high confidence predictions analysis."""
        print(f"\n{'='*100}")
        print(f"HIGH CONFIDENCE (90%+) PREDICTIONS ANALYSIS")
        print(f"{'='*100}")
        
        for stat_type in ['hit', 'strikeout']:
            summary = self.results_summary[stat_type]
            total = summary['total_predictions']
            
            if total == 0:
                print(f"\n{stat_type.upper()}: No high confidence predictions found")
                continue
            
            achieved_1_plus = summary['achieved_1_plus']
            achieved_2_plus = summary['achieved_2_plus']
            achieved_3_plus = summary['achieved_3_plus']
            
            rate_1_plus = achieved_1_plus / total * 100
            rate_2_plus = achieved_2_plus / total * 100
            rate_3_plus = achieved_3_plus / total * 100
            
            print(f"\n{stat_type.upper()} - High Confidence Predictions (90%+):")
            print(f"  Total predictions analyzed: {total}")
            print(f"  Achieved 1+ {stat_type}s: {achieved_1_plus} ({rate_1_plus:.1f}%)")
            print(f"  Achieved 2+ {stat_type}s: {achieved_2_plus} ({rate_2_plus:.1f}%)")
            print(f"  Achieved 3+ {stat_type}s: {achieved_3_plus} ({rate_3_plus:.1f}%)")
        
        # Print combined analysis
        total_all_predictions = sum(summary['total_predictions'] for summary in self.results_summary.values())
        total_achieved_1_plus = sum(summary['achieved_1_plus'] for summary in self.results_summary.values())
        total_achieved_2_plus = sum(summary['achieved_2_plus'] for summary in self.results_summary.values())
        
        if total_all_predictions > 0:
            overall_rate_1_plus = total_achieved_1_plus / total_all_predictions * 100
            overall_rate_2_plus = total_achieved_2_plus / total_all_predictions * 100
            
            print(f"\nCOMBINED ANALYSIS:")
            print(f"  Total high confidence predictions: {total_all_predictions}")
            print(f"  Overall success rate (1+): {total_achieved_1_plus} ({overall_rate_1_plus:.1f}%)")
            print(f"  Overall success rate (2+): {total_achieved_2_plus} ({overall_rate_2_plus:.1f}%)")
    
    def create_visualization(self, save_path: str = "high_confidence_analysis.png"):
        """Create visualization of high confidence predictions success rates."""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        
        # Chart 1: Success rates by stat type (1+ vs 2+ vs 3+)
        stat_types = ['hit', 'strikeout']
        rates_1_plus = []
        rates_2_plus = []
        rates_3_plus = []
        
        for stat_type in stat_types:
            summary = self.results_summary[stat_type]
            total = summary['total_predictions']
            
            if total > 0:
                rates_1_plus.append(summary['achieved_1_plus'] / total * 100)
                rates_2_plus.append(summary['achieved_2_plus'] / total * 100)
                rates_3_plus.append(summary['achieved_3_plus'] / total * 100)
            else:
                rates_1_plus.append(0)
                rates_2_plus.append(0)
                rates_3_plus.append(0)
        
        x = np.arange(len(stat_types))
        width = 0.25
        
        bars1 = ax1.bar(x - width, rates_1_plus, width, label='1+ Achieved', color='lightblue')
        bars2 = ax1.bar(x, rates_2_plus, width, label='2+ Achieved', color='darkblue')
        bars3 = ax1.bar(x + width, rates_3_plus, width, label='3+ Achieved', color='navy')
        
        ax1.set_ylabel('Success Rate (%)')
        ax1.set_title('High Confidence (90%+) Predictions Success Rates')
        ax1.set_xticks(x)
        ax1.set_xticklabels([s.title() for s in stat_types])
        ax1.legend()
        ax1.set_ylim(0, 100)
        
        # Add percentage labels
        for bars in [bars1, bars2, bars3]:
            for bar in bars:
                height = bar.get_height()
                if height > 0:
                    ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                            f'{height:.1f}%', ha='center', va='bottom', fontsize=8)
        
        # Chart 2: Number of predictions by stat type
        total_predictions = [self.results_summary[stat]['total_predictions'] for stat in stat_types]
        colors = ['lightcoral', 'lightblue']
        
        bars4 = ax2.bar(stat_types, total_predictions, color=colors)
        ax2.set_ylabel('Number of Predictions')
        ax2.set_title('Total High Confidence Predictions by Stat Type')
        ax2.set_xticklabels([s.title() for s in stat_types])
        
        # Add count labels
        for bar, count in zip(bars4, total_predictions):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                    f'{count}', ha='center', va='bottom', fontsize=10, fontweight='bold')
        
        # Chart 3: Daily distribution of high confidence predictions
        daily_counts = {'hit': [], 'strikeout': []}
        dates = []
        
        for detail in self.daily_details:
            dates.append(detail['date'])
            for stat_type in stat_types:
                daily_counts[stat_type].append(len(detail['predictions'][stat_type]))
        
        if dates:
            # Show last 20 days for readability
            display_dates = dates[-20:] if len(dates) > 20 else dates
            hit_counts = daily_counts['hit'][-20:] if len(dates) > 20 else daily_counts['hit']
            strikeout_counts = daily_counts['strikeout'][-20:] if len(dates) > 20 else daily_counts['strikeout']
            
            x_pos = np.arange(len(display_dates))
            width = 0.35
            
            ax3.bar(x_pos - width/2, hit_counts, width, label='Hits', color='lightcoral', alpha=0.7)
            ax3.bar(x_pos + width/2, strikeout_counts, width, label='Strikeouts', color='lightblue', alpha=0.7)
            
            ax3.set_ylabel('Number of Predictions')
            ax3.set_title('Daily High Confidence Predictions (Last 20 Days)')
            ax3.set_xticks(x_pos)
            ax3.set_xticklabels([d[-5:] for d in display_dates], rotation=45, ha='right')
            ax3.legend()
        
        # Chart 4: Combined success rate comparison
        categories = ['1+ Achieved', '2+ Achieved', '3+ Achieved']
        
        total_predictions_all = sum(self.results_summary[stat]['total_predictions'] 
                                  for stat in stat_types)
        
        if total_predictions_all > 0:
            combined_rates = [
                sum(self.results_summary[stat]['achieved_1_plus'] for stat in stat_types) / total_predictions_all * 100,
                sum(self.results_summary[stat]['achieved_2_plus'] for stat in stat_types) / total_predictions_all * 100,
                sum(self.results_summary[stat]['achieved_3_plus'] for stat in stat_types) / total_predictions_all * 100
            ]
        else:
            combined_rates = [0, 0, 0]
        
        colors = ['gold', 'orange', 'darkorange']
        bars5 = ax4.bar(categories, combined_rates, color=colors)
        ax4.set_ylabel('Success Rate (%)')
        ax4.set_title('Combined High Confidence Success Rates')
        ax4.set_ylim(0, 100)
        
        # Add percentage labels
        for bar, rate in zip(bars5, combined_rates):
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height + 1,
                    f'{rate:.1f}%', ha='center', va='bottom', fontsize=10, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"\nVisualization saved as: {save_path}")
        
        try:
            plt.show()
        except:
            print("Note: Could not display plots interactively. Graphs saved to file.")
        
        plt.close()
    
    def print_detailed_results(self):
        """Print detailed day-by-day results."""
        print(f"\n{'='*120}")
        print(f"DETAILED DAY-BY-DAY RESULTS")
        print(f"{'='*120}")
        
        for detail in self.daily_details:
            print(f"\nDate: {detail['date']}")
            print(f"{'-'*60}")
            
            for stat_type in ['hit', 'strikeout']:
                predictions = detail['predictions'][stat_type]
                
                if not predictions:
                    print(f"\n{stat_type.upper()}: No high confidence predictions")
                    continue
                
                achieved_1_plus = sum(1 for p in predictions if p['achieved_1_plus'])
                achieved_2_plus = sum(1 for p in predictions if p['achieved_2_plus'])
                total = len(predictions)
                
                print(f"\n{stat_type.upper()}: {achieved_1_plus}/{total} achieved 1+, {achieved_2_plus}/{total} achieved 2+")
                
                for prediction in predictions:
                    status_1 = "✓" if prediction['achieved_1_plus'] else "✗"
                    status_2 = "✓" if prediction['achieved_2_plus'] else "✗"
                    prob_display = f"{prediction['probability']*100:.1f}%" if prediction['probability'] <= 1 else f"{prediction['probability']:.1f}%"
                    
                    if prediction['found']:
                        stats = prediction['actual_stats']
                        count = prediction['actual_count']
                        stats_str = f"(H:{stats['hits']} K:{stats['strikeouts']} BB:{stats['walks']}) - {count} {stat_type}s"
                    else:
                        stats_str = f"({prediction.get('reason', 'Unknown error')})"
                    
                    print(f"  {status_1}(1+) {status_2}(2+) {prediction['name']} ({prediction['team']}) - {prob_display} {stats_str}")
    
    def run_analysis(self, directory: str = ".", pattern: str = "*.json"):
        """Run the complete high confidence predictions analysis."""
        print("High Confidence (90%+) Predictions Analysis")
        print("="*60)
        
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
        
        # Display results
        self.print_summary_analysis()
        self.create_visualization()
        self.print_detailed_results()
        
        print("\nAnalysis complete!")


def main():
    """Main function to run the high confidence predictions analysis."""
    parser = argparse.ArgumentParser(description='Analyze high confidence (90%+) predictions from JSON files')
    parser.add_argument('--directory', '-d', default='.', help='Directory to search for JSON files')
    parser.add_argument('--pattern', '-p', default='*.json', help='File pattern to match')
    parser.add_argument('--threshold', '-t', type=float, default=0.90, help='Confidence threshold (default: 0.90)')
    
    args = parser.parse_args()
    
    analyzer = HighConfidencePredictionAnalyzer()
    analyzer.run_analysis(args.directory, args.pattern)


if __name__ == "__main__":
    main()
