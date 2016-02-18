#!/bin/sh -x

mount /dev/xvdh1 /mnt
userdatafile=/mnt/openstack/latest/user_data
sed -n '/SCRIPTSTARTSCRIPTSTARTSCRIPTSTART/q;p' $userdatafile > userdata
sed '1,/SCRIPTSTARTSCRIPTSTARTSCRIPTSTART/d' $userdatafile > scriptfile
if [ -s scriptfile ]
then
  chmod +x scriptfile
  script_to_run="./scriptfile"
else
  rm scriptfile
  script_to_run="coreos-cloudinit --from-file"
fi
umount /mnt
$script_to_run userdata >firstrun 2>&1