#!/bin/bash


# redirect stdout and error to our logfile
exec 1<&-
exec 2<&-
exec 1<>/root/startup.`date +"%m%d%y.%H%M"`
exec 2>&1

# read in paramters
source $1

apt-get -y install haproxy

for port in $HTTPPORTS
do
	cat >>/etc/haproxy/haproxy.cfg << EOF

listen hport$port 0.0.0.0:$port
	stats enable
	stats uri /haproxy?stats
	stats realm Haproxy\ Statistics
	stats auth haproxy:passward
	balance roundrobin
	option httpclose
	option forwardfor
EOF
	let i=1
	for server in $HTTPSERVERS
	do
		echo "	server server$i $server:$port check" >> /etc/haproxy/haproxy.cfg
		let i=i+1
	done
done

for port in $TCPPORTS
do
	cat >>/etc/haproxy/haproxy.cfg << EOF

listen port$port 0.0.0.0:$port
	mode tcp
	option tcplog
	balance roundrobin
EOF
	let i=1
	for server in $HTTPSERVERS
	do
		echo "	server server$i $server:$port check" >> /etc/haproxy/haproxy.cfg
		let i=i+1
	done
done
sed -i 's/ENABLED=0/ENABLED=1/g' /etc/default/haproxy
service haproxy restart

cat > /usr/sbin/haproxy_reconfig.py <<EOF
#!/usr/bin/python

import socket
import subprocess
import sys
import json
import codecs
import urllib
status_url = 'http://localhost:8090/exhibitor/v1/cluster/status'
httpports="$HTTPPORTS"
tcpports="$TCPPORTS"

content="""global
        log /dev/log    local0
        log /dev/log    local1 notice
        chroot /var/lib/haproxy
        user haproxy
        group haproxy
        daemon

defaults
        log     global
        mode    http
        option  httplog
        option  dontlognull
        contimeout 5000
        clitimeout 50000
        srvtimeout 50000
        errorfile 400 /etc/haproxy/errors/400.http
        errorfile 403 /etc/haproxy/errors/403.http
        errorfile 408 /etc/haproxy/errors/408.http
        errorfile 500 /etc/haproxy/errors/500.http
        errorfile 502 /etc/haproxy/errors/502.http
        errorfile 503 /etc/haproxy/errors/503.http
        errorfile 504 /etc/haproxy/errors/504.http

"""
u = urllib.urlopen(status_url)
data = json.loads(u.read())

for httpport in httpports.split():
        content=content+"""
listen hport{} 0.0.0.0:{}
        stats enable
        stats uri /haproxy?stats
        stats realm Haproxy\ Statistics
        stats auth haproxy:passward
        balance roundrobin
        option httpclose
        option forwardfor
""".format(httpport,httpport)
        i=0
        for node in data:
                content=content+"       server server{} {}:{} check\n".format(i,node['hostname'],httpport)
                i=i+1


for tcpport in tcpports.split():
        content=content+"""
listen port{} 0.0.0.0:{}
        mode tcp
        option tcplog
        balance roundrobin
""".format(tcpport,tcpport)
        i=0
        for node in data:
                content=content+"       server server{} {}:{} check\n".format(i,node['hostname'],tcpport)
                i=i+1

oldcontent=open("/etc/haproxy/haproxy.cfg","r").read()

if content != oldcontent:
        print "hello"
        with open("/etc/haproxy/haproxy.cfg","w") as f:
                f.write(content)
        subprocess.call(["service","haproxy","restart"])

EOF
chmod +x /usr/sbin/haproxy_reconfig.py
echo -e "`crontab -l`\n*/5 * * * * /usr/sbin/haproxy_reconfig.py" | crontab -
