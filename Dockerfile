FROM python:3.12.8-alpine3.21

WORKDIR /work/

COPY requirements.txt /work/
RUN pip install -r requirements.txt

COPY *.py /work/
COPY rating_impl/*.py /work/rating_impl/

# for local usage, commented for now
# COPY shared/players-data.csv /work/shared/

# for usage on pantheon server
COPY shared/pantheon_old_games.txt /work/shared/


ENTRYPOINT ./main.py \
           --model trueskill \
           --load-from-portal \
           --old-pantheon-games-load-file shared/pantheon_old_games.txt \
           --output-file /work/out/portal_export.json

# Usage:
# Build: docker build -t [tag] .
# Run: docker run --network=host --volume [local_path]:/work/out/ [tag]
# See results in [local_path]
