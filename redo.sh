#!/bin/bash

set -euo pipefail

export DIR=`mktemp -d`
export LOG=/tmp/nftp.log

# /home/ben/sandbox/sandbox reset
# python algorand/client.py

echo $DIR

echo "" 

echo "--mnt--"
python main.py --algorand $DIR 
cat $LOG
echo "" > $LOG
echo "--mnt--"

echo ""

echo "--ls--"
ls $DIR
cat $LOG
echo "" > $LOG
echo "--ls--"
if [ -f $DIR/README.md ]; then
    echo "--rm--"
    rm $DIR/README.md
    cat $LOG
    echo "" > $LOG
    echo "--rm--"
fi


echo ""

echo "--cp--"

cat $LOG
cp README.md $DIR
cat $LOG
echo "" > $LOG
echo "--cp--"

echo ""

echo "--cat--"
cat $DIR/README.md
cat $LOG
echo "" > $LOG
echo "--cat--"

echo ""

echo "--rm--"
rm $DIR/README.md
cat $LOG
echo "" > $LOG
echo "--rm--"

echo ""

echo "--cp--"
cp data.mp3 $DIR
cat $LOG
echo "" > $LOG
echo "--cp--"

echo ""

echo "--cat--"
cat $DIR/data.mp3
cat $LOG
echo "" > $LOG
echo "--cat--"

echo ""

echo $DIR
