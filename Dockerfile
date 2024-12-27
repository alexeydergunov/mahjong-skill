FROM python:3.12.8-alpine3.21

WORKDIR /work/

COPY requirements.txt /work/
RUN pip install -r requirements.txt

COPY *.py /work/
COPY rating_impl/*.py /work/rating_impl/

ENTRYPOINT echo "Source files hashes:" && md5sum /work/*.py && md5sum /work/rating_impl/*.py && \
           echo "Calculating Trueskill..." && \
           ./main.py \
           --model trueskill \
           --load-from-portal \
           --old-pantheon-games-load-file /work/shared/pantheon_old_games.txt \
           --output-file /work/out/portal_export_trueskill.json > /work/out/log_trueskill.txt && \
           echo "Calculating online Trueskill..." && \
           ./main.py \
           --model trueskill \
           --online \
           --load-from-portal \
           --old-pantheon-games-load-file /work/shared/online_old_games.txt \
           --output-file /work/out/portal_export_trueskill_online.json > /work/out/log_trueskill_online.txt && \
           echo "Calculating Openskill (PL model)..." && \
           ./main.py \
           --model openskill_pl \
           --load-from-portal \
           --old-pantheon-games-load-file /work/shared/pantheon_old_games.txt \
           --output-file /work/out/portal_export_openskill_pl.json > /work/out/log_openskill_pl.txt && \
           echo "Calculating online Openskill (PL model)..." && \
           ./main.py \
           --model openskill_pl \
           --online \
           --load-from-portal \
           --old-pantheon-games-load-file /work/shared/online_old_games.txt \
           --output-file /work/out/portal_export_openskill_pl_online.json > /work/out/log_openskill_pl_online.txt && \
           echo "Done"

# Usage:
# Build: docker build -t [tag] .
# Run: docker run --network=host --volume ./shared/:/work/shared/ --volume ./docker-out/:/work/out/ [tag]
# See results in ./docker-out/
