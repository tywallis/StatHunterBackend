#!/usr/bin/env python3
"""
Script to analyze the accuracy of top 2 predictions from JSON prediction files.
Determines what percentage of time both top 2 picks are correct for each stat type.
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

class Top2PredictionAnalyzer:
    def __init__(self):
        self.daily_results = {
            'hit': [],
            'strikeout': []
        }
        self.daily_details = []
        self.triple_achievements = []  # Track instances of 3+ achievements
        
        # Track Top 1 pick performance
        self.top1_results = {
            'hit': [],      # Track if top 1 hit pick achieved 1+ hits
            'strikeout': [] # Track if top 1 strikeout pick achieved 1+ strikeouts
        }
        self.top1_both_correct = []  # Track days when BOTH top 1 picks achieved their stats
        
        # Track homerun analysis for top 2 hit picks
        self.homerun_results = {
            'top2_hit_picks_with_homeruns': [],  # Track days when 1 or both top 2 hit picks got homeruns
            'both_hit_picks_homeruns': [],       # Track days when BOTH top 2 hit picks got homeruns
            'individual_homerun_success': []     # Track individual homerun success for top 2 hit picks
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
            'stats': {'hits': 0, 'strikeouts': 0, 'walks': 0, 'homeruns': 0}
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
                            'walks': batting_stats.get('baseOnBalls', 0),
                            'homeruns': batting_stats.get('homeRuns', 0)
                        }
                    
                    return result
        
        return result
    
    def get_top_2_picks(self, data: dict) -> dict:
        """Extract top 2 picks for each stat type from the summary."""
        top_picks = {
            'hit': [],
            'strikeout': []
        }
        
        # Get all batters with their probabilities
        all_batters = []
        for batter_data in data['summary']['all_batters']:
            if 'per_game_probabilities' not in batter_data:
                continue
            
            probs = batter_data['per_game_probabilities']
            batter_info = {
                'name': batter_data['name'],
                'team': batter_data['team'],
                'hit_prob': probs.get('hit', 0),
                'strikeout_prob': probs.get('strikeout', 0)
            }
            all_batters.append(batter_info)
        
        # Sort by each stat and get top 2
        for stat in ['hit', 'strikeout']:
            stat_key = f'{stat}_prob'
            sorted_batters = sorted(all_batters, key=lambda x: x[stat_key], reverse=True)
            
            # Get top 2 with non-zero probabilities
            for batter in sorted_batters:
                if len(top_picks[stat]) < 2 and batter[stat_key] > 0:
                    top_picks[stat].append({
                        'name': batter['name'],
                        'team': batter['team'],
                        'probability': batter[stat_key]
                    })
        
        return top_picks
    
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
        
        # Get top 2 picks for each stat
        top_picks = self.get_top_2_picks(data)
        
        daily_detail = {
            'date': date_str,
            'results': {}
        }
        
        # Check performance for each stat type
        for stat_type in ['hit', 'strikeout']:
            picks = top_picks[stat_type]
            
            if len(picks) < 2:
                print(f"  Warning: Only {len(picks)} picks found for {stat_type} on {date_str}")
                continue
            
            correct_count = 0
            correct_2_plus_count = 0  # Track 2+ achievements
            pick_results = []
            
            for i, pick in enumerate(picks, 1):
                player_name = pick['name']
                team = pick['team']
                probability = pick['probability']
                
                # Find the game this player was in
                game_id = None
                for game_data in data['games']:
                    if game_data['home_team'] == team or game_data['away_team'] == team:
                        game_id = str(game_data['game_pk'])
                        break
                
                if game_id not in game_boxscores:
                    pick_results.append({
                        'pick': i,
                        'name': player_name,
                        'team': team,
                        'probability': probability,
                        'correct': False,
                        'correct_2_plus': False,
                        'reason': 'No boxscore data'
                    })
                    continue
                
                # Check player performance
                performance = self.check_player_performance(player_name, team, game_boxscores[game_id])
                
                if not performance['found']:
                    pick_results.append({
                        'pick': i,
                        'name': player_name,
                        'team': team,
                        'probability': probability,
                        'correct': False,
                        'correct_2_plus': False,
                        'reason': 'Player not found'
                    })
                    continue
                
                # Check if prediction was correct
                stats = performance['stats']
                achieved = False
                achieved_2_plus = False
                stat_count = 0
                
                if stat_type == 'hit':
                    stat_count = stats['hits']
                    achieved = stat_count >= 1
                    achieved_2_plus = stat_count >= 2
                elif stat_type == 'strikeout':
                    stat_count = stats['strikeouts']
                    achieved = stat_count >= 1
                    achieved_2_plus = stat_count >= 2
                
                # Track triple achievements (3+)
                if stat_count >= 3:
                    self.triple_achievements.append({
                        'player': player_name,
                        'stat': stat_type,
                        'count': stat_count,
                        'date': date_str,
                        'team': team
                    })
                
                if achieved:
                    correct_count += 1
                if achieved_2_plus:
                    correct_2_plus_count += 1
                
                pick_results.append({
                    'pick': i,
                    'name': player_name,
                    'team': team,
                    'probability': probability,
                    'correct': achieved,
                    'correct_2_plus': achieved_2_plus,
                    'actual_stats': stats,
                    'stat_count': stat_count
                })
            
            # Record results
            both_correct = correct_count == 2
            both_correct_2_plus = correct_2_plus_count == 2
            self.daily_results[stat_type].append(both_correct)
            
            # Track Top 1 pick performance
            if len(pick_results) >= 1:
                top1_achieved = pick_results[0]['correct']
                self.top1_results[stat_type].append(top1_achieved)
            
            daily_detail['results'][stat_type] = {
                'both_correct': both_correct,
                'both_correct_2_plus': both_correct_2_plus,
                'correct_count': correct_count,
                'correct_2_plus_count': correct_2_plus_count,
                'picks': pick_results
            }
            
            print(f"  {stat_type.upper()}: {correct_count}/2 correct (1+), {correct_2_plus_count}/2 correct (2+) ({'✓' if both_correct else '✗'})")
        
        # Track homerun performance for top 2 hit picks
        if 'hit' in daily_detail['results']:
            hit_picks = daily_detail['results']['hit']['picks']
            homerun_count = 0
            individual_homerun_results = []
            
            for pick in hit_picks:
                if 'actual_stats' in pick:
                    homeruns = pick['actual_stats'].get('homeruns', 0)
                    has_homerun = homeruns > 0
                    individual_homerun_results.append(has_homerun)
                    if has_homerun:
                        homerun_count += 1
                else:
                    individual_homerun_results.append(False)
            
            # Track if 1 or both top 2 hit picks got homeruns
            any_homerun = homerun_count > 0
            both_homeruns = homerun_count == 2
            
            self.homerun_results['top2_hit_picks_with_homeruns'].append(any_homerun)
            self.homerun_results['both_hit_picks_homeruns'].append(both_homeruns)
            self.homerun_results['individual_homerun_success'].extend(individual_homerun_results)
            
            daily_detail['results']['hit']['homerun_analysis'] = {
                'any_homerun': any_homerun,
                'both_homeruns': both_homeruns,
                'homerun_count': homerun_count,
                'individual_results': individual_homerun_results
            }
            
            homerun_symbol = "🏠" if any_homerun else ""
            print(f"  HIT HOMERUNS: {homerun_count}/2 got homeruns {'(BOTH!)' if both_homeruns else ''} {homerun_symbol}")
        
        self.daily_details.append(daily_detail)
        
        # Check if both top 1 picks achieved their stats for this day
        self.check_top1_both_correct()
    
    def check_top1_both_correct(self):
        """Check if both top 1 picks achieved their stats for the most recent day."""
        if not self.daily_details:
            return
            
        latest_detail = self.daily_details[-1]
        
        # Check if we have both hit and strikeout data
        has_hit = 'hit' in latest_detail['results']
        has_strikeout = 'strikeout' in latest_detail['results']
        
        if has_hit and has_strikeout:
            hit_picks = latest_detail['results']['hit']['picks']
            strikeout_picks = latest_detail['results']['strikeout']['picks']
            
            # Check if top 1 picks (pick 1) achieved their stats
            hit_top1_correct = len(hit_picks) > 0 and hit_picks[0]['correct']
            strikeout_top1_correct = len(strikeout_picks) > 0 and strikeout_picks[0]['correct']
            
            both_correct = hit_top1_correct and strikeout_top1_correct
            self.top1_both_correct.append(both_correct)
    
    def print_summary_analysis(self):
        """Print summary of top 2 picks analysis."""
        print(f"\n{'='*100}")
        print(f"TOP 2 PICKS ACCURACY ANALYSIS")
        print(f"{'='*100}")
        
        # Track days where all stats had both picks correct
        all_stats_both_correct_days = 0
        all_stats_both_correct_2_plus_days = 0
        days_with_all_stats = 0
        
        for detail in self.daily_details:
            # Check if this day has results for both stat types
            has_all_stats = all(stat_type in detail['results'] for stat_type in ['hit', 'strikeout'])
            
            if has_all_stats:
                days_with_all_stats += 1
                # Check if all stat types had both picks correct (1+)
                all_correct = all(detail['results'][stat_type]['both_correct'] 
                                for stat_type in ['hit', 'strikeout'])
                if all_correct:
                    all_stats_both_correct_days += 1
                
                # Check if all stat types had both picks correct (2+)
                all_correct_2_plus = all(detail['results'][stat_type]['both_correct_2_plus'] 
                                       for stat_type in ['hit', 'strikeout'])
                if all_correct_2_plus:
                    all_stats_both_correct_2_plus_days += 1
        
        for stat_type in ['hit', 'strikeout']:
            results = self.daily_results[stat_type]
            
            if not results:
                continue
            
            # Calculate statistics for 1+ achievements
            both_correct_count = sum(results)
            both_correct_percentage = both_correct_count / len(results) * 100
            
            # Calculate statistics for 2+ achievements
            both_correct_2_plus_count = 0
            for detail in self.daily_details:
                if stat_type in detail['results']:
                    if detail['results'][stat_type]['both_correct_2_plus']:
                        both_correct_2_plus_count += 1
            
            both_correct_2_plus_percentage = both_correct_2_plus_count / len(results) * 100
            
            print(f"\n{stat_type.upper()} - Top 2 Picks Analysis:")
            print(f"  Total days analyzed: {len(results)}")
            print(f"  Days with both picks correct (1+): {both_correct_count} ({both_correct_percentage:.1f}%)")
            print(f"  Days with both picks correct (2+): {both_correct_2_plus_count} ({both_correct_2_plus_percentage:.1f}%)")
            
            # Calculate individual pick success rates
            pick1_correct = 0
            pick2_correct = 0
            pick1_correct_2_plus = 0
            pick2_correct_2_plus = 0
            total_picks = 0
            
            for detail in self.daily_details:
                if stat_type in detail['results']:
                    picks = detail['results'][stat_type]['picks']
                    for pick in picks:
                        if pick['pick'] == 1:
                            pick1_correct += 1 if pick['correct'] else 0
                            pick1_correct_2_plus += 1 if pick['correct_2_plus'] else 0
                        elif pick['pick'] == 2:
                            pick2_correct += 1 if pick['correct'] else 0
                            pick2_correct_2_plus += 1 if pick['correct_2_plus'] else 0
                        total_picks += 1
            
            if total_picks > 0:
                pick1_rate = pick1_correct / (total_picks // 2) * 100 if total_picks >= 2 else 0
                pick2_rate = pick2_correct / (total_picks // 2) * 100 if total_picks >= 2 else 0
                pick1_rate_2_plus = pick1_correct_2_plus / (total_picks // 2) * 100 if total_picks >= 2 else 0
                pick2_rate_2_plus = pick2_correct_2_plus / (total_picks // 2) * 100 if total_picks >= 2 else 0
                
                print(f"  Top pick success rate (1+): {pick1_rate:.1f}% ({pick1_correct}/{total_picks // 2})")
                print(f"  Second pick success rate (1+): {pick2_rate:.1f}% ({pick2_correct}/{total_picks // 2})")
                print(f"  Top pick success rate (2+): {pick1_rate_2_plus:.1f}% ({pick1_correct_2_plus}/{total_picks // 2})")
                print(f"  Second pick success rate (2+): {pick2_rate_2_plus:.1f}% ({pick2_correct_2_plus}/{total_picks // 2})")
        
        # Print overall analysis
        print(f"\n{'='*100}")
        print(f"OVERALL ANALYSIS - HITS AND STRIKEOUTS COMBINED")
        print(f"{'='*100}")
        
        if days_with_all_stats > 0:
            all_stats_percentage = all_stats_both_correct_days / days_with_all_stats * 100
            all_stats_percentage_2_plus = all_stats_both_correct_2_plus_days / days_with_all_stats * 100
            print(f"Days with both stat types analyzed: {days_with_all_stats}")
            print(f"Days with ALL top 2 picks correct (1+): {all_stats_both_correct_days} ({all_stats_percentage:.1f}%)")
            print(f"Days with ALL top 2 picks correct (2+): {all_stats_both_correct_2_plus_days} ({all_stats_percentage_2_plus:.1f}%)")
        else:
            print("No days found with both stat types analyzed")
        
        # Print Top 1 picks analysis
        print(f"\n{'='*100}")
        print(f"TOP 1 PICK ANALYSIS")
        print(f"{'='*100}")
        
        for stat_type in ['hit', 'strikeout']:
            top1_results = self.top1_results[stat_type]
            
            if not top1_results:
                continue
            
            top1_correct_count = sum(top1_results)
            top1_percentage = top1_correct_count / len(top1_results) * 100
            
            print(f"\n{stat_type.upper()} - Top 1 Pick Analysis:")
            print(f"  Total days analyzed: {len(top1_results)}")
            print(f"  Top 1 pick achieved stat: {top1_correct_count} ({top1_percentage:.1f}%)")
        
        # Combined Top 1 analysis
        if self.top1_results['hit'] and self.top1_results['strikeout']:
            combined_top1_correct = sum(self.top1_results['hit']) + sum(self.top1_results['strikeout'])
            combined_top1_total = len(self.top1_results['hit']) + len(self.top1_results['strikeout'])
            combined_top1_percentage = combined_top1_correct / combined_top1_total * 100
            
            print(f"\nCOMBINED Top 1 Picks (Hit + Strikeout):")
            print(f"  Total top 1 picks analyzed: {combined_top1_total}")
            print(f"  Top 1 picks achieved stat: {combined_top1_correct} ({combined_top1_percentage:.1f}%)")
            
            # BOTH Top 1 picks correct on same day
            if self.top1_both_correct:
                both_top1_correct_count = sum(self.top1_both_correct)
                both_top1_percentage = both_top1_correct_count / len(self.top1_both_correct) * 100
                
                print(f"\nBOTH Top 1 Picks Correct Same Day:")
                print(f"  Days analyzed: {len(self.top1_both_correct)}")
                print(f"  Days with BOTH top 1 picks correct: {both_top1_correct_count} ({both_top1_percentage:.1f}%)")
        
        # Print triple achievements
        if self.triple_achievements:
            print(f"\n{'='*100}")
            print(f"TRIPLE+ ACHIEVEMENTS (3 or more of the stat)")
            print(f"{'='*100}")
            
            for achievement in self.triple_achievements:
                print(f"🔥 {achievement['player']} ({achievement['team']}) - {achievement['count']} {achievement['stat']}s on {achievement['date']}")
            
            print(f"\nTotal triple+ achievements: {len(self.triple_achievements)}")
        
        # Print homerun analysis for top 2 hit picks
        if self.homerun_results['top2_hit_picks_with_homeruns']:
            print(f"\n{'='*100}")
            print(f"HOMERUN ANALYSIS - TOP 2 HIT PICKS")
            print(f"{'='*100}")
            
            total_days = len(self.homerun_results['top2_hit_picks_with_homeruns'])
            days_with_any_homerun = sum(self.homerun_results['top2_hit_picks_with_homeruns'])
            days_with_both_homeruns = sum(self.homerun_results['both_hit_picks_homeruns'])
            
            any_homerun_percentage = days_with_any_homerun / total_days * 100
            both_homeruns_percentage = days_with_both_homeruns / total_days * 100
            
            print(f"Total days with top 2 hit pick data: {total_days}")
            print(f"Days with 1+ homerun from top 2 hit picks: {days_with_any_homerun} ({any_homerun_percentage:.1f}%)")
            print(f"Days with BOTH top 2 hit picks getting homeruns: {days_with_both_homeruns} ({both_homeruns_percentage:.1f}%)")
            
            # Individual homerun success rate
            if self.homerun_results['individual_homerun_success']:
                individual_homeruns = sum(self.homerun_results['individual_homerun_success'])
                total_individual_picks = len(self.homerun_results['individual_homerun_success'])
                individual_homerun_rate = individual_homeruns / total_individual_picks * 100
                
                print(f"Individual top 2 hit pick homerun rate: {individual_homeruns}/{total_individual_picks} ({individual_homerun_rate:.1f}%)")
            
            # Find and display homerun achievements
            homerun_achievements = []
            for detail in self.daily_details:
                if 'hit' in detail['results'] and 'homerun_analysis' in detail['results']['hit']:
                    if detail['results']['hit']['homerun_analysis']['any_homerun']:
                        hit_picks = detail['results']['hit']['picks']
                        for pick in hit_picks:
                            if 'actual_stats' in pick and pick['actual_stats'].get('homeruns', 0) > 0:
                                homerun_achievements.append({
                                    'player': pick['name'],
                                    'team': pick['team'],
                                    'homeruns': pick['actual_stats']['homeruns'],
                                    'date': detail['date'],
                                    'pick_number': pick['pick']
                                })
            
            if homerun_achievements:
                print(f"\nHomerun Achievements by Top 2 Hit Picks:")
                for achievement in homerun_achievements:
                    print(f"🏠 {achievement['player']} ({achievement['team']}) - {achievement['homeruns']} HR{'s' if achievement['homeruns'] > 1 else ''} on {achievement['date']} (Pick #{achievement['pick_number']})")
                print(f"\nTotal homerun instances: {len(homerun_achievements)}")
        
        # Calculate total individual pick success across all stats
        total_pick1_correct = 0
        total_pick2_correct = 0
        total_pick1_correct_2_plus = 0
        total_pick2_correct_2_plus = 0
        total_all_picks = 0
        
        for detail in self.daily_details:
            for stat_type in ['hit', 'strikeout']:
                if stat_type in detail['results']:
                    picks = detail['results'][stat_type]['picks']
                    for pick in picks:
                        if pick['pick'] == 1:
                            total_pick1_correct += 1 if pick['correct'] else 0
                            total_pick1_correct_2_plus += 1 if pick['correct_2_plus'] else 0
                        elif pick['pick'] == 2:
                            total_pick2_correct += 1 if pick['correct'] else 0
                            total_pick2_correct_2_plus += 1 if pick['correct_2_plus'] else 0
                        total_all_picks += 1
        
        if total_all_picks > 0:
            overall_pick1_rate = total_pick1_correct / (total_all_picks // 2) * 100 if total_all_picks >= 2 else 0
            overall_pick2_rate = total_pick2_correct / (total_all_picks // 2) * 100 if total_all_picks >= 2 else 0
            overall_pick1_rate_2_plus = total_pick1_correct_2_plus / (total_all_picks // 2) * 100 if total_all_picks >= 2 else 0
            overall_pick2_rate_2_plus = total_pick2_correct_2_plus / (total_all_picks // 2) * 100 if total_all_picks >= 2 else 0
            overall_success_rate = (total_pick1_correct + total_pick2_correct) / total_all_picks * 100
            overall_success_rate_2_plus = (total_pick1_correct_2_plus + total_pick2_correct_2_plus) / total_all_picks * 100
            
            print(f"\nOverall individual pick performance (all stats combined):")
            print(f"  Top picks success rate (1+): {overall_pick1_rate:.1f}% ({total_pick1_correct}/{total_all_picks // 2})")
            print(f"  Second picks success rate (1+): {overall_pick2_rate:.1f}% ({total_pick2_correct}/{total_all_picks // 2})")
            print(f"  Top picks success rate (2+): {overall_pick1_rate_2_plus:.1f}% ({total_pick1_correct_2_plus}/{total_all_picks // 2})")
            print(f"  Second picks success rate (2+): {overall_pick2_rate_2_plus:.1f}% ({total_pick2_correct_2_plus}/{total_all_picks // 2})")
            print(f"  Combined individual pick success rate (1+): {overall_success_rate:.1f}%")
            print(f"  Combined individual pick success rate (2+): {overall_success_rate_2_plus:.1f}%")

    def create_visualization(self, save_path: str = "top2_analysis.png"):
        """Create visualization of top 2 picks success rates."""
        fig, ((ax1, ax2), (ax3, ax4), (ax5, ax6)) = plt.subplots(3, 2, figsize=(16, 18))
        
        # Chart 1: Both picks correct percentage by stat type (1+ vs 2+)
        stat_types = ['hit', 'strikeout']
        both_correct_rates_1_plus = []
        both_correct_rates_2_plus = []
        
        for stat_type in stat_types:
            results = self.daily_results[stat_type]
            if results:
                rate_1_plus = sum(results) / len(results) * 100
                both_correct_rates_1_plus.append(rate_1_plus)
                
                # Calculate 2+ rate
                both_correct_2_plus_count = 0
                for detail in self.daily_details:
                    if stat_type in detail['results']:
                        if detail['results'][stat_type]['both_correct_2_plus']:
                            both_correct_2_plus_count += 1
                rate_2_plus = both_correct_2_plus_count / len(results) * 100
                both_correct_rates_2_plus.append(rate_2_plus)
            else:
                both_correct_rates_1_plus.append(0)
                both_correct_rates_2_plus.append(0)
        
        x = np.arange(len(stat_types))
        width = 0.35
        
        bars1 = ax1.bar(x - width/2, both_correct_rates_1_plus, width, label='1+ Correct', color='skyblue')
        bars2 = ax1.bar(x + width/2, both_correct_rates_2_plus, width, label='2+ Correct', color='darkblue')
        
        ax1.set_ylabel('Both Picks Correct (%)')
        ax1.set_title('Top 2 Picks - Both Correct Rate by Stat Type')
        ax1.set_xticks(x)
        ax1.set_xticklabels(stat_types)
        ax1.legend()
        ax1.set_ylim(0, 100)
        
        # Add percentage labels
        for bars in [bars1, bars2]:
            for bar in bars:
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height + 1,
                        f'{height:.1f}%', ha='center', va='bottom', fontsize=9)
        
        # Chart 2: Individual pick success rates (1+ only)
        pick1_rates = []
        pick2_rates = []
        
        for stat_type in stat_types:
            pick1_correct = 0
            pick2_correct = 0
            total_days = 0
            
            for detail in self.daily_details:
                if stat_type in detail['results']:
                    picks = detail['results'][stat_type]['picks']
                    total_days += 1
                    for pick in picks:
                        if pick['pick'] == 1 and pick['correct']:
                            pick1_correct += 1
                        elif pick['pick'] == 2 and pick['correct']:
                            pick2_correct += 1
            
            if total_days > 0:
                pick1_rates.append(pick1_correct / total_days * 100)
                pick2_rates.append(pick2_correct / total_days * 100)
            else:
                pick1_rates.append(0)
                pick2_rates.append(0)
        
        x = np.arange(len(stat_types))
        width = 0.35
        
        bars3 = ax2.bar(x - width/2, pick1_rates, width, label='Top Pick', color='darkblue')
        bars4 = ax2.bar(x + width/2, pick2_rates, width, label='Second Pick', color='navy')
        
        ax2.set_ylabel('Individual Pick Success Rate (%)')
        ax2.set_title('Individual Pick Success Rates (1+)')
        ax2.set_xticks(x)
        ax2.set_xticklabels(stat_types)
        ax2.legend()
        ax2.set_ylim(0, 100)
        
        # Add percentage labels
        for bars in [bars3, bars4]:
            for bar in bars:
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height + 1,
                        f'{height:.1f}%', ha='center', va='bottom', fontsize=9)
        
        # Chart 3: Top 1 Pick Success Rates (Individual + Both Combined)
        categories = ['Hit Top 1', 'Strikeout Top 1', 'BOTH Top 1\nSame Day']
        rates = []
        
        # Individual top 1 rates
        for stat_type in stat_types:
            top1_results = self.top1_results[stat_type]
            if top1_results:
                rate = sum(top1_results) / len(top1_results) * 100
                rates.append(rate)
            else:
                rates.append(0)
        
        # Both top 1 correct on same day rate
        if self.top1_both_correct:
            both_rate = sum(self.top1_both_correct) / len(self.top1_both_correct) * 100
            rates.append(both_rate)
        else:
            rates.append(0)
        
        colors = ['lightcoral', 'lightblue', 'gold']
        bars5 = ax3.bar(categories, rates, color=colors)
        ax3.set_ylabel('Success Rate (%)')
        ax3.set_title('Top 1 Pick Success Rates')
        ax3.set_ylim(0, 100)
        
        # Add percentage labels
        for bar, rate in zip(bars5, rates):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height + 1,
                    f'{rate:.1f}%', ha='center', va='bottom', fontsize=9)
        
        # Chart 4: Perfect days comparison
        categories = ['All Stats\n1+ Correct', 'All Stats\n2+ Correct']
        
        # Calculate rates
        all_stats_both_correct_days_1_plus = 0
        all_stats_both_correct_days_2_plus = 0
        days_with_all_stats = 0
        
        for detail in self.daily_details:
            has_all_stats = all(stat_type in detail['results'] for stat_type in ['hit', 'strikeout'])
            if has_all_stats:
                days_with_all_stats += 1
                all_correct_1_plus = all(detail['results'][stat_type]['both_correct'] 
                                       for stat_type in ['hit', 'strikeout'])
                if all_correct_1_plus:
                    all_stats_both_correct_days_1_plus += 1
                
                all_correct_2_plus = all(detail['results'][stat_type]['both_correct_2_plus'] 
                                       for stat_type in ['hit', 'strikeout'])
                if all_correct_2_plus:
                    all_stats_both_correct_days_2_plus += 1
        
        rates = []
        if days_with_all_stats > 0:
            rates = [
                all_stats_both_correct_days_1_plus / days_with_all_stats * 100,
                all_stats_both_correct_days_2_plus / days_with_all_stats * 100
            ]
        else:
            rates = [0, 0]
        
        colors = ['gold', 'darkorange']
        bars6 = ax4.bar(categories, rates, color=colors)
        ax4.set_ylabel('Perfect Day Rate (%)')
        ax4.set_title('Perfect Days Comparison')
        ax4.set_ylim(0, max(rates) * 1.2 if rates else 10)
        
        # Add percentage labels
        for bar, rate in zip(bars6, rates):
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height + 1,
                    f'{rate:.1f}%', ha='center', va='bottom', fontsize=10)
        
        # Chart 5: Homerun Analysis for Top 2 Hit Picks
        if self.homerun_results['top2_hit_picks_with_homeruns']:
            total_days = len(self.homerun_results['top2_hit_picks_with_homeruns'])
            days_with_any_homerun = sum(self.homerun_results['top2_hit_picks_with_homeruns'])
            days_with_both_homeruns = sum(self.homerun_results['both_hit_picks_homeruns'])
            
            any_homerun_percentage = days_with_any_homerun / total_days * 100
            both_homeruns_percentage = days_with_both_homeruns / total_days * 100
            
            categories = ['1+ Homerun\nDays', 'Both Hit\nHomeruns']
            percentages = [any_homerun_percentage, both_homeruns_percentage]
            colors = ['orange', 'red']
            
            bars7 = ax5.bar(categories, percentages, color=colors)
            ax5.set_ylabel('Percentage of Days (%)')
            ax5.set_title('Homerun Success - Top 2 Hit Picks')
            ax5.set_ylim(0, max(percentages) * 1.2 if percentages else 10)
            
            # Add percentage labels
            for bar, percentage in zip(bars7, percentages):
                height = bar.get_height()
                ax5.text(bar.get_x() + bar.get_width()/2., height + 1,
                        f'{percentage:.1f}%', ha='center', va='bottom', fontsize=10)
            
            # Add count labels below
            counts = [days_with_any_homerun, days_with_both_homeruns]
            for bar, count in zip(bars7, counts):
                ax5.text(bar.get_x() + bar.get_width()/2., -max(percentages) * 0.1,
                        f'({count}/{total_days})', ha='center', va='top', fontsize=9)
        else:
            ax5.text(0.5, 0.5, 'No homerun data available', ha='center', va='center', 
                    transform=ax5.transAxes, fontsize=12)
            ax5.set_title('Homerun Success - Top 2 Hit Picks')
        
        # Chart 6: Individual Homerun Rate vs Hit Success Rate
        if self.homerun_results['individual_homerun_success']:
            # Calculate individual homerun rate
            individual_homeruns = sum(self.homerun_results['individual_homerun_success'])
            total_individual_picks = len(self.homerun_results['individual_homerun_success'])
            individual_homerun_rate = individual_homeruns / total_individual_picks * 100
            
            # Calculate overall hit success rate for top 2 picks
            hit_successes = 0
            total_hit_picks = 0
            for detail in self.daily_details:
                if 'hit' in detail['results']:
                    picks = detail['results']['hit']['picks']
                    for pick in picks:
                        total_hit_picks += 1
                        if pick['correct']:
                            hit_successes += 1
            
            overall_hit_rate = hit_successes / total_hit_picks * 100 if total_hit_picks > 0 else 0
            
            categories = ['Hit Success\nRate (1+)', 'Homerun\nRate']
            rates = [overall_hit_rate, individual_homerun_rate]
            colors = ['lightblue', 'gold']
            
            bars8 = ax6.bar(categories, rates, color=colors)
            ax6.set_ylabel('Success Rate (%)')
            ax6.set_title('Hit Success vs Homerun Rate (Top 2 Picks)')
            ax6.set_ylim(0, max(rates) * 1.2 if rates else 10)
            
            # Add percentage labels
            for bar, rate in zip(bars8, rates):
                height = bar.get_height()
                ax6.text(bar.get_x() + bar.get_width()/2., height + 1,
                        f'{rate:.1f}%', ha='center', va='bottom', fontsize=10)
            
            # Add count labels below
            counts = [f'{hit_successes}/{total_hit_picks}', f'{individual_homeruns}/{total_individual_picks}']
            for bar, count in zip(bars8, counts):
                ax6.text(bar.get_x() + bar.get_width()/2., -max(rates) * 0.1,
                        count, ha='center', va='top', fontsize=9)
        else:
            ax6.text(0.5, 0.5, 'No homerun data available', ha='center', va='center', 
                    transform=ax6.transAxes, fontsize=12)
            ax6.set_title('Hit Success vs Homerun Rate (Top 2 Picks)')
        
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
                if stat_type not in detail['results']:
                    continue
                
                result = detail['results'][stat_type]
                status_1_plus = "✓ BOTH CORRECT (1+)" if result['both_correct'] else f"✗ {result['correct_count']}/2 correct (1+)"
                status_2_plus = "✓ BOTH CORRECT (2+)" if result['both_correct_2_plus'] else f"✗ {result['correct_2_plus_count']}/2 correct (2+)"
                
                print(f"\n{stat_type.upper()}: {status_1_plus} | {status_2_plus}")
                
                for pick in result['picks']:
                    status_symbol_1_plus = "✓" if pick['correct'] else "✗"
                    status_symbol_2_plus = "✓" if pick['correct_2_plus'] else "✗"
                    prob_display = f"{pick['probability']*100:.1f}%" if pick['probability'] <= 1 else f"{pick['probability']:.1f}%"
                    
                    if 'actual_stats' in pick:
                        stats = pick['actual_stats']
                        stat_count = pick['stat_count']
                        homerun_info = f" HR:{stats.get('homeruns', 0)}" if stat_type == 'hit' else ""
                        homerun_emoji = " 🏠" if stat_type == 'hit' and stats.get('homeruns', 0) > 0 else ""
                        stats_str = f"(H:{stats['hits']} K:{stats['strikeouts']} BB:{stats['walks']}{homerun_info}) - {stat_count} {stat_type}s{homerun_emoji}"
                    else:
                        stats_str = f"({pick.get('reason', 'Unknown error')})"
                    
                    print(f"  Pick {pick['pick']}: {status_symbol_1_plus}(1+) {status_symbol_2_plus}(2+) {pick['name']} ({pick['team']}) - {prob_display} {stats_str}")
                
                # Add homerun summary for hit picks
                if stat_type == 'hit' and 'homerun_analysis' in result:
                    hr_analysis = result['homerun_analysis']
                    if hr_analysis['any_homerun']:
                        homerun_summary = f"🏠 HOMERUN DAY: {hr_analysis['homerun_count']}/2 hit picks got homeruns"
                        if hr_analysis['both_homeruns']:
                            homerun_summary += " (BOTH!)"
                        print(f"  {homerun_summary}")
    
    def run_analysis(self, directory: str = ".", pattern: str = "*.json"):
        """Run the complete top 2 picks analysis."""
        print("Top 2 Picks Accuracy Analysis")
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
        
        # Display results
        self.print_summary_analysis()
        self.create_visualization()
        self.print_detailed_results()
        
        print("\nAnalysis complete!")


def main():
    """Main function to run the top 2 picks analysis."""
    parser = argparse.ArgumentParser(description='Analyze top 2 picks accuracy from JSON predictions')
    parser.add_argument('--directory', '-d', default='.', help='Directory to search for JSON files')
    parser.add_argument('--pattern', '-p', default='*.json', help='File pattern to match')
    
    args = parser.parse_args()
    
    analyzer = Top2PredictionAnalyzer()
    analyzer.run_analysis(args.directory, args.pattern)


if __name__ == "__main__":
    main()