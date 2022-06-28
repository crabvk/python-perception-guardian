import re

with open('guardian/app.py', 'r') as stream:
    contents = stream.read()

result = re.findall('\\.t\\(.+?\\)', contents, re.MULTILINE | re.DOTALL)

for code in result:
    print(code)
