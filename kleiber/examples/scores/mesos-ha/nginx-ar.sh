#!/bin/bash

# redirect stdout and error to our logfile
exec 1<&-
exec 2<&-
exec 1<>/root/startup.`date +"%m%d%y.%H%M"`
exec 2>&1

# read in paramters
source $1


# get openresty
wget https://github.com/suppandi/exhibitor/raw/master/openresty.tgz -O - | tar -zxv -C /usr/local/
mkdir -p /etc/nginx/conf
mkdir -p /etc/nginx/logs

# get dcos amdin router
wget https://github.com/mesosphere/adminrouter-public/archive/master.tar.gz -O - | tar -zxv -C /etc/nginx/conf --strip 1

# adapt nginx conf
sed -i "1s/^/user root;\n/" /etc/nginx/conf/nginx.conf

sed -i "/location = \/mesos {/i\        resolver $HTTPSERVERS valid=30s;\n        set \$m leader.mesos;\n" /etc/nginx/conf/nginx.conf

sed -i "s/proxy_pass http:\/\/mesos\//proxy_pass http:\/\/\$m:5050/g" /etc/nginx/conf/nginx.conf
sed -i "/proxy_pass http:\/\/\$m:5050/i\            rewrite \^\/mesos\/(.*) \/\$1 break;" /etc/nginx/conf/nginx.conf

sed -i "/location = \/exhibitor/i\        location /static/ {\n            proxy_set_header Host \$http_host;\n            rewrite ^/(.*) /\$1 break;\n            proxy_pass http://\$m:5050;\n        }\n" /etc/nginx/conf/nginx.conf

sed -i "s/proxy_pass http:\/\/exhibitor\//proxy_pass http:\/\/\$m:8090/g" /etc/nginx/conf/nginx.conf
sed -i "/proxy_pass http:\/\/\$m:8090/i\            rewrite \^\/exhibitor\/(.*) \/\$1 break;" /etc/nginx/conf/nginx.conf

sed -i "/location \~ \^\/service\//i\        location = \/service\/marathon {\n            rewrite \^\/service\/marathon\$ \$scheme:\/\/\$http_host\/service\/marathon\/ permanent;\n        }" /etc/nginx/conf/nginx.conf
sed -i "/location \~ \^\/service\//i\        location \^\~ \/service\/marathon\/ {\n            proxy_set_header Host \$http_host;\n            proxy_pass http:\/\/marathon\/;\n        }\n" /etc/nginx/conf/nginx.conf

# configure resolv.conf
echo
echo ">>> mesos-dns"
for server in $HTTPSERVERS
do
   grep -q -e "nameserver $server" /etc/resolv.conf || sed -i "1s/^/nameserver $server\n/" /etc/resolv.conf
done


# create upstart file
cat >/etc/init/nginx.conf <<EOF
# nginx service
#

description "openresty nginx"
start on runlevel [2345]
stop on runlevel [!2345]

expect fork
respawn

script
  export PATH=/usr/local/
  PATH=/usr/local/openresty/nginx/sbin:$PATH
  export PATH
  exec nginx -p /etc/nginx -c /etc/nginx/conf/nginx.conf
end script
EOF

echo
service nginx restart

while [ ! -f /etc/nginx/logs/nginx.pid ]
do
   sleep 10
   service nginx restart
done

