# Brain Intake: the machinery for intake, analysis, search and answers, in one image.
# The vault is not in the image: it is mounted at /vault when the container runs.
# Ollama is not in the image either: it stays on the Mac, where it can use the Apple GPU.

# Pinned by digest, so a rebuild uses exactly this base.
FROM python:3.13-slim@sha256:2d44738ebf4ce5f63b9d9ea871e9c7cfdc0426f7b0c97cac915fd88ded1d86bb

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

# git: saves and promotions are commits, checked by the vault's own gate.
# openssh-client: ssh-keygen signs those commits with Brain Intake's own key.
# antiword: old binary Word (.doc) files. tzdata: note dates in your time zone, not UTC.
# The digest above fixes the Debian release; within it, these packages take its current security updates.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git openssh-client antiword tzdata \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --require-hashes --only-binary=:all: -r /tmp/requirements.txt && rm /tmp/requirements.txt

COPY app/ /app/
COPY relay/relay.py /relay/relay.py
RUN python -m compileall -q /app /relay && chmod -R a+rX,a-w /app /relay

# An account for your Mac user ID, so the app writes files as you and ssh-keygen can sign as someone.
ARG BRAIN_UID=501
ARG BRAIN_GID=20
RUN (getent group "$BRAIN_GID" >/dev/null || groupadd -g "$BRAIN_GID" brain) \
 && useradd -u "$BRAIN_UID" -g "$BRAIN_GID" -M -d /tmp -s /usr/sbin/nologin -c "Brain Intake" brain

ENV BRAIN_IN_CONTAINER=1 \
    BRAIN_VAULT=/vault \
    BRAIN_STATE=/state \
    BRAIN_PYTHON=/usr/local/bin/python3 \
    OLLAMA_URL=http://ollama.internal:11434 \
    HOME=/tmp

WORKDIR /app
USER 65534:65534
EXPOSE 8765
CMD ["python", "/app/server.py"]
