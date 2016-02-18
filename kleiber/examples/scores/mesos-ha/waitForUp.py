#!/usr/bin/python

import sys
import requests
import time

if not len(sys.argv) == 4:
    usagestring = "usage: {} <host> <publicslavecount> <privateslavecount>"
    print usagestring.format(sys.argv[0])
    sys.exit(1)

host = sys.argv[1]
slaves = int(sys.argv[2]) + int(sys.argv[3])
url = "http://{}:5050/master/slaves".format(host)

while True:
    req = requests.get(url, timeout=5)
    print req
    resp = req.json()
    if len(resp['slaves']) == slaves:
        break

    print "found {} slaves. waiting for {}".format(len(resp['slaves']), slaves)
    time.sleep(1)
