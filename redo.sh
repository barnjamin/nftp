#!/bin/bash

#set -euo pipefail

DIR=`mktemp -d`
LOG=/tmp/nftp.log

echo $DIR

echo "mnt--"
python main.py $DIR 
cat $LOG
echo "" > $LOG
echo "mnt--"
echo "ls--"
ls $DIR
cat $LOG
echo "" > $LOG
echo "ls--"
if [ -f $DIR/README.md ]; then
    echo "rm--"
    rm $DIR/README.md
    cat $LOG
    echo "" > $LOG
    echo "rm--"
fi

echo "cp--"
cp README.md $DIR
cat $LOG
echo "" > $LOG
echo "cp--"

echo "cat--"
cat $DIR/README.md
cat $LOG
echo "" > $LOG
echo "cat--"

echo $DIR