import urllib.request

jsonUrl = 'https://www.expresslanes.com/maps-api/infra-price-confirmed-all'

jsonData, headers = urllib.request.urlretrieve(jsonUrl, filename="data/pricing.json")
urllib.request.urlcleanup()