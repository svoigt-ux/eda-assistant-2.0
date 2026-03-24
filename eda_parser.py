"""
EDA Parser – Eingehende Gerichtsnachrichten

Liest .eda-Dateien (CP850, 128 Byte Sätze) und gibt strukturiertes JSON zurück.

Unterstützte Satzarten:
  03 – Kosten-/Erlassnachricht MB (KNMB)
  05 – Zustellungs-/Nichtzustellungsnachricht (ZNMBVB)
  16 – Abgabenachricht (ABN)
  18 – Widerspruchsnachricht (WIN)
  20 – Monierung (MO)
  22 – Kosten-/Erlassnachricht VB (KNVB)
  90 – Eingangsbestätigung/Quittung (QU)
"""

from typing import List, Dict, Any, Optional


def _parse_records(data: bytes) -> List[str]:
    """Rohdaten in Liste von 128-Byte-Sätzen (als CP850-Strings) zerlegen."""
    records = []
    i = 0
    while i < len(data):
        chunk = data[i:i+128]
        if len(chunk) == 128:
            records.append(chunk.decode("cp850", errors="replace"))
        i += 128
        # CR/LF überspringen
        while i < len(data) and data[i:i+1] in [b"\r", b"\n"]:
            i += 1
    return records


def _f(rec: str, start: int, length: int) -> str:
    """Feld aus Satz lesen (1-basiert) und trimmen."""
    return rec[start-1:start-1+length].strip()


def _amt(s: str, decimals: int = 2) -> Optional[float]:
    """Numerischen Feldwert als float parsen."""
    s = s.strip()
    if not s or all(c in " 0" for c in s):
        return None
    try:
        return int(s) / (10 ** decimals)
    except ValueError:
        return None


def _parse_gnr(s: str) -> str:
    """GNR in lesbares Format: JJNNNNNNNPS → JJ-NNNNNNN-P-S"""
    s = s.strip().lstrip("0")
    if len(s) == 11:
        return f"{s[0:2]}-{s[2:9]}-{s[9]}-{s[10]}"
    return s


# ---------------------------------------------------------------------------
# Satzarten-Dispatcher
# ---------------------------------------------------------------------------

SATZART_NAMES = {
    "03": "KNMB – Kosten-/Erlassnachricht MB",
    "05": "ZNMBVB – Zustellungs-/Nichtzustellungsnachricht",
    "16": "ABN – Abgabenachricht",
    "18": "WIN – Widerspruchsnachricht",
    "20": "MO – Monierung",
    "22": "KNVB – Kosten-/Erlassnachricht VB",
    "90": "QU – Eingangsbestätigung",
}

NAM_TYPES = {
    "05": "Zustellungsnachricht MB",
    "06": "Nichtzustellungsnachricht MB",
    "08": "Zustellungsnachricht VB",
    "09": "Nichtzustellungsnachricht VB",
}


def parse_eda(data: bytes) -> Dict[str, Any]:
    """
    Parst eine EDA-Datei und gibt ein strukturiertes Dict zurück.
    Kann mehrere logische Dateien innerhalb einer physischen Datei verarbeiten.
    """
    records = _parse_records(data)
    if not records:
        return {"fehler": "Keine Sätze gefunden"}

    result = {
        "datei_info": {},
        "nachrichten": [],
        "nachsatz": {},
    }

    # AA-Satz auswerten
    if records and records[0][:2] == "AA":
        aa = records[0]
        belart = _f(aa, 17, 2)
        result["datei_info"] = {
            "satzart": "AA",
            "tkezi": _f(aa, 3, 8),
            "datum": _f(aa, 11, 6),
            "belart": belart,
            "belart_name": SATZART_NAMES.get(belart, f"Satzart {belart}"),
            "ekezi": _f(aa, 19, 8),
            "format": _f(aa, 27, 4),
            "edaid": _f(aa, 31, 6),
            "edaidz": _f(aa, 37, 2),
            "mahngericht": _mahngericht_name(_f(aa, 37, 2)),
        }

    # BB-Satz
    bb = records[-1] if records[-1][:2] == "BB" else None
    if bb:
        result["nachsatz"] = {
            "tkezi": _f(bb, 3, 8),
            "anzahl_nachrichten": int(_f(bb, 11, 7) or "0"),
            "anzahl_saetze": int(_f(bb, 18, 7) or "0"),
            "summe_gnr": int(_f(bb, 46, 15) or "0"),
        }

    # Nutzätze verteilen
    belart = result["datei_info"].get("belart", "")
    nutz = records[1:-1] if bb else records[1:]

    if belart == "03":
        result["nachrichten"] = _parse_knmb(nutz)
    elif belart == "05":
        result["nachrichten"] = _parse_znmbvb(nutz)
    elif belart == "16":
        result["nachrichten"] = _parse_abn(nutz)
    elif belart == "18":
        result["nachrichten"] = _parse_win(nutz)
    elif belart == "20":
        result["nachrichten"] = _parse_mo(nutz)
    elif belart == "22":
        result["nachrichten"] = _parse_knvb(nutz)
    elif belart == "90":
        result["nachrichten"] = _parse_qu(nutz)
    else:
        result["nachrichten"] = [{"rohdaten": [r[:40] for r in nutz]}]

    return result


def _mahngericht_name(code: str) -> str:
    names = {
        "01": "AG Schleswig",
        "02": "AG Hamburg",
        "03": "AG Uelzen",
        "04": "AG Bremen",
        "05": "AG Hagen",
        "06": "AG Hünfeld",
        "07": "AG Mayen",
        "08": "AG Stuttgart",
        "11": "AG Wedding (Berlin)",
        "13": "AG Euskirchen",
        "14": "AG Coburg",
        "23": "AG Aschersleben / Staßfurt",
    }
    return names.get(code.strip(), code)


# ---------------------------------------------------------------------------
# KNMB (03) Parser
# ---------------------------------------------------------------------------

def _parse_knmb(records: List[str]) -> List[Dict]:
    nachrichten = []
    current: Optional[Dict] = None

    for rec in records:
        sa    = rec[:2]
        kennz = rec[2:7].strip()
        fn    = rec[7:9]

        if sa == "03" and kennz == "KS":
            if current:
                nachrichten.append(current)
            kezi = _f(rec, 10, 8)
            gnrs = []
            for i in range(5):
                g = _f(rec, 18 + i*11, 11)
                if g and g != "00000000000":
                    gnrs.append(_parse_gnr(g))
            current = {
                "typ": "KNMB",
                "kezi": kezi,
                "geschaeftszeichen": _f(rec, 73, 35),
                "erlass_datum": _f(rec, 108, 6),
                "gerichtsnummern": gnrs,
                "gebühren": {},
                "zahlweg": {},
                "rechtsmittel": {},
            }
        elif sa == "03" and kennz == "AUSGB" and current:
            current["gebühren"] = {
                "auslagen_antragsteller": _amt(_f(rec, 10, 8)),
                "gerichtsgebühr_gkg": _amt(_f(rec, 18, 7)),
                "zustellungsauslagen": _amt(_f(rec, 25, 4)),
                "ra_gebühr_rvg": _amt(_f(rec, 29, 9)),
                "ra_auslagen_rvg": _amt(_f(rec, 38, 7)),
                "ra_mwst": _amt(_f(rec, 45, 8)),
                "ausgerechnete_zinsen": _amt(_f(rec, 53, 10)),
                "nebenforderungen": _amt(_f(rec, 63, 10)),
            }
        elif sa == "03" and kennz == "ZAW" and current:
            if fn == "01":
                current["zahlweg"]["empfänger1"] = _f(rec, 10, 27)
                current["zahlweg"]["empfänger2"] = _f(rec, 37, 27)
                current["zahlweg"]["iban"]       = _f(rec, 64, 34)
                current["zahlweg"]["bic"]        = _f(rec, 98, 11)
            elif fn == "02":
                current["zahlweg"]["betrag"]          = _amt(_f(rec, 10, 7))
                current["zahlweg"]["verwendungszweck"] = _f(rec, 17, 27)
        elif sa == "03" and kennz == "RM" and current:
            current["rechtsmittel"] = {
                "art":    "Erinnerung" if _f(rec, 10, 1) == "1" else "Beschwerde",
                "frist":  _f(rec, 11, 2) + " Wochen",
                "norm":   _f(rec, 13, 15),
                "gericht1": _f(rec, 29, 35),
                "gericht2": _f(rec, 65, 35),
            }

    if current:
        nachrichten.append(current)
    return nachrichten


# ---------------------------------------------------------------------------
# ZNMBVB (05) Parser
# ---------------------------------------------------------------------------

def _parse_znmbvb(records: List[str]) -> List[Dict]:
    nachrichten = []
    current: Optional[Dict] = None

    for rec in records:
        sa    = rec[:2]
        kennz = rec[2:7].strip()
        fn    = rec[7:9]

        if sa == "05" and kennz == "KS":
            if current:
                nachrichten.append(current)
            nam   = _f(rec, 73, 2)
            current = {
                "typ": NAM_TYPES.get(nam, f"Zustellungsnachricht ({nam})"),
                "nachrichtenart": nam,
                "kezi": _f(rec, 10, 8),
                "gerichtsnummer": _parse_gnr(_f(rec, 18, 11)),
                "geschaeftszeichen": _f(rec, 29, 35),
                "zustellungsdatum": _f(rec, 75, 6),
                "antragsgegner": {},
                "nichtzustellung": {},
            }
        elif sa == "05" and kennz == "AG" and current:
            if fn == "01":
                current["antragsgegner"]["name_änderung"] = _f(rec, 14, 110).strip()
            elif fn == "03":
                current["antragsgegner"]["strasse"]  = _f(rec, 10, 35)
                current["antragsgegner"]["plz"]      = _f(rec, 45, 5)
                current["antragsgegner"]["ort"]      = _f(rec, 50, 27)
                current["antragsgegner"]["ausland"]  = _f(rec, 77, 3)
                current["antragsgegner"]["gv_form"]  = _f(rec, 81, 35)
        elif sa == "05" and kennz == "AGGV" and current:
            current["antragsgegner"]["gv_name"]    = _f(rec, 10, 35)
            current["antragsgegner"]["gv_strasse"] = _f(rec, 45, 35)
            current["antragsgegner"]["gv_plz"]     = _f(rec, 80, 5)
            current["antragsgegner"]["gv_ort"]     = _f(rec, 85, 27)
        elif sa == "05" and kennz == "NZUG" and current:
            if fn == "01":
                nzumm = _f(rec, 10, 1)
                nz_grund_map = {
                    "A": "Adressat unter angegebener Anschrift nicht ermittelbar",
                    "B": "Adressat verzogen",
                    "C": "Anderer Grund",
                    "D": "A und B",
                    "E": "A und C",
                    "F": "B und C",
                    "G": "A, B und C",
                }
                raw = _f(rec, 12, 90)
                parts = raw.split(";", 2)
                current["nichtzustellung"] = {
                    "schlüssel": nzumm,
                    "grund": nz_grund_map.get(nzumm, nzumm),
                    "neue_strasse": parts[0].strip() if len(parts) > 0 else "",
                    "neue_plzort": parts[1].strip() if len(parts) > 1 else "",
                    "anderer_grund": parts[2].strip() if len(parts) > 2 else "",
                }
            elif fn == "02":
                if current["nichtzustellung"].get("anderer_grund") == "":
                    current["nichtzustellung"]["anderer_grund"] = _f(rec, 10, 30)

    if current:
        nachrichten.append(current)
    return nachrichten


# ---------------------------------------------------------------------------
# ABN (16) Parser
# ---------------------------------------------------------------------------

def _parse_abn(records: List[str]) -> List[Dict]:
    nachrichten = []
    current: Optional[Dict] = None

    for rec in records:
        sa    = rec[:2]
        kennz = rec[2:7].strip()
        fn    = rec[7:9]

        if sa == "16" and kennz == "KS":
            if current:
                nachrichten.append(current)
            pg_art_map = {"1":"AG (Zivil)","2":"LG (Zivil)","3":"LG (Handelssachen)","6":"AG (Familie)","8":"Sozialgericht"}
            rb_map = {"1":"Widerspruch","2":"verspäteter Widerspruch","3":"Einspruch"}
            current = {
                "typ": "ABN",
                "kezi": _f(rec, 10, 8),
                "gerichtsnummer": _parse_gnr(_f(rec, 18, 11)),
                "geschaeftszeichen": _f(rec, 29, 35),
                "abgabedatum": _f(rec, 64, 6),
                "kosten_streitverfahren": _amt(_f(rec, 70, 9)),
                "prozessgericht": {
                    "art": pg_art_map.get(_f(rec, 79, 1), _f(rec, 79, 1)),
                    "plz": _f(rec, 80, 5),
                    "ort": _f(rec, 85, 30),
                },
                "widerspruchsdatum": _f(rec, 115, 6),
                "rechtsbehelf": rb_map.get(_f(rec, 116, 1), ""),
                "antragsgegner": {},
                "agpv": {},
            }
        elif sa == "16" and kennz == "AG" and current:
            current["antragsgegner"] = {
                "strasse": _f(rec, 10, 35),
                "plz":     _f(rec, 45, 5),
                "ort":     _f(rec, 50, 27),
                "ausland": _f(rec, 77, 3),
            }
        elif sa == "16" and kennz == "AGGV" and current:
            if fn == "01":
                current["antragsgegner"]["gv_stellung"] = _f(rec, 10, 35)
                current["antragsgegner"]["gv_name"]     = _f(rec, 45, 35)
            elif fn == "02":
                current["antragsgegner"]["gv_strasse"]  = _f(rec, 10, 35)
                current["antragsgegner"]["gv_plz"]      = _f(rec, 45, 5)
                current["antragsgegner"]["gv_ort"]      = _f(rec, 50, 27)
        elif sa == "16" and kennz == "AGPV" and current:
            if fn == "01":
                current["agpv"]["anrede"] = _f(rec, 10, 1)
                current["agpv"]["name"]   = _f(rec, 11, 105)
            elif fn == "02":
                current["agpv"]["strasse"] = _f(rec, 10, 35)
                current["agpv"]["plz"]     = _f(rec, 45, 5)
                current["agpv"]["ort"]     = _f(rec, 50, 27)

    if current:
        nachrichten.append(current)
    return nachrichten


# ---------------------------------------------------------------------------
# WIN (18) Parser
# ---------------------------------------------------------------------------

def _parse_win(records: List[str]) -> List[Dict]:
    nachrichten = []
    current: Optional[Dict] = None

    for rec in records:
        sa    = rec[:2]
        kennz = rec[2:7].strip()
        fn    = rec[7:9]

        if sa == "18" and kennz == "KS":
            if current:
                nachrichten.append(current)
            current = {
                "typ": "WIN",
                "kezi": _f(rec, 10, 8),
                "gerichtsnummer": _parse_gnr(_f(rec, 18, 11)),
                "geschaeftszeichen_as": _f(rec, 29, 35),
                "geschaeftszeichen_ag": _f(rec, 64, 35),
                "streitwert": _amt(_f(rec, 99, 11)),
                "kosten_streitverfahren": _amt(_f(rec, 110, 9)),
                "antrag_streitverfahren": _f(rec, 122, 1) == "X",
                "widerspruch": {},
                "prozessgericht": {},
                "antragsgegner": {},
                "agpv": {},
                "rechtsmittel": {},
                "zahlweg": {},
            }
        elif sa == "18" and kennz == "WIPG" and current:
            wi_typ = {"1":"Gesamtwiderspruch","2":"Teilwiderspruch"}.get(_f(rec, 10, 1),"")
            current["widerspruch"] = {
                "art":                wi_typ,
                "anzahl":             _f(rec, 11, 1),
                "mit_begruendung":    _f(rec, 12, 1) == "2",
                "betrag_hauptforderung": _amt(_f(rec, 13, 10)),
                "zinsen_widersprochen":  _f(rec, 23, 1) == "X",
                "zinssatz_merkmal":      _f(rec, 24, 2),
                "zinssatz":              _amt(_f(rec, 26, 5), 3),
                "verfahrenskosten_widersprochen": _f(rec, 31, 1) == "X",
                "betrag_nebenforderungen": _amt(_f(rec, 32, 10)),
                "widerspruchsdatum": _f(rec, 109, 6),
            }
            pg_map = {"1":"AG (Zivil)","2":"LG (Zivil)","3":"LG (Handelssachen)","6":"AG (Familie)","8":"Sozialgericht"}
            current["prozessgericht"] = {
                "art": pg_map.get(_f(rec, 42, 1), ""),
                "plz": _f(rec, 43, 5),
                "ort": _f(rec, 48, 30),
            }
        elif sa == "18" and kennz == "AG" and current:
            current["antragsgegner"] = {
                "strasse": _f(rec, 10, 35),
                "plz":     _f(rec, 45, 5),
                "ort":     _f(rec, 50, 27),
            }
        elif sa == "18" and kennz == "AGGV" and current:
            if fn == "01":
                current["antragsgegner"]["gv_stellung"] = _f(rec, 10, 35)
                current["antragsgegner"]["gv_name"]     = _f(rec, 45, 35)
            elif fn == "02":
                current["antragsgegner"]["gv_strasse"]  = _f(rec, 10, 35)
        elif sa == "18" and kennz == "AGPV" and current:
            if fn == "01":
                current["agpv"]["anrede"] = _f(rec, 10, 1)
                current["agpv"]["name"]   = _f(rec, 11, 105)
            elif fn == "02":
                current["agpv"]["strasse"] = _f(rec, 10, 35)
                current["agpv"]["plz"]     = _f(rec, 45, 5)
                current["agpv"]["ort"]     = _f(rec, 50, 27)
        elif sa == "18" and kennz == "RM" and current:
            current["rechtsmittel"] = {
                "art":     "Erinnerung" if _f(rec, 10, 1) == "1" else "Beschwerde",
                "frist":   _f(rec, 11, 2) + " Wochen",
                "norm":    _f(rec, 13, 15),
                "gericht1": _f(rec, 29, 35),
                "gericht2": _f(rec, 65, 35),
            }
        elif sa == "18" and kennz == "ZAW" and current:
            if fn == "01":
                current["zahlweg"]["empfänger1"] = _f(rec, 10, 27)
                current["zahlweg"]["iban"]       = _f(rec, 64, 34)
                current["zahlweg"]["bic"]        = _f(rec, 98, 11)
            elif fn == "02":
                current["zahlweg"]["betrag"]      = _amt(_f(rec, 10, 7))
                current["zahlweg"]["verwendungszweck"] = _f(rec, 17, 27)

    if current:
        nachrichten.append(current)
    return nachrichten


# ---------------------------------------------------------------------------
# MO (20) Parser
# ---------------------------------------------------------------------------

def _parse_mo(records: List[str]) -> List[Dict]:
    nachrichten = []
    current: Optional[Dict] = None

    mobelart_map = {
        "01": "MB-Antrag",
        "02": "VB-Antrag",
        "03": "Erneute Monierung VB",
        "07": "Neuzustellungsantrag MB",
        "08": "Erneute Monierung NEMB",
        "10": "Neuzustellungsantrag VB",
        "11": "Erneute Monierung NEVB",
    }

    for rec in records:
        sa    = rec[:2]
        kennz = rec[2:7].strip()

        if sa == "20" and kennz == "KS":
            if current:
                nachrichten.append(current)
            kezi = _f(rec, 10, 8)
            asgz = _f(rec, 18, 35)
            gnrs = []
            for i in range(5):
                g = _f(rec, 53 + i*11, 11)
                if g and g.strip("0"):
                    gnrs.append(_parse_gnr(g))
            mobelart = _f(rec, 108, 2)
            current = {
                "typ": "MO",
                "kezi": kezi,
                "geschaeftszeichen": asgz,
                "gerichtsnummern": gnrs,
                "monierungsdatum": _f(rec, 103, 6),
                "antragsdatum": _f(rec, 109, 6) if len(rec) > 109 else "",
                "monierte_antragsart": mobelart_map.get(mobelart, mobelart),
                "monierungszeilen": [],
            }
        elif sa == "20" and kennz == "MO" and current:
            form_map = {
                "1": "Text (35 Zeichen)",
                "2": "Betrag (10,2)",
                "3": "Zinssatz (5,3)",
                "4": "Datum (JJMMTT)",
                "5": "Merkmal (1 Zeichen)",
                "6": "Adresse (PLZ/Ort)",
                "7": "Schlüssel (2-stellig num.)",
                "8": "Text (35 Zeichen)",
            }
            form  = _f(rec, 37, 1)
            inhalt_raw = rec[37:72]  # Position 38-72 = Feldinhalt
            current["monierungszeilen"].append({
                "fehlerschlüssel": _f(rec, 10, 3),
                "feldname":        _f(rec, 13, 20),
                "index1":          _f(rec, 33, 2),
                "index2":          _f(rec, 35, 2),
                "seite":           _f(rec, 37, 1),
                "zeile":           _f(rec, 38, 1),
                "position":        _f(rec, 39, 1),
                "feldformat":      form_map.get(form, form),
                "inhalt":          inhalt_raw.strip(),
                "_rohdaten":       rec[9:72].strip(),
            })

    if current:
        nachrichten.append(current)
    return nachrichten


# ---------------------------------------------------------------------------
# KNVB (22) Parser
# ---------------------------------------------------------------------------

def _parse_knvb(records: List[str]) -> List[Dict]:
    nachrichten = []
    current: Optional[Dict] = None

    for rec in records:
        sa    = rec[:2]
        kennz = rec[2:7].strip()

        if sa == "22" and kennz == "KS":
            if current:
                nachrichten.append(current)
            gnr_raw = _f(rec, 18, 11)
            current = {
                "typ": "KNVB",
                "kezi": _f(rec, 10, 8),
                "gerichtsnummer": _parse_gnr(gnr_raw),
                "geschaeftszeichen": _f(rec, 73, 35),
                "gebühren": {},
            }
        elif sa == "22" and kennz == "AUSGB" and current:
            current["gebühren"] = {
                "auslagen_antragsteller": _amt(_f(rec, 10, 8)),
                "gerichtsgebühr_gkg": _amt(_f(rec, 18, 7)),
                "zustellungsauslagen": _amt(_f(rec, 25, 4)),
                "ra_gebühr_rvg": _amt(_f(rec, 29, 9)),
                "ra_auslagen_rvg": _amt(_f(rec, 38, 7)),
                "ra_mwst": _amt(_f(rec, 45, 8)),
                "ausgerechnete_zinsen": _amt(_f(rec, 53, 10)),
                "nebenforderungen": _amt(_f(rec, 63, 10)),
            }

    if current:
        nachrichten.append(current)
    return nachrichten


# ---------------------------------------------------------------------------
# QU (90) Parser
# ---------------------------------------------------------------------------

def _parse_qu(records: List[str]) -> List[Dict]:
    zeilen = []
    for rec in records:
        if rec[:2] == "90" and rec[2:7].strip() == "QU":
            zeilen.append(_f(rec, 10, 116))
    return [{"typ": "QU", "protokollzeilen": zeilen}]
