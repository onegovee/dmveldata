import json
import requests
import datetime
import os
import sys

today = datetime.datetime.today()

pricing_timestamp = datetime.datetime.fromtimestamp(os.path.getmtime('data/pricing.json'))
pricing_age = today - pricing_timestamp
#print(pricing_age.total_seconds())
if pricing_age.total_seconds() > 300:
    pricing_url = "https://www.expresslanes.com/maps-api/infra-price-confirmed-all"
    pricing_response = requests.get(pricing_url)
    # store JSON response from url in data
    pricing_json = pricing_response.json()
    # store pretty JSON response in a file
    with open( "data/pricing.json" , "w" ) as pricing_file:
        json.dump(pricing_json, pricing_file, indent=2)

entry_exit_timestamp = datetime.datetime.fromtimestamp(os.path.getmtime('data/entry_exit.js'))
entry_exit_age = today - entry_exit_timestamp
#print(entry_exit_age.days)
if entry_exit_age.days > 0:
    entry_exit_url = "https://www.expresslanes.com/themes/custom/transurbangroup/js/on-the-road/entry_exit.js"
    entry_exit_response = requests.get(entry_exit_url)
    open('data/entry_exit.js', 'wb').write(entry_exit_response.content)

with open('data/pricing.json') as pricing_file:
    pricing_data=pricing_file.read()
pricing_json = json.loads(pricing_data)

with open('data/idmap.json') as idmap_file:
    idmap_data=idmap_file.read()
idmap_json = json.loads(idmap_data)

# parse which direction I-95 is going
direction_95 = pricing_json['direction_95']
#print(direction_95)
if direction_95 == "S":
    direction_txt = "SOUTH"
elif direction_95 == "C":
    direction_txt = "CHANGING"
else:
    direction_txt = "NORTH"

# select a specific direction for pricing
select_direction = sys.argv[1]
if select_direction == "S": 
    # 180SO - 495 Express Start (near MD)
    # 2232SO - Washington D.C.
    # 191SO - I-95/I-395/I-495 (Springfield Interchange)
    # 217SD - I-95 Near Dumfries Road/Route 234
    select_entry_id = "180SO"
    select_exit_id = "217SD"
    entry_ramps = idmap_json['ramps'][1]['Southbound'][0]['entries']
    exit_ramps = idmap_json['ramps'][1]['Southbound'][1]['exits']
else: 
    select_entry_id = "218NO"
    # 191ND - I-95/I-395/I-495 (Springfield Interchange)
    # 181ND - 495 Express End (near MD)
    # 186ND - Route 7 (Leesburg Pike)
    # 182ND - Route 267
    # 218NO - I-95 Near Dumfries Road/Route 234
    # 224ND - Washington D.C.
    select_exit_id = "186ND"
    entry_ramps = idmap_json['ramps'][0]['Northbound'][0]['entries']
    exit_ramps = idmap_json['ramps'][0]['Northbound'][1]['exits']
timestamp = datetime.datetime.now()
print("As of", pricing_timestamp, "I-95 express lanes direction is", direction_txt)

pricing_response = pricing_json['response']
# pricing_detail = pricing_json['debug_db_ramps_price']
#print(pricing_response)
for entry in entry_ramps:
    if (select_entry_id == entry.get('id')):
        entry_name = entry.get('name')
        print('ENTRY: ' + entry_name + '\n')
        exits = entry.get('exits')
        #print(exitids)
        for exit in exits:
            #print(exit.get('id'))
            if (exit.get('id') == select_exit_id):
                ods = exit.get('ods')
                #print(exit.get('ods'))
                for od in ods:
                    #print(od)
                    for price in pricing_response:
                        #print(price)
                        if (od in price.get('od')):
                            od_id = od
                            #print(od_id)
                            od_price = price.get('price')
                            if (od_price == 'null'):
                                od_price = "0"
                            #print(od_price)
                            od_status = price.get('status')
                            od_road = price.get('road')
                            print(od_road,od_price,od_status)
                            # for detail in pricing_detail:
                            #     #print(detail)
                            #     if (od == str(detail.get('ODPair'))):
                            #         od_name = detail.get('od_name')[:-1]
                            #         print(od_name, '--> $' + od_price, od_status)

# get the exit ramp name
for exit in exit_ramps:
    if (select_exit_id in exit.get('id')):
        exit_name = exit.get('name')
        print('\nEXIT: ' + exit_name)