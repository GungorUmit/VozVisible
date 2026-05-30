import os, sys
# Ensure repo root is on sys.path when invoked from tools/
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from spoken_to_signed.bin import _text_to_gloss
from spoken_to_signed.gloss_to_pose.lookup.csv_lookup import CSVPoseLookup
from pose_format import Pose

text = 'El tren con destino Atocha sale a las ocho.'
lex = 'spoken_to_signed/assets/lse_lexicon'

print('Using lexicon:', lex)
sentences = _text_to_gloss(text, 'es', 'simple')
print('Sentences:', sentences)
lookup = CSVPoseLookup(lex)

for sent in sentences:
    for word, gloss in sent:
        if not word or not gloss:
            continue
        print('\nChecking', repr(word), '/', repr(gloss))
        try:
            res = lookup.lookup(word, gloss, 'es', 'lse')
            print('OK')
        except Exception as e:
            print('Lookup failed:', e)
            # find candidate rows
            rows = lookup.words_index.get('es', {}).get('lse', {}).get(word.lower())
            print('candidate rows:', rows)
            if rows:
                for r in rows:
                    p = os.path.join(lex, r['path'])
                    print('-> row path', r['path'], 'exists', os.path.exists(p), 'size', os.path.getsize(p) if os.path.exists(p) else None)
                    try:
                        with open(p, 'rb') as f:
                            Pose.read(f.read())
                        print('   pose OK')
                    except Exception as e2:
                        print('   pose read error:', repr(e2))
            sys.exit(1)

print('\nAll lookups OK')
