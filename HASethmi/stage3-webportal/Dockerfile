# VAULT-03 - Nexora Bank internal document portal
# RaidTheRoot (RTR) Stage 3 challenge container
#
# INTENTIONALLY VULNERABLE. Isolated on stage3-net, no host volumes,
# unprivileged, resource limited. Built for this CTF only.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /opt/portal

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /opt/portal/

# Run as a non-root user: the challenge is a web authorization flaw,
# not a container escape.
RUN useradd --no-create-home --shell /usr/sbin/nologin portal \
    && chown -R portal:portal /opt/portal
USER portal

EXPOSE 5000

CMD ["python3", "app.py"]
