#!/usr/bin/env python3
"""Fetch archived Adilet document pages from Common Crawl (https://commoncrawl.org).

The Internet Archive throttles us to a few pages per minute, so the bulk of the archived
adilet.zan.kz pages is taken from Common Crawl's public WARC archives instead:

  index:  data.commoncrawl.org/cc-index/collections/<crawl>/indexes/cluster.idx  (zipnum index;
          only the blocks covering "kz,zan,adilet)/kaz/docs" .. "kz,zan,adilet)/rus/docs" are read)
  pages:  HTTP range requests on the WARC files named in the index.

Usage:
  kz_cc.py index CC-MAIN-2026-30 CC-MAIN-2026-25 ...   -> _raw/kz/cc/<crawl>.cdx
  kz_cc.py fetch                                        -> _raw/kz/html/<lang>/<ID>.html.gz
                                                           (first line: "cc:<crawl-timestamp>")
"""
import gzip, io, json, os, re, sys, time, zlib, requests

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '_raw', 'kz')
CC = os.path.join(RAW, 'cc')
UA = 'LawCodex/1.0 (+https://github.com/LawCodex)'
BASE = 'https://data.commoncrawl.org/'
LO, HI = 'kz,zan,adilet)/kaz/docs/', 'kz,zan,adilet)/rus/docs/~'
MARKER = b'<article'
CUTOFF = '20260911'
ID_RE = re.compile(r'^kz,zan,adilet\)/(rus|kaz)/docs/([a-z0-9_]+)$')


def get(s, url, headers=None, stream=False):
    for a in range(8):
        try:
            r = s.get(url, headers=headers or {}, timeout=300, stream=stream)
            if r.status_code in (200, 206):
                return r
            print('HTTP', r.status_code, url, file=sys.stderr, flush=True)
        except Exception as e:
            print('ERR', url, str(e)[:100], file=sys.stderr, flush=True)
        time.sleep(10 * (a + 1))
    return None


def index(s, crawls):
    os.makedirs(CC, exist_ok=True)
    for crawl in crawls:
        out = os.path.join(CC, crawl + '.cdx')
        if os.path.exists(out):
            continue
        r = get(s, f'{BASE}cc-index/collections/{crawl}/indexes/cluster.idx', stream=True)
        if r is None:
            continue
        blocks, prev = [], None
        for line in r.iter_lines(chunk_size=1 << 20):
            line = line.decode('utf-8', 'replace')
            key = line.split(' ', 1)[0]
            if key < LO:
                prev = line
                continue
            if prev is not None:
                blocks.append(prev)
                prev = None
            if key > HI:
                break
            blocks.append(line)
        r.close()
        lines = []
        for b in blocks:
            parts = b.split('\t')
            fname, off, ln = parts[1], int(parts[2]), int(parts[3])
            rr = get(s, f'{BASE}cc-index/collections/{crawl}/indexes/{fname}',
                     headers={'Range': f'bytes={off}-{off + ln - 1}'})
            if rr is None:
                continue
            txt = zlib.decompress(rr.content, 47).decode('utf-8', 'replace')
            lines += [l for l in txt.split('\n') if l.startswith(('kz,zan,adilet)/rus/docs/', 'kz,zan,adilet)/kaz/docs/'))]
            time.sleep(0.5)
        open(out, 'w').write('\n'.join(lines) + '\n')
        print(crawl, len(blocks), 'blocks', len(lines), 'lines', flush=True)


def candidates():
    best = {}
    for fn in sorted(os.listdir(CC)):
        if not fn.endswith('.cdx'):
            continue
        for line in open(os.path.join(CC, fn)):
            p = line.split(' ', 2)
            if len(p) != 3:
                continue
            m = ID_RE.match(p[0])
            if not m or p[1] >= CUTOFF:
                continue
            d = json.loads(p[2])
            if d.get('status') != '200' or 'html' not in d.get('mime', '') or int(d['length']) < 4000:
                continue
            k = (m.group(1), m.group(2).upper())
            if k[1][0] not in 'ZK':      # Z = laws, K = constitution / codes (and presidential addresses)
                continue
            best.setdefault(k, []).append((p[1], d['filename'], int(d['offset']), int(d['length'])))
    for k in best:
        best[k].sort(reverse=True)
    return best


def warc_body(raw):
    data = zlib.decompress(raw, 47)
    # WARC headers, then HTTP headers, then payload
    i = data.find(b'\r\n\r\n')
    j = data.find(b'\r\n\r\n', i + 4)
    http_head = data[i + 4:j].decode('latin-1')
    body = data[j + 4:]
    if not http_head.startswith('HTTP/') or ' 200' not in http_head.split('\r\n')[0]:
        return None
    h = http_head.lower()
    if 'transfer-encoding: chunked' in h:
        out, pos = b'', 0
        while True:
            e = body.find(b'\r\n', pos)
            if e < 0:
                break
            size = int(body[pos:e].split(b';')[0] or b'0', 16)
            if size == 0:
                break
            out += body[e + 2:e + 2 + size]
            pos = e + 2 + size + 2
        body = out
    if body[:2] == b'\x1f\x8b':
        try:
            body = zlib.decompress(body, 47)
        except Exception:
            pass
    return body


def fetch(s, only_lang=None, keep=None):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    best = candidates()
    print(len(best), 'documents in Common Crawl', flush=True)
    local = threading.local()
    todo = [(k, v) for k, v in sorted(best.items())
            if (not only_lang or k[0] == only_lang) and (keep is None or k[1] in keep)]

    def job(item):
        (lang, docid), caps = item
        out = os.path.join(RAW, 'html', lang, docid + '.html.gz')
        if os.path.exists(out):
            return
        if not hasattr(local, 's'):
            local.s = requests.Session(); local.s.headers['User-Agent'] = UA
        os.makedirs(os.path.dirname(out), exist_ok=True)
        for ts, fname, off, ln in caps[:3]:
            r = get(local.s, BASE + fname, headers={'Range': f'bytes={off}-{off + ln - 1}'})
            if r is None:
                continue
            try:
                body = warc_body(r.content)
            except Exception as e:
                print('bad record', docid, e, file=sys.stderr)
                body = None
            if body and MARKER in body:
                with gzip.open(out + '.tmp', 'wb') as f:
                    f.write(f'cc:{ts}:{fname}:{off}:{ln}\n'.encode() + body)
                os.replace(out + '.tmp', out)
                break

    with ThreadPoolExecutor(4) as ex:      # data.commoncrawl.org (CloudFront/S3); <= 4 parallel requests
        for i, _ in enumerate(ex.map(job, todo)):
            if i % 200 == 0:
                print('fetched', i, len(todo), flush=True)
    print('done', len(todo))


if __name__ == '__main__':
    s = requests.Session(); s.headers['User-Agent'] = UA
    if sys.argv[1] == 'index':
        index(s, sys.argv[2:])
    else:
        keep = None
        if len(sys.argv) > 3:
            keep = set(l.split('\t')[0] for l in open(sys.argv[3]))
        fetch(s, sys.argv[2] if len(sys.argv) > 2 else None, keep)
