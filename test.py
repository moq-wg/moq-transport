import re

text = open("draft-ietf-moq-transport.md").read()

if "Type (i) = 0x00..0x0F / 0x20..0x21 / 0x24..0x25" in text:
    print("Found Datagram Types")

print("Checking Stream Types:")
match = re.search(r"\| 0x05\s+\| FETCH_HEADER", text)
if match:
    print("FETCH_HEADER is 0x05")
