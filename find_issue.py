import urllib.request
import json

url = "https://api.github.com/repos/moq-wg/moq-transport/issues/1405"
req = urllib.request.Request(url)
with urllib.request.urlopen(req) as response:
    print(json.loads(response.read().decode())['body'])
