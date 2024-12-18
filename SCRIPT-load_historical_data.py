import pandas as pd

from loaders.custom_data.app import load_daily_player_stats


for date in pd.date_range(start='2024-03-28', end='2024-10-30'):
    load_daily_player_stats(date)