import json
import requests
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--entry", type=str)
parser.add_argument("--exit", type=str)
parser.add_argument("--direction", type=str, choices=['N','S',''])
args = parser.parse_args()

# get pricing and write to file
pricing_url = "https://www.expresslanes.com/maps-api/infra-price-confirmed-all"
pricing_response = requests.get(pricing_url)
# store JSON response from url in data
pricing_json = pricing_response.json()
# store pretty JSON response in a file
with open( "data/pricing.json" , "w" ) as pricing_file:
  json.dump(pricing_json, pricing_file, indent=2)

# get entry/exit OD map and write to file
entry_exit_url = "https://www.expresslanes.com/themes/custom/transurbangroup/js/on-the-road/entry_exit.js"
entry_exit_response = requests.get(entry_exit_url)
open('data/entry_exit.js', 'wb').write(entry_exit_response.content)

# read pricing file
with open('data/pricing.json') as pricing_file:
  pricing_data=pricing_file.read()
pricing_json = json.loads(pricing_data)

# read OD map file
with open('data/entryExits.json') as odmap_file:
  odmap_data=odmap_file.read()
odmap_json = json.loads(odmap_data)

def get_direction():
  # get direction code from pricing data/json
  direction_code = pricing_json['direction_95']
  # print(direction_code)

  # get I-95/395 direction text from 'lane status' URL
  direction_txt_url = "https://www.expresslanes.com/maps-api/lane-status"
  get_direction_txt_response = requests.get(direction_txt_url)
  direction_txt_json = get_direction_txt_response.json()
  direction_txt = direction_txt_json['road95and395']
  # print(direction_txt)

  pricing_timestamp = pricing_json['response'][0]['time']
  direction_msg = f"\nAs of {pricing_timestamp}, the I-95/395 direction is {direction_code}: \'{direction_txt}\'\n"
  return direction_code, direction_msg

direction_code, direction_msg = get_direction()
print(direction_msg)

# Override direction if manually entered
if args.direction:
  direction_code = args.direction
# If lanes are changing then a direction must be entered
elif direction_code == "C":
  direction_code = input("\tLanes are changing! Enter a direction to continue [S/N]: ")
else:
  pass

if direction_code == "S":
  all_entries = odmap_json['Southbound']['entries']
  all_exits = odmap_json['Southbound']['exits']
elif direction_code == "N":
  all_entries = odmap_json['Northbound']['entries']
  all_exits = odmap_json['Northbound']['exits']
else:
  raise "Missing direction!"

if args.entry:
  entry_id = args.entry
  entry = all_entries.get(entry_id)
  if entry:
    entry_label = entry['label']
    print("Entry ID selected: ", entry_id, entry_label)
  else:
    raise Exception("Couldn't find that entry!")
else:
  for entry_id in all_entries:
    entry_label = all_entries[entry_id]['label']
    print(entry_id, entry_label)
  entry_id = input("\tEnter entry ID: ")
  #print(entry_id)

# Only get exits for the selected entry
if args.exit:
  exit_id = args.exit
  exit = all_exits.get(exit_id)
  if exit:
    exit_label = exit['label']
    print("Exit ID selected: ", exit_id, exit_label)
  else:
    raise Exception("Couldn't find that exit!")
else:
  entry = all_entries.get(entry_id)
  if entry:
    exits = entry['exits']
    for exit in exits:
      exit_id = exit['id']
      exit_label = all_exits[exit_id]['label']
      print(exit_id, exit_label)
    exit_id = input("\tEnter exit ID: ")
    #print(exit_id)
  else:
    raise Exception("Couldn't find that entry!")

# Get the ODs for the exit ID selected if it exists
od_exits = all_entries[entry_id]['exits']
ods = []
for exit in od_exits:
  id = exit['id']
  if id == exit_id:
    ods = exit['ods']

if ods:
  for od in ods:
    od_id = "od_" + od
    for ramp in pricing_json['response']:
      if od_id == ramp['od']:
        road = ramp['road']
        price = ramp['price']
        status = ramp['status']
        print(road, status, price)
else:
  raise Exception("Couldn't find that exit!")
