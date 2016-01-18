#!/usr/bin/python

"""kleiber cluster director

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

"""

from docopt import docopt
import SoftLayer
import object_storage
from provision import provision, validate_provision_parms_passed, normalize
import json
import yaml
import logging
import os
import traceback

from lib import state_containers, findInList, set_value, debug, DebugLevel
from lib import save_state, state_container_create, state_container_clean
from lib import get_resources, run_script_text, error

"kleiber module"


logging.captureWarnings(True)


def clusters(sl_storage):
    return state_containers(sl_storage)


def clean_dns(resources, client):
    if 'dns' not in resources:
        return

    dns_m = SoftLayer.DNSManager(client)
    allzones = dns_m.list_zones()
    for domain, entries in resources['dns'].iteritems():
        zone = findInList(allzones, 'name', domain)
        if not zone:
            print('no zone for {} found!!!'.format(domain))
            continue

        records = dns_m.get_records(zone['id'])
        for hostname, ip in entries.iteritems():
            record = findInList(records, 'host', hostname)
            print("deleting dns record for {} : {}".format(
                hostname, dns_m.delete_record(record['id'])))


def delete_loadbalancers(resources, client):
    if 'loadbalancers' not in resources:
        return

    lbmgr = SoftLayer.LoadBalancerManager(client)
    for lb, lbinfo in resources['loadbalancers'].iteritems():
        print("deleting loadbalancer {}: {}".format(
          lb, lbmgr.cancel_lb(lbinfo['id'])))


def status_group(resources, groupname, filter, filteredresources,
                 vs_manager, client):
    group = resources['serverinstances'][groupname]

    # if manually provisioned group
    if 'vms' in group:
        groupvms = group['vms']

        to_fill = []
        if filter == 'all':
            to_fill = groupvms.keys()
        elif filter in groupvms:  # if our vm is here, add it
            to_fill = [filter]

        # if any vms to lookup, lookup
        for hostname in to_fill:
            try:
                host = groupvms[hostname]
                vs = vs_manager.get_instance(host['id'])
                del vs['billingItem']
                host.update(vs)
            except Exception, e:
                host['error'] = str(e)

            set_value(filteredresources,
                      ['serverinstances', groupname, 'vms', hostname],
                      host)

    elif 'autoscale' in group:  # autoscale
        if filter == all:  # we have nothing to filter inside..all/none
            autoscalegrp = group['autoscale']
            msk = "virtualGuestMembers.virtualGuest.primaryIpAddress"
            set_value(filteredresources,
                      ['serverinstances', group, 'autoscale'],
                      client['Scale_Group'].getObject(id=autoscalegrp['id'],
                                                      mask=msk))


def status_serverinstances(resources, filter, filteredresources, vs_manager,
                           client):

    if 'serverinstances' not in resources:
        return

    serverinstances = resources['serverinstances']

    # does it match groupname, then return all in that group
    if filter in serverinstances:
        status_group(resources, filter, 'all',
                     filteredresources, vs_manager, client)
    else:  # keep looking
        for group in serverinstances:
            status_group(resources, group, filter, filteredresources,
                         vs_manager, client)


def deletable(resources):
    for k, v in resources.iteritems():
        # if we have an 'id' field, there is a SL resource..so fail
        if k == 'id':
            return False
        else:
            # if dictionary, check dict to see if it has something usefull
            if type(v) is dict:
                if not deletable(v):
                    return False
    return True


def do_create(args, client, sl_storage, configuration):

    if args['-v']:
        DebugLevel.set_level('verbose')
    else:
        DebugLevel.set_level('progress')

    containername = args['<clustername>']
    if args['<clustername>'] in clusters(sl_storage):
        error('cluster {} already exists'.format(args['<clustername>']))

    scoretext = open(args['<score.yaml>'], 'r').read()
    score = yaml.load(scoretext)

    score['clustername'] = args['<clustername>']
    dirname = os.path.dirname(args['<score.yaml>'])
    if dirname == "":
        dirname = "."
    score['path'] = dirname+"/"

    # setup environment for scripts in score to run properly. Change to
    #  the score directory and add . to the path
    os.chdir(score['path'])
    os.environ['PATH'] = ':'.join([os.environ['PATH'], './'])

    if 'parameters' in score:
        parmvalues = score['parameters']
    else:
        parmvalues = {}

    parameters = args['<key=value>']
    for param in parameters:
        splits = param.split('=', 1)
        if len(splits) != 2:
            raise Exception("{} is not a key=value pair".format(param))
        parmvalues[splits[0]] = splits[1]
    score['parameters'] = parmvalues
    scoretext = yaml.dump(score, indent=4)

    msg = validate_provision_parms_passed(scoretext, parmvalues)
    debug(msg)
    if msg:
        error(msg)

    state_container_create(sl_storage, containername)
    try:
        # save score for later operations
        save_state(sl_storage, containername, 'score', scoretext)
        provision(args['<clustername>'], containername, score,
                  configuration, client, sl_storage)
    except Exception, e:
        debug(traceback.format_exc())
        resources = get_resources(sl_storage, containername)
        del resources['score']
        if deletable(resources):
            state_container_clean(sl_storage, containername)
        error(e.message)


def do_status(args, client, sl_storage, configuration):
    containername = args['<clustername>']
    if containername in clusters(sl_storage):

        vs_manager = SoftLayer.VSManager(client)
        resources = get_resources(sl_storage, containername)
        if 'score' in resources:
            del resources['score']

        if args['<resourcename>']:
            resourcename = args['<resourcename>']
            filteredresources = {}
            status_serverinstances(resources, resourcename,
                                   filteredresources, vs_manager, client)
            resources = filteredresources
        print json.dumps(resources, indent=4, sort_keys=True)
    else:
        error('cluster does not exist')


def do_delete(args, client, sl_storage, configuration):
    if args['-v']:
        DebugLevel.set_level('verbose')
    containername = args['<clustername>']
    if containername in clusters(sl_storage):
        resources = get_resources(sl_storage, containername)

        score = yaml.load(resources['score'])
        if 'cleanup-scripts' in score and 'scripts' in resources:
            score['cleanup-scripts'] = normalize(score['cleanup-scripts'],
                                                 score)
            for script, args in score['cleanup-scripts'].iteritems():
                for id, data in resources['scripts'].iteritems():
                    if data['name'] == script:
                        print 'executing cleanup script {}'.format(script)
                        rc, out, err = run_script_text(data['text'], args)
                        if rc != 0:
                            print out
                            print err

        if 'serverinstances' in resources:
            vs_manager = SoftLayer.VSManager(client)

            for grpname, group in resources['serverinstances'].iteritems():
                print 'working on '+grpname
                if 'vms' in group:
                    for hostname, vm in group['vms'].iteritems():
                        try:
                            print "deleting vm {}({}): {}".format(
                                hostname, vm['id'],
                                vs_manager.cancel_instance(vm['id']))
                        except Exception, e:
                            print "error deleting "+str(e)

                elif 'autoscale' in group:
                    try:
                        autoscalegrp = client['Scale_Group'].getObject(
                                      id=group['autoscale']['id'])
                        if not autoscalegrp['suspendedFlag']:
                            client['Scale_Group'].suspend(
                                                id=autoscalegrp['id'])
                        print "deleting autoscale group {}: {}".format(
                                  autoscalegrp,
                                  client['Scale_Group'].forceDeleteObject(
                                      id=autoscalegrp['id']))
                    except Exception, e:
                        print "error deleting autoscale group "
                        print grpname
                        print str(e)

        delete_loadbalancers(resources, client)
        clean_dns(resources, client)

        state_container_clean(sl_storage, containername)
    else:
        error('cluster does not exist')


def main():
    args = docopt(__doc__, version='kleiber cluster director  0.1')
    try:
        configuration = yaml.load(
                open(os.environ['HOME']+'/.kleiber', 'r').read())
    except IOError:
        error('kleiber configuration file {} not found'.format(
                    os.environ['HOME']+'/.kleiber'))

    client = SoftLayer.create_client_from_env(
                          username=configuration['username'],
                          api_key=configuration['api_key'])

    if 'obj_store' not in configuration:
        if 'local_store' in configuration:
            directory = configuration['local_store']
        else:
            directory = os.path.expanduser("~/.kleiber-data")
        sl_storage = {
            'type': 'local',
            'directory': os.path.expanduser(directory+"/containers/")
        }
    else:
        sl_storage = {
            'type': 'swift',
            'client': object_storage.get_client(
              configuration['obj_store']['name']+':'+configuration['username'],
              configuration['api_key'],
              datacenter=configuration['obj_store']['datacenter'])
        }

    if args['create']:
        do_create(args, client, sl_storage, configuration)
    elif args['status']:
        do_status(args, client, sl_storage, configuration)
    elif args['delete']:
        do_delete(args, client, sl_storage, configuration)
    elif args['list']:
        print clusters(sl_storage)

if __name__ == '__main__':
    main()
