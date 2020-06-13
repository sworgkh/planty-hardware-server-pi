import sys
sys.path =  ['', '/usr/lib/python37.zip', '/usr/lib/python3.7', '/usr/lib/python3.7/lib-dynload', '/home/pi/.local/lib/python3.7/site-packages', '/usr/local/lib/python3.7/dist-packages', '/usr/lib/python3/dist-packages']

import boto3
from boto3.dynamodb.conditions import Key
import json
import decimal
from datetime import datetime, timedelta
import dateutil.relativedelta as rdelta

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)


def dayNameFromWeekday(weekday):
    if weekday == 0:
        return "Mon"
    if weekday == 1:
        return "Tue"
    if weekday == 2:
        return "Wed"
    if weekday == 3:
        return "Thu"
    if weekday == 4:
        return "Fri"
    if weekday == 5:
        return "Sat"
    if weekday == 6:
        return "Sun"


def lambda_handler():
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

    plots = {
        "daily": {
            "soilHumidity": {'labels': [], "datasets": [{'data': []}]},
            "uvIntensity": {'labels': [], "datasets": [{'data': []}]},
            "ambientTemperatureCelsius": {'labels': [], "datasets": [{'data': []}]}
        },
        "weekly": {
            "soilHumidity": {'labels': [], "datasets": [{'data': []}]},
            "uvIntensity": {'labels': [], "datasets": [{'data': []}]},
            "ambientTemperatureCelsius": {'labels': [], "datasets": [{'data': []}]}
        }
    }

    items = response["Items"]

    print(len(items))
    h = datetime.fromtimestamp(items[0]["timeStamp"]).hour
    last = datetime.fromtimestamp(items[len(items) - 1]["timeStamp"])
    hoursCount = last.hour + 1

    print('last ', last)
    print('first ', datetime.fromtimestamp(items[0]["timeStamp"]))


    plots["daily"]["soilHumidity"]["datasets"][0]["data"] = [None] * hoursCount
    plots["daily"]["soilHumidity"]["labels"] = [""] * hoursCount
    plots["daily"]["soilHumidity"]["labels"][0] = "0"
    plots["daily"]["soilHumidity"]["labels"][h - 1] = f"{last.hour:0}"

    plots["daily"]["uvIntensity"]["datasets"][0]["data"] = [None] * hoursCount
    plots["daily"]["uvIntensity"]["labels"] = [""] * hoursCount
    plots["daily"]["uvIntensity"]["labels"][0] = "0"
    plots["daily"]["uvIntensity"]["labels"][h - 1] = f"{last.hour:0}"

    plots["daily"]["ambientTemperatureCelsius"]["datasets"][0]["data"] = [None] * hoursCount
    plots["daily"]["ambientTemperatureCelsius"]["labels"] = [""] * hoursCount
    plots["daily"]["ambientTemperatureCelsius"]["labels"][0] = "0"
    plots["daily"]["ambientTemperatureCelsius"]["labels"][h - 1] = f"{last.hour:0}"


    my_sum = [0, 0, 0]
    count = 0
    for i in items:
        date = datetime.fromtimestamp(i["timeStamp"])
        soilHumidity = i["soilHumidity"]
        uvIntensity = i["uvIntesity"]
        ambientTemperatureCelsius = i["ambientTemperatureCelsius"]

        if h != date.hour or date == last:
            if date == last:
                my_sum[0] = my_sum[0] + soilHumidity
                my_sum[1] = my_sum[1] + uvIntensity
                my_sum[2] = my_sum[2] + ambientTemperatureCelsius
                count = count + 1

            plots["daily"]["soilHumidity"]["datasets"][0]["data"][h] = (
                round(my_sum[0] / count, 2))
            plots["daily"]["uvIntensity"]["datasets"][0]["data"][h] = (
                round(my_sum[1] / count, 2))
            plots["daily"]["ambientTemperatureCelsius"]["datasets"][0]["data"][h] = (
                round(my_sum[2] / count, 2))

            h = date.hour
            my_sum = [0, 0, 0]
            count = 0

        my_sum[0] = my_sum[0] + soilHumidity
        my_sum[1] = my_sum[1] + uvIntensity
        my_sum[2] = my_sum[2] + ambientTemperatureCelsius
        count = count + 1


    now = decimal.Decimal(utcNow.timestamp())
    today = datetime.today()
    past_monday = today + rdelta.relativedelta(days=-1, weekday=rdelta.MO(-1))
    past_monday = decimal.Decimal(past_monday.replace(hour=00, minute=00).timestamp())

    response = table.query(
        # ProjectionExpression="#yr, title, info.genres, info.actors[0]",
        # ExpressionAttributeNames={ "#yr": "year" }, # Expression Attribute Names for Projection Expression only.
        KeyConditionExpression=Key('planterId').eq(
            planterId) & Key('timeStamp').between(past_monday, now)
    )

    days = {}
    items = response['Items']

    count = 0
    for i in items:
        date = datetime.fromtimestamp(i["timeStamp"])
        soilHumidity = i["soilHumidity"]
        uvIntensity = i["uvIntesity"]
        ambientTemperatureCelsius = i["ambientTemperatureCelsius"]


        #add day to dict
        if dayNameFromWeekday(date.weekday()) not in days:
            days[dayNameFromWeekday(date.weekday())] = dict(soilHumidity={
                "sum": []
            }, uvIntensity={
                "sum": []
            }, ambientTemperatureCelsius={
                "sum": []
            })

        days[dayNameFromWeekday(date.weekday())]['soilHumidity']['sum'].append(float(soilHumidity))
        days[dayNameFromWeekday(date.weekday())]['uvIntensity']['sum'].append(float(uvIntensity))

        if ambientTemperatureCelsius > 0 and ambientTemperatureCelsius < 50:
            days[dayNameFromWeekday(date.weekday())]['ambientTemperatureCelsius']['sum'].append(
                float(ambientTemperatureCelsius))


    for val in days:
        days[val]['soilHumidity']['max'] =  decimal.Decimal( str(float(max(
            days[val]['soilHumidity']['sum']))))
        days[val]['soilHumidity']['min'] =  decimal.Decimal( str(float(min(
            days[val]['soilHumidity']['sum']))))

        i = decimal.Decimal( str(float(sum(days[val]['soilHumidity']['sum']) / len(
            days[val]['soilHumidity']['sum']))))

        days[val]['soilHumidity']['avg'] = i

        days[val]['uvIntensity']['max'] =  decimal.Decimal( str(float(max(
            days[val]['uvIntensity']['sum']))))
        days[val]['uvIntensity']['min'] =  decimal.Decimal( str(float(min(
            days[val]['uvIntensity']['sum']))))
        days[val]['uvIntensity']['avg'] =  decimal.Decimal( str(float(sum(days[val]['uvIntensity']['sum']) / len(
            days[val]['uvIntensity']['sum']))))

        days[val]['ambientTemperatureCelsius']['max'] = decimal.Decimal(str(float("{:.2f}".format(max(
            days[val]['ambientTemperatureCelsius']['sum'])))))

        days[val]['ambientTemperatureCelsius']['min'] = decimal.Decimal( str(float("{:.2f}".format(min(days[val]['ambientTemperatureCelsius']['sum'])))))
        days[val]['ambientTemperatureCelsius']['avg'] =  float("{:.2f}".format(sum(days[val]['ambientTemperatureCelsius']['sum']))) / float("{:.2f}".format(len(
            days[val]['ambientTemperatureCelsius']['sum'])))

        days[val]['ambientTemperatureCelsius']['avg'] = decimal.Decimal (str( days[val]['ambientTemperatureCelsius']['avg']))
        days[val]['uvIntensity']['sum'] = []
        days[val]['soilHumidity']['sum'] = []
        days[val]['ambientTemperatureCelsius']['sum'] = []



    plots["weekly"] = days

    planters = dynamodb.Table('Test_Planters')

    response = planters.update_item(
        Key={
            'UUID': planterId
        },
        UpdateExpression="set plots = :p",
        ExpressionAttributeValues={
            ':p': plots,
        },
        ReturnValues="UPDATED_NEW"
    )
    return response


lambda_handler()