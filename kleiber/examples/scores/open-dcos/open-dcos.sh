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
   curl -fsSL https://get.docker.com/ | sh
   service docker start
   SSH_USER=root
else
   cd /home/core/
   SSH_USER=core
fi


echo ">>> read input parameters"
source $1

MASTER_PRIV_IPS="$MASTER_PRIVATE_IPS"
IFS=' ' read -ra a <<<"$MASTER_PRIVATE_IPS"
MASTER_PRIVATE_IPS=''
for ip in ${a[@]}; do MASTER_PRIVATE_IPS=$MASTER_PRIVATE_IPS'- '$ip$'\n'; done

AGENT_PRIV_IPS="$AGENT_PRIVATE_IPS"
IFS=' ' read -ra a <<<"$AGENT_PRIVATE_IPS"
AGENT_PRIVATE_IPS=''
for ip in ${a[@]}; do AGENT_PRIVATE_IPS=$AGENT_PRIVATE_IPS'- '$ip$'\n'; done

PUBLIC_AGENT_PRIV_IPS="$PUBLIC_AGENT_PRIVATE_IPS"
IFS=' ' read -ra a <<<"$PUBLIC_AGENT_PRIVATE_IPS"
PUBLIC_AGENT_PRIVATE_IPS=''
for ip in ${a[@]}; do PUBLIC_AGENT_PRIVATE_IPS=$PUBLIC_AGENT_PRIVATE_IPS'- '$ip$'\n'; done


echo ">>> create genconf directory"
mkdir -p genconf


echo ">>> create ip detect script"
cat > ./genconf/ip-detect <<EOF
#!/usr/bin/env bash
set -o nounset -o errexit
export PATH=/usr/sbin:/usr/bin:\$PATH
echo \$(ip addr show eth0 | grep -Eo '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}' | head -1)
EOF


echo ">>> create configuration file"
cat > ./genconf/config.yaml <<EOF
---
master_list:
$MASTER_PRIVATE_IPS
agent_list:
$AGENT_PRIVATE_IPS 
public_agent_list:
$PUBLIC_AGENT_PRIVATE_IPS
# Use this bootstrap_url value unless you have moved the DC/OS installer assets.
bootstrap_url: file:///opt/dcos_install_tmp
cluster_name: dcos
exhibitor_storage_backend: static
process_timeout: 600
master_discovery: static
resolvers:
- 10.0.80.11
- 10.0.80.12
ssh_port: 22
ssh_user: $SSH_USER
EOF

echo ">>> create private ssh key file"
# replace all | with new lines
cat > ./genconf/ssh_key <<EOF
${SSH_KEY//|/
}
EOF
chmod 0600 genconf/ssh_key


echo ">>> download dcos installer"
#curl -O -s https://downloads.dcos.io/dcos/EarlyAccess/dcos_generate_config.sh
curl -O https://downloads.dcos.io/dcos/stable/dcos_generate_config.sh
chmod +x dcos_generate_config.sh

echo ">>> run --genconf"
DCOS_INSTALLER_DAEMONIZE=false ./dcos_generate_config.sh --genconf

echo ">>> run --install-prereqs"
DCOS_INSTALLER_DAEMONIZE=false ./dcos_generate_config.sh --install-prereqs

echo ">>> if centos then deactivate overlayfs on agenst for now"
if [ $(which yum) ]; then
   IFS=' ' read -ra a <<<"$AGENT_PRIV_IPS $PUBLIC_AGENT_PRIV_IPS $MASTER_PRIV_IPS"
   for ip in ${a[@]}; do ssh -o StrictHostKeyChecking=no -i genconf/ssh_key root@$ip "sed -i -e 's/overlay.*$/overlay -H unix:\/\/\/var\/run\/docker.sock/g' /etc/systemd/system/docker.service.d/override.conf; systemctl daemon-reload ; systemctl restart docker.service" ; done
fi

echo ">>> run --preflight"
DCOS_INSTALLER_DAEMONIZE=false ./dcos_generate_config.sh --preflight

echo ">>> run --deploy"
DCOS_INSTALLER_DAEMONIZE=false ./dcos_generate_config.sh --deploy

echo ">>> run --postflight"
DCOS_INSTALLER_DAEMONIZE=false ./dcos_generate_config.sh --postflight


echo ">>> if centos then deactivate overlayfs on agenst for now"
if [ $(which yum) ]; then
   IFS=' ' read -ra a <<<"$AGENT_PRIV_IPS $PUBLIC_AGENT_PRIV_IPS"
   for ip in ${a[@]}; do ssh -o StrictHostKeyChecking=no -i genconf/ssh_key root@$ip "sed -i -e 's/overlay/devicemapper/g' /etc/systemd/system/docker.service.d/override.conf; systemctl daemon-reload ; systemctl restart docker.service" ; done
fi


echo ">>> create and launch container for dcoscli"
mkdir dcoscli
cat > ./dcoscli/Dockerfile <<EOF
FROM ubuntu:latest
RUN apt-get update
RUN apt-get install -y curl
RUN apt-get install -y vim
RUN apt-get install -y python
RUN apt-get install -y python-pip
RUN apt-get install -y jq
RUN pip install virtualenv
RUN mkdir dcos
WORKDIR dcos
RUN curl -O https://downloads.dcos.io/binaries/cli/linux/x86-64/dcos-1.8/dcos
RUN chmod +x dcos
RUN mv dcos /usr/local/bin
RUN dcos config set core.dcos_url http://$MASTER_PUBLIC_IP
EOF
docker build -t dcoscli dcoscli
docker run -di --name=dcoscli dcoscli /bin/bash


