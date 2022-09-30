#!/bin/bash

#set -euo pipefail

export DIR=`mktemp -d`
export LOG=/tmp/nftp.log

/home/ben/sandbox/sandbox reset

python algorand/contract.py

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

echo "cp--"
cp data.mp3 $DIR
cat $LOG
echo "" > $LOG
echo "cp--"

echo "cat--"
cat $DIR/data.mp3 | wc -c
cat $LOG
echo "" > $LOG
echo "cat--"

echo $DIR