#!/bin/bash
# =============================================================================
# VPS2 n8n Container Health Monitor
# =============================================================================
# Checks that stack-n8n-1 is running and HTTP-responsive.
# If down: attempts restart via docker compose, sends Discord alert either way.
#
# Cron: */5 * * * * /opt/n8n-monitor/vps2_n8n_monitor.sh >> /var/log/n8n-monitor.log 2>&1
# =============================================================================

CONTAINER_NAME="stack-n8n-1"
COMPOSE_DIR="/opt/stack"
N8N_HEALTH_URL="http://172.18.0.10:5678/healthz"
DISCORD_WEBHOOK="https://discordapp.com/api/webhooks/1321695633959284787/3bXfwNb2kMLtDwdJnQc5Ydx_3CPbmWPbnDC55DW6WHHv_QN3kMZL8CFR4vlSz5lHGvFF"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')] [n8n-monitor]"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log() {
    echo "$LOG_PREFIX $1"
}

discord_alert() {
    local title="$1"
    local description="$2"
    local color="$3"   # 15158332 = red, 16776960 = yellow, 3066993 = green
    curl -s -o /dev/null -X POST "$DISCORD_WEBHOOK" \
        -H "Content-Type: application/json" \
        -d "{\"embeds\":[{\"title\":\"$title\",\"description\":\"$description\",\"color\":$color,\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)\"}]}"
}

container_running() {
    local status
    status=$(docker inspect --format='{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null)
    [ "$status" = "running" ]
}

http_healthy() {
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$N8N_HEALTH_URL" 2>/dev/null)
    [[ "$code" =~ ^(200|301|302|401)$ ]]
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# 1. Check Docker container state
if ! container_running; then
    log "WARN: Container $CONTAINER_NAME is NOT running. Attempting restart..."
    discord_alert \
        ":warning: n8n Container Down" \
        "Container \`$CONTAINER_NAME\` was found stopped on VPS2. Attempting automatic restart via docker compose." \
        "16776960"

    cd "$COMPOSE_DIR" && docker compose up -d n8n
    sleep 15

    if container_running; then
        log "OK: Container restarted successfully."
        discord_alert \
            ":white_check_mark: n8n Restarted" \
            "Container \`$CONTAINER_NAME\` was restarted and is now running. Monitor continues." \
            "3066993"
    else
        log "ERROR: Container restart FAILED. Manual intervention required."
        discord_alert \
            ":red_circle: n8n Restart FAILED" \
            "CRITICAL: \`$CONTAINER_NAME\` could not be restarted automatically on VPS2. **Manual intervention required immediately.**" \
            "15158332"
    fi
    exit 0
fi

# 2. Container is running — verify HTTP health
if ! http_healthy; then
    log "WARN: Container running but HTTP health check failed on $N8N_HEALTH_URL"
    discord_alert \
        ":warning: n8n Unresponsive" \
        "Container \`$CONTAINER_NAME\` is running but not responding to HTTP health checks at \`$N8N_HEALTH_URL\`. Workflows may be stalled." \
        "16776960"
    exit 1
fi

# 3. All good
log "OK: $CONTAINER_NAME is running and HTTP-healthy."
exit 0
