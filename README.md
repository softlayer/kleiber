# kleiber
Simple cluster director for SoftLayer

`kleiber` currently supports the following SoftLayer resources:
* vms
* autoscale groups
* loadbalancers
* vlans

## install & configure
* Clone this repository.
* Install - `sudo python setup.py install`
* Copy one of `kleiber/examples/kleiber.*.template` to `~/.kleiber` and enter your credentials.

```

username: SLUSER                                                  
api_key: SLAPIKEY
# where to store kleiber management data
obj_store:
    name: IBMOS619705-2
    datacenter: tor01
```

## kleiber cli

kleiber provides the following commands.

```
# kleiber -h
kleiber cluster director

Usage:
  kleiber create <score.yaml> <clustername> [<key=value>...] [-v]
  kleiber status <clustername> [<resourcename>]
  kleiber delete <clustername>
  kleiber list 
  kleiber (-h | --help)
  kleiber --version

Options:
  -h --help     Show this screen.
  --version     Show version.
```

sample score.yaml files are in the [scores](kleiber/examples/scores) directory

## score file format

look at [detailed.yaml](kleiber/examples/scores/detailed.yaml) for full input options and configuration options for individual resources
* everything except `name` and `parameters` in the score files can be jinja 
templates to fill in values from other data. look at [mesos-ha.yml](scores/mesos-ha/mesos-ha.yml) for an example
* the optional dependson field in a resource provides ordering of the resources. otherwise resources are deployed in an 
order automatically selected by the director

```
# a name to define the cluster
name: myweb-topology

# a set of parameters with default values. These can be overridden by 
# passing a key=value pair on create
parameters:
  key1: value1
  key2: value2

# datacenter where this needs to be deployed
datacenter: tor01

# commonly used mappings
mappings:
  servertypes:
    ...

# resources to deploy as part of the cluster
resources:
   vlans: ...
   loadbalancers: ...
   serverinstances: ...
     # autoscale: ....

...
output:
    template: a jinja template to generate output
    # result -> optional output file, if none provided, 
    # the output is printed on screen
    result: output file to generate from template
```

## samples
create a multi master mesos cluster
```

# kleiber create kleiber/examples/scores/mesos-ha/mesos-ha.yml inst1 datacenter=mon01 
...
# kleiber create kleiber/examples/scores/mesos/mesos.yml inst2 key=mysshkeyname domain=demo.com
...
```

list existing clusters
```

# kleiber list
['mesos:inst1', 'mesos:inst2']