#!/bin/sh
# Dovecot entrypoint: sync passwd from Relayd API, then start Dovecot

set -e

RELAYD_API="${RELAYD_API_URL:-http://backend:8000/api}"
PASSWD_FILE="/etc/dovecot/passwd"
SSL_DIR="/etc/ssl/dovecot"
MAIL_DIR="/var/mail"

echo "[entrypoint] Starting Relayd-Dovecot bridge..."

# ---- Create vmail user/group for mail storage ----
if ! id -u vmail > /dev/null 2>&1; then
  addgroup -g 5000 vmail
  adduser -u 5000 -G vmail -H -D vmail
fi
mkdir -p "$MAIL_DIR"
chown vmail:vmail "$MAIL_DIR"

# ---- Generate self-signed SSL cert if not mounted ----
mkdir -p "$SSL_DIR"
if [ ! -f "$SSL_DIR/server.pem" ]; then
  echo "[entrypoint] Generating self-signed SSL cert with SAN..."
  PUBLIC_IP=$(wget -qO- https://api.ipify.org || curl -s https://api.ipify.org || echo "")
  SAN="DNS:localhost,IP:127.0.0.1"
  if [ -n "$PUBLIC_IP" ]; then
    SAN="$SAN,IP:$PUBLIC_IP"
    echo "[entrypoint] Found public IP: $PUBLIC_IP"
  fi
  openssl req -new -x509 -days 3650 -nodes \
    -out "$SSL_DIR/server.pem" \
    -keyout "$SSL_DIR/server.key" \
    -subj "/CN=relayd-imap" \
    -addext "subjectAltName=$SAN"
fi

# Generate DH params if missing (fixes Dovecot DH warning)
if [ ! -f "$SSL_DIR/dh.pem" ]; then
  echo "[entrypoint] Generating DH parameters (this may take a moment)..."
  openssl dhparam -out "$SSL_DIR/dh.pem" 2048
fi

# Ensure correct permissions for SSL certs & DH parameters so Dovecot can read them
chmod 755 "$SSL_DIR"
if [ -f "$SSL_DIR/server.pem" ]; then chmod 644 "$SSL_DIR"/server.pem; fi
if [ -f "$SSL_DIR/server.key" ]; then chmod 600 "$SSL_DIR"/server.key; fi
if [ -f "$SSL_DIR/dh.pem" ]; then chmod 644 "$SSL_DIR"/dh.pem; fi


# ---- Sync passwd file from Relayd API ----
sync_passwd() {
  echo "[entrypoint] Syncing mailbox credentials from Relayd..."
  # The /api/internal/dovecot-passwd endpoint returns a passwd-file format
  # Each line: email:{PLAIN}password:::::
  HTTP_CODE=$(wget -qO "$PASSWD_FILE.tmp" \
    --header="X-Internal-Secret: ${INTERNAL_SECRET:-relayd-internal}" \
    --server-response \
    "${RELAYD_API}/internal/dovecot-passwd" 2>&1 | grep "HTTP/" | tail -1 | awk '{print $2}')
  
  if [ -f "$PASSWD_FILE.tmp" ] && [ -s "$PASSWD_FILE.tmp" ]; then
    mv "$PASSWD_FILE.tmp" "$PASSWD_FILE"
    echo "[entrypoint] Passwd file synced ($(wc -l < $PASSWD_FILE) entries)"
  else
    echo "[entrypoint] Warning: Could not sync passwd (Relayd may not be ready yet). Using existing file."
    touch "$PASSWD_FILE"
  fi
}

sync_passwd

# ---- Background passwd sync every 5 minutes ----
(while true; do
  sleep 300
  sync_passwd
done) &

echo "[entrypoint] Starting Dovecot..."
exec dovecot -F -c /etc/dovecot/dovecot.conf
