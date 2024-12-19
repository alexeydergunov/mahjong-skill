#!/bin/bash

set -e

#./main.py --load-from-portal --model elo > _elo.txt
./main.py --load-from-portal --model trueskill > _ts.txt
./main.py --load-from-portal --model openskill_pl > _os_pl.txt
./main.py --load-from-portal --model openskill_bt > _os_bt.txt

echo "All done"
