from loaders.mlb_pages.app import load_dynamo


def lambda_handler(event, context):

    load_dynamo()
    
    return {
        "statusCode": 200,
        "body": "Success",
    }