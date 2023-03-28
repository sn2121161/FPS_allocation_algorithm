#!/bin/bash
cd $(dirname -- $0)

echo running "python unit test scripts" in $PWD
UnittestPyfiles=(unittest_*.py)
boarder=======================================================================
for pyfile in "${UnittestPyfiles[@]}"
do
    echo $boarder
    echo ======= Processing $pyfile
    python $pyfile
    if [ $? -eq 0 ]
       then
           echo $boarder
    else
        echo ======= Check $(readlink -f $pyfile)
        echo ''
        exit
    fi
    echo ''
done
