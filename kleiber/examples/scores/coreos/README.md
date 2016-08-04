# coreos cluster orchestration for softlayer

The following is a quick guide on how to install a [coreos](https://coreos.com/) cluster on softlayer. Detailed information about coreos
can be found [here](https://coreos.com/os/docs/latest/).

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


## install the coreos cluster

First change to the directory that contains the kleiber score for coreos.
```
cd <kleiber_home>/kleiber/examples/scores/coreos
```

Next we use the following kleiber create command to install the coreos cluster.

**Note:** This process takes a while so be patient, don't close your terminal. We run with **-v** option so that you see debug output, and know something is happening.

```
kleiber create coreos.yml cluster_name datacenter=sjc01 masters=1 agents=1  keyname=public_key_name discovery=https://discovery.etcd.io/<token> -v

```
* cluster_name - the name you want to give the cluster, will be the prefix on all the node names
* datacenter - the softlayer datacenter you want the dc/os cluster created in
* masters - the number of mesos master nodes you want in your dc/os cluster, for HA you would want 3
* agents - the number of mesos agent nodes you want in your dc/os cluster
* keyname - the name of the public key registered with softlayer with which the nodes get configured
* discovery - cluster token. Generate a new token for each unique cluster from https://discovery.etcd.io/new?size=3 , specify initial cluster size with ?size=X


The creation ends with the following ouput.
```
... tbd ...
```

...
