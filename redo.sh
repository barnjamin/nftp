#!/bin/bash

DIR=`mktemp -d`
echo $DIR
#if [ -d $DIR ]; then
#    umount $DIR 
#    rm -rf $DIR
#fi
#mkdir $DIR 
python nftp.py $DIR 
ls $DIR
cat $DIR/gotcha.mp3
cat /tmp/003.log