"""
EDA Generator – Alle ausgehenden Antragsarten (Format 4.x)
Zeichensatz: CP850, feste Satzlänge 128 Bytes (+ CRLF)

Unterstützte Satzarten:
  01 – Mahnbescheidsantrag (MBA)
  07 – Neuzustellungsantrag MB (NEMB)
  08 – Vollstreckungsbescheidsantrag (VBA)
  10 – Neuzustellungsantrag VB (NEVB)
  20 – Monierungsantwort (MOA)
  25 – Rücknahme / Erledigterklärung (RN)
  29 – Kosteneinzug / Abgabeantrag (EZKOAB)
  30 – Widerspruch (WI)
"""

import datetime
from dataclasses import dataclass, field
from typing import Optional, List


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _l(value: str, length: int) -> str:
    """Linksbündig, mit Leerzeichen aufgefüllt."""
    return str(value or "")[:length].ljust(length)


def _r(value, length: int, fill: str = "0") -> str:
    """Rechtsbündig, mit Zeichen aufgefüllt (Standard: Nullen)."""
    return str(value or "0")[:length].rjust(length, fill)


def _num(value, length: int, decimals: int = 0) -> str:
    """Betrag als Festkommazahl (z.B. 123.45 → '0000012345' bei dec=2)."""
    if value is None or value == "":
        return " " * length
    try:
        cent = round(float(value) * (10 ** decimals))
        return str(int(cent)).rjust(length, "0")[:length]
    except Exception:
        return " " * length


def _num_b(value, length: int, decimals: int = 0) -> str:
    """Wie _num, aber Leerwert = BLANK statt NULL."""
    if value is None or value == "" or float(value or 0) == 0:
        return " " * length
    return _num(value, length, decimals)


def _date(value: Optional[str]) -> str:
    """Datum JJMMTT aus ISO YYYY-MM-DD oder JJMMTT."""
    if not value:
        return " " * 6
    v = value.replace("-", "")
    if len(v) == 8:
        return v[2:]
    return v[:6]


def _record(data: str) -> bytes:
    """Satz auf exakt 128 Bytes bringen, CP850 kodieren, CRLF anhängen."""
    encoded = data[:125].encode("cp850", errors="replace")
    encoded = encoded.ljust(125, b" ")
    encoded += b"   "
    return encoded + b"\r\n"


def _gnr_sum(gnrs: List[str]) -> int:
    """Kontrollsumme: Stellen 3-9 der GNR ohne Jahr und Zusatz."""
    total = 0
    for gnr in gnrs:
        if not gnr:
            continue
        clean = gnr.replace("-", "").replace("N", "").strip()
        # GNR: JJ-NNNNNNN-P-S → 11-stellig: JJNNNNNNNPS
        # laufende Nummer = Stellen 3-9 (0-indiziert: [2:9])
        if len(clean) >= 9:
            try:
                total += int(clean[2:9])
            except ValueError:
                pass
    return total


# ---------------------------------------------------------------------------
# Basis-AA/BB-Satz
# ---------------------------------------------------------------------------

def _aa(tkezi: str, datum: str, belart: str, ekezi: str, fmt: str,
        edaid: str, swn: str, swv: str) -> bytes:
    s  = "AA"
    s += _l(tkezi, 8)
    s += _date(datum) if len(datum) > 6 else datum.ljust(6)
    s += _l(belart, 2)
    s += _l(ekezi, 8)
    s += _l(fmt, 4)
    s += _l(edaid.upper(), 6)
    s += "  "          # FILLER 37-38
    s += " "           # FILLER 39
    s += " " * 16      # FILLER 40-55
    s += _l(swn, 20)
    s += _l(swv, 10)
    s += " " * 40
    return _record(s)


def _bb(tkezi: str, antanz: int, sanz: int, skatnr: int = 0,
        suasp_cent: int = 0, sugnr: int = 0, aspanz: int = 0) -> bytes:
    s  = "BB"
    s += _l(tkezi, 8)
    s += _r(antanz, 7)
    s += _r(sanz, 7)
    s += _r(skatnr, 7)
    s += _r(suasp_cent, 14)
    s += _r(sugnr, 15)
    s += _r(aspanz, 7)
    s += " " * 61
    return _record(s)


# ---------------------------------------------------------------------------
# Datenklassen
# ---------------------------------------------------------------------------

@dataclass
class Metadaten:
    tkezi: str = "        "
    ekezi: str = "        "
    edaid: str = "EDA001"
    datum: str = ""
    software_name: str = "EDA-Generator"
    software_version: str = "1.0"

    def today_str(self) -> str:
        return self.datum or datetime.date.today().strftime("%y%m%d")


@dataclass
class Partei:
    anrede: str = ""
    rechtsform: str = ""
    name1: str = ""
    name2: str = ""
    name3: str = ""
    name4: str = ""
    strasse: str = ""
    plz: str = ""
    ort: str = ""
    ausland: str = ""
    gesetzliche_vertreter: List[dict] = field(default_factory=list)
    prozessgericht_schluessel: str = "1"
    prozessgericht_plz: str = ""
    prozessgericht_ort: str = ""


@dataclass
class NeuerGV:
    """Neuer gesetzlicher Vertreter (VBA/NEMB)."""
    stellung: str = ""
    name: str = ""
    strasse: str = ""
    plz: str = ""
    ort: str = ""
    ausland: str = ""


@dataclass
class ZustellungsGV:
    """Gesetzlicher Vertreter als Zustellungsempfänger."""
    stellung: str = ""
    name: str = ""
    strasse: str = ""
    plz: str = ""
    ort: str = ""
    ausland: str = ""


@dataclass
class Prozessbevollmaechtigter:
    anrede: str = "1"
    bezeichnung: str = ""
    rechtsform: str = ""
    strasse: str = ""
    plz: str = ""
    ort: str = ""
    ausland: str = ""
    gv_stellung: str = ""
    gv_name: str = ""
    geschaeftszeichen: str = ""
    beauftragungsdatum: str = ""
    auslagenbetrag: Optional[float] = None
    minderungsbetrag_vv2300: Optional[float] = None
    erstattungsbetrag_iku: Optional[float] = None
    mwst_satz: str = ""
    vorsteuer_merkmal: str = ""
    ust_merkmal: str = ""


@dataclass
class Bankverbindung:
    kontozuordnung: str = "1"
    iban: str = ""
    bic: str = ""


@dataclass
class Anspruch:
    art: str = "katalog"
    katalognummer1: str = ""
    katalognummer2: str = ""
    begruendung: str = ""
    rechnungsnummer: str = ""
    vom_datum: str = ""
    bis_datum: str = ""
    betrag: float = 0.0
    zinssatz: Optional[float] = None
    zins_merkmal: str = "B"
    zins_art: str = "1"
    zins_von: str = ""
    zins_bis: str = ""
    zu_verzinsender_betrag: Optional[float] = None
    abtretungsdatum: str = ""
    abtretung_name: str = ""
    abtretung_plz: str = ""
    abtretung_ort: str = ""


@dataclass
class Nebenforderung:
    art: str = ""
    betrag: float = 0.0
    begruendung: str = ""
    zinssatz: Optional[float] = None
    zins_merkmal: str = "B"
    zins_von: str = ""
    zins_bis: str = ""
    vv2300_streitwert: Optional[float] = None


# ---------------------------------------------------------------------------
# MBA (Satzart 01) – unverändert aus v1
# ---------------------------------------------------------------------------

@dataclass
class MBAntrag:
    meta: Metadaten = field(default_factory=Metadaten)
    geschaeftszeichen: str = ""
    mahngericht_plz: str = ""
    mahngericht_ort: str = ""
    antrag_auf_streitverfahren: bool = False
    gesamtschuldner: bool = False
    anspruch_von_vorleistung: bool = False
    antragsteller: List[Partei] = field(default_factory=list)
    prozessbevollmaechtigter: Optional[Prozessbevollmaechtigter] = None
    bankverbindung: Optional[Bankverbindung] = None
    antragsgegner: List[Partei] = field(default_factory=list)
    ausgerechnete_zinsen_betrag: Optional[float] = None
    ausgerechnete_zinsen_von: str = ""
    ausgerechnete_zinsen_bis: str = ""
    ausgerechnete_zinsen_satz: Optional[float] = None
    ansprueche: List[Anspruch] = field(default_factory=list)
    nebenforderungen: List[Nebenforderung] = field(default_factory=list)
    auslagen_vordruck: Optional[float] = None
    auslagen_sonstige: Optional[float] = None
    auslagen_sonstige_begruendung: str = ""


# ---------------------------------------------------------------------------
# VBA (Satzart 08)
# ---------------------------------------------------------------------------

@dataclass
class VBAntrag:
    meta: Metadaten = field(default_factory=Metadaten)
    tkezi_antrag: str = ""            # Kennziffer im Kennsatz (kann leer sein)
    gnr: str = ""                     # Gerichtsnummer (11-stellig)
    geschaeftszeichen: str = ""
    antragsdatum: str = ""            # YYYY-MM-DD
    zahlungen_merkmal: str = "1"      # 1=keine Zahlungen, 2=Zahlungen vorhanden
    zustellungsart: str = "1"         # 1=Mahngericht, 2=Parteibetrieb
    porto_betrag: Optional[float] = None
    sonstige_kosten: Optional[float] = None
    sonstige_kosten_begruendung: str = ""
    zinsen_auf_kosten: bool = False
    aspv_ikubet: Optional[float] = None   # IKU-Erstattungsbetrag VB
    zahlungen: List[dict] = field(default_factory=list)  # [{datum, betrag}]
    weitere_auslagen: List[dict] = field(default_factory=list)  # [{betrag, begruendung}]
    antragsgegner: List[Partei] = field(default_factory=list)
    neuer_gv: Optional[NeuerGV] = None
    zustellungs_gv: Optional[ZustellungsGV] = None


# ---------------------------------------------------------------------------
# NEMB (Satzart 07)
# ---------------------------------------------------------------------------

@dataclass
class NEMBAntrag:
    meta: Metadaten = field(default_factory=Metadaten)
    tkezi_antrag: str = ""
    gnr: str = ""
    geschaeftszeichen: str = ""
    porto_betrag: Optional[float] = None
    sonstige_kosten: Optional[float] = None
    sonstige_kosten_begruendung: str = ""
    auskunftskosten: Optional[float] = None
    antragsgegner: List[Partei] = field(default_factory=list)
    neuer_gv: Optional[NeuerGV] = None
    zustellungs_gv: Optional[ZustellungsGV] = None


# ---------------------------------------------------------------------------
# NEVB (Satzart 10)
# ---------------------------------------------------------------------------

@dataclass
class NEVBAntrag:
    meta: Metadaten = field(default_factory=Metadaten)
    tkezi_antrag: str = ""
    gnr: str = ""
    geschaeftszeichen: str = ""
    zustellungsart: str = "1"         # 1=Mahngericht, 2=Parteibetrieb
    ag_strasse: str = ""
    ag_plz: str = ""
    ag_ort: str = ""
    ag_ausland: str = ""
    zustellungs_gv: Optional[ZustellungsGV] = None


# ---------------------------------------------------------------------------
# Rücknahme / Erledigterklärung (Satzart 25)
# ---------------------------------------------------------------------------

@dataclass
class Ruecknahme:
    meta: Metadaten = field(default_factory=Metadaten)
    tkezi_antrag: str = ""
    geschaeftszeichen: str = ""
    merkmal: str = "R"            # R=Rücknahme, E=Erledigung
    gnr_merkmal: str = "J"        # J=mit GNR, N=ohne GNR, Z=eindeutiges GZ+KEZI
    gnr: str = ""                 # 11-stellige GNR (bei J)
    mb_eingang_merkmal: str = "E" # B=Vordruck, E=maschinell
    # Parteikurzdaten (nur bei N)
    as_anrede: str = ""
    as_name1: str = ""
    as_name2: str = ""
    as_strasse: str = ""
    as_plz: str = ""
    as_ort: str = ""
    as_rechtsform: str = "2"      # 1=nat.Person, 2=sonstig
    ag_anrede: str = ""
    ag_name1: str = ""
    ag_name2: str = ""
    ag_strasse: str = ""
    ag_plz: str = ""
    ag_ort: str = ""
    ag_rechtsform: str = "2"
    anspruchsbetrag: Optional[float] = None


# ---------------------------------------------------------------------------
# Kosteneinzug / Abgabeantrag (Satzart 29)
# ---------------------------------------------------------------------------

@dataclass
class EZKOABAntrag:
    meta: Metadaten = field(default_factory=Metadaten)
    tkezi_antrag: str = ""
    gnr: str = ""
    geschaeftszeichen: str = ""
    # Einzugs-/Abgabemerkmal ist immer X (Pflicht)


# ---------------------------------------------------------------------------
# Widerspruch (Satzart 30)
# ---------------------------------------------------------------------------

@dataclass
class Widerspruch:
    meta: Metadaten = field(default_factory=Metadaten)
    agpv_kezi: str = ""           # PV-Kennziffer des Widersprechenden
    gnr: str = ""
    geschaeftszeichen_ag: str = ""
    widerspruchs_merkmal: str = "1"   # 1=Gesamt, 2=Teil
    # Teilwiderspruch:
    widerspruchsbetrag_hf: Optional[float] = None
    widerspruch_zinsen: bool = False
    zinssatz_merkmal: str = ""        # BLANK, B+, B-
    zinssatz: Optional[float] = None
    widerspruch_verfahrenskosten: bool = False
    widerspruchsbetrag_nf: Optional[float] = None
    # Änderungsangaben:
    ag_strasse: str = ""
    ag_plz: str = ""
    ag_ort: str = ""
    ag_ausland: str = ""
    ag_gv_stellung: str = ""
    ag_gv_name: str = ""
    ag_gv_strasse: str = ""
    ag_gv_plz: str = ""
    ag_gv_ort: str = ""
    ag_gv_ausland: str = ""


# ---------------------------------------------------------------------------
# Monierungsantwort (Satzart 20)
# ---------------------------------------------------------------------------

@dataclass
class MonierungsAntwort:
    """
    Monierungsantwort: Die komplette Monierung wird zurückgegeben,
    nur das INHALT-Feld in G02-Sätzen wird überschrieben.
    """
    meta: Metadaten = field(default_factory=Metadaten)
    tkezi_antrag: str = ""
    geschaeftszeichen: str = ""
    gnrs: List[str] = field(default_factory=list)    # bis zu 5 GNRs
    monierungsdatum: str = ""       # Original-MO-Datum (JJMMTT)
    antragsdatum: str = ""          # Datum des monierten Antrags (JJMMTT)
    monierte_antragsart: str = "01"
    # G02-Sätze: Liste von Dicts mit allen Feldern aus der Monierung,
    # nur 'inhalt' kann geändert werden.
    monierungszeilen: List[dict] = field(default_factory=list)


# ===========================================================================
# Builder-Klassen
# ===========================================================================

class _BaseBuilder:
    def __init__(self):
        self.records: List[bytes] = []
        self._count = 0

    def _emit(self, data: str):
        self.records.append(_record(data))
        self._count += 1

    def _emit_raw(self, data: str):
        """BB-Satz nicht zählen."""
        self.records.append(_record(data))

    def _pv_satz(self, sa: str, pv: Prozessbevollmaechtigter):
        """ASPV_01/02/03 + ASPVA00."""
        bez = pv.bezeichnung
        n1  = _l(bez[:35], 35)
        n2  = _l(bez[35:70], 35)
        n3  = _l(bez[70:105], 35)
        s   = sa + "ASPV " + "01" + _l(pv.anrede, 1) + n1 + n2 + n3 + " " * 13
        self._emit(s)

        rf  = _l(pv.rechtsform, 35)
        sh  = _l(pv.strasse, 35)
        plz = _l(pv.plz, 5)
        ort = _l(pv.ort, 27)
        al  = _l(pv.ausland, 3)
        s   = sa + "ASPV " + "02" + rf + sh + plz + ort + al + " " * 14
        self._emit(s)

        needs_03 = pv.anrede in ("7", "9") or (pv.anrede == "8" and pv.rechtsform)
        if needs_03 and (pv.gv_stellung or pv.gv_name):
            fu = _l(pv.gv_stellung, 35)
            nm = _l(pv.gv_name, 35)
            s  = sa + "ASPV " + "03" + fu + nm + " " * 49
            self._emit(s)

        gz   = _l(pv.geschaeftszeichen, 35)
        aufd = _date(pv.beauftragungsdatum)
        ausl = _num_b(pv.auslagenbetrag, 8, 2)
        mn   = _num_b(pv.minderungsbetrag_vv2300, 10, 2)
        iku  = _num_b(pv.erstattungsbetrag_iku, 7, 2)
        vv23m = " "
        mwsts = _l(pv.mwst_satz, 4)
        vorstm = _l(pv.vorsteuer_merkmal, 1)
        ustm   = _l(pv.ust_merkmal, 1)
        s  = sa + "ASPVA" + "00" + gz + aufd + ausl + mn + vv23m + iku + mwsts + vorstm + ustm + " " * 46
        self._emit(s)


# ---------------------------------------------------------------------------
# MBA Builder
# ---------------------------------------------------------------------------

class MBABuilder(_BaseBuilder):
    def __init__(self, a: MBAntrag):
        super().__init__()
        self.a = a
        self._katsum = 0
        self._aspsum = 0
        self._aspanz = 0

    def _as_satz(self, p: Partei):
        anr = _l(p.anrede, 1) if p.anrede else " "
        rf  = _l(p.rechtsform, 35)
        n1  = _l(p.name1, 35)
        n2  = _l(p.name2, 35)
        self._emit("01" + "AS   " + "01" + anr + rf + n1 + n2 + " " * 13)
        if p.name3 or p.name4:
            self._emit("01" + "AS   " + "02" + _l(p.name3, 35) + _l(p.name4, 35) + " " * 49)
        sh = _l(p.strasse, 35)
        self._emit("01" + "AS   " + "03" + sh + _l(p.plz, 5) + _l(p.ort, 27) + _l(p.ausland, 3) + " " * 49)
        for gv in p.gesetzliche_vertreter[:6]:
            self._emit("01" + "ASGV " + "01" + _l(gv.get("stellung",""),35) + _l(gv.get("name",""),35) + " "*49)
            if gv.get("strasse"):
                self._emit("01" + "ASGV " + "02" + _l(gv.get("strasse",""),35) + _l(gv.get("plz",""),5) + _l(gv.get("ort",""),27) + _l(gv.get("ausland",""),3) + " "*49)

    def _ag_satz(self, p: Partei):
        anr = _l(p.anrede, 1) if p.anrede else " "
        rf  = _l(p.rechtsform, 35)
        n1  = _l(p.name1, 35)
        n2  = _l(p.name2, 35)
        self._emit("01" + "AG   " + "01" + anr + rf + n1 + n2 + " " * 13)
        if p.name3 or p.name4:
            self._emit("01" + "AG   " + "02" + _l(p.name3, 35) + _l(p.name4, 35) + " " * 49)
        self._emit("01" + "AG   " + "03" + _l(p.strasse,35) + _l(p.plz,5) + _l(p.ort,27) + _l(p.ausland,3) + " "*49)
        pgm  = _l(p.prozessgericht_schluessel or "1", 1)
        pgplz = _l(p.prozessgericht_plz, 5)
        pgo   = _l(p.prozessgericht_ort, 30)
        self._emit("01" + "AG   " + "04" + pgm + pgplz + pgo + " " * 83)
        for gv in p.gesetzliche_vertreter[:6]:
            self._emit("01" + "AGGV " + "01" + _l(gv.get("stellung",""),35) + _l(gv.get("name",""),35) + " "*49)
            if gv.get("strasse"):
                self._emit("01" + "AGGV " + "02" + _l(gv.get("strasse",""),35) + _l(gv.get("plz",""),5) + _l(gv.get("ort",""),27) + _l(gv.get("ausland",""),3) + " "*49)

    def _aspk(self, asp: Anspruch):
        kat1 = _r(asp.katalognummer1, 2)
        kat2 = _r(asp.katalognummer2, 2) if asp.katalognummer2 else "  "
        bet  = _num(asp.betrag, 10, 2)
        self._emit("01" + "ASPK " + "00" + kat1 + kat2 + " "*8 + _l(asp.begruendung,35) + _l(asp.rechnungsnummer,35) + _date(asp.vom_datum) + _date(asp.bis_datum) + bet + " "*15)
        try:
            self._katsum += int(kat1.strip())
        except Exception:
            pass
        self._aspsum += round(float(asp.betrag) * 100)
        self._aspanz += 1
        self._abt(asp)
        self._zins(asp, "01")

    def _asps(self, asp: Anspruch):
        bet = _num(asp.betrag, 10, 2)
        self._emit("01" + "ASPS " + "01" + bet + _date(asp.vom_datum) + _date(asp.bis_datum) + _l(asp.begruendung[:93],93) + " "*4)
        self._aspsum += round(float(asp.betrag) * 100)
        self._aspanz += 1
        if len(asp.begruendung) > 93:
            self._emit("01" + "ASPS " + "02" + _l(asp.begruendung[93:163],70) + " "*49)
        self._abt(asp)
        self._zins(asp, "01")

    def _abt(self, asp: Anspruch):
        if not asp.abtretungsdatum:
            return
        self._emit("01" + "ABT  " + "00" + _date(asp.abtretungsdatum) + _l(asp.abtretung_name,35) + _l(asp.abtretung_plz,5) + _l(asp.abtretung_ort,27) + "   " + " "*43)

    def _zins(self, asp: Anspruch, sa: str):
        if asp.zinssatz is None:
            return
        sz  = _num(asp.zinssatz, 5, 3)
        sam = _l(asp.zins_merkmal, 1)
        art = _l(asp.zins_art, 1)
        vd  = _date(asp.zins_von)
        bd  = _date(asp.zins_bis)
        rb  = _num_b(asp.zu_verzinsender_betrag, 10, 2)
        self._emit(sa + "ZINS " + "00" + sz + sam + art + vd + bd + rb + " "*90)

    def build(self) -> bytes:
        m = self.a.meta
        datum = m.today_str()
        records = [_aa(m.tkezi, datum, "01", m.ekezi, "4000", m.edaid, m.software_name, m.software_version)]

        a = self.a
        tgz   = _l(a.geschaeftszeichen, 35)
        mgplz = _l(a.mahngericht_plz, 5)
        mgo   = _l(a.mahngericht_ort, 30)
        aggmm = "X" if a.gesamtschuldner else " "
        vglm1 = "X" if a.anspruch_von_vorleistung else " "
        astrvm = "X" if a.antrag_auf_streitverfahren else " "
        ks = "01KS   00" + tgz + " "*8 + " "*8 + mgplz + mgo + " "*11 + " " + aggmm + vglm1 + " " + " "*4 + astrvm + " "*13
        records.append(_record(ks))
        self._count += 1

        for ast in a.antragsteller:
            self._as_satz(ast)
        if a.prozessbevollmaechtigter:
            self._pv_satz("01", a.prozessbevollmaechtigter)
        if a.bankverbindung:
            bv = a.bankverbindung
            self._emit("01" + "BANK " + "00" + _l(bv.kontozuordnung,1) + _l(bv.iban.replace(" ",""),34) + _l(bv.bic,11) + " "*73)
        for ag in a.antragsgegner:
            self._ag_satz(ag)

        if a.ausgerechnete_zinsen_betrag is not None:
            vd  = _date(a.ausgerechnete_zinsen_von)
            bd  = _date(a.ausgerechnete_zinsen_bis)
            bet = _num(a.ausgerechnete_zinsen_betrag, 10, 2)
            sz  = _num(a.ausgerechnete_zinsen_satz, 5, 3) if a.ausgerechnete_zinsen_satz else " "*5
            self._emit("01" + "ZIAUS" + "00" + vd + bd + bet + sz + " "*92)

        for asp in a.ansprueche:
            if asp.art == "katalog":
                self._aspk(asp)
            else:
                self._asps(asp)

        # Nebenforderungen
        kennz_map = {"mahnk":"MAHNK","ausk":"AUSK ","bkrl":"BKRL ","inkb":"INKB ","vv23":"VV23 ","anf":"ANF  "}
        bet_len   = {"mahnk":7,"ausk":7,"bkrl":7,"inkb":10,"vv23":10,"anf":8}
        if a.auslagen_vordruck is not None or a.auslagen_sonstige is not None:
            vp  = _num_b(a.auslagen_vordruck, 8, 2)
            ms  = _num_b(a.auslagen_sonstige, 8, 2)
            self._emit("01" + "AUSL " + "00" + vp + ms + _l(a.auslagen_sonstige_begruendung,35) + " "*68)
        for nf in a.nebenforderungen:
            art = nf.art.lower()
            kz  = kennz_map.get(art)
            if not kz:
                continue
            bl   = bet_len.get(art, 8)
            bet  = _num_b(nf.betrag, bl, 2)
            sz   = _num(nf.zinssatz, 5, 3) if nf.zinssatz is not None else " "*5
            zm   = _l(nf.zins_merkmal,1) if nf.zinssatz is not None else " "
            vd   = _date(nf.zins_von)
            bd   = _date(nf.zins_bis)
            if art == "vv23":
                stw  = _num_b(nf.vv2300_streitwert, 10, 2)
                fl   = " " * (125 - 9 - bl - 10 - 5 - 1 - 12)
                self._emit("01" + kz + "00" + bet + stw + sz + zm + vd + bd + fl)
            elif art == "anf":
                bgr = _l(nf.begruendung, 35)
                fl  = " " * (125 - 9 - bl - 35 - 5 - 1 - 12)
                self._emit("01" + kz + "00" + bet + bgr + sz + zm + vd + bd + fl)
            else:
                fl  = " " * (125 - 9 - bl - 5 - 1 - 12)
                self._emit("01" + kz + "00" + bet + sz + zm + vd + bd + fl)

        sanz = self._count - 1   # ohne AA
        for r in self.records:
            records.append(r)
        records.append(_bb(m.tkezi, 1, sanz, self._katsum, self._aspsum, 0, self._aspanz))
        return b"".join(records)


# ---------------------------------------------------------------------------
# VBA Builder (Satzart 08)
# ---------------------------------------------------------------------------

def build_vba(a: VBAntrag) -> bytes:
    m = a.meta
    datum = m.today_str()
    records = [_aa(m.tkezi, datum, "08", m.ekezi, "4100", m.edaid, m.software_name, m.software_version)]
    cnt = 0

    gnr_clean = a.gnr.replace("-", "").replace("N", "").strip().ljust(11, "0")[:11]

    # E01 Kennsatz
    tkezi_k = _l(a.tkezi_antrag or "", 8)
    vband   = _date(a.antragsdatum)
    porto   = _num_b(a.porto_betrag, 8, 2)
    sko     = _num_b(a.sonstige_kosten, 8, 2)
    skobg   = _l(a.sonstige_kosten_begruendung, 35)
    kozim   = "X" if a.zinsen_auf_kosten else " "
    aspvausl = _num(a.aspv_ikubet, 7, 2) if a.aspv_ikubet is not None else " "*7
    s = "08KS   00" + tkezi_k + gnr_clean + _l(a.geschaeftszeichen,30) + vband + _l(a.zahlungen_merkmal,1) + _l(a.zustellungsart,1) + porto + sko + skobg + kozim + aspvausl + " "*3
    records.append(_record(s)); cnt += 1

    # E02 Zahlungen (max. 6 je Satz, Fortsetzung E11)
    if a.zahlungen_merkmal == "2" and a.zahlungen:
        z6 = a.zahlungen[:6]
        row = "08ZAHL 00"
        for z in z6:
            row += _date(z.get("datum","")) + _num_b(z.get("betrag"),10,2)
        # Auffüllen auf 6 Zahlungen
        for _ in range(6 - len(z6)):
            row += " "*6 + " "*10
        row += " "*23
        records.append(_record(row)); cnt += 1
        if len(a.zahlungen) > 6:
            z12 = a.zahlungen[6:12]
            row2 = "08ZAHL200"
            for z in z12:
                row2 += _date(z.get("datum","")) + _num_b(z.get("betrag"),10,2)
            for _ in range(6 - len(z12)):
                row2 += " "*6 + " "*10
            row2 += " "*23
            records.append(_record(row2)); cnt += 1

    # AG-Sätze (vereinfacht: Name + Adresse, E03/E04/E05)
    for ag in a.antragsgegner:
        n1 = _l(ag.name1, 35)
        n2 = _l(ag.name2, 35)
        n3 = _l(ag.name3, 35)
        records.append(_record("08AG   01" + n1 + n2 + n3 + " "*14)); cnt += 1
        if ag.name4:
            records.append(_record("08AG   02" + _l(ag.name4,35) + " "*84)); cnt += 1
        rf  = _l(ag.rechtsform, 35)
        sh  = _l(ag.strasse, 35)
        plz = _l(ag.plz, 5)
        ort = _l(ag.ort, 27)
        al  = _l(ag.ausland, 3)
        records.append(_record("08AG   03" + rf + sh + plz + ort + al + " "*14)); cnt += 1

    # Neuer GV (E06/E07)
    if a.neuer_gv:
        gv = a.neuer_gv
        records.append(_record("08AGGVN 01" + _l(gv.stellung,35) + _l(gv.name,35) + " "*48)); cnt += 1
        if gv.strasse:
            records.append(_record("08AGGVN 02" + _l(gv.strasse,35) + _l(gv.plz,5) + _l(gv.ort,27) + _l(gv.ausland,3) + " "*48)); cnt += 1

    # Zustellungs-GV (E08/E09)
    if a.zustellungs_gv:
        zgv = a.zustellungs_gv
        records.append(_record("08AGGVZ 01" + _l(zgv.stellung,35) + _l(zgv.name,35) + " "*48)); cnt += 1
        records.append(_record("08AGGVZ 02" + _l(zgv.strasse,35) + _l(zgv.plz,5) + _l(zgv.ort,27) + _l(zgv.ausland,3) + " "*48)); cnt += 1

    # Weitere Auslagen (E10)
    if a.weitere_auslagen:
        wa = a.weitere_auslagen
        b1 = _num_b(wa[0].get("betrag") if len(wa)>0 else None, 10, 2)
        g1 = _l(wa[0].get("begruendung","") if len(wa)>0 else "", 35)
        b2 = _num_b(wa[1].get("betrag") if len(wa)>1 else None, 10, 2)
        g2 = _l(wa[1].get("begruendung","") if len(wa)>1 else "", 35)
        records.append(_record("08WAUSL 00" + b1 + g1 + b2 + g2 + " "*29)); cnt += 1

    # ASPVA (E12) – nur bei IKU
    if a.aspv_ikubet is not None:
        iku = _num(a.aspv_ikubet, 7, 2)
        records.append(_record("08ASPVA 00" + iku + " "*112)); cnt += 1

    gnr_sum = _gnr_sum([a.gnr])
    records.append(_bb(m.tkezi, 1, cnt, 0, 0, gnr_sum, 0))
    return b"".join(records)


# ---------------------------------------------------------------------------
# NEMB Builder (Satzart 07)
# ---------------------------------------------------------------------------

def build_nemb(a: NEMBAntrag) -> bytes:
    m = a.meta
    datum = m.today_str()
    records = [_aa(m.tkezi, datum, "07", m.ekezi, "4100", m.edaid, m.software_name, m.software_version)]
    cnt = 0

    gnr_clean = a.gnr.replace("-", "").replace("N", "").strip().ljust(11, "0")[:11]
    tkezi_k   = _l(a.tkezi_antrag or "", 8)
    porto     = _num_b(a.porto_betrag, 8, 2)
    sko       = _num_b(a.sonstige_kosten, 8, 2)
    skobg     = _l(a.sonstige_kosten_begruendung, 35)
    ausk      = _num_b(a.auskunftskosten, 8, 2)
    s = "07KS   00" + tkezi_k + gnr_clean + _l(a.geschaeftszeichen,35) + porto + sko + skobg + ausk + " "*6
    records.append(_record(s)); cnt += 1

    for ag in a.antragsgegner:
        n1 = _l(ag.name1,35); n2 = _l(ag.name2,35); n3 = _l(ag.name3,35)
        records.append(_record("07AG   01" + n1 + n2 + n3 + " "*14)); cnt += 1
        if ag.name4:
            records.append(_record("07AG   02" + _l(ag.name4,35) + " "*84)); cnt += 1
        records.append(_record("07AG   03" + _l(ag.rechtsform,35) + _l(ag.strasse,35) + _l(ag.plz,5) + _l(ag.ort,27) + _l(ag.ausland,3) + " "*14)); cnt += 1
        pgm = _l(ag.prozessgericht_schluessel or "1",1)
        records.append(_record("07AG   04" + pgm + _l(ag.prozessgericht_plz,5) + _l(ag.prozessgericht_ort,30) + " "*83)); cnt += 1

    if a.neuer_gv:
        gv = a.neuer_gv
        records.append(_record("07AGGVN 01" + _l(gv.stellung,35) + _l(gv.name,35) + " "*48)); cnt += 1
        if gv.strasse:
            records.append(_record("07AGGVN 02" + _l(gv.strasse,35) + _l(gv.plz,5) + _l(gv.ort,27) + _l(gv.ausland,3) + " "*48)); cnt += 1

    if a.zustellungs_gv:
        zgv = a.zustellungs_gv
        records.append(_record("07AGGVZ 01" + _l(zgv.stellung,35) + _l(zgv.name,35) + " "*48)); cnt += 1
        records.append(_record("07AGGVZ 02" + _l(zgv.strasse,35) + _l(zgv.plz,5) + _l(zgv.ort,27) + _l(zgv.ausland,3) + " "*48)); cnt += 1

    gnr_sum = _gnr_sum([a.gnr])
    records.append(_bb(m.tkezi, 1, cnt, 0, 0, gnr_sum, 0))
    return b"".join(records)


# ---------------------------------------------------------------------------
# NEVB Builder (Satzart 10)
# ---------------------------------------------------------------------------

def build_nevb(a: NEVBAntrag) -> bytes:
    m = a.meta
    datum = m.today_str()
    records = [_aa(m.tkezi, datum, "10", m.ekezi, "4100", m.edaid, m.software_name, m.software_version)]
    cnt = 0

    gnr_clean = a.gnr.replace("-","").replace("N","").strip().ljust(11,"0")[:11]
    tkezi_k   = _l(a.tkezi_antrag or "", 8)
    s = "10KS   00" + tkezi_k + gnr_clean + _l(a.geschaeftszeichen,35) + _l(a.zustellungsart,1) + " "*64
    records.append(_record(s)); cnt += 1

    # F02 AG-Adresse (nur bei amtsgerichtlicher Zustellung ohne AGGVZ)
    if a.zustellungsart == "1" and a.ag_strasse and not a.zustellungs_gv:
        records.append(_record("10AG   00" + _l(a.ag_strasse,35) + _l(a.ag_plz,5) + _l(a.ag_ort,27) + _l(a.ag_ausland,3) + " "*49)); cnt += 1

    if a.zustellungs_gv:
        zgv = a.zustellungs_gv
        records.append(_record("10AGGVZ 01" + _l(zgv.stellung,35) + _l(zgv.name,35) + " "*48)); cnt += 1
        records.append(_record("10AGGVZ 02" + _l(zgv.strasse,35) + _l(zgv.plz,5) + _l(zgv.ort,27) + _l(zgv.ausland,3) + " "*48)); cnt += 1

    gnr_sum = _gnr_sum([a.gnr])
    records.append(_bb(m.tkezi, 1, cnt, 0, 0, gnr_sum, 0))
    return b"".join(records)


# ---------------------------------------------------------------------------
# Rücknahme Builder (Satzart 25)
# ---------------------------------------------------------------------------

def build_rn(a: Ruecknahme) -> bytes:
    m = a.meta
    datum = m.today_str()
    records = [_aa(m.tkezi, datum, "25", m.ekezi, "4000", m.edaid, m.software_name, m.software_version)]
    cnt = 0

    tkezi_k = _l(a.tkezi_antrag or "", 8)
    tgz     = _l(a.geschaeftszeichen, 35)
    rem     = _l(a.merkmal, 1)
    gnrm    = _l(a.gnr_merkmal, 1)
    gnr_raw = a.gnr.replace("-","").replace("N","").strip().ljust(11,"0")[:11] if a.gnr else "00000000000"
    mbeg    = _l(a.mb_eingang_merkmal, 1)
    s = "25KS   00" + tkezi_k + tgz + rem + gnrm + gnr_raw + mbeg + " "*62
    records.append(_record(s)); cnt += 1

    # Parteikurzdaten nur bei gnr_merkmal "N"
    if a.gnr_merkmal == "N" and a.as_name1:
        as_anr  = _l(a.as_anrede, 1)
        as_n1   = _l(a.as_name1, 10)
        as_n2   = _l(a.as_name2, 10)
        as_sh   = _l(a.as_strasse, 10)
        as_plz  = _l(a.as_plz, 5)
        as_ort  = _l(a.as_ort, 9)
        ag_anr  = _l(a.ag_anrede, 1)
        ag_n1   = _l(a.ag_name1, 10)
        ag_n2   = _l(a.ag_name2, 10)
        ag_sh   = _l(a.ag_strasse, 10)
        ag_plz  = _l(a.ag_plz, 5)
        ag_ort  = _l(a.ag_ort, 9)
        aspbet  = _num_b(a.anspruchsbetrag, 10, 2)
        asrf    = _l(a.as_rechtsform, 1)
        agrf    = _l(a.ag_rechtsform, 1)
        s2 = "25ASAG 00" + as_anr + as_n1 + as_n2 + as_sh + as_plz + as_ort + ag_anr + ag_n1 + ag_n2 + ag_sh + ag_plz + ag_ort + aspbet + asrf + agrf + " "*14
        records.append(_record(s2)); cnt += 1

    gnr_sum = _gnr_sum([a.gnr]) if a.gnr else 0
    records.append(_bb(m.tkezi, 1, cnt, 0, 0, gnr_sum, 0))
    return b"".join(records)


# ---------------------------------------------------------------------------
# EZKOAB Builder (Satzart 29)
# ---------------------------------------------------------------------------

def build_ezkoab(a: EZKOABAntrag) -> bytes:
    m = a.meta
    datum = m.today_str()
    records = [_aa(m.tkezi, datum, "29", m.ekezi, "4000", m.edaid, m.software_name, m.software_version)]
    cnt = 0

    tkezi_k = _l(a.tkezi_antrag or "", 8)
    gnr_raw = a.gnr.replace("-","").replace("N","").strip().ljust(11,"0")[:11] if a.gnr else "00000000000"
    asgz    = _l(a.geschaeftszeichen, 35)
    s = "29KS   00" + tkezi_k + gnr_raw + asgz + "X" + " "*64
    records.append(_record(s)); cnt += 1

    gnr_sum = _gnr_sum([a.gnr])
    records.append(_bb(m.tkezi, 1, cnt, 0, 0, gnr_sum, 0))
    return b"".join(records)


# ---------------------------------------------------------------------------
# Widerspruch Builder (Satzart 30)
# ---------------------------------------------------------------------------

def build_wi(a: Widerspruch) -> bytes:
    m = a.meta
    datum = m.today_str()
    # AA hat kein EKEZI-Feld (Feld 5 = BLANK)
    aa_s  = "AA"
    aa_s += _l(m.tkezi, 8)
    aa_s += datum.ljust(6)
    aa_s += "30"
    aa_s += " " * 8       # kein EKEZI
    aa_s += "4100"
    aa_s += _l(m.edaid.upper(), 6)
    aa_s += " " * (125 - 36)
    records = [_record(aa_s)]
    cnt = 0

    kezi  = _l(a.agpv_kezi, 8)
    gnr   = a.gnr.replace("-","").replace("N","").strip().ljust(11,"0")[:11] if a.gnr else "00000000000"
    aggz  = _l(a.geschaeftszeichen_ag, 35)
    wim   = _l(a.widerspruchs_merkmal, 1)
    hfbet = _num_b(a.widerspruchsbetrag_hf, 10, 2)
    wizim = "X" if a.widerspruch_zinsen else " "
    wiziartm = _l(a.zinssatz_merkmal, 2)
    wizisa   = _num_b(a.zinssatz, 5, 3)
    wivkom   = "X" if a.widerspruch_verfahrenskosten else " "
    winebbet = _num_b(a.widerspruchsbetrag_nf, 10, 2)
    s = "30KS   00" + kezi + gnr + _l(a.agpv_kezi[:35] if a.agpv_kezi else "",35)[:35] + aggz[:35] + wim + hfbet + wizim + wiziartm + wizisa + wivkom + winebbet + " "*35
    # Adjust – Kennsatz fields as per spec:
    s = "30KS   00" + kezi + gnr + " "*35 + aggz + wim + hfbet + wizim + wiziartm + wizisa + wivkom + winebbet + " "*35
    records.append(_record(s)); cnt += 1

    # J02 – Andere AG-Anschrift
    if a.ag_strasse:
        records.append(_record("30AG   00" + _l(a.ag_strasse,35) + _l(a.ag_plz,5) + _l(a.ag_ort,27) + _l(a.ag_ausland,3) + " "*49)); cnt += 1

    # J03/J04 – Anderer GV des AG
    if a.ag_gv_stellung or a.ag_gv_name:
        records.append(_record("30AGGV 01" + _l(a.ag_gv_stellung,35) + _l(a.ag_gv_name,35) + " "*49)); cnt += 1
        if a.ag_gv_strasse:
            records.append(_record("30AGGV 02" + _l(a.ag_gv_strasse,35) + _l(a.ag_gv_plz,5) + _l(a.ag_gv_ort,27) + _l(a.ag_gv_ausland,3) + " "*49)); cnt += 1

    gnr_sum = _gnr_sum([a.gnr])
    records.append(_bb(m.tkezi, 1, cnt, 0, 0, gnr_sum, 0))
    return b"".join(records)


# ---------------------------------------------------------------------------
# Monierungsantwort Builder (Satzart 20)
# ---------------------------------------------------------------------------

def build_moa(a: MonierungsAntwort) -> bytes:
    m = a.meta
    datum = m.today_str()
    records = [_aa(m.tkezi, datum, "20", m.ekezi, "4000", m.edaid, m.software_name, m.software_version)]
    cnt = 0

    tkezi_k = _l(a.tkezi_antrag or "", 8)
    asgz    = _l(a.geschaeftszeichen, 35)
    gnrs    = (a.gnrs + [""] * 5)[:5]
    g_strs  = [g.replace("-","").replace("N","").strip().ljust(11,"0")[:11] if g else "00000000000" for g in gnrs]
    mod     = _l(a.monierungsdatum, 6)
    and_    = _l(a.antragsdatum, 6)
    mobelart = _l(a.monierte_antragsart, 2)
    s = "20KS   00" + tkezi_k + asgz + "".join(g_strs) + mod + and_ + mobelart + " "*7
    records.append(_record(s)); cnt += 1

    # G02 Monierungssätze
    for mo in a.monierungszeilen:
        fschl  = _r(mo.get("fschl",""), 3)
        feldn  = _l(mo.get("feldn",""), 20)
        idx1   = _r(mo.get("index1",""), 2)
        idx2   = _r(mo.get("index2",""), 2)
        mas    = _l(mo.get("mas",""), 1)
        maz    = _l(mo.get("maz",""), 1)
        mazpos = _l(mo.get("mazpos",""), 1)
        form   = _l(mo.get("form",""), 1)
        inhalt = _l(mo.get("inhalt",""), 35)
        s2 = "20MO   00" + fschl + feldn + idx1 + idx2 + mas + maz + mazpos + form + inhalt + " "*53
        records.append(_record(s2)); cnt += 1

    gnr_sum = _gnr_sum(a.gnrs)
    records.append(_bb(m.tkezi, 1, cnt, 0, 0, gnr_sum, 0))
    return b"".join(records)


# ---------------------------------------------------------------------------
# Dispatch-Funktion
# ---------------------------------------------------------------------------

def generate_eda(antrag) -> bytes:
    if isinstance(antrag, MBAntrag):
        return MBABuilder(antrag).build()
    elif isinstance(antrag, VBAntrag):
        return build_vba(antrag)
    elif isinstance(antrag, NEMBAntrag):
        return build_nemb(antrag)
    elif isinstance(antrag, NEVBAntrag):
        return build_nevb(antrag)
    elif isinstance(antrag, Ruecknahme):
        return build_rn(antrag)
    elif isinstance(antrag, EZKOABAntrag):
        return build_ezkoab(antrag)
    elif isinstance(antrag, Widerspruch):
        return build_wi(antrag)
    elif isinstance(antrag, MonierungsAntwort):
        return build_moa(antrag)
    else:
        raise ValueError(f"Unbekannter Antragstyp: {type(antrag)}")
