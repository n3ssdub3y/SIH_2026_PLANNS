"""
Unit-aware field parsers for the hybrid NLP layer.

The original regexes in nlp_rules.extract_entities are metres-only and store
SG values in `mud_weight_ppg` unconverted. These parsers recognise the unit
and normalise to the schema's units (m, ppg, bbl, h) so that field DDRs in
feet / SG / m3 (e.g. the Utah FORGE reports) produce correct records.
Used only by the hybrid path — the keyword corpus path is unchanged.
"""
import re

FT_TO_M = 0.3048
SG_TO_PPG = 8.33
PCF_TO_PPG = 1 / 7.4805
KGM3_TO_PPG = 8.33 / 1000
M3_TO_BBL = 6.2898
L_TO_BBL = 6.2898 / 1000

_NUM = r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:[.,]\d+)?)"


def _num(s):
    s = s.strip()
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", s):      # 6,210 / 1,842.5
        return float(s.replace(",", ""))
    return float(s.replace(",", "."))                        # 1,45 (EU decimal) / 12.5


# depth: value + unit; feet variants include 6210' and 6210 ft / ftMD / feet
_DEPTH_RX = re.compile(
    _NUM + r"\s*(?P<u>mMD|mTVD|m\s*MD|m\s*TVD|meters?|metres?|m(?![a-z0-9/³])|"
           r"ftMD|ftTVD|ft\s*MD|ft(?![a-z])|feet|'(?!'))",
    re.I)
# numbers that are not depths even with an "m"/"ft" unit (rates, ratios)
_NOT_DEPTH_AFTER = re.compile(r"^\s*(/\s*(hr|h|min)|3\b|³|\s*per\s+h)", re.I)


def parse_depths(text):
    """All depth mentions in metres, in order: [(value_m, start, end, raw)]."""
    out = []
    for m in _DEPTH_RX.finditer(text):
        tail = text[m.end():m.end() + 8]
        if _NOT_DEPTH_AFTER.match(tail):
            continue
        u = m.group("u").lower().replace(" ", "")
        try:
            v = _num(m.group(1))
        except ValueError:
            continue
        if u.startswith("ft") or u in ("feet", "'"):
            v *= FT_TO_M
        if not (1.0 <= v <= 12000.0):                        # plausible MD range
            continue
        out.append((round(v, 1), m.start(), m.end(), m.group(0)))
    return out


_MW_RX = re.compile(_NUM + r"\s*(?P<u>ppg|lb/gal|sg\b|s\.g\.|g/cc|g/cm3|kg/m3|pcf|lb/ft3)", re.I)


def parse_mud_weight_ppg(text):
    for m in _MW_RX.finditer(text):
        v = _num(m.group(1))
        u = m.group("u").lower()
        if u in ("sg", "s.g.", "g/cc", "g/cm3"):
            v *= SG_TO_PPG
        elif u == "kg/m3":
            v *= KGM3_TO_PPG
        elif u in ("pcf", "lb/ft3"):
            v *= PCF_TO_PPG
        if 6.0 <= v <= 22.0:                                  # plausible drilling-fluid range
            return round(v, 2)
    return None


_VOL_RX = re.compile(_NUM + r"\s*(?P<u>bbls?|barrels?|m3|m³|cu\.?\s*m|litres?|liters?|ltrs?)\b(?!\s*/)",
                     re.I)


def parse_volume_bbl(text):
    for m in _VOL_RX.finditer(text):
        v = _num(m.group(1))
        u = m.group("u").lower()
        if u.startswith(("m3", "m³", "cu")):
            v *= M3_TO_BBL
        elif u.startswith(("lit", "ltr")):
            v *= L_TO_BBL
        return round(v, 1)
    return None


_NPT_RX = re.compile(r"(?:npt|non[- ]?prod(?:uctive)?(?:\s+time)?)[\s:=]*" + _NUM + r"\s*(?:h|hrs?|hours?)?",
                     re.I)


# "Total hours of NPT on daily report 13 due to Schlumberger 12.0 HRS"
_NPT_STMT_RX = re.compile(r"\bNPT\b[^\n]{0,80}?(\d+(?:\.\d+)?)\s*(?:h|hrs?|hours?)\b", re.I)


def parse_npt_hours(text):
    for rx in (_NPT_RX, _NPT_STMT_RX):
        m = rx.search(text)
        if m:
            v = _num(m.group(1))
            if 0 < v <= 48:
                return v
    return None


def sum_npt_hours(text):
    """Sum of explicit NPT statements in a whole report (each line counted once)."""
    total = 0.0
    for line in text.splitlines():
        v = parse_npt_hours(line)
        if v:
            total += v
    return round(total, 2)


# Formation / lithology gazetteer: NCS (Volve/FORCE) + common onshore/geothermal units.
FORMATIONS = [
    "Hordaland", "Shetland", "Draupne", "Utsira", "Statfjord", "Smith Bank", "Lista", "Lyr",
    "Skagerrak", "Balder", "Heimdal", "Rogaland", "Hugin", "Sleipner", "Ty", "Nordland",
    "Milford Volcanics", "Precambrian Granite", "Mineral Mountains", "Alluvium",
]
LITHOLOGY = ["granite", "granodiorite", "diorite", "rhyolite", "basalt", "sandstone", "shale",
             "claystone", "siltstone", "limestone", "dolomite", "marl", "chalk", "anhydrite",
             "salt", "coal", "conglomerate", "alluvium", "gneiss", "quartzite"]
_FM_RX = re.compile(r"\b(" + "|".join(re.escape(f) for f in sorted(FORMATIONS, key=len, reverse=True))
                    + r")\b(?:\s+(?:fm|formation))?", re.I)
_FM_GENERIC = re.compile(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})?)\s+(?:Fm|Formation)\b")
_LITH_RX = re.compile(r"\b(" + "|".join(LITHOLOGY) + r")\b", re.I)


def parse_formation(text):
    m = _FM_RX.search(text)
    if m:
        name = m.group(1)
        for f in FORMATIONS:
            if f.lower() == name.lower():
                return f
        return name
    m = _FM_GENERIC.search(text)
    if m:
        return m.group(1)
    m = _LITH_RX.search(text)
    if m:
        return m.group(1).capitalize()
    return None
