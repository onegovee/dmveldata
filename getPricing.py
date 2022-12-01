import json
import requests
import datetime

pricing_url = "https://www.expresslanes.com/maps-api/infra-price-confirmed-all"
#>>>write file to s3 with date stamp

entry_exit_url = "https://www.expresslanes.com/themes/custom/transurbangroup/js/on-the-road/entry_exit.js?v=1.x"

# store URL response
pricing_response = requests.get(pricing_url)

entry_exit_response = requests.get(entry_exit_url)
  
# store JSON response from url in data
pricing_json = pricing_response.json()
  
# store pretty JSON response in a file
with open( "data/pricing.json" , "w" ) as pricing_file:
    json.dump(pricing_json, pricing_file, indent=2)

open('data/entry_exit.js', 'wb').write(entry_exit_response.content)

with open('data/idmap.json') as idmap_file:
    idmap_data=idmap_file.read()
idmap_json = json.loads(idmap_data)

# parse which direction I-95 is going
direction_95 = pricing_json['direction_95']
if direction_95 == "S": 
    direction = "SOUTH"
    select_entry_id = 191 #I-95/I-395/I-495 (Springfield Interchange)
    select_exit_id = "217SD" #I-95 Near Dumfries Road/Route 234
    entry_ramps = idmap_json['ramps'][1]['south'][0]['entry']
    exit_ramps = idmap_json['ramps'][1]['south'][1]['exit']
else: 
    direction = "NORTH"
    select_entry_id = 218 #I-95 Near Dumfries Road/Route 234
    # 191ND - I-95/I-395/I-495 (Springfield Interchange)
    # 181ND - 495 Express End (near MD)
    # 186ND - Route 7 (Leesburg Pike)
    # 182ND - Route 267
    # 224ND - Washington D.C.
    select_exit_id = "182ND"
    entry_ramps = idmap_json['ramps'][0]['north'][0]['entry']
    exit_ramps = idmap_json['ramps'][0]['north'][1]['exit']
timestamp = datetime.datetime.now()
print("As of", timestamp, "the I-95 express lanes are heading", direction)

pricing = pricing_json['response']
#print(pricing)
for entry in entry_ramps:
    if (entry.get('id') is select_entry_id):
        exitids = entry.get('data-exitids')
        #print(exitids)
        for exit in exitids:
            #print(exit.get('id'))
            if (exit.get('id') == select_exit_id):
                ods = exit.get('ods')
                #print(exit.get('ods'))
                for od in ods:
                    #print(od)
                    for price in pricing:
                        #print(price)
                        if (od in price.get('od')):
                            print(od, '$' + price.get('price'), price.get('status'))