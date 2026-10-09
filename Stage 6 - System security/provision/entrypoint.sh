#!/bin/bash
#
# BANK-CORE-01 entrypoint
# RaidTheRoot (RTR) Stage 6
#
# The foothold account is created at runtime from the environment rather than
# baked into the image, so the credential never ends up in the image history
# and always matches whatever the Stage 5 capture embedded.

set -e

USER_NAME="${STAGE6_USER:-svc_backup}"
USER_PASS="${STAGE6_PASSWORD:-}"

if [[ -z "$USER_PASS" || "$USER_PASS" == "CHANGE_ME" ]]; then
    echo "FATAL: STAGE6_PASSWORD is not set." >&2
    echo "It must match the credential embedded in the Stage 5 capture." >&2
    exit 1
fi

# --- foothold account --------------------------------------------------
if ! id "$USER_NAME" >/dev/null 2>&1; then
    useradd --create-home --shell /bin/bash "$USER_NAME"
fi
echo "${USER_NAME}:${USER_PASS}" | chpasswd

# --- THE VULNERABILITY -------------------------------------------------
# The maintenance directory is group-writable and the foothold account is in
# that group. The script inside is owned by root and is NOT writable - but a
# user who can write to the directory can rename it out of the way and put
# their own file there instead. cron then runs that file as root.
#
# This is the documented weakness, not an accident of the build.
usermod -aG svc_ghost "$USER_NAME"
chown svc_ghost:svc_ghost /opt/nexora/maintenance
chmod 775 /opt/nexora/maintenance

chown root:root /opt/nexora/maintenance/rotate_logs.sh
chmod 755 /opt/nexora/maintenance/rotate_logs.sh

# log directory the task writes to
chown root:svc_ghost /var/log/nexora
chmod 775 /var/log/nexora
touch /var/log/nexora/maintenance.log
chmod 664 /var/log/nexora/maintenance.log
chown root:svc_ghost /var/log/nexora/maintenance.log

# --- services ----------------------------------------------------------
cron

echo "BANK-CORE-01 ready. foothold account: ${USER_NAME}"

exec /usr/sbin/sshd -D -e
