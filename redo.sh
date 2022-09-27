#!/bin/bash

DIR=/tmp/wat
umount $DIR 
rm -rf $DIR
mkdir $DIR 
python nftp.py $DIR 
