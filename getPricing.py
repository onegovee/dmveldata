# import urllib library
from urllib.request import urlopen
  
# import json
import json
# store the URL in url as 
# parameter for urlopen
url = "https://www.expresslanes.com/maps-api/infra-price-confirmed-all"
  
# store the response of URL
response = urlopen(url)
  
# storing the JSON response 
# from url in data
data = json.loads(response.read())
  
# print the json response
# print(data_json)

with open( "data/pricing.json" , "w" ) as write:
    json.dump( data , write )