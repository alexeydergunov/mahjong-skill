FROM python:3.12-slim-bookworm

WORKDIR /work/

# Install postgres client, here I had to inline $(lsb_release -cs)
RUN apt update && \
    apt install -y curl ca-certificates && \
    install -d /usr/share/postgresql-common/pgdg && \
    curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc --fail https://www.postgresql.org/media/keys/ACCC4CF8.asc && \
    sh -c 'echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list' && \
    apt update && \
    apt install -y postgresql-client-16

COPY requirements.txt /work/
RUN pip install -r requirements.txt

COPY *.py /work/
COPY rating_impl/*.py /work/rating_impl/

# for local usage, commented for now
# COPY shared/players-data.csv /work/shared/

# for usage on pantheon server
COPY shared/pantheon_old_games.txt /work/shared/


ENTRYPOINT export TIME=`date +%s` && \
           ./main.py \
           --model trueskill \
           --load-from-portal \
           --old-pantheon-games-load-file shared/pantheon_old_games.txt \
           --output-file /work/out/portal_export_$TIME.json

# Usage:
# Build: docker build -t [tag] .
# Run: docker run --network=host --volume [local_path]:/work/out/ [tag]
# See results in [local_path]
