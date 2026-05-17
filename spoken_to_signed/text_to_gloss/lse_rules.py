"""
lse_rules.py — Spanish text → LSE (Lengua de Signos Española) gloss converter
===============================================================================
SAIgn project — Part 3 (Gabriel, 2026)

Source: Celia Botella López — LSE-Gloss-Generator-2.ipynb / ruLSE algorithm
Reference paper: Perea-Trigo et al., Sensors 2024 (doi:10.3390/s24051472)
Adapted for: Swiss spoken-to-signed pipeline
  https://github.com/sign-language-processing/spoken-to-signed-translation

HOW IT WORKS (4-step ruLSE algorithm):
  1. Text preparation  — Stanza parses the Spanish sentence into Word objects
                          with lemma, UPOS (universal POS) and XPOS (Ancora POS).
  2. Rule application  — rules from lse_rules.csv are applied group by group.
                          Each rule finds a consecutive window of words that
                          matches its input pattern and transforms it.
  3. Gloss generation  — the transformed word list becomes UPPERCASE gloss tokens.
  4. (Optional) corpus — the input/output pair is saved to a CSV for future use.

RULE PATTERN SYNTAX (inside lse_rules.csv):
  <position>_<descriptor>   e.g.  1_vmis0s0   2_*   0_PASADO
  - position = integer (1-based for input, 0 = insertion in output)
  - descriptor:
      *             → wildcard, matches any word
      ALL-UPPERCASE → lemma match  (e.g.  COMPRAR  matches lemma "comprar")
      lowercase     → POS match:  try UPOS first, then XPOS with '0' as wildcard
                      (e.g.  verb  → UPOS match;  vmis0s0  → XPOS match)
  - output suffix like -PL or -NP appended to descriptor marks the gloss suffix
      (e.g.  1_nc0p000-PL  → keep word at slot 1 but gloss it as lemma+"-PL")

SWISS PIPELINE ENTRY POINT:
  text_to_gloss(text, language='es', **kwargs) → list[Gloss]
"""

from __future__ import annotations

import csv
import os
import re
from typing import Optional

import pandas as pd
import stanza

from spoken_to_signed.text_to_gloss.types import Gloss, GlossItem


# ─────────────────────────────────────────────────────────────────────────────
# Lazy Stanza pipeline — loaded only once on the first call
# ─────────────────────────────────────────────────────────────────────────────

_nlp: Optional[stanza.Pipeline] = None


def _get_nlp() -> stanza.Pipeline:
    """Return the shared Stanza NLP pipeline, loading it on the first call.

    NOTE: If you see a download prompt the first time, run this once in the
    terminal beforehand:
        python3 -c "import stanza; stanza.download('es')"
    """
    global _nlp
    if _nlp is None:
        _nlp = stanza.Pipeline(
            lang="es",
            processors="tokenize,mwt,pos,lemma",
            verbose=False,
        )
    return _nlp


# ─────────────────────────────────────────────────────────────────────────────
# Word — one token and all its linguistic attributes
# ─────────────────────────────────────────────────────────────────────────────

class Word:
    """Container for one token produced by Stanza.

    Attributes:
        id          Token index within the sentence (−1 for rule-inserted words).
        text        Surface form as it appears in the sentence, e.g. "compró".
        upper_text  Surface form in uppercase (cached for convenience).
        lemma       Base form returned by Stanza, e.g. "comprar".
        upos        Universal POS tag, e.g. "VERB", "NOUN", "ADP".
        xpos        Ancora extended POS tag, e.g. "vmis3s0", "ncms000".
        feats       Morphological features string, e.g. "Number=Plur|Gender=Masc".
        pos         Alias: xpos if available, otherwise upos.
        gloss_suffix  Suffix to append when glossing (e.g. "-PL", "-NP").
                      Set by transformation rules; empty string by default.
    """

    __slots__ = (
        "id", "text", "upper_text", "lemma", "upos", "xpos",
        "feats", "pos", "gloss_suffix",
    )

    def __init__(
        self,
        id: int,
        text: str,
        lemma: str,
        upos: str,
        xpos: str,
        feats: str = "",
        gloss_suffix: str = "",
    ) -> None:
        self.id = id
        self.text = text
        self.upper_text = text.upper()
        self.lemma = lemma
        self.upos = upos
        self.xpos = xpos
        self.feats = feats
        self.pos = xpos if xpos else upos
        self.gloss_suffix = gloss_suffix

    def __repr__(self) -> str:
        return (
            f"Word({self.text!r}, lemma={self.lemma!r}, "
            f"upos={self.upos!r}, xpos={self.xpos!r})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Text preparation
# ─────────────────────────────────────────────────────────────────────────────

_LEMMA_FIXES: dict[str, str] = {
    # Stanza gerund/conjugation errors — key = text.lower(), value = correct lemma
    "hirviendo":  "hervir",
    "toqué":      "tocar",
    "toqué":      "tocar",
    "crucir":     "cruzar",
    "diríjanse":  "dirigir",
    "diríjase":   "dirigir",
    "diríjar":    "dirigir",
    "dirijan":    "dirigir",
    "recojar":    "recoger",
    "recojan":    "recoger",
    "cierren":    "cerrar",
    "sigan":      "seguir",
    "llame":      "llamar",
    "cuide":      "cuidar",
    "cedar":      "ceder",
    "crucen":     "cruzar",
    "consulte":   "consultar",
    "consultir":  "consultar",
    # Reflexive infinitive: Stanza strips "se" → keep full reflexive form as gloss
    "alejarse":   "alejarse",
    # Past participle used as adjective: map to verb lemma for LSE gloss
    "preparado":  "preparar",
    # Interjection: Stanza lemmatizes "gracias" → "gracia"; fix for gloss map below
    "gracias":    "gracias",
}

# Multi-word or fixed-form LSE glosses that override the default lemma.upper() path.
# Key = word.lemma.lower(); value = the exact gloss string to emit (may be multiple tokens).
_LEMMA_TO_GLOSS: dict[str, str] = {
    "niño":    "HOMBRE PEQUEÑO2",  # child (boy) — RADIS/LSE corpus convention
    "niña":    "MUJER PEQUEÑO2",   # child (girl) — RADIS/LSE corpus convention
    "fin":     "FIN",              # prevents FIN-NP when "Fin." is tagged PROPN
    "gracias": "GRACIAS",          # prevents GRACIA-PL (plural common noun fallback)
    # LSE lexical substitutions validated against RADIS corpus
    "ver":     "MIRAR",            # ver → MIRAR (LSE uses MIRAR for both ver/mirar)
    "oír":     "ESCUCHAR",         # oír → ESCUCHAR (LSE convention)
    "temer":      "MIEDO",            # temer → MIEDO (noun sign, not verb)
    "casualidad": "CASUAL",           # casualidad → CASUAL (LSE lexical substitution)
}


def prepareText(str_text: str, nlp: stanza.Pipeline) -> list[list[Word]]:
    """Run Stanza over *str_text* and return one list of Words per sentence.

    Stanza handles:
    - Sentence splitting by punctuation
    - Tokenisation into individual word tokens
    - MWT expansion: "del" → ["de", "el"];  "al" → ["a", "el"]
    - UPOS and XPOS (Ancora) tagging
    - Lemmatisation
    """
    doc = nlp(str_text)
    sentences: list[list[Word]] = []
    for sent in doc.sentences:
        words: list[Word] = []
        for token in sent.words:
            lemma = token.lemma if token.lemma else token.text
            lemma = _LEMMA_FIXES.get(token.text.lower(), lemma)
            lemma = _LEMMA_FIXES.get(lemma.lower(), lemma)
            w = Word(
                id=token.id,
                text=token.text,
                lemma=lemma,
                upos=token.upos if token.upos else "",
                xpos=token.xpos if token.xpos else "",
                feats=token.feats if token.feats else "",
            )
            words.append(w)
        sentences.append(words)
    return sentences


# ─────────────────────────────────────────────────────────────────────────────
# Rule parsing helpers
# ─────────────────────────────────────────────────────────────────────────────

def ruleAsDictionary(rule_str: str) -> dict[int, str]:
    """Parse a rule string into a {position: descriptor} dict.

    Examples:
        "1_vmis0s0 2_* 3_noun"  →  {1: 'vmis0s0', 2: '*', 3: 'noun'}
        "0_PASADO 1_*"          →  {0: 'PASADO',  1: '*'}
        "1_nc0p000-PL"          →  {1: 'nc0p000-PL'}

    Position 0 in an OUTPUT rule means "insert a new word here".
    """
    result: dict[int, str] = {}
    if not isinstance(rule_str, str) or not rule_str.strip():
        return result
    for token in rule_str.strip().split():
        parts = token.split("_", 1)          # split only on the FIRST underscore
        if len(parts) == 2:
            try:
                pos = int(parts[0])
                result[pos] = parts[1]
            except ValueError:
                pass
    return result


_SUFFIX_RE = re.compile(r"^(.+?)(-[A-Z]+)$")


def _parseSuffix(value: str) -> tuple[str, str]:
    """Split a rule value into (base, suffix).

    Examples:
        'nc0p000-PL'  →  ('nc0p000', '-PL')
        'np00000-NP'  →  ('np00000', '-NP')
        'PASADO'      →  ('PASADO', '')
        '*'           →  ('*', '')
    """
    m = _SUFFIX_RE.match(value)
    if m:
        return m.group(1), m.group(2)
    return value, ""


# ─────────────────────────────────────────────────────────────────────────────
# Rule matching — single word
# ─────────────────────────────────────────────────────────────────────────────

def isLemma(word: Word, value: str) -> bool:
    """ALL-UPPERCASE value → check against the word's lemma (uppercased).

    Example: value="COMPRAR" matches word with lemma="comprar".
    """
    return word.lemma.upper() == value.upper()


def isUPOS(word: Word, value: str) -> bool:
    """Pure-lowercase alphabetic value → compare against Universal POS tag.

    Example: value="verb" matches word.upos="VERB".
    """
    return word.upos.lower() == value.lower()


def isXPOS(word: Word, value: str) -> bool:
    """Lowercase Ancora XPOS value with '0' as wildcard character.

    Characters in *value* must equal the corresponding character in word.xpos,
    except '0' which matches any character.

    Example: value="vmis0s0" matches word.xpos="vmis3s0" (person wildcard).
    """
    xpos = word.xpos.lower()
    rule = value.lower()
    if len(xpos) != len(rule):
        return False
    for xc, rc in zip(xpos, rule):
        if rc != "0" and xc != rc:
            return False
    return True


def checkPartialRule(word: Word, value: str) -> bool:
    """Return True if *word* satisfies the rule *value*.

    Decision tree:
        "*"            → always True (wildcard)
        ALL-UPPERCASE  → lemma check (isLemma)
        lowercase      → try isUPOS first, then isXPOS
    """
    if value == "*":
        return True
    base, _ = _parseSuffix(value)          # ignore suffix for matching
    if base == base.upper() and any(c.isalpha() for c in base):
        return isLemma(word, base)
    return isUPOS(word, base) or isXPOS(word, base)


# ─────────────────────────────────────────────────────────────────────────────
# Rule matching — contiguous window in the sentence
# ─────────────────────────────────────────────────────────────────────────────

def checkRule(
    sentence: list[Word],
    rule_dict: dict[int, str],
) -> Optional[list[int]]:
    """Find the first contiguous window in *sentence* matching *rule_dict*.

    The input pattern must match a run of N consecutive words.
    Returns the list of sentence indices [i, i+1, …, i+N−1] on success,
    or None if no match exists.

    (The paper specifies: "it is sufficient for a subset of consecutive words
    in the original sentence to match the input structure of a rule.")
    """
    n = len(rule_dict)
    if n == 0:
        return None

    for start in range(len(sentence) - n + 1):
        matched: list[int] = []
        ok = True
        for slot in range(1, n + 1):
            if slot not in rule_dict:
                ok = False
                break
            if not checkPartialRule(sentence[start + slot - 1], rule_dict[slot]):
                ok = False
                break
            matched.append(start + slot - 1)
        if ok:
            return matched
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Transformation — apply one fired rule to the sentence
# ─────────────────────────────────────────────────────────────────────────────

def _applyTransformation(
    sentence: list[Word],
    output_dict: dict[int, str],
    matched_indices: list[int],
) -> list[Word]:
    """Rebuild the sentence after a rule has fired.

    The matched window (consecutive words at *matched_indices*) is replaced
    by the sequence defined in *output_dict*:

        Position 0    → insert a brand-new Word whose text/lemma = the value
                         (e.g.  0_PASADO  inserts word with text="PASADO")
        Position N>0  → keep the word that matched input slot N, optionally
                         setting a gloss suffix if the value ends in -PL/-NP/etc.

    Words outside the matched window are preserved in their relative order.
    """
    if not output_dict:
        # Deletion rule: remove all matched words, keep everything else
        matched_set = set(matched_indices)
        return [w for i, w in enumerate(sentence) if i not in matched_set]

    # Build replacement sequence
    output_words: list[Word] = []
    for out_pos in sorted(output_dict.keys()):
        out_value = output_dict[out_pos]
        if out_pos == 0:
            # Brand-new inserted word (PASADO, FUTURO, NOSOTROS, …)
            output_words.append(
                Word(id=-1, text=out_value, lemma=out_value, upos="", xpos="")
            )
        else:
            slot_idx = out_pos - 1
            if slot_idx < len(matched_indices):
                original = sentence[matched_indices[slot_idx]]
                _, suffix = _parseSuffix(out_value)
                if suffix:
                    # Create a copy with the gloss suffix set
                    modified = Word(
                        id=original.id,
                        text=original.text,
                        lemma=original.lemma,
                        upos=original.upos,
                        xpos=original.xpos,
                        feats=original.feats,
                        gloss_suffix=suffix,
                    )
                    output_words.append(modified)
                else:
                    output_words.append(original)

    # Splice output_words in place of the matched window
    matched_set = set(matched_indices)
    new_sentence: list[Word] = []
    inserted = False
    for i, word in enumerate(sentence):
        if i in matched_set:
            if not inserted:
                new_sentence.extend(output_words)
                inserted = True
            # Skip the original matched word (handled via output_words above)
        else:
            new_sentence.append(word)
    if not inserted:
        new_sentence.extend(output_words)

    return new_sentence


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Rule application
# ─────────────────────────────────────────────────────────────────────────────

def applyRules(
    sentence: list[Word],
    rules: pd.DataFrame,
    nlp: stanza.Pipeline,
) -> list[Word]:
    """Apply all CSV rules to *sentence*, group by group.

    Rule groups (ascending numeric priority):
        0.x   Elimination   — articles, prepositions, conjunctions, punctuation
        1.x   Temporal      — tense markers (PASADO/FUTURO), negation, pronouns
        1.5   Comparatives  — MAS/MENOS QUE → comparative marker
        2.x   Nominal       — proper nouns (-NP suffix), plurals (-PL suffix)
        3.x   Adjectival    — adjective placement after noun
        4.x   Adverbial     — temporal/locative adverbs moved before verb
        5.x   Verbal        — auxiliary elimination, infinitive reordering

    Within each group rules are applied in CSV order.
    Rules with the same *exclusive* number in the same group exclude each other:
    once one fires, others with the same number are skipped.
    Each rule is applied REPEATEDLY until it no longer matches (handles
    multiple occurrences, e.g. several prepositions in one sentence).
    """
    # Convert group column to float so "0" and "0.0" compare equal
    groups_col = rules.iloc[:, 0].apply(
        lambda x: float(x) if pd.notna(x) else None
    )
    raw_groups = sorted(set(g for g in groups_col if g is not None))

    fired_exclusive: dict[float, set] = {}

    for group in raw_groups:
        fired_exclusive.setdefault(group, set())
        group_mask = groups_col == group
        group_rules = rules[group_mask]

        for _, row in group_rules.iterrows():
            input_str  = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ""
            output_str = str(row.iloc[2]) if pd.notna(row.iloc[2]) else ""
            excl_raw   = row.iloc[3]      if pd.notna(row.iloc[3]) else None

            if not input_str.strip():
                continue

            # Resolve exclusive number
            excl_num: Optional[int] = None
            if excl_raw is not None:
                try:
                    excl_num = int(float(excl_raw))
                except (ValueError, TypeError):
                    pass

            # Skip if a conflicting exclusive rule already fired in this group
            if excl_num is not None and excl_num in fired_exclusive[group]:
                continue

            input_dict  = ruleAsDictionary(input_str)
            output_dict = ruleAsDictionary(output_str)

            if not input_dict:
                continue

            # Apply the rule repeatedly until no more matches remain.
            # Safety cap: at most len(sentence)+1 iterations.
            for _ in range(len(sentence) + 1):
                matched = checkRule(sentence, input_dict)
                if matched is None:
                    break
                sentence = _applyTransformation(sentence, output_dict, matched)
                if excl_num is not None:
                    fired_exclusive[group].add(excl_num)

    # Weakness 1 fix: deduplicate temporal markers.
    # Each future/past verb in the sentence triggers one insertion of FUTURO/PASADO
    # via the repeat loop. Keep only the first occurrence of each marker.
    seen_temporal: set[str] = set()
    deduped: list[Word] = []
    for w in sentence:
        if w.id == -1 and w.text in ("PASADO", "FUTURO"):
            if w.text not in seen_temporal:
                seen_temporal.add(w.text)
                deduped.append(w)
        else:
            deduped.append(w)
    sentence = deduped

    # Weakness 3 fix: remove articles/clitics that survive rule 2.1 because
    # Stanza assigns them lemma "él" (e.g. "la"→"él", "Se"→"él"), causing
    # isLemma("EL") to fail and producing a spurious ÉL in the gloss.
    # The real pronoun "él" is safe: its surface text is "él" (with accent),
    # so text.lower()=="él" excludes it from the filter.
    sentence = [
        w for w in sentence
        if not (
            w.id != -1
            and w.lemma.lower() in {"el", "él"}
            and w.upos in {"DET", "PRON"}
            and w.text.lower() != "él"   # preserve real pronoun "él"
        )
    ]

    return sentence


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Gloss generation
# ─────────────────────────────────────────────────────────────────────────────

_SKIP_UPOS  = {"PUNCT", "SYM"}
_SKIP_TEXTS = {".", ",", "¿", "?", "¡", "!", ";", ":", "«", "»", "—", "–", "-"}


def glossSentece(sentence: list[Word]) -> str:
    """Convert the rule-transformed *sentence* into a space-separated gloss string.

    For each word:
    - Inserted words (id == −1): use .text directly  (e.g. "PASADO", "NOSOTROS")
    - Punctuation / symbol tokens: skip
    - All other words: use lemma.upper() plus any gloss_suffix set by a rule
    - Fallback: if no rule added a suffix, add -NP for proper nouns
                and -PL for plural common nouns

    Note: the function name preserves the original spelling from Celia's notebook
    (glossSentece, intentionally without the second 'n').
    """
    glosses: list[str] = []

    for word in sentence:
        if word.id == -1:
            # Rule-inserted word — text IS the gloss (e.g. "PASADO", "PEPE-NP")
            glosses.append(word.text)
            continue
        elif word.upos in _SKIP_UPOS or word.text in _SKIP_TEXTS:
            continue
        else:
            # Multi-word / fixed-form overrides (checked before POS-suffix logic)
            mapped = _LEMMA_TO_GLOSS.get(word.lemma.lower())
            if mapped is not None:
                glosses.append(mapped)
                continue
            gloss = word.lemma.upper()
            if word.gloss_suffix:
                # Suffix was set explicitly by a transformation rule
                gloss += word.gloss_suffix
            elif word.upos == "PROPN":
                # Fallback: proper nouns are fingerspelled → -NP
                gloss += "-NP"
            elif word.upos == "NOUN" and "Number=Plur" in (word.feats or ""):
                # Fallback: plural common nouns → -PL
                gloss += "-PL"

        if gloss:
            glosses.append(gloss)

    return " ".join(glosses)


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 (optional) — Corpus insertion
# ─────────────────────────────────────────────────────────────────────────────

def insertCorpus(path: str, input_sentence: str, output_gloss: str) -> None:
    """Append an (input, output) pair to a CSV corpus file at *path*.

    Creates the file with a header row if it does not exist yet.
    Useful for building a training/validation corpus from real airport
    announcements during demos or testing sessions.
    """
    file_exists = os.path.isfile(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["input", "output"])
        writer.writerow([input_sentence, output_gloss])


# ─────────────────────────────────────────────────────────────────────────────
# Master wrapper — mirrors the API from Celia's notebook
# ─────────────────────────────────────────────────────────────────────────────

def generatorText2Gloss(
    str_text: str,
    rules_path: Optional[str] = None,
    corpus_path: Optional[str] = None,
) -> str:
    """End-to-end Spanish → LSE gloss string (ruLSE algorithm).

    Args:
        str_text:     One or more Spanish sentences.
        rules_path:   Path to the rules CSV; defaults to lse_rules.csv in the
                      same directory as this module.
        corpus_path:  If provided, the (input, gloss) pair is saved there.

    Returns:
        Gloss string with sentences separated by " | ".

    Example:
        >>> generatorText2Gloss("El vuelo sale mañana.")
        'MAÑANA VUELO SALIR'
    """
    nlp = _get_nlp()
    if rules_path is None:
        rules_path = os.path.join(os.path.dirname(__file__), "lse_rules.csv")

    rules     = pd.read_csv(rules_path, encoding="utf-8")
    sentences = prepareText(str_text, nlp)

    all_glosses: list[str] = []
    for sentence in sentences:
        if sentence:
            transformed = applyRules(sentence, rules, nlp)
            gloss_str   = glossSentece(transformed)
            if gloss_str:
                all_glosses.append(gloss_str)

    result = " | ".join(all_glosses)
    if corpus_path:
        insertCorpus(corpus_path, str_text, result)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Swiss pipeline adapter  ←  THIS IS THE ENTRY POINT CALLED BY THE PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def text_to_gloss(
    text: str,
    language: str = "es",
    **kwargs,   # absorbs signed_language and any other pipeline kwargs
) -> list[Gloss]:
    """Entry point called by the Swiss spoken-to-signed pipeline.

    The pipeline in bin.py calls:
        module.text_to_gloss(text=text, language=language, **kwargs)
    where language is the spoken language code (should be "es" for Spanish).

    Returns:
        list[Gloss]  — one Gloss (= list[GlossItem]) per input sentence.
        Each GlossItem: word=None (no original word stored), gloss=UPPERCASE_TOKEN.

    Example output for "El vuelo sale mañana.":
        [[GlossItem(word=None, gloss='MAÑANA'),
          GlossItem(word=None, gloss='VUELO'),
          GlossItem(word=None, gloss='SALIR')]]
    """
    if not text or not text.strip():
        return []

    nlp        = _get_nlp()
    rules_path = os.path.join(os.path.dirname(__file__), "lse_rules.csv")
    rules      = pd.read_csv(rules_path, encoding="utf-8")

    sentences  = prepareText(text, nlp)
    result: list[Gloss] = []

    for sentence in sentences:
        if not sentence:
            continue
        transformed = applyRules(sentence, rules, nlp)
        gloss_str   = glossSentece(transformed)

        gloss_items: Gloss = [
            GlossItem(word=None, gloss=g)
            for g in gloss_str.strip().split()
            if g
        ]
        if gloss_items:
            result.append(gloss_items)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Quick self-test — run with:  python3 lse_rules.py
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Reference test cases from Celia's notebook (15/15 passed)
    REFERENCE_TESTS = [
        ("Pepe compró un coche a Pepa.",
         "PASADO PEPE-NP COCHE COMPRAR PEPA-NP"),
        ("Llegaremos mañana al lugar previsto.",
         "MAÑANA NOSOTROS LLEGAR LUGAR PREVISTO"),
        ("¿Quién ha estado en París?",
         "PARÍS-NP QUIÉN"),
        ("Diego golpeó ayer las sillas.",
         "AYER DIEGO-NP SILLA-PL GOLPEAR"),
    ]

    # Airport-domain sentences (SAIgn target domain)
    AIRPORT_TESTS = [
        "El vuelo IB403 sale mañana a las diez.",
        "Los pasajeros deben facturar el equipaje en la puerta dos.",
        "El vuelo con destino Madrid tiene un retraso de veinte minutos.",
        "Se ruega a los señores pasajeros que embarquen por la puerta doce.",
        "Atención: el vuelo ha sido cancelado.",
    ]

    print("=" * 65)
    print("lse_rules.py — SAIgn Part 3 self-test")
    print("=" * 65)

    print("\n--- Reference tests (from Celia's notebook) ---")
    for spanish, expected in REFERENCE_TESTS:
        glosses = text_to_gloss(spanish, language="es")
        got = " | ".join(" ".join(g.gloss for g in sent) for sent in glosses)
        status = "✓" if got == expected else "?"
        print(f"{status} IN : {spanish}")
        print(f"  EXP: {expected}")
        print(f"  GOT: {got}")
        print()

    print("--- Airport domain sentences ---")
    for spanish in AIRPORT_TESTS:
        glosses = text_to_gloss(spanish, language="es")
        got = " | ".join(" ".join(g.gloss for g in sent) for sent in glosses)
        print(f"IN : {spanish}")
        print(f"OUT: {got}")
        print()
