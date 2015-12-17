#!/bin/bash 

# redirect stdout and error to our logfile
exec 1<&-
exec 2<&-
exec 1<>/root/startup.`date +"%m%d%y.%H%M"`
exec 2>&1

# read in paramters
source $1
wget https://github.com/suppandi/exhibitor/raw/master/openresty.tgz -O - | tar -zxv -C /usr/local/

mkdir -p /etc/nginx/conf
mkdir -p /etc/nginx/logs

echo "
worker_processes  1;
daemon off;
error_log logs/error.log;
events {
    worker_connections 1024;
}
include /etc/nginx/conf/dcos.conf;

" > /etc/nginx/conf/nginx.conf

conffile="/etc/nginx/conf/dcos.conf"

echo "http {" > $conffile

for port in $HTTPPORTS
do
        echo "  upstream hport$port {" 
	for server in $HTTPSERVERS
	do
		echo "        server $server:$port;"
	done
        echo "  }"

        echo "
  server {
    listen $port;
    location / {
      proxy_pass http://hport$port;
    }
  }
"
done >> $conffile

if [ "$DCOS_PROXY" != "" ]; then
  read -d '' config << "EOF"
    server {
        listen 80;

        location /marathon/ {
                proxy_pass http://hport8080/;
        }

        location  /mesos/ {
                proxy_pass http://hport5050/;
        }

        location  /mesos_dns/ {
                proxy_pass http://hport8123/;
        }

        location ~ ^/slave/(?<id>[a-zA-Z0-9-]+)(?<call>.+)$ {
                rewrite ^/slave/.+$ $call break;
                set $addr nil;
                rewrite_by_lua '
                        local cjson = require "cjson"
                        local slavesreq = ngx.location.capture("/mesos/master/slaves")
                        local slaves = cjson.decode(slavesreq.body)["slaves"]

                        for i,slave in ipairs(slaves) do
                                if slave["id"] == ngx.var.id then
                                        ngx.var.addr = string.gsub(slave["pid"],"[^@]+@","")
                                        break
                                end
                        end
                ';
                proxy_pass http://$addr;
        }


        # /service/kafka/api/brokers/add?id=0
        location ~ ^/service/(?<name>[^/]+)/?(?<call>.*) {
                rewrite ^/service/.+$ /$call break;
                set $addr nil;
                rewrite_by_lua '
                        local cjson = require "cjson"
                        local ldn=nil
                        if ngx.var.name == "sparkcli"  then
                                ldn = "_spark._tcp.marathon.mesos"
                        else
                                ldn = "_" .. ngx.var.name .. "._tcp.marathon.mesos"
                        end

                        local dnsreq = ngx.location.capture("/mesos_dns/v1/services/" .. ldn)
                        local dnsentry = cjson.decode(dnsreq.body)
                        ngx.var.addr = dnsentry[1]["ip"] .. ":" .. dnsentry[1]["port"]
                ';

                proxy_pass http://$addr;
        }

  }
EOF
 echo "$config" >> $conffile
fi 

echo "}" >> $conffile


if [ "$TCPPORTS" != "" ]; then
        echo "stream {" 
        for port in $TCPPORTS
        do
                echo "  upstream tport$port {"
                for server in $HTTPSERVERS
                do
                        echo "          server $server:$port;"
                done
                echo "  }
        server {
                listen $port;
                proxy_pass tport$port;
        }
"
        done
        echo "}"
fi >> $conffile

# create upstart file
cat >/etc/init/nginx.conf <<EOF
# nginx service
#

description "openresty nginx"
start on runlevel [2345]
stop on runlevel [!2345]

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