#!/bin/bash

set -e

# Don't forget to build docker image:
# docker build -t mahjong-skill .

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

ls -la ./docker-out/
