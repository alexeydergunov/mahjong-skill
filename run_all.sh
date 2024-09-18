#!/bin/bash

set -e

./main.py elo >_elo.txt
./main.py trueskill >_ts.txt
./main.py openskill_pl >_os_pl.txt
./main.py openskill_bt >_os_bt.txt

echo "All done"
