#!/bin/bash
echo "time : " >> /root/startup
date >> /root/startup


echo >> /root/startup
echo ">>> setting up firewall" >> /root/startup
ufw allow 22/tcp >> /root/startup
#ufw --force enable >> /root/startup
ufw allow 2888,3888,2181/tcp >> /root/startup
ufw allow 5050/tcp >> /root/startup
ufw allow 8080/tcp >> /root/startup
ufw allow 53 >> /root/startup
ufw allow 8123/tcp >> /root/startup
ufw status >> /root/startup

echo >> /root/startup
echo ">>> getting private and public ip" >> /root/startup
PRIVATE_IP=$(ip -o -4 addr list eth0 | awk '{print $4}' | cut -d/ -f1)
PUBLIC_IP=$(ip -o -4 addr list eth1 | awk '{print $4}' | cut -d/ -f1)
echo $PRIVATE_IP"   "$PUBLIC_IP >> /root/startup


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
apt-get -y install mesos marathon >> /root/startup
wget -qO- https://get.docker.com/ | sh >> /root/startup

echo "" >> /root/startup
echo ">>> set zookeeper id" >> /root/startup
echo 1 > /etc/zookeeper/conf/myid

# will have to change zk config to list all the zk nodes
# /etc/zookeeper/conf/zoo.cfg

echo >> /root/startup
echo ">>> restart zk" >> /root/startup
service zookeeper restart >> /root/startup

echo >> /root/startup
echo ">>> mesos zk setting" >> /root/startup
echo "zk://localhost:2181/mesos" > /etc/mesos/zk

# will have to change quorum setting
# /etc/mesos-master/quorum

echo >> /root/startup
echo ">>> mesos hostname setting" >> /root/startup
echo $PUBLIC_IP > /etc/mesos-master/hostname
echo $PUBLIC_IP > /etc/mesos-master/ip

echo >> /root/startup
echo ">>> slave_public role setting" >> /root/startup
echo "slave_public" > /etc/mesos-master/roles
mkdir -p /etc/marathon/conf >> /root/startup
echo "slave_public" > /etc/marathon/conf/mesos_role
echo "*" > /etc/marathon/conf/default_accepted_resource_roles

echo >> /root/startup
echo ">>> disable mesos slave" >> /root/startup
service mesos-slave stop >> /root/startup
echo "manual" > /etc/init/mesos-slave.override

echo >> /root/startup
echo ">>> restart mesos-master and marathon" >> /root/startup
service mesos-master restart >> /root/startup
service marathon restart >> /root/startup

echo >> /root/startup
echo ">>> mesos-dns" >> /root/startup
mkdir /etc/mesos-dns >> /root/startup
cat <<EOF > /etc/mesos-dns/config.json
{
  "zk": "zk://$PRIVATE_IP:2181/mesos",
  "refreshSeconds": 60,
  "ttl": 60,
  "domain": "mesos",
  "port": 53,
  "resolvers": ["10.0.80.11","10.0.80.12"],
  "timeout": 5,
  "email": "root.mesos-dns.mesos"
}
EOF
docker run --net=host -d -v "/etc/mesos-dns/config.json:/config.json" mesosphere/mesos-dns /mesos-dns -config=/config.json >> /root/startup
sed -i "1s/^/nameserver $PRIVATE_IP\n /" /etc/resolv.conf >> /root/startup
