#!/usr/bin/python

import inspect

import SoftLayer
import sys
import subprocess
import Queue
import thread
import os
import shutil
import hashlib
import tempfile
import stat

doDebug = 'quiet'


def set_debug(val):
    global doDebug
    doDebug = val


def debug(str):
    global doDebug
    if doDebug == 'quiet':
        return
    elif doDebug == 'progress':
        sys.stderr.write(".")
        sys.stderr.flush()
        return

    f = inspect.currentframe().f_back
    fname = inspect.getframeinfo(f).filename
    sys.stderr.write("\033[1;31m{}:{}:\033[1;m{}\n".format(
            fname, f.f_lineno, str))


def save_state(sl_storage, containername, path, value):
    if sl_storage['type'] == 'swift':
        sl_storage['client'][containername][path].create()
        sl_storage['client'][containername][path].send(str(value))
    else:
        fname = sl_storage['directory']+containername+"/"+path
        dirname = os.path.dirname(fname)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        with open(fname, 'w') as f:
            f.write(str(value))


def save_state_script(sl_storage, containername, scriptname, scripttext):
    sha1 = hashlib.sha1(scriptname).hexdigest()
    save_state(sl_storage, containername, "scripts/{}/name".format(sha1),
               scriptname)
    save_state(sl_storage, containername, "scripts/{}/text".format(sha1),
               scripttext)


def state_containers(sl_storage):
    if sl_storage['type'] == 'swift':
        return [str(e.name) for e in sl_storage['client'].containers()]
    else:
        if os.path.exists(sl_storage['directory']):
            return filter(lambda x: os.path.isdir(sl_storage['directory']+x),
                          os.listdir(sl_storage['directory']))
        else:
            return []


def state_container_clean(sl_storage, containername):
    if sl_storage['type'] == 'swift':
        debug("deleting container data: {}".format(
            sl_storage['client'][containername].delete_all_objects()))
        debug("deleting container {}: {}".format(
            containername,
            sl_storage['client'][containername].delete(recursive=True)))
    else:
        debug("deleting container {}: {}".format(
                    containername,
                    shutil.rmtree(sl_storage['directory']+containername)))


def state_container_create(sl_storage, containername):
    if sl_storage['type'] == 'swift':
        debug(sl_storage['client'][containername].create())
    else:
        debug(os.makedirs(sl_storage['directory']+containername))


def set_value(dictionary, names, value):
    field = names[0]
    del names[0]  # delete the first element

    # if we are at the leaf, set the value
    if len(names) == 0:
        dictionary[field] = value
    else:  # not at leaf, so browse down

        # is there a branch down this path, go down, else create one

        if field not in dictionary:
            dictionary[field] = {}

        dict_at_level = dictionary[field]
        set_value(dict_at_level, names, value)


def get_resources(sl_storage, containername):
    retval = {}
    if sl_storage['type'] == 'swift':
        for x in sl_storage['client'][containername].objects():
            name = x.name
            names = x.name.split('/')
            text = x.read()
            set_value(retval, names, text)
    else:
        containerdir = sl_storage['directory']+containername
        striplen = containerdir.__len__() + 1
        for root, d, files in os.walk(containerdir, topdown=False):
            for name in files:
                #  get full name as dir+name
                fullname = os.path.join(root, name)
                #  remove the common dir part (~/.kleiber-data...)
                #  split using the os separator (/ or \)
                names = fullname[striplen:].split(os.sep)
                with open(fullname, 'r') as f:
                    text = f.read()
                    set_value(retval, names, text)

    return retval


def findInList_match_item(field, val):
    return field == val


def findInList_match_items(field, values):
    return field in values


def findInList(aList, keyname, value, matchfunc=None):
    # if no user provided match func
    if not matchfunc:
        # if value is a list, look for matching any value in the list
        if isinstance(value, list):
            matchfunc = findInList_match_items
        else:
            matchfunc = findInList_match_item

    # if item in aList has the keyname and matchfunc returns true, collect it
    retval = filter(lambda item: keyname in item and
                    matchfunc(item[keyname], value), aList)

    number = len(retval)
    if number == 0:
        return None
    elif number == 1:
        return retval[0]
    else:
        return retval


def sl_retry(f, *args):
    tries = 0
    while tries < 3:
        try:
            retval = f(*args)
            return retval
        except SoftLayer.exceptions.SoftLayerAPIError as e:
            debug("  create inst exception: code: {}, fault str: {} ".format(
                e.faultCode, e.faultString))
        tries = tries + 1


def __readFd(key, fd, q):
    # read contents of a file descriptor
    # designed to be called in a thread. will put result on parameter q

    retstring = ""
    while True:
        line = fd.readline()
        if not line:
            break
        debug(key+":"+line.rstrip())
        retstring = retstring + line

    q.put(retstring)


def run_script_text(text, args):
    f = tempfile.NamedTemporaryFile(delete=False)
    f.write(text)
    f.close()
    os.chmod(f.name, stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR)
    rc, stdout, stderr = run_command([f.name]+args)
    #  os.unlink(f.name)
    return rc, stdout, stderr


def run_command(commandAndArgArray):

    debug(commandAndArgArray)

    currenv = os.environ.copy()

    process = subprocess.Popen(commandAndArgArray,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               env=currenv)

    # start threads to read stdout and err. could be a long process
    q = Queue.Queue()  # a queue to read stdout on
    thread.start_new_thread(__readFd, ("stdout:", process.stdout, q))
    q1 = Queue.Queue()  # a queue to read stderr on
    thread.start_new_thread(__readFd, ("stderr:", process.stderr, q1))

    process.wait()  # wait for the process to finish
    stdoutstring = q.get()  # wait till stdout is drained
    stderrstring = q1.get()  # wait till stderr is drained

    return process.returncode, stdoutstring, stderrstring


def error(message):
    sys.stderr.write(message)
    sys.stderr.write("\n")

    sys.exit(1)
