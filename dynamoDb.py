
from __future__ import print_function
import boto3
from boto3.dynamodb.conditions import Key
import json
import decimal
from datetime import datetime, timedelta


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)


dynamodb = boto3.resource('dynamodb', region_name='eu-west-1',
                          endpoint_url="https://dynamodb.eu-west-1.amazonaws.com")
table = dynamodb.Table('PlantersMeasurements')

planterId = "e0221623-fb88-4fbd-b524-6f0092463c93"
utcNow = datetime.utcnow()
now = decimal.Decimal(utcNow.timestamp())
dayAgo = decimal.Decimal(
    (utcNow + timedelta(hours=-(utcNow.hour))).timestamp())

response = table.query(
    # ProjectionExpression="#yr, title, info.genres, info.actors[0]",
    # ExpressionAttributeNames={ "#yr": "year" }, # Expression Attribute Names for Projection Expression only.
    KeyConditionExpression=Key('planterId').eq(
        planterId) & Key('timeStamp').between(dayAgo, now)
)

plot = {'labels': [], "datasets": [{'data': []}]}
items = response["Items"]
h = datetime.fromtimestamp(items[0]["timeStamp"]).hour
last = datetime.fromtimestamp(items[len(items)-1]["timeStamp"])

sum = 0
count = 0
for i in items:

    date = datetime.fromtimestamp(i["timeStamp"])
    soilHumidity = i["soilHumidity"]
   
    if h != date.hour or last == i["timeStamp"]:
        if last == i["timeStamp"] or h==0:
            plot["labels"].append(str(h))
        else:
            plot["labels"].append("")

        plot["datasets"][0]["data"].append(sum/count)
        h = h+1
        sum = 0
        count = 0

    sum = sum+soilHumidity
    count = count+1
    print(f'{date:%Y-%m-%d %H-%M-%S.%z} {soilHumidity}')


print(json.dumps(plot, cls=DecimalEncoder))
# with open('./responses/measurements1.json', 'w') as outfile:
#     json.dump(response["Items"], outfile, cls=DecimalEncoder)
