FROM python:3.12.8-alpine3.21

WORKDIR /work/

# jq to output Russian letters
RUN apk --no-cache add curl jq

COPY requirements.txt /work/
RUN pip install -r requirements.txt

COPY *.py /work/
COPY rating_impl/*.py /work/rating_impl/

ENTRYPOINT echo "Files hashes:" && md5sum /work/*.py && md5sum /work/rating_impl/*.py && \
           md5sum /work/shared/players_mapping.py && md5sum /work/shared/*_old_games.txt && \
           echo "Loading portal tournaments..." && \
           curl -X GET 'https://mahjong.click/api/v0/tournaments/finished/' | jq > /work/out/portal_tournaments.json && \
           ls -la /work/out/portal_tournaments.json && \
           echo "Calculating Trueskill..." && \
           ./main.py \
           --model trueskill \
           --event-list-file /work/out/portal_tournaments.json \
           --old-pantheon-games-load-file /work/shared/pantheon_old_games.txt \
           --output-file /work/out/portal_export_trueskill.json > /work/out/log_trueskill.txt && \
           echo "Calculating online Trueskill..." && \
           ./main.py \
           --model trueskill \
           --online \
           --event-list-file /work/out/portal_tournaments.json \
           --old-pantheon-games-load-file /work/shared/online_old_games.txt \
           --output-file /work/out/portal_export_trueskill_online.json > /work/out/log_trueskill_online.txt && \
           echo "Calculating Openskill (PL model)..." && \
           ./main.py \
           --model openskill_pl \
           --event-list-file /work/out/portal_tournaments.json \
           --old-pantheon-games-load-file /work/shared/pantheon_old_games.txt \
           --output-file /work/out/portal_export_openskill_pl.json > /work/out/log_openskill_pl.txt && \
           echo "Calculating online Openskill (PL model)..." && \
           ./main.py \
           --model openskill_pl \
           --online \
           --event-list-file /work/out/portal_tournaments.json \
           --old-pantheon-games-load-file /work/shared/online_old_games.txt \
           --output-file /work/out/portal_export_openskill_pl_online.json > /work/out/log_openskill_pl_online.txt && \
           echo "Done"

# Usage:
# Build: docker build -t [tag] .
# Run: docker run --network=host --volume ./shared/:/work/shared/ --volume ./docker-out/:/work/out/ [tag]
# See results in ./docker-out/
