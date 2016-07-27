# dc/os cluster orchestration for softlayer

The following is a quick guide on how to install [dc/os](https://dcos.io/) on softlayer. Detailed information about dc/os
can be found [here](https://dcos.io/docs/1.7/).

## install & configure kleiber

First clone the [kleiber](https://github.rtp.raleigh.ibm.com/edgepoc/kleiber) repository.

**Note:** If you don't want to install kleiber to your OS'es python then you should setup a python [virualenv](http://docs.python-guide.org/en/latest/dev/virtualenvs/) 
before you run the following install command.

Change to the kleiber directory and run the install command as follows.
```
cd <kleiber_home>
python setup.py install
```

Next create the following configration file `~/.kleiber` and enter your softlayer credentials as shown in the following.

```
username: SLUSER                                                  
api_key: SLAPIKEY
```


## install the dc/os cluster

First change to the directory that contains the kleiber score for dc/os.
```
cd <kleiber_home>/kleiber/examples/scores/open-dcos
```

Next we use the following kleiber create command to install the dc/os cluster.

**Note:** This process takes a while so be patient, don't close your terminal. In our experience a 
simple cluster (1 master, 1 agent) takes like 15 mins, a more complex one (3 masters, 3 agents) takes like > 30 mins.
We run with **-v** option so that you see debug output, and know something is happening.

```
kleiber create open-dcos.yml cluster_name datacenter=sjc01 masters=1 agents=1 keyname=public_key_name pkey="$(< private_key_path)" -v
```
* cluster_name - the name you want to give the cluster, will be the prefix on all the node names
* datacenter - the softlayer datacenter you want the dc/os cluster created in
* masters - the number of mesos master nodes you want in your dc/os cluster, for HA you would want 3
* agents - the number of mesos agent nodes you want in your dc/os cluster
* keyname - the name of the public key registered with softlayer with which the nodes get configured
* pkey - the private key (see former snippet for easy way to pass it), required by the bootstrap node to install the dc/os roles on masters and agents


The creation ends with the following ouput.
```
dcos: "http://<master_ip>"
mesos: "http://<master_ip>/mesos"
marathon: "http://<master_ip>/marathon"
exhibitor: "http://<master_ip>/exhibitor"
bootstrap: "<boostrap_ip>"
```

Pick the dcos url and put it into your browser, it will take you to the dc/os console.


## install the dc/os cli

For installing the dc/os cli yourself and how to use it go [here](https://dcos.io/docs/1.7/usage/cli/).

If you dont want to install the dc/os cli on your client just yet, then we have a quick way for you to explore it.

In the previous install step we also created a container on the boostrap node that has the dc/os cli installed. First
ssh into the boostrap node. Once you are in the boostrap node enter the following command to get you to the shell of
the container that has the dc/os cli.
```
docker exec -ti dcoscli bash
```

Entering the dcos command should give you the following.
```
root@69e768a60f2a:/dcos# dcos
Command line utility for the Mesosphere Datacenter Operating
System (DCOS). The Mesosphere DCOS is a distributed operating
system built around Apache Mesos. This utility provides tools
for easy management of a DCOS installation.

Available DCOS commands:

	auth           	Authenticate to DCOS cluster
	config         	Manage the DCOS configuration file
	help           	Display help information about DCOS
	marathon       	Deploy and manage applications to DCOS
	node           	Administer and manage DCOS cluster nodes
	package        	Install and manage DCOS software packages
	service        	Manage DCOS services
	task           	Manage DCOS tasks

Get detailed command description with 'dcos <command> --help'.
```

