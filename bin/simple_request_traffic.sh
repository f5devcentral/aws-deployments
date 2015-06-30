#!/bin/bash
for i in `seq 1 1000`;
  do
    curl http://$1 > /dev/null 2>&1 
  done
