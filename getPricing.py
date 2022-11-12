import json
from urllib.request import urlopen

url = "https://www.expresslanes.com/maps-api/infra-price-confirmed-all"
  
# store URL response
response = urlopen(url)
  
# store JSON response from url in data
data = json.loads(response.read())
  
# store pretty JSON response in a file
with open( "data/pricing.json" , "w" ) as write:
    json.dump( data , write, indent=2 )