#!/bin/bash 

if [ -f /.dockerenv ]; then
    Xvfb :1 &
    export xvfb_pid=$!
    export DISPLAY=:1
    wine $@
    kill $xvfb_pid
    rm -Rf /tmp/.X1-lock
else
    wine $@
fi