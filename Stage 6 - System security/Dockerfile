# BANK-CORE-01 - Nexora Bank internal application server
# RaidTheRoot (RTR) Stage 6 capstone challenge
#
# INTENTIONALLY VULNERABLE. Contains a deliberate privilege-escalation path.
# Isolated on stage6-net, unprivileged, no host volumes, resource limited.
# Built for this CTF only - do not deploy anywhere else.

FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        openssh-server \
        cron \
        procps \
        nano \
        less \
        iproute2 \
    && rm -rf /var/lib/apt/lists/*

# --- SSH ---------------------------------------------------------------
RUN mkdir -p /run/sshd \
    && sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config \
    && sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config \
    && sed -i 's/^#\?PrintMotd.*/PrintMotd yes/' /etc/ssh/sshd_config

# --- Ghost's persistence ----------------------------------------------
# A service account that no one in IT Infrastructure created.
RUN useradd --system --create-home --home-dir /opt/nexora/svc \
            --shell /bin/bash svc_ghost

# The maintenance directory and the script the scheduler runs as root.
RUN mkdir -p /opt/nexora/maintenance /var/log/nexora
COPY provision/rotate_logs.sh /opt/nexora/maintenance/rotate_logs.sh
RUN chown root:root /opt/nexora/maintenance/rotate_logs.sh \
    && chmod 755 /opt/nexora/maintenance/rotate_logs.sh

# The scheduled task. Runs as root, every minute, so the box is playable.
COPY provision/nexora-maintenance /etc/cron.d/nexora-maintenance
RUN chmod 644 /etc/cron.d/nexora-maintenance

# --- The evidence ------------------------------------------------------
COPY provision/ghost_identity.txt /root/ghost_identity.txt
RUN chown root:root /root/ghost_identity.txt \
    && chmod 600 /root/ghost_identity.txt

# --- Scenery -----------------------------------------------------------
COPY provision/motd /etc/motd
COPY provision/notes.txt /opt/nexora/svc/notes.txt
RUN chown svc_ghost:svc_ghost /opt/nexora/svc/notes.txt \
    && chmod 644 /opt/nexora/svc/notes.txt

COPY provision/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 755 /usr/local/bin/entrypoint.sh

EXPOSE 22

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
