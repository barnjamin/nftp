#!/bin/bash

#set -euo pipefail

DIR=`mktemp -d`
echo $DIR
python main.py $DIR 
ls $DIR
if [ -f $DIR/README.md ]; then
    rm $DIR/README.md
fi
cp README.md $DIR
cat $DIR/README.md
cat /tmp/nftp.log
#rm $DIR/README.md