# Sheltr Cloud per Home Assistant

Integrazione custom che collega Home Assistant a un portale [Sheltr Cloud](https://github.com/filippobenozzi/sheltr-cloud)
(`iotsheltr`). Bastano **URL del portale**, **ID impianto** e le credenziali (o un **token istanza**):
l'integrazione importa automaticamente tutte le schede configurate — `light`, `dimmer`, `shutter`,
`thermostat` — e le rende comandabili come entità native.

## Cosa viene creato

| Scheda Sheltr | Entità Home Assistant | Comandi |
|---|---|---|
| `light` | `light.*` (on/off) | accendi, spegni |
| `dimmer` | `light.*` con luminosità | accendi, spegni, livello 0..9 mappato su 0..255 |
| `shutter` | `cover.*` (tapparella) | su, giù, stop |
| `thermostat` | `climate.*` + `sensor.*` temperatura | setpoint 5..30 °C (passo 0,5), inverno → riscaldamento, estate → raffrescamento, on/off |
| impianto | `binary_sensor.*` connessione, `sensor.*` ultimo contatto, `button.*` aggiorna stato | polling attivo dei moduli |

Ogni scheda diventa un **dispositivo** di Home Assistant, agganciato al dispositivo «impianto»
(hub) che porta il nome dell'istanza. Nomi dei canali e stanze sono quelli configurati nel portale;
gli attributi di ogni entità riportano `board_id`, `address`, `channel` e `room` del protocollo 1.6.

Le schede aggiunte nel portale dopo la configurazione vengono importate al successivo
aggiornamento, senza dover ricaricare l'integrazione.

## Installazione

### HACS (consigliata)

1. HACS → menu in alto a destra → **Custom repositories**.
2. Repository: `https://github.com/filippobenozzi/sheltr-homeassistant`, categoria **Integration**.
3. Installa **Sheltr Cloud** e riavvia Home Assistant.

### Manuale

Copia la cartella `custom_components/sheltr` in `config/custom_components/` e riavvia Home Assistant.

## Configurazione

**Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Sheltr Cloud**.

| Campo | Descrizione |
|---|---|
| URL del portale | `http://192.168.1.10:8080` oppure l'indirizzo HTTPS dietro reverse proxy |
| ID impianto | l'istanza usata dal portale, cioè `<id>` in `/control/<id>` |
| Username / Password | le stesse credenziali con cui accedi al controllo dell'istanza |
| Token istanza | alternativa alle credenziali (`token` restituito da `/api/instances/<id>/auth/login`) |
| Verifica certificato SSL | disattivalo solo con certificati self-signed |

> Il token istanza ha vita limitata (`INSTANCE_AUTH_TTL_SEC`, 12 ore di default). Se inserisci
> username e password l'integrazione rinnova il token da sola; con il solo token, alla scadenza
> Home Assistant chiede di riautenticarsi.

L'utente deve essere abilitato sull'impianto nel portale (Config → utenti), altrimenti il portale
risponde `403` e la configurazione fallisce con «nessun permesso su questo impianto».

## Opzioni

**Impostazioni → Dispositivi e servizi → Sheltr Cloud → Configura**:

- **Intervallo di lettura dello stato** (default 30 s): con che frequenza viene letto
  `/api/instances/<id>/status`. È una lettura del database del portale, non genera traffico verso
  il modulo.
- **Intervallo di polling attivo dei moduli** (default 300 s): con che frequenza viene chiesto
  `refresh=1`, cioè il polling MQTT reale dei moduli (comando `0x40`). Metti `0` per disattivarlo e
  usare solo il pulsante **Aggiorna stato**: consigliato quando l'istanza è in *risparmio dati* su
  SIM IoT, dove il portale limita comunque la frequenza dei refresh.
- **Verifica lo stato del modulo dopo ogni comando** (default off): dopo ogni comando esegue il
  polling mirato del modulo (`/poll`), come fa la UI del portale. Più affidabile, ma raddoppia i
  frame sul bus.

## Note di funzionamento

- **Stato sconosciuto**: finché un modulo non risponde a un polling, le luci restano in stato
  sconosciuto — il protocollo non ha uno stato retained.
- **Tapparelle**: il protocollo espone solo su/giù/stop e nessuna posizione, quindi le entità
  `cover` sono in *assumed state* e mostrano sempre entrambi i pulsanti.
- **Termostati**: `power off` corrisponde al setpoint `0` sul modulo; l'azione
  riscaldamento/raffrescamento deriva dal relè riportato dal polling.
- **Dispositivo offline**: se l'istanza ha l'heartbeat configurato e il portale segnala il
  dispositivo offline, le entità dei canali diventano non disponibili, come nella UI del portale.

## Sviluppo

L'integrazione usa solo le API HTTP documentate nel
[riferimento API](https://github.com/filippobenozzi/sheltr-cloud/blob/main/docs/wiki/API.md) del
portale: `GET /api/instances/<id>`, `GET /api/instances/<id>/status`,
`POST /api/instances/<id>/poll` e le rotte `.../{lights,dimmers,shutters,thermostats}/command`.
Nessun accesso diretto a MQTT.

Diagnostica scaricabile dalla pagina dell'integrazione (credenziali e token sono oscurati).

Test e lint (portale simulato, nessuna installazione di Home Assistant necessaria):

```bash
pip install -r requirements-test.txt ruff && ruff check . && pytest
```

## Licenza

MIT
