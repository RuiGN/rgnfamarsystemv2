FROM alpine:3.19

RUN apk add --no-cache ca-certificates curl \
    && curl -fsSL -o /usr/local/bin/cloudflared \
       "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64" \
    && chmod +x /usr/local/bin/cloudflared

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["tunnel", "--config", "/etc/cloudflared/config.yml", "run"]
