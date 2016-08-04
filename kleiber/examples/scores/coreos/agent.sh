#!/bin/bash
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

# redirect stdout and error to our logfile
exec 1<&-
exec 2<&-
exec 1<>/home/core/startup.`date +"%m%d%y.%H%M"`
exec 2>&1


echo ">>> read input parameters"
source $1


echo ">>> getting private and public ip"
COREOS_PRIVATE_IPV4=$(ip -o -4 addr list eth0 | awk '{print $4}' | cut -d/ -f1)
COREOS_PUBLIC_IPV4=$(ip -o -4 addr list eth1 | awk '{print $4}' | cut -d/ -f1)
echo $COREOS_PRIVATE_IPV4"   "$COREOS_PUBLIC_IPV4


echo ">>> writing cloud-config.yml"
cat > /home/core/cloud-config.yml <<EOF
#cloud-config
coreos:
  etcd2:
    discovery: $DISCOVERY
    listen-client-urls: http://0.0.0.0:2379
  fleet:
    metadata: "$METADATA"
  units:
    - name: etcd2.service
      command: restart
    - name: fleet.service
      command: restart
EOF

echo ">>> run coreos-cloudinit"
rm -r /var/lib/etcd2/*
coreos-cloudinit --from-file=/home/core/cloud-config.yml
