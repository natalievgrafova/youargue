"""Does this comment actually name this topic?

The three misses in the eval file are three different problems and only one
of them is fuzzy-matchable:

    isreal   -> israel          typo         -> Damerau-Levenshtein, 1 edit
    western  -> the west        derivative   -> prefix / stem
    the US   -> united states   abbreviation -> alias list (nothing else can do it)

Edit distance is gated on alias length: a 4-letter alias gets no edits at all,
because iran/iraq and mali/mali sit 1 edit apart.
"""
import re, unicodedata, pandas as pd
from rapidfuzz.distance import DamerauLevenshtein as DL

PREFIX_MIN  = 4     # alias word may be extended:  west -> western
PREFIX_GROW = 4     # but only by an inflection, not into another word: "krim"
                    # must not reach "kriminell", "blair" not "blaireau"
# Stemming is productive in Russian and German, where users coin new endings off
# a root. In English/Dutch/French it mostly manufactures false friends --
# "democrats" stems to "democra" and swallows "democracy", "gezondheidszorg"
# swallows "gezondheidsrisico" -- and the inflections that matter there
# (plurals, -e) are already covered by the prefix rule.
# German is left out: its inflections are suffixal (prefix matching covers them)
# while its compounds share long prefixes, so stemming there only invents
# matches -- "gesundheit" would swallow "gesundheitsrisiko".
STEM_LANGS = {"ru"}
TYPO_HEAD  = 3      # a typo may not change the start of the word: "hassen" is not
                    # a typo of "hassan", "braten" not of "briten"
STEM_MIN   = 6      # alias long enough to lose an ending
STEM_CUT   = 2      # how much of the ending may differ (Russian case endings)
STEM_FLOOR = 5      # but the stem never drops below this: at 4, 'путин' stems
                    # to 'пути' and fires on the ordinary word for 'paths'
STEM_GROW  = 4      # and the text word may not run far past the stem, or the
                    # 4-letter stem of 'право' reaches 'правительство'
EDIT_LEN   = ((10, 2), (6, 1))   # len >=10 -> 2 edits, >=6 -> 1, else 0

# A match is void when the next word turns the alias into a different name.
# "the west" is a target; "the West Bank" is not.
BLOCK = {"west": {"bank", "coast", "side", "end", "africa", "germany",
                  "point", "virginia", "indies", "papua"}}

def budget(a):
    for n, e in EDIT_LEN:
        if len(a) >= n:
            return e
    return 0

def fold(s):
    s = str(s).lower()
    for a, b in (("ö","oe"), ("ü","ue"), ("ä","ae"), ("ß","ss")):
        s = s.replace(a, b)
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))

def words(s):
    return re.findall(r"\w+", fold(s))

def hit(text, alias, lang=None):
    """(matched, evidence, how) — how is exact / derivative / typo."""
    tw, aw = words(text), words(alias)
    if not aw:
        return False, "", ""
    n = len(aw)
    for i in range(len(tw) - n + 1):
        span = tw[i:i+n]
        ev = " ".join(span)
        nxt = tw[i+n] if i + n < len(tw) else ""
        if nxt and nxt in BLOCK.get(aw[-1], ()):
            continue
        if span == aw:
            return True, ev, "exact"
        if all(len(a) >= PREFIX_MIN and t.startswith(a) and len(t) <= len(a) + PREFIX_GROW
               for a, t in zip(aw, span)):
            return True, ev, "derivative"
        if lang in STEM_LANGS and all(
                len(a) >= STEM_MIN
                and t.startswith(a[:max(len(a)-STEM_CUT, STEM_FLOOR)])
                and len(t) <= max(len(a)-STEM_CUT, STEM_FLOOR) + STEM_GROW
                for a, t in zip(aw, span)):
            return True, ev, "derivative"
        # typos are allowed per word, and only in words long enough to survive
        # one: "the rest" must not pass as a typo of "the west".
        if all(budget(a) and a[:TYPO_HEAD] == t[:TYPO_HEAD] and DL.distance(a, t) <= budget(a)
               for a, t in zip(aw, span)):
            return True, ev, "typo"
    return False, "", ""

def load_aliases(lang, path="curated_topics_checked.csv"):
    d = pd.read_csv(path)
    out = {}
    for _, r in d.iterrows():
        al = {str(r.target)}
        for col in ("alias_any", f"alias_{lang}"):
            if col in d.columns and pd.notna(r.get(col)):
                al |= {a.strip() for a in str(r[col]).split(";") if a.strip()}
        out[str(r.target).lower()] = sorted(al, key=len, reverse=True)
    return out

def mentions(text, topic, aliases, lang=None):
    """(matched, which alias, evidence in the text, how)"""
    for a in aliases.get(str(topic).lower(), [str(topic)]):
        ok, ev, how = hit(text, a, lang)
        if ok:
            return True, a, ev, how
    return False, "", "", ""
