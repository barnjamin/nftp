#!/bin/bash

DIR=`mktemp -d`
echo $DIR
python main.py $DIR 
ls $DIR
cat $DIR/gotcha.mp3
cat /tmp/nftp.log