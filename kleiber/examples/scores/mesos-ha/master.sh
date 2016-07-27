#!/bin/bash


# redirect stdout and error to our logfile
exec 1<&-
exec 2<&-
exec 1<>/root/startup.`date +"%m%d%y.%H%M"`
exec 2>&1

# read in paramters
source $1

echo ">>> setting up firewall"
ufw allow 22/tcp
#ufw --force enable >> /root/startup
ufw allow 2888,3888,2181/tcp
ufw allow 5050/tcp 
ufw allow 8080/tcp
ufw allow 53
ufw allow 8123/tcp
ufw allow 8090/tcp
ufw status

echo 
echo ">>> getting private and public ip" 
PRIVATE_IP=$(ip -o -4 addr list eth0 | awk '{print $4}' | cut -d/ -f1)
PUBLIC_IP=$(ip -o -4 addr list eth1 | awk '{print $4}' | cut -d/ -f1)
echo $PRIVATE_IP"   "$PUBLIC_IP 

EXHIBITOR_TAR="exhibitor-standalone-0.0.1-SNAPSHOT.tar"
# get zookeeper and exhibitor files
wget -nv -O- https://github.com/suppandi/exhibitor/raw/master/zookeeper-3.4.6.tar.gz | tar -zx -C /opt/
ln -s /opt/zookeeper-3.4.6 /opt/zookeeper
wget https://github.com/suppandi/exhibitor/raw/master/$EXHIBITOR_TAR -O - | tar -xv -C /opt/

# install java
apt-get -y install software-properties-common
add-apt-repository ppa:webupd8team/java
apt-get -y update
echo oracle-java8-installer shared/accepted-oracle-license-v1-1 select true | /usr/bin/debconf-set-selections
apt-get -y install oracle-java8-installer

mkdir -p /var/zookeeper/log
# create exhibitor config file
cat >/opt/zookeeper/exhibitor.conf << EOF
zookeeper-install-directory=/opt/zookeeper/
zookeeper-data-directory=/var/zookeeper/
zookeeper-log-directory=/var/zookeeper/log
backup-extra=throttle\=0&container-name\=$CONTAINER&key-prefix\=mybackup&max-retries\=3&retry-sleep-ms\=200
auto-manage-instances-fixed-ensemble-size=0
auto-manage-instances=1
auto-manage-instances-settling-period-ms=60000
check-ms=30000
auto-manage-instances-apply-all-at-once=1
EOF

# create upstart file
cat >/etc/init/exhibitor.conf <<EOF
# exhibitor - netflix exhibitor
#

description	"zookeeper manager"
start on runlevel [2345]
stop on runlevel [!2345]

respawn

script
  export JAVA_OPTS="-Djclouds.keystone.credential-type=tempAuthCredentials"
	exec /opt/exhibitor-standalone-0.0.1-SNAPSHOT/bin/exhibitor-standalone -c swift --hostname $PUBLIC_IP --port 8090 --swiftbackup true --swiftidentity $SWIFTIDENTITY --swiftapikey $SWIFTAPIKEY --swiftauthurl $SWIFTAUTHURL --swiftconfig $CONTAINER:sample_config.properties --defaultconfig /opt/zookeeper/exhibitor.conf
end script
EOF

service exhibitor start

# create exhibitor wait script
echo $CLUSTERSIZE > /opt/zookeeper/clustersize
cat > /opt/zookeeper/exhibitor-wait <<EOF
#!/bin/sh

clustersize=\`cat /opt/zookeeper/clustersize\`

while true; do
        echo 'checking exhibitor'
        x=\`wget -q http://localhost:8090/exhibitor/v1/cluster/status -O- | python -mjson.tool\`
        serving=\`echo "\$x" | grep -c "serving" \`
        if [ \$serving -eq \$clustersize ]; then
                echo "\$x" | grep '"isLeader": true' 2>&1 >>/dev/null
                if [ \$? -eq 0 ]; then
                        echo 'all requirements satisfied'
                        break
                else
                        echo 'leader not found...more tries'
                fi
        fi

        echo "waiting for \$clustersize, only found \$serving. going to sleep"
        sleep 5
done
# run the original that we are wrapping around
if [ -f \$0.orig ]; then
    sleep 60
	\$0.orig \$@
fi
EOF
chmod +x /opt/zookeeper/exhibitor-wait

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
apt-get -y install mesos marathon
wget -qO- https://get.docker.com/ | sh 


# make zookeeper service not start by default...it is under exhibitor control
service zookeeper stop
echo "manual" > /etc/init/zookeeper.override

echo 
echo ">>> mesos zk setting" 
echo "zk://localhost:2181/mesos" > /etc/mesos/zk

# will have to change quorum setting
let quorum=($CLUSTERSIZE+1)/2
echo $quorum > /etc/mesos-master/quorum

echo 
echo ">>> mesos and marathon hostname setting" 
echo $PUBLIC_IP > /etc/mesos-master/hostname
echo $PUBLIC_IP > /etc/mesos-master/ip
mkdir -p /etc/marathon/conf
echo $PUBLIC_IP > /etc/marathon/conf/hostname

echo 
echo ">>> slave_public role setting" 
echo "slave_public,riak" > /etc/mesos-master/roles
echo "slave_public" > /etc/marathon/conf/mesos_role
echo "*" > /etc/marathon/conf/default_accepted_resource_roles
echo "600000" > /etc/marathon/conf/task_launch_confirm_timeout 
echo ">>> marathon artifact store setting"
mkdir -p /var/marathon/store
echo "file:///var/marathon/store" > /etc/marathon/conf/artifact_store

echo 
echo ">>> disable mesos slave" 
service mesos-slave stop 
echo "manual" > /etc/init/mesos-slave.override

echo 
echo ">>> wrap mesos scripts with exhibitor wait"
mv /usr/bin/mesos-init-wrapper /usr/bin/mesos-init-wrapper.orig
ln -s /opt/zookeeper/exhibitor-wait /usr/bin/mesos-init-wrapper
mv /usr/bin/marathon /usr/bin/marathon.orig
ln -s /opt/zookeeper/exhibitor-wait /usr/bin/marathon

echo
echo ">>> restart mesos-master and marathon" 
service mesos-master restart 
service marathon restart 

echo 
echo ">>> mesos-dns" 
mkdir /etc/mesos-dns 
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
# download mesos-dns
wget https://github.com/mesosphere/mesos-dns/releases/download/v0.3.0/mesos-dns-v0.3.0-linux-amd64.gz -O - | gunzip > /opt/mesos-dns
chmod +x /opt/mesos-dns

sed -i "1s/^/nameserver $PRIVATE_IP\n /" /etc/resolv.conf 

# create upstart file
cat >/etc/init/mesos-dns.conf <<EOF
# mesos dns service
#

description "dns based on mesos"
start on runlevel [2345]
stop on runlevel [!2345]

respawn

script
  /opt/mesos-dns -config=/etc/mesos-dns/config.json
end script
EOF

service mesos-dns restart
