#!/bin/bash

set -e

# Don't forget to build docker image:
# docker build -t mahjong-skill .

echo "Running 'git pull' on repository mahjong-skill-private-files..."
cd ../mahjong-skill-private-files
git pull
cd ../mahjong-skill

echo "Copying files from repository mahjong-skill-private-files to directory 'shared'..."
cp ../mahjong-skill-private-files/players_mapping.py ./shared/players_mapping.py
cp ../mahjong-skill-private-files/shared/online_old_games.txt ./shared/online_old_games.txt
cp ../mahjong-skill-private-files/shared/pantheon_old_games.txt ./shared/pantheon_old_games.txt

echo "Running docker..."

docker run \
  -e MIMIR_USER=mimir \
  -e MIMIR_PASSWORD=pgpass \
  -e MIMIR_DB_NAME=mimir \
  -e MIMIR_HOST=db.pantheon.internal \
  -e MIMIR_PORT=5432 \
  -e FREY_USER=frey \
  -e FREY_PASSWORD=pgpass \
  -e FREY_DB_NAME=frey \
  -e FREY_HOST=db.pantheon.internal \
  -e FREY_PORT=5432 \
  --network=pantheon_internal_net \
  --volume ./shared/:/work/shared/ \
  --volume ./docker-out/:/work/out/ \
  mahjong-skill

echo "Docker run completed"

echo "Files in directory 'docker-out':"
ls -la ./docker-out/
