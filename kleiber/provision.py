#!/usr/bin/python

import SoftLayer
import json
import yaml
import re
import time
from jinja2 import Environment,  DictLoader
import sys

import lib


def manual_provision_vms(vs_config,
                         groupname,
                         groupdef,
                         clustername,
                         score,
                         client,
                         sl_storage,
                         configuration,
                         containername):
    configs = []
    count = int(groupdef['count'])
    for i in range(count):
        vscopy = vs_config.copy()
        vscopy['hostname'] = vscopy['hostname']+'-'+str(i)
        configs.append(vscopy)
    lib.debug(json.dumps(configs, indent=4, sort_keys=True))

    vs_manager = SoftLayer.VSManager(client)

    vms = lib.sl_retry(vs_manager.create_instances, configs)

    for vm in vms:
        lib.save_state(sl_storage, containername,
                       "serverinstances/{}/vms/{}/id".format(
                            groupname, vm['hostname']),
                       vm['id'])

    for vm in vms:
        lib.sl_retry(vs_manager.wait_for_ready, vm['id'], 600)

    groupdef['vms'] = []
    for vm in vms:
        groupdef['vms'].append(vs_manager.get_instance(vm['id']))


def trigger_read(triggerstring, triggertypes, duration):
    regex = re.compile("^([^\s><=]+)[\s]*([><=])[\s]*(.+)$")
    result = regex.match(triggerstring)

    field = result.group(1)
    check = result.group(2)
    value = result.group(3)

    retval = {}
    if field == "cron":
        field = "REPEATING"
        retval["schedule"] = value
        retval["class"] = "Scale_Policy_Trigger_Repeating"
    elif field == "time":
        field = "ONE_TIME"
        retval["date"] = value
        retval["class"] = "Scale_Policy_Trigger_OneTime"
    else:
        retval["watches"] = [{
            "algorithm": "EWMA",
            "metric": field,
            "value": value,
            "period": duration,
            "operator": check
        }]
        field = "RESOURCE_USE"
        retval["class"] = "Scale_Policy_Trigger_ResourceUse"

    retval["typeId"] = lib.findInList(triggertypes, 'keyName', field)

    return retval


def action_read(actionstring):
    regex = re.compile("^([-+=])([0-9]+)([%]*)$")
    result = regex.match(actionstring)
    direction = result.group(1)
    amount = result.group(2)
    unit = result.group(3)

    # if = its absolute, else its relative
    if direction == '=':
        scaleType = 'ABSOLUTE'
    else:
        # make amount +/-X
        amount = "{}{}".format(direction, amount)

        if unit == '%':
            scaleType = 'PERCENT'
        else:
            scaleType = 'RELATIVE'

    return {
        "amount": int(amount),
        "scaleType": scaleType,
        "typeId": 1
    }


def autoscale_provision_vms(vs_config, groupname, groupdef, clustername, score,
                            client, sl_storage, configuration, containername):
    autoscaledef = groupdef['autoscale']
    if 'regionalGroupID' not in score['datacenter']:
        raise Exception('datacenter does not support autoscale groups')

    asconfig = {
        'cooldown': 30,
        'suspendedFlag': True,
        'name': "{}_{}_{}".format(score['name'], clustername, groupname),
        'regionalGroupId': score['datacenter']['regionalGroupID'],
        'minimumMemberCount': groupdef['count'],
        # autoscaledef['minimumMemberCount'],
        'minimumVirtualGuestMemberCount': groupdef['count'],
        # autoscaledef['minimumMemberCount'],
        'maximumMemberCount': autoscaledef['maximumMemberCount'],
        'maximumVirtualGuestMemberCount': autoscaledef['maximumMemberCount'],
        'terminationPolicyId':
            lib.findInList(client['Scale_Termination_Policy'].getAllObjects(),
                           'keyName', 'CLOSEST_TO_NEXT_CHARGE')['id'],
        'virtualGuestMemberTemplate':  {
            'startCpus': vs_config['cpus'],
            'maxMemory': vs_config['memory'],
            'datacenter': {"name": score['datacenter']['name']},
            'hostname': vs_config['hostname'],
            'domain': vs_config['domain'],
            'operatingSystemReferenceCode': vs_config['os_code'],
            'hourlyBillingFlag': vs_config['hourly'],
            'localDiskFlag': False
        }
    }

    if 'local_disk' in vs_config:
        asconfig['virtualGuestMemberTemplate']['localDiskFlag'] = True

    if 'disks' in vs_config:
        asconfig['virtualGuestMemberTemplate']['blockDevices'] = [
            {"device": "0", "diskImage": {"capacity": vs_config['disks'][0]}}
        ]

        for dev_id, disk in enumerate(vs_config['disks'][1:], start=2):
            asconfig['virtualGuestMemberTemplate']['blockDevices'].append(
                {
                    "device": str(dev_id),
                    "diskImage": {"capacity": disk}
                })

    if 'nic_speed' in vs_config:
        asconfig['virtualGuestMemberTemplate']['networkComponents'] = [{
            'maxSpeed': vs_config['nic_speed']
        }]

    if 'ssh_keys' in vs_config:
        asconfig['virtualGuestMemberTemplate']['sshKeys'] = []
        for key in vs_config['ssh_keys']:
            asconfig['virtualGuestMemberTemplate']['sshKeys'].append(
                {"id": key})

    if 'private_vlan' in vs_config:
        asconfig['networkVlans'] = [
            {"networkVlanId": vs_config['private_vlan']}
        ]
    if 'public_vlan' in vs_config:
        publicvlan = {"networkVlanId": vs_config['public_vlan']}
        if 'networkVlans' in asconfig:
            asconfig['networkVlans'].append(publicvlan)
        else:
            asconfig['networkVlans'] = [publicvlan]

    if 'post_uri' in vs_config:
        vt = 'virtualGuestMemberTemplate'
        asconfig[vt]['postInstallScriptUri'] = vs_config['post_uri']
    if 'userdata' in vs_config:
        asconfig[vt]['userdata'] = [{'value': vs_config['userdata']}]

    lib.debug(json.dumps(asconfig, indent=4, sort_keys=True))
    asgroup = client['Scale_Group'].createObject(asconfig)
    lib.debug(asgroup)
    lib.save_state(sl_storage, containername,
                   "serverinstances/{}/autoscale/id".format(groupname),
                   asgroup['id'])

    triggertypes = client['Scale_Policy_Trigger_Type'].getAllObjects()
    lib.debug(json.dumps(triggertypes))

    if 'polcies' in autoscaledef:
        for policyname, policydef in autoscaledef['policies'].iteritems():
            lib.debug(json.dumps(policydef))
            if 'duration' in policydef:
                duration = policydef['duration']
            trigger = trigger_read(policydef['trigger'], triggertypes,
                                   duration)
            action = action_read(policydef['action'])
            lib.debug(trigger)
            lib.debug(action)

            newpolicy = {
                "name": policyname,
                "scaleGroupId": asgroup['id'],
                "complexType": 'SoftLayer_Scale_Policy',
                'scaleActions': [action]
            }
            lib.debug(newpolicy)
            policy = client['Scale_Policy'].createObject(newpolicy)
            triggerclass = trigger["class"]
            # remove field
            del trigger["class"]
            trigger["scalePolicyId"] = policy["id"]
            lib.debug(trigger)
            trigger = client[triggerclass].createObject(trigger)
            lib.debug(trigger)

    if 'loadbalancer' in autoscaledef:
        lbconfig = autoscaledef['loadbalancer']
        x = lbconfig['name'].split('.')
        lbname = x[0]
        lbgroup = x[1]
        sg = score['resources']['loadbalancers'][lbname]['service-groups']
        lbg = sg[lbgroup]
        newdef = {
            'scaleGroupId': asgroup['id'],
            'virtualServerId': lbg['id'],
            'healthCheck': {'type':
                            {'keyname': lbg['health_check'].upper()}},
            'port': lbconfig['balance-to']
        }

        debug(client['Scale_LoadBalancer'].createObject(newdef))

    # now activate the group
    client['Scale_Group'].resume(id=asgroup['id'])

    # sleep till provisioning of vms done
    sleeps = 600/5
    mask = "virtualGuestMembers.virtualGuest.primaryIpAddress"
    while sleeps != 0:
        lib.debug('sleeping')
        time.sleep(5)
        sleeps = sleeps - 1
        asgroup = client['Scale_Group'].getObject(id=asgroup['id'], mask=mask)
        if asgroup['status']['keyName'] == 'ACTIVE':
            groupdef['vms'] = [v['virtualGuest']
                               for v in asgroup['virtualGuestMembers']]
            break
    client['Scale_Group'].editObject(
        {
          'minimumMemberCount': autoscaledef['minimumMemberCount'],
          'minimumVirtualGuestMemberCount': autoscaledef['minimumMemberCount'],
        }, id=asgroup['id'])


def subfunc(match):
    return "{{{{ {} }}}}".format(match.group(2))


def get_templated_string(templatestring, score):
    lib.debug(templatestring)
    regex = re.compile(r'{{(\\\n  \\)*\s*([a-zA-Z0-9-_\.]+)(\\\n\s*\\)*\s*}}',
                       re.MULTILINE)
    templatestring = re.sub(regex, subfunc, templatestring)
    lib.debug(templatestring)
    env = Environment(autoescape=False,
                      loader=DictLoader({'templatestring': templatestring}),
                      trim_blocks=False)
    return env.get_template('templatestring').render(score)


def deploy_group(groupname, groupdef, clustername, score, client, sl_storage,
                 configuration, containername):
    vs_config = groupdef.copy()
    del vs_config['count']
    del vs_config['servertype']

    if 'vlan' in vs_config:
        del vs_config['vlan']

    if 'dependson' in vs_config:
        del vs_config['dependson']

    if 'keyname' in vs_config:
        sshkey_manager = SoftLayer.SshKeyManager(client)
        keys = sshkey_manager.list_keys(vs_config['keyname'])
        if len(keys) == 0:
            raise Exception("Key {} not found".format(vs_config['keyname']))
        vs_config['ssh_keys'] = [keys[0]['id']]
        del vs_config['keyname']

    vs_config['datacenter'] = score['datacenter']['name']

    vs_config.update(normalize(
            score['mappings']['servertypes'][groupdef['servertype']],
            score))

    if 'script' in vs_config or 'userdata' in vs_config:
        vs_config['post_uri'] = "https://gist.githubusercontent.com/suppandi/"\
                "92160b055d74662a1deb/raw/0f2737f427ab7a1f0287"\
                "a4d6f9e7eff341e882c4/script.sh"

        newuserdata = ""
        if 'userdata' in vs_config:
            newuserdata = vs_config['userdata']

        if 'script' in vs_config:
            regex = re.compile("^(http|https)://.*")
            result = regex.match(vs_config['script'])
            # if a url, just use it
            if result:
                vs_config['post_uri'] = vs_config['script']
            else:
                scripttext = open(vs_config['script'], "r").read()
                lib.save_state_script(sl_storage, containername,
                                      vs_config['script'],
                                      scripttext)
                newuserdata = newuserdata + \
                    "\nSCRIPTSTARTSCRIPTSTARTSCRIPTSTART\n" + scripttext

            del vs_config['script']

        vs_config['userdata'] = newuserdata

    if 'vlan' in groupdef:
        for vlanname in groupdef['vlan']:
            vlan = score['resources']['vlans'][vlanname]
            if vlan['type'] == 'public':
                vs_config['public_vlan'] = vlan['id']
            else:
                vs_config['private_vlan'] = vlan['id']

    if 'autoscale' in groupdef:
        autoscale_provision_vms(vs_config, groupname, groupdef, clustername,
                                score, client, sl_storage, configuration,
                                containername)
    else:
        manual_provision_vms(vs_config, groupname, groupdef, clustername,
                             score, client, sl_storage, configuration,
                             containername)
    lib.debug(groupdef)


def findPriceIdsForDatacenter(prices, datacenter):
    lib.debug(prices)
    lib.debug(datacenter)
    return lib.findInList(prices, 'locationGroupId',
                          datacenter['locationGroupIDs'])


def provision_vlans(score, client, sl_storage, containername, configuration):

    if 'vlans' not in score['resources']:
        return

    network_manager = SoftLayer.NetworkManager(client)
    existingvlans = network_manager.list_vlans(score['datacenter']['name'])

    omask = "id, keyName, prices"
    filter = {
        "items": {
            "keyName": {
                "operation": '~ *NETWORK_VLAN|*STATIC_PUBLIC_IP_ADDRESSES'
            }
        }
    }
    items = client['Product_Package'].getItems(id=0, mask=omask, filter=filter)

    for vlanname, vlan in score['resources']['vlans'].iteritems():
        vlan = normalize(vlan, score)
        score['resources']['vlans'][vlanname] = vlan
        # check if vlan exists already
        # lib.debug( "looking for "+vlanname+" in " + str(existingvlans))
        vlan_to_use = lib.findInList(existingvlans, 'name', vlanname)
        # if one doesnt exist, create a new one
        if not vlan_to_use:
            createoptions = {
                'name': vlanname,
                'packageId': 0,
                'location': score['datacenter']['id'],
                'quantity': 1,
                'endPointIpAddressId': 0,
                'endPointVlanId': 0,
                'prices': [],
                'complexType': 'SoftLayer_Container_Product_Order_Network_Vlan'
            }
            # key is PRIVATE_NETWORK_VLAN or PUBLIC_NETWORK_VLAN
            # first find prices for item and then find matching
            # price for datacenter
            keyname = "{}_NETWORK_VLAN".format(vlan['type'].upper())
            createoptions['prices'].append(
                findPriceIdsForDatacenter(
                    lib.findInList(items, 'keyName', keyname)['prices'],
                    score['datacenter']['id'])
            )
            # hard code 16 addresses
            createoptions['prices'].append(
                lib.findInList(lib.findInList(items,
                                              'keyName',
                                              '16_STATIC_PUBLIC_IP_ADDRESSES')
                               ['prices'],
                               'hourlyRecurringFee',
                               '0')
            )
            # lib.debug(json.dumps(createoptions))
            client['Product_Order'].placeOrder(createoptions)
            existingvlans = network_manager.list_vlans(
                                    score['datacenter']['name'])
            vlan_to_use = lib.findInList(existingvlans, 'name', vlanname)

        vlan['id'] = vlan_to_use['id']


def resolveDatacenter(client, dc):
    dc = lib.findInList(client['Location'].getDatacenters(mask="groups"),
                        'name', dc)
    lib.debug(json.dumps(dc))
    dc['locationGroupIDs'] = [(i['id']) for i in dc['groups'] if
                              i['locationGroupType']['name'] == 'PRICING']
    regionalGroups = [(i['id']) for i in dc['groups'] if
                      i['locationGroupType']['name'] == 'REGIONAL']
    if len(regionalGroups) != 0:
        dc['regionalGroupID'] = regionalGroups[0]
    del dc['groups']
    return dc


def waitForOrderCompletion(orderid, client):
    ''' returns id of billingitem for the finished order '''
    boclient = client['Billing_Order']
    mask = "orderTopLevelItems.billingItem.provisionTransaction"
    while True:
        order = boclient.getObject(id=orderid, mask=mask)
        lib.debug(order)
        # if transaction finished, break
        pt = 'provisionTransaction'
        otli = 'orderTopLevelItems'
        bi = 'billingItem'
        ts = 'transactionStatus'
        if otli in order and bi in order[otli][0]:
            if pt in order[otli][0][bi]:
                if order[otli][0][bi][pt][ts]["name"] == 'COMPLETE':
                    break
        # else retry in 30s
        lib.debug("sleeping 30s")
        time.sleep(30)

    return order['orderTopLevelItems'][0]['billingItem']['id']


def normalize(aDict, score):
    str_form = yaml.dump(aDict, default_flow_style=False)
    lib.debug(str_form)
    return yaml.load(get_templated_string(str_form, score))


def provision_loadbalancers(score, client, sl_storage, containername,
                            configuration):

    if 'loadbalancers' not in score['resources']:
        return

    lbmgr = SoftLayer.LoadBalancerManager(client)
    all_pkgs = lbmgr.get_lb_pkgs()
    # lib.debug([ (i['capacity']) for i in all_pkgs ])

    for lbname, lbconfig in score['resources']['loadbalancers'].iteritems():
        lbconfig = normalize(lbconfig, score)
        score['resources']['loadbalancers'][lbname] = lbconfig
        # first find lb packages with given connection support
        lbs_available = lib.findInList(all_pkgs,
                                       'capacity',
                                       str(lbconfig['connections']))
        if lbs_available is None:
            msg = 'no loadbalancer option found with capacity {}'
            raise Exception(msg.format(lbconfig['connections']))

        # if only one option available use it...
        #  otherwise do some more filtering
        if isinstance(lbs_available, list):
            # find the requested ssl support
            if 'ssl-offload' in lbconfig and lbconfig['ssl-offload']:
                lbs_available = lib.findInList(
                                        lbs_available, 'keyName', 'SSL',
                                        (lambda field, val: val in field))
            else:
                lbs_available = lib.findInList(
                                        lbs_available, 'keyName', 'SSL',
                                        (lambda field, v: v not in field))

            # lib.debug(lbs_available)

        # build a list to walk through
        if not isinstance(lbs_available, list):
            lbs_available = [lbs_available]

        # find prices for the current datacenter
        priceitems = []
        for lbitem in lbs_available:
            lib.debug(lbitem)
            priceitems.append(findPriceIdsForDatacenter(lbitem['prices'],
                                                        score['datacenter']))

        # sort the priceitems and pick the inexpensive one
        priceitems = sorted(priceitems, key=lambda p: float(p['recurringFee']))

        lib.debug(json.dumps(priceitems, indent=4))
        # do the create now
        lib.debug(priceitems[0])
        lib.debug(priceitems[0]['id'])
        order = lbmgr.add_local_lb(priceitems[0]['id'],
                                   score['datacenter']['name'])
        lib.debug(order)
        # wait for some time for order to be fulfilled
        billingItem = waitForOrderCompletion(order['orderId'], client)
        lib.debug(billingItem)
        # now list all load balancers
        all_lbs = client['Account'].getAdcLoadBalancers(mask='billingItem')
        provisioned_lb = lib.findInList(all_lbs, 'billingItem', billingItem,
                                        (lambda field,
                                            val: field['id'] == val))
        lib.debug(provisioned_lb)
        lib.save_state(sl_storage, containername,
                       "loadbalancers/{}/id".format(lbname),
                       provisioned_lb['id'])
        lbconfig['id'] = provisioned_lb['id']
        objtype = 'Network_Application_Delivery_Controller_LoadBalancer_'\
                  'Routing_Type'
        routing_types = client[objtype].getAllObjects()
        objtype = 'Network_Application_Delivery_Controller_LoadBalancer_'\
                  'Routing_Method'
        routing_methods = client[objtype].getAllObjects()
        for groupname, groupconfig in lbconfig['service-groups'].iteritems():
            lib.debug(groupconfig)
            routingtype = lib.findInList(routing_types, 'name',
                                         groupconfig['type'].upper())
            lib.debug(routingtype)
            routingmethod = lib.findInList(routing_methods, 'keyname',
                                           groupconfig['method'].upper())
            lib.debug(routingmethod)
            lib.debug(lbmgr.add_service_group(provisioned_lb['id'],
                                              groupconfig['allocation%'],
                                              groupconfig['port'],
                                              routingtype['id'],
                                              routingmethod['id']))
            # refresh lb info
            objtype = 'Network_Application_Delivery_Controller_LoadBalancer'\
                      '_VirtualIpAddress'
            lb = client[objtype].getObject(id=provisioned_lb['id'],
                                           mask="virtualServers.serviceGroups")
            groupconfig['id'] = lib.findInList(lb['virtualServers'], 'port',
                                               groupconfig['port'])['id']


def print_output(score):
    # check if no outputs requested
    if 'output' not in score:
        return

    output = get_templated_string(score['output']['template'], score)

    lib.debug(output)
    if 'result' in score['output']:
        with open(score['output']['result'], 'w') as f:
            f.write(output)
    else:
        print(output)


def get_nodes_till_leaf(branches, root):
    retval = []
    retval.append(root)
    if root in branches:
        children = branches[root]
        for child in children:
            retval = retval + get_nodes_till_leaf(branches, child)

    return retval


def order_groups(score):
    roots = []
    branches = {}
    for groupname, grpdef in score['resources']['serverinstances'].iteritems():
        if 'dependson' not in grpdef:
            roots.append(groupname)
        else:
            branchroot = grpdef['dependson']
            if branchroot in branches:
                branch = branches[branchroot]
            else:
                branch = []
                branches[branchroot] = branch
            branch.append(groupname)

    orderedlist = []
    for root in roots:
        orderedlist = orderedlist + get_nodes_till_leaf(branches, root)

    lib.debug(orderedlist)

    return orderedlist


def dns_update(score, client, sl_storage, containername, configuration):

    dns_m = SoftLayer.DNSManager(client)
    zones = dns_m.list_zones()
    score['resources']['dns'] = normalize(score['resources']['dns'], score)
    lib.debug(score['resources']['dns'])
    for domain, zonedef in score['resources']['dns'].iteritems():
        zone = lib.findInList(zones, 'name', domain)
        if not zone:
            raise Exception("no zone found for {}".format(domain))
        for entry in zonedef:
            group = entry.split(".")[1]
            lib.debug("reg vms in group {} to dns zone {}".format(group,
                                                                  domain))
            for vm in score['resources']['serverinstances'][group]['vms']:

                if not vm['domain'].endswith(domain):
                    sys.stderr.write("{}.{} not in zone {}\n".format(
                            vm['hostname'], vm['domain'], domain))
                    break

                # strip out root domain to register with DNS as a host
                #   record w/in the root domain

                record = "{}.{}".format(vm['hostname'], vm['domain'])
                record = record[:-(len(domain)+1)]
                lib.debug(dns_m.create_record(zone_id=zone['id'],
                                              record=record,
                                              record_type='A',
                                              data=vm['primaryIpAddress'],
                                              ttl=900))
                lib.save_state(sl_storage, containername,
                               "dns/{}/{}".format(domain, record),
                               vm['primaryIpAddress'])


def run_post_scripts(score, client, sl_storage, containername, configuration):
    score['post-scripts'] = normalize(score['post-scripts'], score)
    for script, args in score['post-scripts'].iteritems():
        rc, stdout, stderr = lib.run_command([script]+args)
        score['post-scripts'][script] = {'rc': rc, 'stdout': stdout,
                                         'stderr': stderr, 'args': args}


def backup_cleanup_scripts(sl_storage, containername, score):
    if 'cleanup-scripts' in score:
        for script, args in score['cleanup-scripts'].iteritems():
            scripttext = open(script).read()
            lib.save_state_script(sl_storage, containername, script,
                                  scripttext)


def provision(clustername, containername, score, configuration,
              client, sl_storage):

    backup_cleanup_scripts(sl_storage, containername, score)

    score['datacenter'] = resolveDatacenter(
            client,
            get_templated_string(score['datacenter'], score))

    provision_loadbalancers(score, client, sl_storage, containername,
                            configuration)

    provision_vlans(score, client, sl_storage, containername, configuration)

    orderedgroupnames = order_groups(score)

    for groupname in orderedgroupnames:
        groupdef = score['resources']['serverinstances'][groupname]
        groupdef = normalize(groupdef, score)
        score['resources']['serverinstances'][groupname] = groupdef
        deploy_group(groupname, groupdef, clustername, score, client,
                     sl_storage, configuration, containername)

    if 'dns' in score['resources']:
        dns_update(score, client, sl_storage, containername, configuration)

    if 'post-scripts' in score:
        run_post_scripts(score, client, sl_storage,
                         containername, configuration)

    print_output(score)


def validate_provision_parms_passed(scoretext, parmvalues):
    lib.debug(scoretext)
    regex = re.compile(r'{{\s*parameters\.([a-zA-Z0-9-_]+)', re.MULTILINE)
    parmnames = re.findall(regex, scoretext)
    lib.debug(parmnames)
    lib.debug(parmvalues)
    missingparms = []
    for parm in parmnames:
        if parm not in parmvalues:
            missingparms.append(parm)

    if len(missingparms):
        return "missing inputs: "+str(missingparms)

    return None
