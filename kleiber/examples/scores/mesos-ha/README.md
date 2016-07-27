
## setting up the dcos-cli
Now that you stood up a mesos cluster using Kleiber you can install the [dcos-cli](https://github.com/mesosphere/dcos-cli).

Follow the instructions on the [dcos-cli](https://github.com/mesosphere/dcos-cli) site to install it on your client machine.

Next we configure the dcos_url to point to the frontend load balancer setup by kleiber. You can find the url in the console output of the kleiber create command.

```
dcos config set core.dcos_url http://<frontend-load-balancer-host>
```

Once we are done with that we configure from where the dcos-client will get packages, e.g. there are packages for kafka, spark, ... .

```
dcos config append package.sources https://github.com/mesosphere/universe/archive/version-1.x.zip
dcos config set package.cache /tmp/dcos
dcos package update
```

Now lets search for the packages that are avaialble to you.

```
dcos package search
```

Now you are ready to install services or create marathon applications

```
dcos package install <package-name>

dcos marathon app add <app-resource-json-file>
```