
from __future__ import print_function 
import boto3
import json
import decimal
import datetime

# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if abs(o) % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)

dynamodb = boto3.resource('dynamodb', region_name='eu-west-1', endpoint_url="https://dynamodb.eu-west-1.amazonaws.com")

table = dynamodb.Table('PlantersActions')

planterId = "e0221623-fb88-4fbd-b524-6f0092463c93"
timeStamp = decimal.Decimal(datetime.datetime.utcnow().timestamp())

response = table.put_item(
   Item={
        'planterId': planterId,
        'timeStamp':    timeStamp ,
        'type':'MOVE_CAMERA',
        'value':'RIGHT'
    }
)

print(json.dumps(response, indent=4, cls=DecimalEncoder))