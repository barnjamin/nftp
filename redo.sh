#!/bin/bash

DIR=/tmp/demo
if [ -d $DIR ]; then
    umount $DIR 
    rm -rf $DIR
fi
mkdir $DIR 
python nftp.py $DIR 
