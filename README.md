# kleiber
Simple cluster director for SoftLayer

`kleiber` currently supports the following SoftLayer resources:
* vms
* autoscale groups
* loadbalancers
* vlans

## install & configure
Clone this repository.
```
git clone ...
```

Change to the kleiber directory and install kleiber using the following commands.
```
cd <kleiber_home>
python setup.py install
```

Create the file `~/.kleiber` and add your SoftLayer credentials to it as shown in the following.
```
username: SLUSER                                                  
api_key: SLAPIKEY
```
Metadata about the clusters you create gets store locally in the folder `~/.kleiber-data`

If you want the cluster metadata to be stored at a different location or in object store, then you have to add
one of the following in addition to the `~/.kleiber` file.
```
...
local_store: <folder-path>
# or
obj_store:
    name: <obj-store-name>
    datacenter: <dc>
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

## score samples
Score samples can be found in the [scores](kleiber/examples/scores) directory.

* [open-dcos](kleiber/examples/scores/open-dcos)
* [coreos](kleiber/examples/scores/coreos)
* ...


## score file format

Look at [detailed.yaml](kleiber/examples/scores/detailed.yaml) for full input and configuration options for individual resources.
* everything except `name` and `parameters` in the score files can be jinja 
templates to fill in values from other data. Look at [open-dcos.yml](kleiber/examples/scores/open-dcos/open-dcos.yml) for an example
* the optional dependson field in a resource provides ordering of the resources. Otherwise resources are deployed in an 
order automatically selected by the director

```
# a name describing the cluster
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