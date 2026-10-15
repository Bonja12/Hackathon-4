# Minor-adviseur (spraakassistent)

Spraakgestuurde AI-studieadviseur voor minorkeuze. Zoekt met embeddings de best passende minoren uit KiesOpMaat en laat een Groq-LLM het gesprek voeren volgens het Prompt Charter.

**Vereisten:** Python 3.10+, Chrome of Edge (voor spraak), gratis Groq API-key van https://console.groq.com

## Installeren (PowerShell)

Ga naar de projectmap:

```powershell
cd C:\School\Projecten\Hackathon-4
```

Installeer de packages:

```powershell
pip install -r requirements.txt
```

Installeer de browser voor de scraper (eenmalig):

```powershell
python -m playwright install chromium
```

## Minoren ophalen (eenmalig)

```powershell
python scraper.py
```

Dit duurt een paar minuten en maakt `minors.json`. Stoppen kan met Ctrl+C (dan wordt er niets opgeslagen). Optioneel: filter eerst op de site en geef de URL mee:

```powershell
python scraper.py "https://www.kiesopmaat.nl/modules/?...jouw-filter..."
```

## API-key instellen

Kies een van de twee. Zet je key nooit in git of in een chat.

Optie 1: alleen voor dit terminalvenster:

```powershell
$env:GROQ_API_KEY = "gsk_jouw_key"
```

Optie 2: in een bestand `.env` in de projectmap met deze regel:

```
GROQ_API_KEY=gsk_jouw_key
```

Optioneel een ander model kiezen (standaard `openai/gpt-oss-120b`, met terugval op `openai/gpt-oss-20b`):

```powershell
$env:GROQ_MODEL = "openai/gpt-oss-20b"
```

## Starten

```powershell
python -m uvicorn server:app --reload
```

Wacht tot je `[matching] embeddings, N minoren` ziet (de eerste keer downloadt het model ~450 MB). Open daarna http://localhost:8000 in Chrome of Edge. De bot begint zelf; klik op de microfoon om te antwoorden.

Draait er al iets op poort 8000? Gebruik een andere poort:

```powershell
python -m uvicorn server:app --reload --port 8001
```

## Mapstructuur

```
server.py          FastAPI-server, retrieval en Groq-aanroep, systeemprompt
scraper.py         haalt minoren op van kiesopmaat.nl, schrijft minors.json
minors.json        de data (na het scrapen)
static/index.html  de spraakinterface
.env               je API-key (niet delen)
```

## Problemen oplossen

| Melding | Oplossing |
| --- | --- |
| `GROQ_API_KEY ontbreekt` | Key niet gezet in dit terminalvenster, zie hierboven. |
| `401` van Groq | Key fout of ingetrokken: maak een nieuwe aan. |
| `model_not_found` | Zet `GROQ_MODEL` op een model uit https://console.groq.com/docs/models |
| "Ik heb nog geen minoren" | `minors.json` ontbreekt of is leeg. Draai de scraper en herstart de server. |
| `JSONDecodeError` bij opstarten | `minors.json` is beschadigd. Draai de scraper opnieuw. |
| `static\index.html does not exist` | `index.html` moet in de map `static` staan. |
| Scraper: "Verifying your browser" | Zet `HEADLESS = False` bovenaan `scraper.py`. |
| Oude pagina zichtbaar | Ververs met Ctrl+F5. |
| Geen spraak in Firefox | Gebruik Chrome of Edge, of typ je antwoord. |

## Privacy

Er wordt geen gesprek of audio opgeslagen door deze app. Let op: de spraakherkenning van Chrome stuurt audio naar Google, en de gesprekstekst gaat naar Groq. Vraag geen persoonsgegevens.
