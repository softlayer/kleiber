#!/usr/bin/python
#*******************************************************************************
# Copyright (c) 2016 IBM Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#*******************************************************************************

import sys
import requests
import time

if not len(sys.argv) == 2:
    usagestring = "usage: {} <masterip>"
    print usagestring.format(sys.argv[0])
    sys.exit(1)

masterip = sys.argv[1]
url = "http://{}/mesos".format(masterip)

while True:
    try:
       r = requests.get(url, timeout=5)
       print r
       if (r.status_code == 401) or (r.status_code == 200):
          break
       print "{}, master not up yet".format(r.status_code)
    except:
       print "please wait, masters not up yet"
    time.sleep(1)
