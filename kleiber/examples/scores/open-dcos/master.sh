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
if [ $(which yum) ]; then
   exec 1<>/root/startup.`date +"%m%d%y.%H%M"`
else
   exec 1<>/home/core/startup.`date +"%m%d%y.%H%M"`
fi
exec 2>&1


echo ">>> if centos basic os prep"
if [ $(which yum) ]; then
   yum upgrade -y
   systemctl stop firewalld
   systemctl disable firewalld

   tee /etc/modules-load.d/overlay.conf <<-'EOF'
overlay
EOF

   tee /etc/yum.repos.d/docker.repo <<-'EOF'
[dockerrepo]
name=Docker Repository
baseurl=https://yum.dockerproject.org/repo/main/centos/$releasever/
enabled=1
gpgcheck=1
gpgkey=https://yum.dockerproject.org/gpg
EOF

   yum install --assumeyes --tolerant docker-engine
   systemctl start docker
   systemctl enable docker

   mkdir -p /etc/systemd/system/docker.service.d
   tee /etc/systemd/system/docker.service.d/override.conf <<-'EOF'
[Service]
ExecStart=
ExecStart=/usr/bin/docker daemon --storage-driver=overlay -H fd://
EOF

fi


echo ">>> read input parameters"
source $1


echo ">>> setting up firewall"
cat > /var/lib/iptables/rules-save <<EOF
*filter
:INPUT DROP [0:0]
-A INPUT -p tcp -m tcp --dport 22 -j ACCEPT
-A INPUT -p tcp -m tcp --dport 80 -j ACCEPT
-A INPUT -p tcp -m tcp --dport 443 -j ACCEPT
-A INPUT -p tcp -m tcp --dport 2181 -j ACCEPT
-A INPUT -p tcp -m tcp --dport 2888 -j ACCEPT
-A INPUT -p tcp -m tcp --dport 3888 -j ACCEPT
-A INPUT -p tcp -m tcp --dport 5050 -j ACCEPT
-A INPUT -p tcp -m tcp --dport 5051 -j ACCEPT
-A INPUT -p tcp -m tcp --dport 8080 -j ACCEPT
-A INPUT -p tcp -m tcp --dport 8123 -j ACCEPT
-A INPUT -p tcp -m tcp --dport 8181 -j ACCEPT
-A INPUT -i lo -j ACCEPT
-A INPUT -i eth0 -j ACCEPT
-A INPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
-A INPUT -p icmp -m icmp --icmp-type 0 -j ACCEPT
-A INPUT -p icmp -m icmp --icmp-type 3 -j ACCEPT
-A INPUT -p icmp -m icmp --icmp-type 8 -j ACCEPT
-A INPUT -p icmp -m icmp --icmp-type 11 -j ACCEPT
:DOCKER-ISOLATION - [0:0]
:DOCKER - [0:0]
:FORWARD ACCEPT [0:0]
-A FORWARD -p all -j DOCKER-ISOLATION
-A FORWARD -i eth1 -j REJECT
-A FORWARD -p all -o docker0 -j DOCKER
-A FORWARD -p all -o docker0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
-A FORWARD -p all -i docker0 "!" -o docker0 -j ACCEPT
-A FORWARD -p all -i docker0 -o docker0 -j ACCEPT
COMMIT
EOF

if $FIREWALL 
then 
   systemctl start iptables-restore.service
   systemctl enable iptables-restore.service 
fi

echo ">>> if centos then reboot necessary to activate overlayfs"
if [ $(which yum) ]; then
   reboot
fi

