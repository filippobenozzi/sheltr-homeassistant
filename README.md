# Sheltr Cloud per Home Assistant

Integrazione custom che porta in Home Assistant gli impianti di un portale
[Sheltr Cloud](https://github.com/filippobenozzi/sheltr-cloud): luci, dimmer, tapparelle, termostati,
sequenze e ingressi, comandabili come entità native e aggiornati **in tempo reale**.

Bastano l'**indirizzo del portale** e un **token**.

> **Versione 2.** Funziona col portale Sheltr Cloud 2 (token API). Le configurazioni fatte con la
> versione 1.x (portale precedente, con ID impianto e credenziali) non si convertono: rimuovi
> l'integrazione e aggiungila di nuovo con indirizzo e token.

## Cosa viene creato

| Sheltr | Home Assistant | Comandi |
|---|---|---|
| Luce | `light` (on/off) | accendi, spegni |
| Dimmer | `light` con luminosità | livelli 0–9 del bus su 0–255 |
| Tapparella | `cover` (stato presunto) | su, giù, stop: il bus non dà la posizione |
| Termostato | `climate` | setpoint 5–30 °C a mezzi gradi, inverno = riscaldamento, estate = raffrescamento, spento |
| Sequenza (Sheltr ESP) | `button` | avvia |
| Ingresso (Sheltr ESP) | `binary_sensor` | — |
| Gateway (DR154, Sheltr ESP) | dispositivo, con un sensore di **collegamento** | — |

Ogni gateway diventa un dispositivo di Home Assistant (*Impianto · Gateway*), con la stanza suggerita
dal portale. I moduli aggiunti nel portale dopo la configurazione arrivano da soli.

## Installazione

### HACS (consigliata)

1. HACS → menu in alto a destra → **Custom repositories**.
2. Repository: `https://github.com/filippobenozzi/sheltr-homeassistant`, categoria **Integration**.
3. Installa **Sheltr Cloud** e riavvia Home Assistant.

### Manuale

Copia la cartella `custom_components/sheltr` in `config/custom_components/` e riavvia Home Assistant.

## Il token

Nel portale, in uno dei due modi:

- **Token dell'impianto** (consigliato): impianto → **Impostazioni → API dell'impianto → Attiva e
  genera il token**. Vale solo per quell'impianto, con qualunque modalità dei gateway (**Direct** o
  **API**), e non richiede un utente. Da lì si scarica anche la **guida API** dell'impianto.
- **Token personale**: **Profilo → Token API → Nuovo token**. Ha i permessi dell'utente: vedi tutte le
  sue case.

Il token si vede una volta sola: copialo subito.

## Configurazione

**Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Sheltr Cloud**:

| Campo | Esempio |
|---|---|
| Indirizzo del portale | `https://cloud.sheltr.it` (senza `https://` viene aggiunto) |
| Token API | `shltr_…` |

Se il token viene revocato o rigenerato nel portale, Home Assistant chiede di inserire quello nuovo.

## Come funziona

- All'avvio una lettura completa (`/api/homes`), poi gli aggiornamenti arrivano dal flusso in tempo
  reale del portale (Mercure, Server-Sent Events); ogni 2 minuti una rilettura di sicurezza.
- I comandi passano dalle stesse API dell'app del portale (`/api/channels/<id>/command`).
- Un gateway offline rende non disponibili le sue entità.
- Per i gateway in modalità **API** i canali hanno i nomi di default del portale: rinominali in Home
  Assistant.
- **Diagnostica** scaricabile dalla pagina dell'integrazione (senza il token).

## Sviluppo

```bash
pip install -r requirements-test.txt ruff
ruff check . && ruff format --check .
pytest
```
