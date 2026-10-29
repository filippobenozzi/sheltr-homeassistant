"""Costanti dell'integrazione Sheltr Cloud."""

DOMAIN = "sheltr"
CONF_URL = "url"
CONF_TOKEN = "token"

# Rilettura completa di sicurezza: gli aggiornamenti arrivano in tempo reale (SSE),
# questa serve solo se il collegamento in tempo reale cade.
SCAN_INTERVAL_SECONDS = 120

PLATFORMS = ["binary_sensor", "button", "climate", "cover", "light"]
