#!/usr/bin/python

import object_storage
import sys

if not len(sys.argv) == 5:
    usagestring = "usage: {} swiftuser swiftkey datacenter clustername"
    print usagestring.format(sys.argv[0])
    sys.exit(1)

swiftuser = sys.argv[1]
swiftkey = sys.argv[2]
dc = sys.argv[3]
clustername = sys.argv[4]

client = object_storage.get_client(swiftuser, swiftkey, datacenter=dc)

client[clustername].delete_all_objects()
client[clustername].delete(recursive=True)
