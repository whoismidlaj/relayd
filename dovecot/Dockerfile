FROM alpine:3.19

RUN apk add --no-cache \
    dovecot \
    dovecot-lmtpd \
    openssl \
    wget

COPY dovecot.conf /etc/dovecot/dovecot.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Mail storage
VOLUME ["/var/mail"]

# IMAP (plain + SSL) and LMTP (internal delivery)
EXPOSE 143 993 2525

ENTRYPOINT ["/entrypoint.sh"]
