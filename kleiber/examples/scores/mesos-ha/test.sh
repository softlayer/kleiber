#!/bin/bash


# redirect stdout and error to our logfile
exec 1<&-
exec 2<&-
exec 1<>/root/startup.`date +"%m%d%y.%H%M"`
exec 2>&1

cat $1