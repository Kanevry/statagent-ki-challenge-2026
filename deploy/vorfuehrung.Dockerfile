# Vorführ-Instanz: das App-Image plus git, damit die Freigabe ihren Commit schreiben kann. Die öffentliche Demo bleibt
# ohne git (deploy/app.Dockerfile). Gebaut von scripts/vorfuehrung.sh ohne Kontext aus dem Tag des Basis-Images.
FROM ki-challenge-vorfuehrung:basis
USER root
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
# Einhängepunkte; der Inhalt kommt aus dem Compose-Volume bzw. tmpfs
RUN mkdir -p /app/.git /app/uc3/erzeugt
USER app
