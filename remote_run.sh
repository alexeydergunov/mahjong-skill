#!/bin/bash

set -e

# Don't forget to build docker image:
# docker build -t mahjong-skill .

# Search private files repository in parent directory
CURRENT_DIR=`pwd`
echo "Current dir: $CURRENT_DIR"
FILEPATH=$(find .. -name "pantheon_new_games__2024_12_02.txt")
if [ -z $FILEPATH ]; then
  echo "Repository mahjong-skill-private-files is not found"
  exit 1
else
  PRIVATE_DIR=$(dirname $(dirname $(realpath $FILEPATH)))
  echo "Repository mahjong-skill-private-files directory: $PRIVATE_DIR"
fi

echo "Running 'git pull' on repository mahjong-skill-private-files..."
cd $PRIVATE_DIR
git pull
cd $CURRENT_DIR

echo "Copying files from repository mahjong-skill-private-files to directory 'shared'..."
cp $PRIVATE_DIR/players_mapping.py ./shared/players_mapping.py
cp $PRIVATE_DIR/shared/online_old_games.txt ./shared/online_old_games.txt
cp $PRIVATE_DIR/shared/pantheon_old_games.txt ./shared/pantheon_old_games.txt

echo "Running docker..."

docker run \
  -e MIMIR_USER=mimir \
  -e MIMIR_PASSWORD=pgpass \
  -e MIMIR_DB_NAME=mimir \
  -e MIMIR_HOST=db.pantheon.internal \
  -e MIMIR_PORT=5432 \
  -e FREY_USER=frey2 \
  -e FREY_PASSWORD=pgpass \
  -e FREY_DB_NAME=frey2 \
  -e FREY_HOST=db.pantheon.internal \
  -e FREY_PORT=5432 \
  --network=pantheon_internal_net \
  --volume ./shared/:/work/shared/ \
  --volume ./docker-out/:/work/out/ \
  mahjong-skill

echo "Docker run completed"

echo "Files in directory 'docker-out':"
ls -la ./docker-out/
