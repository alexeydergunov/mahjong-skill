#!/bin/bash

set -e

./main.py \
  --model trueskill \
  --old-pantheon-games-dump-file shared/pantheon_old_games.txt \
  --new-pantheon-games-dump-file shared/pantheon_new_games.txt

./main.py \
  --online \
  --model trueskill \
  --old-pantheon-games-dump-file shared/online_old_games.txt \
  --new-pantheon-games-dump-file shared/online_new_games.txt

echo "Done"
