"""
EDA Webhook API v2 – Vollständige Antragsunterstützung + Nachrichten-Parser

POST /generate/<typ>   → gibt .eda-Datei zurück
POST /parse            → liest .eda-Datei und gibt JSON zurück
POST /validate/<typ>   → prüft JSON, gibt Fehlerliste zurück
GET  /health           → Statuscheck
GET  /schema/<typ>     → JSON-Schema für Antragstyp
GET  /types            → Übersicht aller Typen

Antragstypen (POST /generate/<typ>):
  mba     – Mahnbescheidsantrag
  vba     – Vollstreckungsbescheidsantrag
  nemb    – Neuzustellungsantrag MB
  nevb    – Neuzustellungsantrag VB
  rn      – Rücknahme / Erledigterklärung
  ezkoab  – Kosteneinzug / Abgabeantrag
  wi      – Widerspruch
  moa     – Monierungsantwort
"""

import datetime
import json
import re
from flask import Flask, request, jsonify, Response

from eda_generator import (
    Metadaten, Partei, Prozessbevollmaechtigter,
    Bankverbindung, Anspruch, Nebenforderung,
    MBAntrag, VBAntrag, NEMBAntrag, NEVBAntrag,
    Ruecknahme, EZKOABAntrag, Widerspruch, MonierungsAntwort,
    NeuerGV, ZustellungsGV,
    generate_eda,
)
from eda_parser import parse_eda

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Mapping-Hilfsfunktionen
# ---------------------------------------------------------------------------

def _meta(d: dict) -> Metadaten:
    return Metadaten(
        tkezi=d.get("tkezi", "        "),
        ekezi=d.get("ekezi", "        "),
        edaid=d.get("edaid", "EDA001"),
        datum=d.get("datum", ""),
        software_name=d.get("software_name", "EDA-Generator"),
        software_version=d.get("software_version", "1.0"),
    )


def _partei(d: dict) -> Partei:
    return Partei(
        anrede=d.get("anrede", ""),
        rechtsform=d.get("rechtsform", ""),
        name1=d.get("name1", ""),
        name2=d.get("name2", ""),
        name3=d.get("name3", ""),
        name4=d.get("name4", ""),
        strasse=d.get("strasse", ""),
        plz=d.get("plz", ""),
        ort=d.get("ort", ""),
        ausland=d.get("ausland", ""),
        gesetzliche_vertreter=d.get("gesetzliche_vertreter", []),
        prozessgericht_schluessel=d.get("prozessgericht_schluessel", "1"),
        prozessgericht_plz=d.get("prozessgericht_plz", ""),
        prozessgericht_ort=d.get("prozessgericht_ort", ""),
    )


def _pv(d: dict) -> Prozessbevollmaechtigter:
    return Prozessbevollmaechtigter(
        anrede=str(d.get("anrede", "1")),
        bezeichnung=d.get("bezeichnung", ""),
        rechtsform=d.get("rechtsform", ""),
        strasse=d.get("strasse", ""),
        plz=d.get("plz", ""),
        ort=d.get("ort", ""),
        ausland=d.get("ausland", ""),
        gv_stellung=d.get("gv_stellung", ""),
        gv_name=d.get("gv_name", ""),
        geschaeftszeichen=d.get("geschaeftszeichen", ""),
        beauftragungsdatum=d.get("beauftragungsdatum", ""),
        auslagenbetrag=d.get("auslagenbetrag"),
        minderungsbetrag_vv2300=d.get("minderungsbetrag_vv2300"),
        erstattungsbetrag_iku=d.get("erstattungsbetrag_iku"),
        mwst_satz=d.get("mwst_satz", ""),
        vorsteuer_merkmal=d.get("vorsteuer_merkmal", ""),
        ust_merkmal=d.get("ust_merkmal", ""),
    )


def _anspruch(d: dict) -> Anspruch:
    return Anspruch(
        art=d.get("art", "katalog"),
        katalognummer1=str(d.get("katalognummer1", "")),
        katalognummer2=str(d.get("katalognummer2", "")),
        begruendung=d.get("begruendung", ""),
        rechnungsnummer=d.get("rechnungsnummer", ""),
        vom_datum=d.get("vom_datum", ""),
        bis_datum=d.get("bis_datum", ""),
        betrag=float(d.get("betrag", 0)),
        zinssatz=d.get("zinssatz"),
        zins_merkmal=d.get("zins_merkmal", "B"),
        zins_art=d.get("zins_art", "1"),
        zins_von=d.get("zins_von", ""),
        zins_bis=d.get("zins_bis", ""),
        zu_verzinsender_betrag=d.get("zu_verzinsender_betrag"),
        abtretungsdatum=d.get("abtretungsdatum", ""),
        abtretung_name=d.get("abtretung_name", ""),
        abtretung_plz=d.get("abtretung_plz", ""),
        abtretung_ort=d.get("abtretung_ort", ""),
    )


def _nebenforderung(d: dict) -> Nebenforderung:
    return Nebenforderung(
        art=d.get("art", ""),
        betrag=float(d.get("betrag", 0)),
        begruendung=d.get("begruendung", ""),
        zinssatz=d.get("zinssatz"),
        zins_merkmal=d.get("zins_merkmal", "B"),
        zins_von=d.get("zins_von", ""),
        zins_bis=d.get("zins_bis", ""),
        vv2300_streitwert=d.get("vv2300_streitwert"),
    )


def _neuer_gv(d: dict) -> NeuerGV:
    return NeuerGV(
        stellung=d.get("stellung", ""),
        name=d.get("name", ""),
        strasse=d.get("strasse", ""),
        plz=d.get("plz", ""),
        ort=d.get("ort", ""),
        ausland=d.get("ausland", ""),
    )


def _zgv(d: dict) -> ZustellungsGV:
    return ZustellungsGV(
        stellung=d.get("stellung", ""),
        name=d.get("name", ""),
        strasse=d.get("strasse", ""),
        plz=d.get("plz", ""),
        ort=d.get("ort", ""),
        ausland=d.get("ausland", ""),
    )


# ---------------------------------------------------------------------------
# JSON → Antragsobjekte
# ---------------------------------------------------------------------------

def _build_mba(d: dict) -> MBAntrag:
    return MBAntrag(
        meta=_meta(d),
        geschaeftszeichen=d.get("geschaeftszeichen", ""),
        mahngericht_plz=d.get("mahngericht_plz", ""),
        mahngericht_ort=d.get("mahngericht_ort", ""),
        antrag_auf_streitverfahren=d.get("antrag_auf_streitverfahren", False),
        gesamtschuldner=d.get("gesamtschuldner", False),
        anspruch_von_vorleistung=d.get("anspruch_von_vorleistung", False),
        antragsteller=[_partei(p) for p in d.get("antragsteller", [])],
        prozessbevollmaechtigter=_pv(d["prozessbevollmaechtigter"]) if d.get("prozessbevollmaechtigter") else None,
        bankverbindung=Bankverbindung(**d["bankverbindung"]) if d.get("bankverbindung") else None,
        antragsgegner=[_partei(p) for p in d.get("antragsgegner", [])],
        ausgerechnete_zinsen_betrag=d.get("ausgerechnete_zinsen_betrag"),
        ausgerechnete_zinsen_von=d.get("ausgerechnete_zinsen_von", ""),
        ausgerechnete_zinsen_bis=d.get("ausgerechnete_zinsen_bis", ""),
        ausgerechnete_zinsen_satz=d.get("ausgerechnete_zinsen_satz"),
        ansprueche=[_anspruch(a) for a in d.get("ansprueche", [])],
        nebenforderungen=[_nebenforderung(n) for n in d.get("nebenforderungen", [])],
        auslagen_vordruck=d.get("auslagen_vordruck"),
        auslagen_sonstige=d.get("auslagen_sonstige"),
        auslagen_sonstige_begruendung=d.get("auslagen_sonstige_begruendung", ""),
    )


def _build_vba(d: dict) -> VBAntrag:
    return VBAntrag(
        meta=_meta(d),
        tkezi_antrag=d.get("tkezi_antrag", ""),
        gnr=d.get("gnr", ""),
        geschaeftszeichen=d.get("geschaeftszeichen", ""),
        antragsdatum=d.get("antragsdatum", ""),
        zahlungen_merkmal=d.get("zahlungen_merkmal", "1"),
        zustellungsart=d.get("zustellungsart", "1"),
        porto_betrag=d.get("porto_betrag"),
        sonstige_kosten=d.get("sonstige_kosten"),
        sonstige_kosten_begruendung=d.get("sonstige_kosten_begruendung", ""),
        zinsen_auf_kosten=d.get("zinsen_auf_kosten", False),
        aspv_ikubet=d.get("aspv_ikubet"),
        zahlungen=d.get("zahlungen", []),
        weitere_auslagen=d.get("weitere_auslagen", []),
        antragsgegner=[_partei(p) for p in d.get("antragsgegner", [])],
        neuer_gv=_neuer_gv(d["neuer_gv"]) if d.get("neuer_gv") else None,
        zustellungs_gv=_zgv(d["zustellungs_gv"]) if d.get("zustellungs_gv") else None,
    )


def _build_nemb(d: dict) -> NEMBAntrag:
    return NEMBAntrag(
        meta=_meta(d),
        tkezi_antrag=d.get("tkezi_antrag", ""),
        gnr=d.get("gnr", ""),
        geschaeftszeichen=d.get("geschaeftszeichen", ""),
        porto_betrag=d.get("porto_betrag"),
        sonstige_kosten=d.get("sonstige_kosten"),
        sonstige_kosten_begruendung=d.get("sonstige_kosten_begruendung", ""),
        auskunftskosten=d.get("auskunftskosten"),
        antragsgegner=[_partei(p) for p in d.get("antragsgegner", [])],
        neuer_gv=_neuer_gv(d["neuer_gv"]) if d.get("neuer_gv") else None,
        zustellungs_gv=_zgv(d["zustellungs_gv"]) if d.get("zustellungs_gv") else None,
    )


def _build_nevb(d: dict) -> NEVBAntrag:
    return NEVBAntrag(
        meta=_meta(d),
        tkezi_antrag=d.get("tkezi_antrag", ""),
        gnr=d.get("gnr", ""),
        geschaeftszeichen=d.get("geschaeftszeichen", ""),
        zustellungsart=d.get("zustellungsart", "1"),
        ag_strasse=d.get("ag_strasse", ""),
        ag_plz=d.get("ag_plz", ""),
        ag_ort=d.get("ag_ort", ""),
        ag_ausland=d.get("ag_ausland", ""),
        zustellungs_gv=_zgv(d["zustellungs_gv"]) if d.get("zustellungs_gv") else None,
    )


def _build_rn(d: dict) -> Ruecknahme:
    return Ruecknahme(
        meta=_meta(d),
        tkezi_antrag=d.get("tkezi_antrag", ""),
        geschaeftszeichen=d.get("geschaeftszeichen", ""),
        merkmal=d.get("merkmal", "R"),
        gnr_merkmal=d.get("gnr_merkmal", "J"),
        gnr=d.get("gnr", ""),
        mb_eingang_merkmal=d.get("mb_eingang_merkmal", "E"),
        as_anrede=d.get("as_anrede", ""),
        as_name1=d.get("as_name1", ""),
        as_name2=d.get("as_name2", ""),
        as_strasse=d.get("as_strasse", ""),
        as_plz=d.get("as_plz", ""),
        as_ort=d.get("as_ort", ""),
        as_rechtsform=d.get("as_rechtsform", "2"),
        ag_anrede=d.get("ag_anrede", ""),
        ag_name1=d.get("ag_name1", ""),
        ag_name2=d.get("ag_name2", ""),
        ag_strasse=d.get("ag_strasse", ""),
        ag_plz=d.get("ag_plz", ""),
        ag_ort=d.get("ag_ort", ""),
        ag_rechtsform=d.get("ag_rechtsform", "2"),
        anspruchsbetrag=d.get("anspruchsbetrag"),
    )


def _build_ezkoab(d: dict) -> EZKOABAntrag:
    return EZKOABAntrag(
        meta=_meta(d),
        tkezi_antrag=d.get("tkezi_antrag", ""),
        gnr=d.get("gnr", ""),
        geschaeftszeichen=d.get("geschaeftszeichen", ""),
    )


def _build_wi(d: dict) -> Widerspruch:
    return Widerspruch(
        meta=_meta(d),
        agpv_kezi=d.get("agpv_kezi", ""),
        gnr=d.get("gnr", ""),
        geschaeftszeichen_ag=d.get("geschaeftszeichen_ag", ""),
        widerspruchs_merkmal=d.get("widerspruchs_merkmal", "1"),
        widerspruchsbetrag_hf=d.get("widerspruchsbetrag_hf"),
        widerspruch_zinsen=d.get("widerspruch_zinsen", False),
        zinssatz_merkmal=d.get("zinssatz_merkmal", ""),
        zinssatz=d.get("zinssatz"),
        widerspruch_verfahrenskosten=d.get("widerspruch_verfahrenskosten", False),
        widerspruchsbetrag_nf=d.get("widerspruchsbetrag_nf"),
        ag_strasse=d.get("ag_strasse", ""),
        ag_plz=d.get("ag_plz", ""),
        ag_ort=d.get("ag_ort", ""),
        ag_ausland=d.get("ag_ausland", ""),
        ag_gv_stellung=d.get("ag_gv_stellung", ""),
        ag_gv_name=d.get("ag_gv_name", ""),
        ag_gv_strasse=d.get("ag_gv_strasse", ""),
        ag_gv_plz=d.get("ag_gv_plz", ""),
        ag_gv_ort=d.get("ag_gv_ort", ""),
        ag_gv_ausland=d.get("ag_gv_ausland", ""),
    )


def _build_moa(d: dict) -> MonierungsAntwort:
    return MonierungsAntwort(
        meta=_meta(d),
        tkezi_antrag=d.get("tkezi_antrag", ""),
        geschaeftszeichen=d.get("geschaeftszeichen", ""),
        gnrs=d.get("gnrs", []),
        monierungsdatum=d.get("monierungsdatum", ""),
        antragsdatum=d.get("antragsdatum", ""),
        monierte_antragsart=d.get("monierte_antragsart", "01"),
        monierungszeilen=d.get("monierungszeilen", []),
    )


BUILDERS = {
    "mba":    _build_mba,
    "vba":    _build_vba,
    "nemb":   _build_nemb,
    "nevb":   _build_nevb,
    "rn":     _build_rn,
    "ezkoab": _build_ezkoab,
    "wi":     _build_wi,
    "moa":    _build_moa,
}

TYPE_NAMES = {
    "mba":    "Mahnbescheidsantrag (MBA, Satzart 01)",
    "vba":    "Vollstreckungsbescheidsantrag (VBA, Satzart 08)",
    "nemb":   "Neuzustellungsantrag MB (NEMB, Satzart 07)",
    "nevb":   "Neuzustellungsantrag VB (NEVB, Satzart 10)",
    "rn":     "Rücknahme / Erledigterklärung (RN, Satzart 25)",
    "ezkoab": "Kosteneinzug / Abgabeantrag (EZKOAB, Satzart 29)",
    "wi":     "Widerspruch (WI, Satzart 30)",
    "moa":    "Monierungsantwort (MOA, Satzart 20)",
}

PARSER_TYPES = {
    "03": "KNMB – Kosten-/Erlassnachricht MB",
    "05": "ZNMBVB – Zustellungs-/Nichtzustellungsnachricht",
    "16": "ABN – Abgabenachricht",
    "18": "WIN – Widerspruchsnachricht",
    "20": "MO – Monierung",
    "22": "KNVB – Kosten-/Erlassnachricht VB",
    "90": "QU – Eingangsbestätigung",
}


# ---------------------------------------------------------------------------
# Validierung
# ---------------------------------------------------------------------------

def _validate(typ: str, d: dict) -> list:
    errors = []

    def req(field, label):
        if not d.get(field):
            errors.append(f"{label} ({field}) ist erforderlich")

    def req_list(field, label, min_len=1):
        lst = d.get(field, [])
        if len(lst) < min_len:
            errors.append(f"Mindestens {min_len} {label} ({field}) erforderlich")
        return lst

    # Gemeinsame Felder
    if typ in ("vba", "nemb", "nevb", "rn", "ezkoab"):
        req("gnr", "Gerichtsnummer")
        req("geschaeftszeichen", "Geschäftszeichen")
    if typ == "wi":
        req("gnr", "Gerichtsnummer")

    if typ == "mba":
        req("mahngericht_plz", "Mahngericht PLZ")
        req("mahngericht_ort", "Mahngericht Ort")
        req("geschaeftszeichen", "Geschäftszeichen")
        asts = req_list("antragsteller", "Antragsteller")
        for i, ast in enumerate(asts):
            if not ast.get("name1"):
                errors.append(f"antragsteller[{i}].name1 fehlt")
            if not ast.get("strasse"):
                errors.append(f"antragsteller[{i}].strasse fehlt")
            if not ast.get("plz"):
                errors.append(f"antragsteller[{i}].plz fehlt")
            if not ast.get("ort"):
                errors.append(f"antragsteller[{i}].ort fehlt")
        ags = req_list("antragsgegner", "Antragsgegner")
        for i, ag in enumerate(ags):
            if not ag.get("name1"):
                errors.append(f"antragsgegner[{i}].name1 fehlt")
        asps = req_list("ansprueche", "Anspruch")
        for i, asp in enumerate(asps):
            if float(asp.get("betrag", 0)) <= 0:
                errors.append(f"ansprueche[{i}].betrag muss > 0 sein")
        bv = d.get("bankverbindung")
        if bv:
            iban = bv.get("iban", "").replace(" ", "")
            if not re.match(r'^[A-Z]{2}\d{2}[A-Z0-9]+$', iban):
                errors.append("bankverbindung.iban ist ungültig")

    elif typ == "vba":
        req("gnr", "Gerichtsnummer")
        if not d.get("antragsgegner"):
            errors.append("Mindestens ein Antragsgegner erforderlich")

    elif typ in ("nemb", "nevb"):
        req("gnr", "Gerichtsnummer")

    elif typ == "rn":
        req("merkmal", "Rücknahme-Merkmal (R oder E)")
        req("gnr_merkmal", "GNR-Merkmal (J, N oder Z)")
        if d.get("gnr_merkmal") == "J":
            req("gnr", "Gerichtsnummer")

    elif typ == "ezkoab":
        req("gnr", "Gerichtsnummer")

    elif typ == "wi":
        req("agpv_kezi", "AG-PV-Kennziffer")
        req("gnr", "Gerichtsnummer")

    elif typ == "moa":
        if not d.get("gnrs"):
            errors.append("Mindestens eine Gerichtsnummer (gnrs) erforderlich")
        if not d.get("monierungszeilen"):
            errors.append("Monierungszeilen (monierungszeilen) fehlen")

    return errors


# ---------------------------------------------------------------------------
# Routen
# ---------------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "version": "2.0", "time": datetime.datetime.now().isoformat()})


@app.route("/types", methods=["GET"])
def types():
    return jsonify({
        "ausgehend": TYPE_NAMES,
        "eingehend_parser": PARSER_TYPES,
        "beschreibung": "POST /generate/<typ> zum Generieren, POST /parse zum Einlesen von Gerichtsnachrichten"
    })


@app.route("/validate/<typ>", methods=["POST"])
def validate_endpoint(typ):
    typ = typ.lower()
    if typ not in BUILDERS:
        return jsonify({"error": f"Unbekannter Typ '{typ}'. Verfügbar: {list(BUILDERS.keys())}"}), 400
    if not request.is_json:
        return jsonify({"error": "Content-Type muss application/json sein"}), 400
    data = request.get_json()
    errors = _validate(typ, data)
    if errors:
        return jsonify({"valid": False, "errors": errors}), 422
    return jsonify({"valid": True, "errors": []})


@app.route("/generate/<typ>", methods=["POST"])
def generate_endpoint(typ):
    typ = typ.lower()
    if typ not in BUILDERS:
        return jsonify({"error": f"Unbekannter Typ '{typ}'. Verfügbar: {list(BUILDERS.keys())}"}), 400
    if not request.is_json:
        return jsonify({"error": "Content-Type muss application/json sein"}), 400

    data = request.get_json()
    errors = _validate(typ, data)
    if errors:
        return jsonify({"valid": False, "errors": errors}), 422

    try:
        antrag = BUILDERS[typ](data)
        eda_bytes = generate_eda(antrag)
    except Exception as e:
        return jsonify({"error": f"Generierungsfehler: {str(e)}"}), 500

    edaid   = data.get("edaid", "EDA001").upper()
    datum   = datetime.date.today().strftime("%d_%m_%Y")
    filename = f"EDA_{typ.upper()}_{datum}_{edaid}.eda"

    return Response(
        eda_bytes,
        mimetype="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-EDA-Type": typ.upper(),
            "X-EDA-Records": str(len(eda_bytes) // 130),
        }
    )


@app.route("/parse", methods=["POST"])
def parse_endpoint():
    """
    Liest eine .eda-Gerichtsnachricht und gibt strukturiertes JSON zurück.
    Content-Type: application/octet-stream  (rohe EDA-Bytes)
    oder multipart/form-data mit Feld 'file'
    """
    if request.content_type and "multipart" in request.content_type:
        if "file" not in request.files:
            return jsonify({"error": "Kein 'file'-Feld in multipart/form-data"}), 400
        raw = request.files["file"].read()
    else:
        raw = request.get_data()

    if not raw:
        return jsonify({"error": "Keine Daten empfangen"}), 400

    try:
        result = parse_eda(raw)
    except Exception as e:
        return jsonify({"error": f"Parser-Fehler: {str(e)}"}), 500

    return jsonify(result)


@app.route("/schema/<typ>", methods=["GET"])
def schema_endpoint(typ):
    typ = typ.lower()
    schemas = {
        "mba": {
            "beschreibung": "Mahnbescheidsantrag (Satzart 01, Format 4000)",
            "pflichtfelder": ["mahngericht_plz", "mahngericht_ort", "geschaeftszeichen", "antragsteller", "antragsgegner", "ansprueche"],
            "felder": {
                "tkezi": "Kennziffer EDA-Teilnehmer (8-stellig)",
                "edaid": "Dateikennung (6 Zeichen, Großbuchst., unique je 2 Wochen)",
                "geschaeftszeichen": "Ihr Aktenzeichen (max. 35 Z.)",
                "mahngericht_plz": "PLZ des Mahngerichts",
                "mahngericht_ort": "Ort des Mahngerichts",
                "antrag_auf_streitverfahren": "bool – Abgabe bei Widerspruch",
                "gesamtschuldner": "bool – mehrere AG als Gesamtschuldner",
                "antragsteller": "[{anrede, rechtsform, name1, name2, strasse, plz, ort, gesetzliche_vertreter}]",
                "prozessbevollmaechtigter": "{anrede, bezeichnung, rechtsform, strasse, plz, ort, ...}",
                "bankverbindung": "{kontozuordnung, iban, bic}",
                "antragsgegner": "[{name1, strasse, plz, ort, prozessgericht_plz, prozessgericht_ort, ...}]",
                "ansprueche": "[{art, katalognummer1, begruendung, betrag, zinssatz, ...}]",
                "nebenforderungen": "[{art: mahnk|ausk|bkrl|inkb|vv23|anf, betrag, ...}]",
                "auslagen_sonstige": "Betrag in EUR",
                "auslagen_sonstige_begruendung": "max. 35 Z."
            }
        },
        "vba": {
            "beschreibung": "Vollstreckungsbescheidsantrag (Satzart 08, Format 4100)",
            "pflichtfelder": ["gnr", "geschaeftszeichen", "antragsgegner"],
            "felder": {
                "gnr": "Gerichtsnummer (11-stellig, z.B. '26-1234567-0-1')",
                "geschaeftszeichen": "Ihr Aktenzeichen",
                "antragsdatum": "Datum YYYY-MM-DD",
                "zahlungen_merkmal": "'1'=keine Zahlungen, '2'=Zahlungen vorhanden",
                "zustellungsart": "'1'=Mahngericht, '2'=Parteibetrieb",
                "porto_betrag": "Porto/Telefon nach MB-Zustellung (EUR)",
                "sonstige_kosten": "Sonstige Kosten nach MB-Zustellung (EUR)",
                "zinsen_auf_kosten": "bool – Zinsen gem. § 104 ZPO",
                "zahlungen": "[{datum: YYYY-MM-DD, betrag: EUR}] – max. 12",
                "weitere_auslagen": "[{betrag, begruendung}] – max. 2",
                "antragsgegner": "[{name1, rechtsform, strasse, plz, ort}]",
                "neuer_gv": "{stellung, name, strasse, plz, ort} – neuer gesetzl. Vertreter",
                "zustellungs_gv": "{stellung, name, strasse, plz, ort} – GV als Zustellungsempfänger",
                "aspv_ikubet": "IKU-Erstattungsbetrag für VB-Antrag (EUR)"
            }
        },
        "nemb": {
            "beschreibung": "Neuzustellungsantrag MB (Satzart 07, Format 4100)",
            "pflichtfelder": ["gnr", "geschaeftszeichen"],
            "felder": {
                "gnr": "Gerichtsnummer",
                "geschaeftszeichen": "Ihr Aktenzeichen",
                "porto_betrag": "Porto/Telefon (EUR)",
                "sonstige_kosten": "Sonstige Kosten (EUR)",
                "auskunftskosten": "Auskunftskosten (EUR)",
                "antragsgegner": "[{name1, rechtsform, strasse, plz, ort, prozessgericht_*}]",
                "neuer_gv": "{stellung, name, strasse, plz, ort}",
                "zustellungs_gv": "{stellung, name, strasse, plz, ort}"
            }
        },
        "nevb": {
            "beschreibung": "Neuzustellungsantrag VB (Satzart 10, Format 4100)",
            "pflichtfelder": ["gnr", "geschaeftszeichen"],
            "felder": {
                "gnr": "Gerichtsnummer",
                "geschaeftszeichen": "Ihr Aktenzeichen",
                "zustellungsart": "'1'=Mahngericht, '2'=Parteibetrieb",
                "ag_strasse": "Neue AG-Strasse",
                "ag_plz": "Neue AG-PLZ",
                "ag_ort": "Neuer AG-Ort",
                "zustellungs_gv": "{stellung, name, strasse, plz, ort}"
            }
        },
        "rn": {
            "beschreibung": "Rücknahme / Erledigterklärung (Satzart 25, Format 4000)",
            "pflichtfelder": ["merkmal", "gnr_merkmal"],
            "felder": {
                "merkmal": "'R'=Rücknahme, 'E'=Erledigt",
                "gnr_merkmal": "'J'=mit GNR, 'N'=ohne GNR (Parteikurzdaten), 'Z'=eindeutiges GZ+KEZI",
                "gnr": "Gerichtsnummer (bei gnr_merkmal='J')",
                "mb_eingang_merkmal": "'B'=Vordruck, 'E'=maschinell",
                "geschaeftszeichen": "Ihr Aktenzeichen",
                "as_name1/as_name2/...": "Parteikurzdaten (nur bei gnr_merkmal='N')",
                "anspruchsbetrag": "Summe der Hauptansprüche (EUR, nur bei gnr_merkmal='N')"
            }
        },
        "ezkoab": {
            "beschreibung": "Kosteneinzug / Abgabeantrag (Satzart 29, Format 4000)",
            "pflichtfelder": ["gnr", "geschaeftszeichen"],
            "felder": {
                "gnr": "Gerichtsnummer",
                "geschaeftszeichen": "Ihr Aktenzeichen",
                "tkezi_antrag": "Kennziffer im Antrag"
            }
        },
        "wi": {
            "beschreibung": "Widerspruch durch Prozessbevollmächtigten des AG (Satzart 30, Format 4100)",
            "pflichtfelder": ["agpv_kezi", "gnr"],
            "felder": {
                "agpv_kezi": "PV-Kennziffer des Widersprechenden (Stelle 3 muss 5-7 sein)",
                "gnr": "Gerichtsnummer des Mahnbescheids",
                "geschaeftszeichen_ag": "Geschäftszeichen des AGPV",
                "widerspruchs_merkmal": "'1'=Gesamtwiderspruch, '2'=Teilwiderspruch",
                "widerspruchsbetrag_hf": "Widersprochene Hauptforderung EUR (bei Teilwiderspruch)",
                "widerspruch_zinsen": "bool",
                "widerspruch_verfahrenskosten": "bool",
                "widerspruchsbetrag_nf": "Widersprochene Nebenforderung EUR",
                "ag_strasse/ag_plz/ag_ort": "Abweichende AG-Anschrift (optional)",
                "ag_gv_stellung/ag_gv_name/...": "Abweichender GV des AG (optional)"
            }
        },
        "moa": {
            "beschreibung": "Monierungsantwort (Satzart 20, Format 4000)",
            "pflichtfelder": ["gnrs", "monierungszeilen"],
            "felder": {
                "tkezi_antrag": "Kennziffer",
                "geschaeftszeichen": "Ihr Aktenzeichen",
                "gnrs": "Liste der Gerichtsnummern (wie in der Monierung)",
                "monierungsdatum": "Datum der Monierung JJMMTT",
                "antragsdatum": "Datum des monierten Antrags JJMMTT",
                "monierte_antragsart": "01=MB, 02=VB, 07=NEMB, 10=NEVB ...",
                "monierungszeilen": "Komplette G02-Sätze aus der Monierung, nur 'inhalt' ändern. [{fschl, feldn, index1, index2, mas, maz, mazpos, form, inhalt}]"
            }
        },
    }
    schema = schemas.get(typ)
    if not schema:
        return jsonify({"error": f"Kein Schema für Typ '{typ}'"}), 404
    return jsonify({**schema, "typ": typ, "name": TYPE_NAMES.get(typ, typ)})


@app.route("/example/<typ>", methods=["GET"])
def example_endpoint(typ):
    typ = typ.lower()
    examples = {
        "mba": {
            "tkezi": "07012345",
            "edaid": "MBA001",
            "geschaeftszeichen": "Musterfirma ./. Schuldner GmbH 2026-001",
            "mahngericht_plz": "70154",
            "mahngericht_ort": "Stuttgart",
            "antrag_auf_streitverfahren": True,
            "antragsteller": [{"rechtsform": "GmbH", "name1": "Musterfirma GmbH",
                "strasse": "Musterstraße 1", "plz": "70182", "ort": "Stuttgart",
                "gesetzliche_vertreter": [{"stellung": "Geschäftsführer", "name": "Max Mustermann"}]}],
            "antragsgegner": [{"rechtsform": "GmbH", "name1": "Schuldner GmbH",
                "strasse": "Schuldnerweg 5", "plz": "70190", "ort": "Stuttgart",
                "prozessgericht_plz": "70190", "prozessgericht_ort": "Stuttgart",
                "gesetzliche_vertreter": [{"stellung": "Geschäftsführer", "name": "Hans Schulze",
                    "strasse": "Privatweg 3", "plz": "70192", "ort": "Stuttgart"}]}],
            "bankverbindung": {"kontozuordnung": "1", "iban": "DE21700202700035665790", "bic": "HYVEDEMMXXX"},
            "ansprueche": [{"art": "katalog", "katalognummer1": "4",
                "begruendung": "Darlehensvertrag", "rechnungsnummer": "DV-2025-001",
                "vom_datum": "2025-01-15", "betrag": 5000.00,
                "zinssatz": 9.0, "zins_merkmal": "B", "zins_art": "1", "zins_von": "2026-01-01"}],
            "nebenforderungen": [{"art": "anf", "betrag": 40.00, "begruendung": "Verzugspauschale § 288 Abs. 5 BGB"}]
        },
        "vba": {
            "tkezi": "07012345",
            "edaid": "VBA001",
            "gnr": "26-1234567-0-1",
            "geschaeftszeichen": "Musterfirma ./. Schuldner GmbH 2026-001",
            "antragsdatum": "2026-03-01",
            "zahlungen_merkmal": "1",
            "zustellungsart": "1",
            "antragsgegner": [{"rechtsform": "GmbH", "name1": "Schuldner GmbH",
                "strasse": "Schuldnerweg 5", "plz": "70190", "ort": "Stuttgart"}]
        },
        "nemb": {
            "tkezi": "07012345",
            "edaid": "NMB001",
            "gnr": "26-1234567-0-1",
            "geschaeftszeichen": "Musterfirma ./. Schuldner GmbH 2026-001",
            "antragsgegner": [{"rechtsform": "GmbH", "name1": "Schuldner GmbH",
                "strasse": "Neue Straße 10", "plz": "70180", "ort": "Stuttgart",
                "prozessgericht_plz": "70190", "prozessgericht_ort": "Stuttgart"}]
        },
        "nevb": {
            "tkezi": "07012345",
            "edaid": "NVB001",
            "gnr": "26-1234567-0-1",
            "geschaeftszeichen": "Musterfirma ./. Schuldner GmbH 2026-001",
            "zustellungsart": "1",
            "ag_strasse": "Neue Straße 10",
            "ag_plz": "70180",
            "ag_ort": "Stuttgart"
        },
        "rn": {
            "tkezi": "07012345",
            "edaid": "RN0001",
            "geschaeftszeichen": "Musterfirma ./. Schuldner GmbH 2026-001",
            "merkmal": "R",
            "gnr_merkmal": "J",
            "gnr": "26-1234567-0-1",
            "mb_eingang_merkmal": "E"
        },
        "ezkoab": {
            "tkezi": "07012345",
            "edaid": "EZK001",
            "gnr": "26-1234567-0-1",
            "geschaeftszeichen": "Musterfirma ./. Schuldner GmbH 2026-001",
            "tkezi_antrag": "07012345"
        },
        "wi": {
            "tkezi": "07056789",
            "edaid": "WI0001",
            "agpv_kezi": "07056789",
            "gnr": "26-1234567-0-1",
            "geschaeftszeichen_ag": "RA Müller Aktenzeichen 2026/123",
            "widerspruchs_merkmal": "1"
        },
        "moa": {
            "tkezi": "07012345",
            "edaid": "MOA001",
            "tkezi_antrag": "07012345",
            "geschaeftszeichen": "Musterfirma ./. Schuldner GmbH 2026-001",
            "gnrs": ["26-1234567-0-1"],
            "monierungsdatum": "260315",
            "antragsdatum": "260301",
            "monierte_antragsart": "01",
            "monierungszeilen": [
                {"fschl": "042", "feldn": "AGSH", "index1": "01", "index2": "00",
                 "mas": "1", "maz": "3", "mazpos": "1", "form": "1",
                 "inhalt": "Neue Straße 15"}
            ]
        }
    }
    example = examples.get(typ)
    if not example:
        return jsonify({"error": f"Kein Beispiel für Typ '{typ}'"}), 404
    return jsonify(example)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
