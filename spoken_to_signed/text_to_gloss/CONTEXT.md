# SAIgn — Project Context
> Updated: 2026-05-17 (session 4 complete) · Gabriel (Part 3: LOE → LSE glosses)

---

## 1. What is SAIgn?

TFM pipeline: Spanish speech → LSE glosses → avatar animation.
Gabriel owns **Part 3** (Spanish text → LSE gloss translation) using the **ruLSE** rule-based algorithm (Perea-Trigo et al., Sensors 2024, doi:10.3390/s24051472), adapted from the Swiss spoken-to-signed pipeline.

---

## 2. Key Files

```
SAIgn/
├── lse_rules.py                   ← Main engine (ruLSE algorithm)
├── lse_rules.csv                  ← Rule table (group, input_pattern, output_pattern, exclusive)
├── lse_rules_20260517.csv         ← Backup before session-3 edits
├── radis_normalizado_v2.csv       ← RADIS gold dataset — DO NOT MODIFY
├── resultados_saign_renfe_v6.csv  ← Latest RENFE output (qualitative, no reference glosses)
├── saign_frases_aeropuerto.csv    ← Airport domain (90 sentences, glosas_lse EMPTY)
└── saign_renfe_frases.csv         ← RENFE domain (90 sentences, glosas_lse EMPTY)
```

---

## 3. Algorithm Overview

```
Spanish text
  → prepareText()    Stanza NLP: tokenize, POS (UPOS+XPOS Ancora), lemmatize
                     + _LEMMA_FIXES (text lookup, then lemma double-lookup)
  → applyRules()     Apply lse_rules.csv groups 0.x→5.x; dedup FUTURO/PASADO; filter ÉL espurio
  → glossSentece()   Word list → uppercase gloss string; applies _LEMMA_TO_GLOSS overrides
```

### Rule groups

| Group | Function |
|-------|----------|
| 0.1 | Elimination — prepositions (adp) |
| 0.2 | Elimination — conjunctions (cconj), relative pronouns (pr000000) |
| 0.3 | Elimination — punctuation |
| 0.9 | SE clitic removal |
| 0.10 | ÉL espurio elimination (explicit verb subjects) |
| 0.101 | Multi-word transport phrases: EFECTUAR SU ENTRADA→LLEGAR, EFECTUAR SU SALIDA→SALIR, DIRIGIR/ENCONTRAR ÉL cleanup |
| 0.11 | UNO espurio elimination |
| 0.12 | SU posesivo elimination |
| 0.14 | Lexical corrections: CHICA→MUJER, CHICO→HOMBRE, ADVERTIR→AVISAR |
| 0.15 | MIRA→VER |
| 0.16 | PROCEDENTE elimination (transport domain) |
| 1.x | Temporal markers (PASADO/FUTURO), negation, pronouns |
| 1.5/1.6 | Comparatives/superlatives → SUP |
| 2.x | Nominal — proper nouns (-NP), plurals (-PL), determiner reordering |
| 3.x | Adjectival — adjective after noun |
| 4.x | Adverbial — temporal adverbs before verb |
| 5.x | Verbal — auxiliary elimination, infinitive reordering |

### `_LEMMA_FIXES` — full current dict (lse_rules.py)

Key = `token.text.lower()` **or** Stanza's wrong lemma (double lookup applied). Value = correct lemma.

```python
"hirviendo":  "hervir",
"toqué":      "tocar",
"crucir":     "cruzar",      # also catches Stanza lemma "crucir" via double lookup
"diríjanse":  "dirigir",
"diríjase":   "dirigir",
"diríjar":    "dirigir",
"dirijan":    "dirigir",
"recojar":    "recoger",     # also catches Stanza lemma "recojar" via double lookup
"recojan":    "recoger",
"cierren":    "cerrar",
"sigan":      "seguir",
"llame":      "llamar",
"cuide":      "cuidar",
"cedar":      "ceder",
"crucen":     "cruzar",
"consulte":   "consultar",
"consultir":  "consultar",   # Stanza lemma fix, caught by double lookup
"alejarse":   "alejarse",
"preparado":  "preparar",
"gracias":    "gracias",
```

**Double lookup in prepareText (added session 3):**
```python
lemma = _LEMMA_FIXES.get(token.text.lower(), lemma)  # fix by surface text
lemma = _LEMMA_FIXES.get(lemma.lower(), lemma)         # fix by (wrong) Stanza lemma
```

### `_LEMMA_TO_GLOSS` — full current dict (lse_rules.py)

```python
"niño":       "HOMBRE PEQUEÑO2",
"niña":       "MUJER PEQUEÑO2",
"fin":        "FIN",
"gracias":    "GRACIAS",
"ver":        "MIRAR",
"oír":        "ESCUCHAR",
"temer":      "MIEDO",
"casualidad": "CASUAL",
```

### Entry points

```python
from lse_rules import generatorText2Gloss
gloss = generatorText2Gloss("El vuelo sale mañana.", rules_path="lse_rules.csv")
# → "MAÑANA VUELO SALIR"
```

---

## 4. Current State (2026-05-17)

### RADIS results

| Version | EM | Notes |
|---------|-----|-------|
| Baseline | 23/460 = 5.0% | Pre-session-2 |
| v4 (stable) | **28/460 = 6.1%** | After all session-2 fixes |
| v5 | 28/460 = 6.1% | Colab loaded stale file — _LEMMA_TO_GLOSS not applied |
| v6 | **42/460 = 9.1%** | ver→MIRAR, oír→ESCUCHAR, temer→MIEDO, niño/niña, gracias |
| v7 | **43/460 = 9.3%** | casualidad→CASUAL (+1); domain fixes added (no RADIS impact) |

**Last confirmed RADIS: v7 = 43/460 = 9.3% EM.**

### BLEU scores (RADIS v7, 460 sentences)

| Metric | Score |
|--------|-------|
| Sentence-BLEU avg (method1 smooth) | **8.85%** |
| Corpus-BLEU (unsmoothed) | 2.92% |
| Exact Match | 43/460 = 9.3% |

Computed locally from `resultados_radis_v7.csv` using `nltk.translate.bleu_score`.

### RENFE validation

| Version | Status | Key changes |
|---------|--------|-------------|
| v2 | baseline | — |
| v3 | +15 improvements | PROCEDENTE, EFECTUAR SU ENTRADA→LLEGAR, diríjanse/diríjase/diríjar fixed |
| v4 | regression on F002/F004 | Added SALIDA rule (Colab sync issue) |
| v5 | F002/F004/F007/F019 fixed | Wildcard fallback rules 0.101 added |
| v6 | F013/F032/F045 fixed | crucen→CRUZAR, consulte→CONSULTAR, recojan→RECOGER; double lookup |

**No reference glosses in RENFE dataset → no EM score. Qualitative only.**
**F007 ("efectúa su salida", Alvia) is a persistent outlier — unblocked by RADIS/score.**

### All active fixes (confirmed in Colab)

- di0000/da0000 elimination, pr000000 (relative QUE), CHICO→HOMBRE, CHICA→MUJER
- hirviendo→hervir (lemma fix), MIRA(PROPN)→VER
- ver→MIRAR, oír→ESCUCHAR, temer→MIEDO, niño/niña→HOMBRE/MUJER PEQUEÑO2, gracias→GRACIAS
- casualidad→CASUAL (_LEMMA_TO_GLOSS)
- diríjase/diríjanse/diríjar/dirijan→dirigir (_LEMMA_FIXES)
- recojar/recojan→recoger, crucir/crucen→cruzar, consulte/consultir→consultar (_LEMMA_FIXES)
- Double lookup in prepareText (text first, then Stanza lemma)
- 0.16: PROCEDENTE elimination
- 0.101: EFECTUAR SU ENTRADA/SALIDA → LLEGAR/SALIR (specific + wildcard fallback)

### RADIS ceiling

RADIS uses full LSE conventions (PERSONA classifiers, LOS-DOS, semantic substitutions) not derivable from Spanish. **At 9.3% EM, near the realistic ceiling of ~8-10%.** BLEU is more informative. Primary eval target is airport/RENFE (domain-specific).

### Known remaining gaps

- PERSONA token after HOMBRE/MUJER (73 missing) — inconsistent in corpus, not reliably addable
- PASADO omitted in RADIS but inserted by our rules (48 spurious) — by design
- Plural -PL — RADIS omits, our rules add (needed for airport/RENFE)
- "deber" auxiliary not eliminated (tagged as main verb by Stanza)
- F027: "niños pequeños" → HOMBRE PEQUEÑO2 PEQUEÑO (double PEQUEÑO — cosmetic)
- F044: "su equipaje" deleted by generic 0.12 rule before specific PREPARAR SU EQUIPAJE fires

---

## 5. Google Colab Setup

**Link:** https://colab.research.google.com/drive/1Ev6risEDqhJ7-JVshZHubz4p9MbBM1GM

Self-test (15/15) only runs in Colab — Stanza locally gives different POS tags.

| Cell | Purpose | Upload needed |
|------|---------|---------------|
| 1 | Install stanza + pandas | — |
| 2 | Clone spoken-to-signed repo | — |
| 3 | Load lse_rules.py + lse_rules.csv | **Upload both** |
| 4 | Quick test (3 sentences) | — |
| 5 | Upload dataset CSV | **Upload dataset** |
| 6+ | Process + save results | — |

**Important:** After kernel restart, always re-upload **both** lse_rules.py and lse_rules.csv in Cell 3. Python module caching means re-running Cell 3 without a kernel restart does NOT reload the Python module.

---

## 6. RADIS Validation Script

**Cell 7 — Run validation:**
```python
import time
COLUMNA_FRASE = 'español'
COLUMNA_REF   = 'glosas_saign'

df_radis = df[df[COLUMNA_REF].notna() & (df[COLUMNA_REF].str.strip() != '')].copy()
total = len(df_radis)
print(f'Procesando {total} frases...\n')

resultados = []
for idx, row in df_radis.iterrows():
    frase = str(row[COLUMNA_FRASE]).strip()
    referencia = str(row[COLUMNA_REF]).strip()
    t0 = time.time()
    try:
        resultado = text_to_gloss(frase, language='es')
        glosas = ' '.join(
            item.gloss for sent in resultado for item in sent
            if hasattr(item, 'gloss') and item.gloss not in (None, '', 'None', 'nan')
        )
        status, error = 'OK', ''
    except Exception as e:
        glosas, status, error = '', 'ERROR', f'{type(e).__name__}: {e}'
    fila = row.to_dict()
    fila.update({'glosas_generadas': glosas, 'exact_match': (glosas.strip() == referencia),
                 'status': status, 'error': error, 'segundos': round(time.time()-t0,3)})
    resultados.append(fila)
    if idx % 50 == 0: print(f'  {idx}/{total}...')

df_out = pd.DataFrame(resultados)
n_ok = (df_out.status=='OK').sum()
n_em = df_out.exact_match.sum()
print(f'\nExact Match: {n_em}/{n_ok} = {n_em/n_ok*100:.1f}%')
```

**Cell 8 — Save + BLEU:**
```python
from google.colab import files
import nltk
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
nltk.download('punkt', quiet=True)

ARCHIVO = 'resultados_radis_v8.csv'
df_out.to_csv(ARCHIVO, index=False, encoding='utf-8-sig')

smooth = SmoothingFunction().method1
bleu_scores = [
    sentence_bleu([str(r['glosas_saign']).split()], str(r['glosas_generadas']).split(), smoothing_function=smooth)
    for _, r in df_out[df_out.status=='OK'].iterrows()
    if str(r['glosas_saign']).split() and str(r['glosas_generadas']).split()
]
print(f'BLEU promedio: {sum(bleu_scores)/len(bleu_scores)*100:.1f}')
files.download(ARCHIVO)
```

---

## 7. Quick Reference — POS Tags

| Tag | Meaning | Example |
|-----|---------|---------|
| `noun` / `n000000` | Common noun | perro, vuelo |
| `verb` / `v000000` | Any verb | sale, llega |
| `v00s000` | Present tense | llega |
| `v00f000` | Future tense | llegará |
| `vmis0s0` | Past indicative | llegó |
| `vmg0000` | Gerund | llegando |
| `vmn0000` | Infinitive | llegar |
| `adj` | Adjective | nuevo |
| `adp` / `sp000` | Preposition | de, en |
| `np00000` | Proper noun | Madrid |
| `da0000` | Definite article | el, la |
| `di0000` | Indefinite article | un, una |
| `dp0000` | Possessive det. | su, sus |
| `rg` | General adverb | muy, bien |
| `pr000000` | Relative pronoun | que, quien |
| `cconj` | Coordinating conj. | y, o |
| `punct` | Punctuation | . , ; |

---

## 8. GitHub

Branch: `part3-translation`. Commit after each session:
- `lse_rules.py`, `lse_rules.csv`, `CONTEXT.md`
- Never commit `radis_normalizado_v2.csv` modifications

**Session 4 commit:**
```
fix: RENFE domain rules + lemma fixes | RADIS EM 6.1%→9.3%, BLEU 8.85%

- ver→MIRAR, oír→ESCUCHAR, temer→MIEDO, casualidad→CASUAL
- niño/niña→HOMBRE/MUJER PEQUEÑO2, gracias→GRACIAS
- diríjase/dirijan/recojan/crucen/consulte lemma fixes
- Double lookup in prepareText (text + Stanza lemma)
- 0.16 PROCEDENTE elimination
- 0.101 EFECTUAR SU ENTRADA/SALIDA → LLEGAR/SALIR (+ wildcard fallback)
- CONTEXT.md updated with BLEU results (sentence-BLEU 8.85%, corpus-BLEU 2.92%)
```

**Next session priorities:**
1. Airport domain validation (saign_frases_aeropuerto.csv — 90 sentences, no reference glosses)
2. Write TFM evaluation section with EM + BLEU results
3. (Optional) Investigate PERSONA classifier gap (73 missing cases)
