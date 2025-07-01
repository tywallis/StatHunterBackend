import pandas as pd

from loaders.custom_data.app import load_daily_player_stats


for date in pd.date_range(start='2025-03-01', end='2025-04-10'):
    load_daily_player_stats(date)