#!/usr/bin/env python3
"""Enumerate Internet Archive snapshots of the (pre-September-2026) server-rendered
Adilet pages (https://adilet.zan.kz/<lang>/docs/<ID>) for constitution (K...), codes (K...)
and laws (Z...), in Russian and Kazakh. For every document, keep the most recent
snapshot with HTTP 200 and a full-size page that predates the SPA redesign.

Output: _raw/kz/snapshots.tsv  (lang, id, timestamp, length)
"""
import os, re, sys, time, requests

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '_raw', 'kz')
UA = 'LawCodex/1.0 (+https://github.com/LawCodex)'
CUTOFF = '20260911'          # new SPA (no server-side text) went live around 2026-09-11
MINLEN = 3000                # SPA shell / error pages are ~1-2 KB
ID_RE = re.compile(r'^kz,zan,adilet\)/(rus|kaz)/docs/([a-z0-9_]+)$')

def cdx(prefix, frm):
    url = 'https://web.archive.org/cdx/search/cdx'
    params = dict(url=prefix, matchType='prefix', filter='statuscode:200',
                  fl='urlkey,timestamp,length', **{'from': frm})
    for attempt in range(6):
        try:
            r = requests.get(url, params=params, headers={'User-Agent': UA}, timeout=900)
            if r.status_code == 200:
                return r.text
            print('cdx', prefix, r.status_code, file=sys.stderr)
        except Exception as e:
            print('cdx err', prefix, e, file=sys.stderr)
        time.sleep(30 * (attempt + 1))
    raise SystemExit('CDX failed for ' + prefix)

def main():
    os.makedirs(RAW, exist_ok=True)
    frm = sys.argv[1] if len(sys.argv) > 1 else '2019'
    best = {}
    for lang in ('rus', 'kaz'):
        for p in ('K', 'Z'):
            cache = os.path.join(RAW, f'cdx_{lang}_{p}_{frm}.txt')
            if not os.path.exists(cache):
                txt = cdx(f'adilet.zan.kz/{lang}/docs/{p}', frm)
                open(cache, 'w').write(txt)
                time.sleep(5)
            for line in open(cache):
                parts = line.split()
                if len(parts) != 3:
                    continue
                key, ts, ln = parts
                m = ID_RE.match(key)
                if not m or ts >= CUTOFF or not ln.isdigit() or int(ln) < MINLEN:
                    continue
                k = (m.group(1), m.group(2).upper())
                best.setdefault(k, []).append((ts, ln))
    with open(os.path.join(RAW, 'snapshots.tsv'), 'w') as f:
        for (lang, i), snaps in sorted(best.items()):
            snaps = sorted(set(snaps), reverse=True)[:4]   # newest first, keep fallbacks
            f.write(f"{lang}\t{i}\t{','.join(t for t, _ in snaps)}\t{snaps[0][1]}\n")
    print(len(best), 'documents')

if __name__ == '__main__':
    main()
