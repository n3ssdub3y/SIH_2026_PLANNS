"""
Per-class prototype phrases for semantic (embedding) event typing.

Written in DDR shorthand style to describe each canonical EVENT_VOCAB class.
They are *descriptions*, deliberately not copied from the evaluation set in
eval_model_selection.py, so the zero-shot evaluation stays honest.

EVT_ROUTINE_DRILLING has prototypes too: the classifier predicts argmax over
all 18 classes, so "normal operations" competes on equal terms instead of
relying on an arbitrary similarity threshold.
"""

EVENT_PROTOTYPES = {
    "EVT_MUD_LOSS_PARTIAL": [
        "partial losses to formation while drilling",
        "seepage losses, losing mud at a reduced rate per hour",
        "dynamic losses observed, reduced pump rate to control loss rate",
        "static loss rate measured during flow check",
        "lost circulation, partial returns at the shakers",
    ],
    "EVT_MUD_LOSS_TOTAL": [
        "total losses, no returns to surface",
        "complete loss of circulation, well taking all the mud",
        "lost all returns while drilling into fractured zone",
        "unable to keep the hole full, no fluid level",
    ],
    "EVT_LCM_APPLIED": [
        "pumped lost circulation material pill to cure losses",
        "spotted LCM pill across the loss zone",
        "added calcium carbonate and fibre bridging material to the mud system",
        "mixed and pumped a loss control pill",
    ],
    "EVT_CIRC_RESTORED": [
        "full returns regained after treatment",
        "losses cured, circulation restored",
        "well static with full returns after pill",
        "losses stopped, resumed drilling with full circulation",
    ],
    "EVT_STUCK_PIPE": [
        "drill string stuck, unable to move pipe up or down",
        "pipe stuck, could not rotate or circulate",
        "hole packed off around the BHA",
        "string became stuck and could not be freed with maximum pull",
    ],
    "EVT_DIFF_STICKING": [
        "differentially stuck against permeable formation",
        "pipe stuck while stationary across the sand, circulation possible",
        "differential sticking during survey, spotted pipe freeing pill",
    ],
    "EVT_TIGHT_HOLE": [
        "tight hole while tripping out, worked through restriction",
        "overpull above string weight on trip, backreamed",
        "high drag while pulling out of hole",
        "took weight running in, reamed through tight section",
    ],
    "EVT_JARRING": [
        "jarred up and down to free the string",
        "fired the drilling jar several times",
        "worked pipe with jar blows",
    ],
    "EVT_FISHING": [
        "fishing operation to recover lost equipment from the hole",
        "ran overshot to retrieve fish",
        "junk left in hole, ran junk basket and magnet",
        "washed over and recovered the fish",
    ],
    "EVT_KICK": [
        "well kick, influx of formation fluid into the wellbore",
        "pit gain observed, flow check positive, well flowing",
        "trip tank gain, well flowing on connection",
        "took an influx while drilling",
    ],
    "EVT_GAS_INFLUX": [
        "high background gas and connection gas peaks",
        "gas cut mud at the shakers, mud weight out reduced",
        "elevated gas readings in the returns",
    ],
    "EVT_BOP_SHUTIN": [
        "shut the well in on the BOP for well control",
        "closed annular preventer and recorded shut in pressures",
        "well control, circulated out influx through the choke with kill mud",
    ],
    "EVT_OVERPRESSURE_DETECTED": [
        "abnormal pore pressure encountered, increased mud weight",
        "overpressured zone indicated by rising gas and cavings",
        "pore pressure higher than prognosed",
    ],
    "EVT_TORQUE_UP": [
        "erratic and fluctuating rotary torque while drilling",
        "torque increasing, reduced weight on bit",
        "high surface torque during reaming",
    ],
    "EVT_TORQUE_SPIKE": [
        "sudden torque spike stalled the top drive",
        "torque exceeded the limit and the rotary stalled out",
        "string torqued up suddenly and stopped rotating",
    ],
    "EVT_CEMENTING_FAILURE": [
        "cement job problem, losses during cement displacement",
        "plug did not bump, remedial squeeze cement required",
        "poor cement bond and low top of cement on the log",
        "cement job aborted due to equipment failure",
    ],
    "EVT_WOC": [
        "waiting on cement to set",
        "WOC before drilling out the shoe track",
        "waited on cement before pressure testing casing",
        "let the cement harden before continuing operations",
    ],
    "EVT_ROUTINE_DRILLING": [
        "drilled ahead to section depth with normal parameters",
        "circulated bottoms up and conditioned the mud",
        "pressure tested BOP and casing, test ok",
        "ran in hole with drill pipe and made up the BHA",
        "pulled out of hole and laid down tools",
        "rigged up and held safety meeting",
        "waited on weather and handover of the well",
        "set packer and tested completion equipment",
        "prepared the well for sidetrack operations",
        "filled pipe and broke circulation while running in",
        "performed formation integrity test or leak off test",
        "drilled out cement and float shoe track",
        "cement job completed with good cement returns to surface",
        "made up casing connections to optimum torque",
        "nippled up or nippled down the blowout preventer stack",
        "reduced pump rate as per the drilling program",
        "rig repair, electrician troubleshooting drawworks motor or SCR system",
        "waiting on service company personnel or replacement downhole tools",
    ],
}

import re as _re

# Common DDR abbreviations, expanded before *embedding* only (the keyword pass and
# raw_text keep the original wording). Abbreviation-heavy text is a known DDR
# difficulty (Hoffimann et al. 2018); a general-domain encoder does not know "FIT".
ABBREVIATIONS = {
    "FIT": "formation integrity test", "LOT": "leak off test", "POOH": "pull out of hole",
    "POH": "pull out of hole", "RIH": "run in hole", "TIH": "trip in hole", "TOOH": "trip out of hole",
    "BHA": "bottom hole assembly", "CBU": "circulate bottoms up", "B/U": "bottoms up",
    "TD": "total depth", "MW": "mud weight", "ECD": "equivalent circulating density",
    "WOB": "weight on bit", "ROP": "rate of penetration", "SIDPP": "shut in drill pipe pressure",
    "SICP": "shut in casing pressure", "TOC": "top of cement", "CIP": "cement in place",
    "WOC": "waiting on cement", "LCM": "lost circulation material", "OBM": "oil based mud",
    "WBM": "water based mud", "HWDP": "heavy weight drill pipe", "DP": "drill pipe",
    "M/U": "make up", "L/D": "lay down", "P/U": "pick up", "N/U": "nipple up", "N/D": "nipple down",
    "BOP": "blowout preventer", "MWD": "measurement while drilling tool", "PU": "pick up",
}
_ABBR_RX = _re.compile(r"(?<![\w/])(" + "|".join(_re.escape(k) for k in
                       sorted(ABBREVIATIONS, key=len, reverse=True)) + r")(?![\w/])")


def expand_abbreviations(text):
    return _ABBR_RX.sub(lambda m: ABBREVIATIONS[m.group(1)], text)
