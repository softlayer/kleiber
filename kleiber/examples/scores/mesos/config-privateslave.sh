#!/bin/bash
echo "time : " >> /root/startup
date >> /root/startup


echo >> /root/startup
echo ">>> setting up firewall" >> /root/startup
ufw allow 22/tcp >> /root/startup
#ufw --force enable >> /root/startup
ufw allow 5051/tcp >> /root/startup
ufw status >> /root/startup

echo >> /root/startup
echo ">>> getting private and public ip" >> /root/startup
PRIVATE_IP=$(ip -o -4 addr list eth0 | awk '{print $4}' | cut -d/ -f1)
PUBLIC_IP=$(ip -o -4 addr list eth1 | awk '{print $4}' | cut -d/ -f1)
echo $PRIVATE_IP"   "$PUBLIC_IP >> /root/startup

echo >> /root/startup
echo ">>> get master ip from userdata" >> /root/startup
MASTER_IP=$(<$1)
echo $MASTER_IP >> /root/startup


echo >> /root/startup
echo ">>> setup" >> /root/startup
apt-key adv --keyserver keyserver.ubuntu.com --recv E56151BF >> /root/startup
DISTRO=$(lsb_release -is | tr '[:upper:]' '[:lower:]')
CODENAME=$(lsb_release -cs)

echo >> /root/startup
echo ">>> add the repository" >> /root/startup
echo "deb http://repos.mesosphere.io/${DISTRO} ${CODENAME} main" | \
  tee /etc/apt/sources.list.d/mesosphere.list
apt-get -y update >> /root/startup

echo >> /root/startup
echo ">>> install" >> /root/startup
apt-get -y install mesos >> /root/startup
wget -qO- https://get.docker.com/ | sh >> /root/startup
apt-get -y install curl >> /root/startup
apt-get -y install unzip >> /root/startup
apt-get -y install nodejs >> /root/startup
apt-get -y install npm >> /root/startup

echo >> /root/startup
echo ">>> disable zookeeper" >> /root/startup
service zookeeper stop >> /root/startup
echo "manual" > /etc/init/zookeeper.override

echo >> /root/startup
echo ">>> mesos zk setting" >> /root/startup
echo "zk://"$MASTER_IP":2181/mesos" > /etc/mesos/zk

echo >> /root/startup
echo ">>> mesos-slave hostname setting" >> /root/startup
#echo $PRIVATE_IP > /etc/mesos-slave/hostname
#echo $PRIVATE_IP > /etc/mesos-slave/ip
echo $PUBLIC_IP > /etc/mesos-slave/hostname
echo $PUBLIC_IP > /etc/mesos-slave/ip

echo >> /root/startup
echo ">>> mesos-slave containerizers and executor registration timeout setting" >> /root/startup
echo "docker,mesos" > /etc/mesos-slave/containerizers
echo "5mins" > /etc/mesos-slave/executor_registration_timeout

echo >> /root/startup
echo ">>> disable mesos-master" >> /root/startup
service mesos-master stop >> /root/startup
echo "manual" > /etc/init/mesos-master.override

echo >> /root/startup
echo ">>> restart mesos-slave" >> /root/startup
sudo service mesos-slave restart >> /root/startup

echo >> /root/startup
echo ">>> mesos-dns" >> /root/startup
sed -i "1s/^/nameserver $MASTER_IP\n /" /etc/resolv.conf >> /root/startup
