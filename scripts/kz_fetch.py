#!/usr/bin/env python3
"""Download the archived Adilet pages listed in _raw/kz/snapshots.tsv from the
Internet Archive (raw 'id_' playback, i.e. the original HTML as served by adilet.zan.kz).
Cached gzip-compressed under _raw/kz/html/<lang>/<ID>.html.gz; re-runs skip cached files.
"""
import gzip, zlib, os, sys, time, threading, requests
from concurrent.futures import ThreadPoolExecutor

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '_raw', 'kz')
UA = 'LawCodex/1.0 (+https://github.com/LawCodex)'
WORKERS = 2
DELAY = 2.0
lock = threading.Lock()
sess = threading.local()

def get(url):
    if not hasattr(sess, 's'):
        sess.s = requests.Session()
        sess.s.headers['User-Agent'] = UA
    for attempt in range(4):
        try:
            r = sess.s.get(url, timeout=180, stream=True)
            if r.status_code == 200:
                body = r.raw.read(decode_content=False)
                # archived captures are sometimes gzip-encoded (possibly twice), sometimes not
                for _ in range(3):
                    if body[:2] == b'\x1f\x8b':
                        try:
                            body = zlib.decompress(body, 47)
                            continue
                        except Exception:
                            pass
                    break
                return body
            if r.status_code == 404:
                return None
            if r.status_code >= 500 and attempt >= 1:
                return None          # broken capture: caller tries an older snapshot
            wait = 60 if r.status_code == 429 else 10 * (attempt + 1)
            print('HTTP', r.status_code, url, 'sleep', wait, file=sys.stderr, flush=True)
            time.sleep(wait)
        except Exception as e:
            print('ERR', url, e, file=sys.stderr, flush=True)
            time.sleep(10 * (attempt + 1))
    return None

def job(row):
    lang, i, tss, _ = row
    out = os.path.join(RAW, 'html', lang, i + '.html.gz')
    if os.path.exists(out):
        return
    data = None
    for ts in tss.split(','):
        url = f'https://web.archive.org/web/{ts}id_/https://adilet.zan.kz/{lang}/docs/{i}'
        data = get(url)
        time.sleep(DELAY)
        if data and len(data) > 5000 and b'<article' in data:
            data = (ts + '\n').encode() + data   # first line = snapshot timestamp
            break
        data = None
    if not data:
        print('FAIL', lang, i, ts, file=sys.stderr, flush=True)
        return
    tmp = out + '.tmp'
    with gzip.open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, out)

def main():
    rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(RAW, 'snapshots.tsv'))]
    phase = sys.argv[1] if len(sys.argv) > 1 else 'rus'
    if phase == 'rus':
        rows = [r for r in rows if r[0] == 'rus']
    else:
        # Kazakh pages only for documents whose Russian page is a law/code in force
        keep = set(l.split('\t')[0] for l in open(os.path.join(RAW, 'rus_inforce.txt')))
        rows = [r for r in rows if r[0] == 'kaz' and r[1] in keep]
    rows.sort(key=lambda r: (r[1][0] != 'K', r[1]))
    for lang in ('rus', 'kaz'):
        os.makedirs(os.path.join(RAW, 'html', lang), exist_ok=True)
    n = 0
    with ThreadPoolExecutor(WORKERS) as ex:
        for _ in ex.map(job, rows):
            n += 1
            if n % 200 == 0:
                print('progress', n, '/', len(rows), flush=True)
    print('done', n)

if __name__ == '__main__':
    main()
