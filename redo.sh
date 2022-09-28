#!/bin/bash

set -euo pipefail

DIR=`mktemp -d`
echo $DIR
python main.py $DIR 
ls $DIR
cp README.md $DIR
cat $DIR/README.md
cat /tmp/nftp.log
rm $DIR/README.md