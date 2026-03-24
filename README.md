# EDA-Webhook v2 – Vollständige Antragsunterstützung + Nachrichten-Parser

Drei Dateien, `pip install flask`, fertig.

## Installation

```bash
pip install flask
python app.py   # Port 5050
```

## Endpunkte

| Methode | Pfad              | Funktion                               |
|---------|-------------------|----------------------------------------|
| GET     | /health           | Statuscheck                            |
| GET     | /types            | Alle unterstützten Typen               |
| GET     | /schema/<typ>     | Feldbeschreibung                       |
| GET     | /example/<typ>    | Beispiel-JSON                          |
| POST    | /validate/<typ>   | JSON prüfen                            |
| POST    | /generate/<typ>   | JSON → .eda-Datei (Download)           |
| POST    | /parse            | .eda-Gerichtsnachricht → JSON          |

## Ausgehende Antragstypen

| Typ      | Bezeichnung                           | Satzart | Format |
|----------|---------------------------------------|---------|--------|
| mba      | Mahnbescheidsantrag                   | 01      | 4000   |
| vba      | Vollstreckungsbescheidsantrag         | 08      | 4100   |
| nemb     | Neuzustellungsantrag MB               | 07      | 4100   |
| nevb     | Neuzustellungsantrag VB               | 10      | 4100   |
| rn       | Rücknahme / Erledigterklärung         | 25      | 4000   |
| ezkoab   | Kosteneinzug / Abgabeantrag           | 29      | 4000   |
| wi       | Widerspruch (nur AGPV mit KEZI)       | 30      | 4100   |
| moa      | Monierungsantwort                     | 20      | 4000   |

## Eingehende Gerichtsnachrichten (/parse)

| Satzart | Bezeichnung                                      |
|---------|--------------------------------------------------|
| 03      | KNMB – Kosten-/Erlassnachricht MB                |
| 05      | ZNMBVB – Zustellungs-/Nichtzustellungsnachricht  |
| 16      | ABN – Abgabenachricht                            |
| 18      | WIN – Widerspruchsnachricht                      |
| 20      | MO – Monierung                                   |
| 22      | KNVB – Kosten-/Erlassnachricht VB                |
| 90      | QU – Eingangsbestätigung                         |

## Schnellstart

```bash
# Beispiel-JSON holen
curl http://localhost:5050/example/vba > vba.json

# Validieren
curl -X POST http://localhost:5050/validate/vba \
     -H "Content-Type: application/json" -d @vba.json

# .eda-Datei generieren
curl -X POST http://localhost:5050/generate/vba \
     -H "Content-Type: application/json" -d @vba.json \
     -o vollstreckungsbescheid.eda

# Gerichtsnachricht einlesen
curl -X POST http://localhost:5050/parse \
     -H "Content-Type: application/octet-stream" \
     --data-binary @eingang_vom_gericht.eda
```

## Typische Abläufe

```
MBA einreichen   → KNMB empfangen (/parse) → ZN/NZN empfangen (/parse)
                 → VBA einreichen → KNVB empfangen (/parse)

Widerspruch:     WIN empfangen (/parse) → EZKOAB einreichen

Nichtzustellung: NZN empfangen (/parse) → NEMB einreichen

Monierung:       MO empfangen (/parse) → inhalt-Felder korrigieren → MOA einreichen
```

## Hinweise

- EDAID muss je Einreichung eindeutig sein und darf binnen 2 Wochen nicht wiederholt werden
- Monierungsantwort: alle G02-Sätze zurückgeben, nur das Feld "inhalt" ändern
- Widerspruch: nur für Prozessbevollmächtigte mit PV-Kennziffer (Stelle 3 = 5–7)
