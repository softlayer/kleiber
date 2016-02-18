#!/usr/bin/python

"""library functions to use in kleiber.py and provision.py

"""

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


class DebugLevel:
    level = 'quiet'

    @classmethod
    def set_level(cls, val):
        """Set debug level to provided value

        :param string val: one of quiet/progress/verbose
        """

        cls.level = val


def debug(str):
    """Print a debug message to stderr based on current debug level
    if quiet, no output
    if progress, print a .
    if verbose, print caller's filename:linenumber and str
    """
    if DebugLevel.level == 'quiet':
        return
    elif DebugLevel.level == 'progress':
        sys.stderr.write(".")
        sys.stderr.flush()
        return

    f = inspect.currentframe().f_back
    fname = inspect.getframeinfo(f).filename
    sys.stderr.write("\033[1;31m{}:{}:\033[1;m{}\n".format(
        fname, f.f_lineno, str))


def save_state(sl_storage, containername, path, value):
    """save a value in the state store

    :param object sl_storage: state store definition - can point to
            objectstorage/locally mounted filesystem
    :param string containername: folder in store for current deployment
    :param string path: key to save the value under, can contain '/'
    :param string value: value to save
    """
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
    """helper around save_state to save a full script in store.
       scripts are stored in scripts/scriptname key"""
    sha1 = hashlib.sha1(scriptname).hexdigest()
    save_state(sl_storage, containername, "scripts/{}/name".format(sha1),
               scriptname)
    save_state(sl_storage, containername, "scripts/{}/text".format(sha1),
               scripttext)


def state_containers(sl_storage):
    """ return a list of all folders in store

    :param object sl_storage: backend definition of store - can point
                to objectstore/locally mounted filesystem
    """
    if sl_storage['type'] == 'swift':
        return [str(e.name) for e in sl_storage['client'].containers()]
    else:
        if os.path.exists(sl_storage['directory']):
            return filter(lambda x: os.path.isdir(sl_storage['directory']+x),
                          os.listdir(sl_storage['directory']))
        else:
            return []


def state_container_clean(sl_storage, containername):
    """ Delete a folder from the state store

    :param object sl_storage: backend definition of store - can point to
            objectstore/locally mounted filesystem
    :param string containername: folder in store to delete
    """
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
    """ create a new folder to represent a deployment"""
    if sl_storage['type'] == 'swift':
        debug(sl_storage['client'][containername].create())
    else:
        debug(os.makedirs(sl_storage['directory']+containername))


def set_value(dictionary, names, value):
    """ create a dictionary of dictionaries and set a value

    :param dict dictionary: create in this dictionary
    :param list names: a list of fields
    :param string value: set this value

    This function creates a dictionary of dictionaries.
    eg: lets say its called the first time as
    dictionary = {}
    names = [servers,server1,id]
    value = 1234

    after the call, dictionary would be
    {
        servers : { server1 : { id : 1234 } }
    }

    continuing on, if its called on the same dictionary with the parameters
    names = [servers,server1,hostname]
    value = myserver

    after the call, dictionary would be
    {
        servers: {
            server1 : {
                id : 1234,
                hostname: myserver
            }
        }
    }

    """
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
    """ get a multi level dictionary that represents the values in the cluster

    eg: save_state(sl_storage,containername,'servers/server1/id','1234')
    would be returned as { servers : { server1 : { id: 1234 }}}

    :param object sl_storage: backend definition - can point to
                objectstorage/locally mounted filesystem
    :param string containername: folder in store for deployment
    """

    retval = {}
    if sl_storage['type'] == 'swift':
        for x in sl_storage['client'][containername].objects():
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
    """helper for findInList - checks if the 2 input strings match

    :param object field: any value
    :param object val: value to check against
    """
    return field == val


def findInList_match_items(field, values):
    """ helper for findInList - checks if the input fieed occurs
            in a list of values

    :param object field: any value
    :param list values: list of values to check in
    """
    return field in values


def findInList(aList, keyname, value, matchfunc=None):
    """search for an object in a list

    :param list aList: the list of dicts to search through
    :param string keyname: match the value of this key
    :param object value: match against this value
    :param lambda matchfunc: by default, this will do a equals
            comparison of dict[keyname] against value, if some
            other comparison is needed, provide function to use
            if matchfunc returns true, the dict is selected
    :returns: none, if no matching object found
              a single object, if one matching object found
              a list, if more than one matching object found
    """

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
    """ sometimes sl apis return wierd messages, catch them and retry the call
        upto 3 times before failing

    :param function f: sl function to call
    :param dict args: arguments to sl call
    """
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
    """
    read contents of a file descriptor to end and put it on a queue

    :param string key: prepend each line with key
    :param fd: file descriptor to read from - file/socket/stdout/stderr etc
    :param queue q: put the result on this queue
    """

    retstring = ""
    while True:
        line = fd.readline()
        if not line:
            break
        debug(key+":"+line.rstrip())
        retstring = retstring + line

    q.put(retstring)


def run_script_text(text, args):
    """ run some code with the given arguments and return the output

    :param string text: script content
    :param list args: arguments to script
    :returns: returncode, stdout text, stderr text
    """
    f = tempfile.NamedTemporaryFile(delete=False)
    f.write(text)
    f.close()
    os.chmod(f.name, stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR)
    rc, stdout, stderr = run_command([f.name]+args)
    #  os.unlink(f.name)
    return rc, stdout, stderr


def run_command(commandAndArgArray):
    """ run a command and return the output
    :param list commandAndArgArray: item[0] is the command
                item[1..] are the arguments
    :returns: return code, stdout text, stderr text
    """

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
    """ fail after printing the given message"""
    sys.stderr.write(message)
    sys.stderr.write("\n")

    sys.exit(1)
