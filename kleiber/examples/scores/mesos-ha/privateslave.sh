#!/bin/bash

# redirect stdout and error to our logfile
exec 1<&-
exec 2<&-
exec 1<>/root/startup.`date +"%m%d%y.%H%M"`
exec 2>&1

echo "time : " 
date 

echo 
echo ">>> setting up firewall" 
ufw allow 22/tcp 
#ufw --force enable >> /root/startup
ufw allow 5051/tcp 
ufw status 

echo 
echo ">>> getting private and public ip" 
PRIVATE_IP=$(ip -o -4 addr list eth0 | awk '{print $4}' | cut -d/ -f1)
PUBLIC_IP=$(ip -o -4 addr list eth1 | awk '{print $4}' | cut -d/ -f1)
echo $PRIVATE_IP"   "$PUBLIC_IP 

echo 
echo ">>> get master ip from userdata" 
MASTER_IP=$(<$1)
MASTER_IP=`echo $MASTER_IP`
echo $MASTER_IP 

echo 
echo ">>> register dns resolver"
apt-get -y update
apt-get -y install python-pip
pip install dnspython
cat > /usr/sbin/gen_resolvconf.py <<EOF
#!/usr/bin/python

import socket
import subprocess
import sys
import json
import codecs
import urllib

import dns.query

status_url = 'http://$MASTER_IP:8090/exhibitor/v1/cluster/status'
fallback_dns = "$(cat /etc/resolv.conf  | grep nameserver | head -1 | cut -d' ' -f2)"
resolvconf_path = "/etc/resolv.conf"
dns_test_query = 'leader.mesos'
dns_timeout = 5

servers = []

if 1 == 1:
#try:
    u = urllib.urlopen(status_url)
    data = json.loads(u.read())
    print(data)
    for node in data:
        try:
            addr = socket.gethostbyname(node['hostname'])
            query = dns.message.make_query(dns_test_query, dns.rdatatype.ANY)
            result = dns.query.udp(query, addr, dns_timeout)
            if len(result.answer) == 0:
                sys.stderr.write('Skipping DNS server {}: no records for {}'.format(addr, dns_test_query))
            else:
                servers.append(addr)
        except socket.gaierror as ex:
            sys.stderr.write(ex)
        except dns.exception.Timeout:
            sys.stderr.write('Skipping DNS server {}: no response'.format(addr))
#except:
#    
#    sys.stderr.write('Error getting DNS entries from {}: {}'.format((status_url), sys.exc_info()[1]))

# Use maximum of three servers per resolv.h MAXNS, with the known good fallback
# dns server always present as the last in the set.
nameservers = servers[:2]
nameservers.append(fallback_dns)

print('Updating {}'.format(resolvconf_path))
with open(resolvconf_path, 'w') as f:
    for ns in nameservers:
        line = "nameserver {}".format(ns)
        sys.stderr.write(line)
        f.write(line)
        f.write('\n')

sys.exit(0)

EOF
# add it to crontab to run every 5 min
chmod +x /usr/sbin/gen_resolvconf.py
echo -e "`crontab -l`\n*/5 * * * * /usr/sbin/gen_resolvconf.py" | crontab -

echo 
echo ">>> setup" 
apt-key adv --keyserver keyserver.ubuntu.com --recv E56151BF 
DISTRO=$(lsb_release -is | tr '[:upper:]' '[:lower:]')
CODENAME=$(lsb_release -cs)

echo 
echo ">>> add the repository" 
echo "deb http://repos.mesosphere.io/${DISTRO} ${CODENAME} main" | \
  tee /etc/apt/sources.list.d/mesosphere.list
apt-get -y update 

echo 
echo ">>> install" 
apt-get -y install mesos 
wget -qO- https://get.docker.com/ | sh 
apt-get -y install curl 
apt-get -y install unzip 
apt-get -y install nodejs 
apt-get -y install npm 

echo 
echo ">>> disable zookeeper" 
service zookeeper stop 
echo "manual" > /etc/init/zookeeper.override

echo 
echo ">>> mesos zk setting" 
echo "zk://"$MASTER_IP":2181/mesos" > /etc/mesos/zk

echo 
echo ">>> mesos-slave hostname setting" 
#echo $PRIVATE_IP > /etc/mesos-slave/hostname
#echo $PRIVATE_IP > /etc/mesos-slave/ip
echo $PUBLIC_IP > /etc/mesos-slave/hostname
echo $PUBLIC_IP > /etc/mesos-slave/ip

echo 
echo ">>> mesos-slave containerizers and executor registration timeout setting" 
echo "docker,mesos" > /etc/mesos-slave/containerizers
echo "5mins" > /etc/mesos-slave/executor_registration_timeout

echo 
echo ">>> disable mesos-master" 
service mesos-master stop 
echo "manual" > /etc/init/mesos-master.override

echo 
echo ">>> restart mesos-slave" 
sudo service mesos-slave restart 

echo 
echo ">>> mesos-dns" 
sed -i "1s/^/nameserver $MASTER_IP\n /" /etc/resolv.conf 
