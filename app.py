from datetime import date, timedelta
from loaders.custom_data.app import load_daily_player_stats
from loaders.mlb_pages.app import load_mlb_page_data


def lambda_handler(event, context):

    yesterday = date.today() - timedelta(days=1)
    load_daily_player_stats(yesterday)

    load_mlb_page_data()
    
    return {
        "statusCode": 200,
        "body": "Success",
    }