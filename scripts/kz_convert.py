#!/usr/bin/env python3
"""Convert archived Adilet pages (_raw/kz/html/<lang>/<ID>.html.gz, produced by kz_fetch.py)
into Markdown under the repository.

Only the Constitution, codes and laws (incl. constitutional laws) that the page marks as
in force (status "Новый" / "Обновленный" / ... i.e. anything except "Утративший силу") are written.

Usage: kz_convert.py rus|kaz      (writes ru/ or kk/ and, for rus, _raw/kz/rus_inforce.txt)
"""
import gzip, os, re, sys, html
from bs4 import BeautifulSoup, NavigableString, Tag

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))
RAW = os.path.abspath(os.path.join(REPO, '..', '_raw', 'kz'))
RETRIEVED = '2026-10-12'

LANGDIR = {'rus': 'ru', 'kaz': 'kk'}
DIRS = {
    'ru': {'constitution': 'konstitutsiya', 'code': 'kodeksy', 'constitutional_law': 'konstitutsionnye-zakony', 'law': 'zakony'},
    'kk': {'constitution': 'konstitutsiya', 'code': 'kodekster', 'constitutional_law': 'konstitutsiyalyq-zandar', 'law': 'zandar'},
}
MONTHS_RU = {'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6, 'июля': 7,
             'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12}
MONTHS_KK = {'қаңтар': 1, 'ақпан': 2, 'наурыз': 3, 'сәуір': 4, 'мамыр': 5, 'маусым': 6, 'шілде': 7,
             'тамыз': 8, 'қыркүйек': 9, 'қазан': 10, 'қараша': 11, 'желтоқсан': 12}

KINDS = ['part', 'section', 'subsection', 'chapter', 'paragraph', 'article']
PATTERNS = {
    'part': re.compile(r'^((общая|особенная|специальная)\s+часть|часть\s+[\dIVXLC]+|(жалпы|ерекше|арнаулы)\s+бөлік|[\dIVXLC]+[-‑\s]*бөлік\b)', re.I),
    'section': re.compile(r'^(раздел\s|[\dIVXLC]+(-\d+)?[-‑\s]*бөлім\b|бөлім\s+[\dIVXLC])', re.I),
    'subsection': re.compile(r'^(подраздел\s|[\dIVXLC]+(-\d+)?[-‑\s]*кіші\s*бөлім|[\dIVXLC]+(-\d+)?[-‑\s]*бөлімше)', re.I),
    'chapter': re.compile(r'^(глава\s|[\dIVXLC]+(-\d+)?[-‑\s]*тарау\b|тарау\s+[\dIVXLC])', re.I),
    'paragraph': re.compile(r'^(параграф\s|§\s*\d|[\dIVXLC]+(-\d+)?[-‑\s]*параграф\b)', re.I),
    'article': re.compile(r'^(статья\s+\d|[\d]+(-\d+)*[-‑\s]*бап\b|бап\s+\d)', re.I),
}


def kind_of(text):
    t = text.strip()
    for k in KINDS:
        if PATTERNS[k].match(t):
            return k
    return None


def clean(t):
    t = t.replace('\xa0', ' ')
    t = re.sub(r'[ \t\r\f\v]+', ' ', t)
    t = re.sub(r' *\n *', '\n', t)
    return t.strip()


def md_escape(t):
    # avoid accidental Markdown structures at line start
    t = re.sub(r'^(#+)', r'\\\1', t)
    t = re.sub(r'^(\d+)([.)]) ', r'\1\\\2 ', t)
    t = re.sub(r'^([-+*>]) ', r'\\\1 ', t)
    return t


def inline_text(node):
    """Text of an inline fragment, with <br> as newlines."""
    if isinstance(node, NavigableString):
        return str(node)
    out = []
    for d in node.descendants:
        if isinstance(d, NavigableString):
            if d.parent.name in ('script', 'style'):
                continue
            out.append(str(d))
        elif d.name == 'br':
            out.append('\n')
    return ''.join(out)


def table_md(tbl):
    rows = []
    for tr in tbl.find_all('tr'):
        cells = [clean(inline_text(td)).replace('\n', '<br>').replace('|', '\\|') for td in tr.find_all(['td', 'th'])]
        if any(cells):
            rows.append(cells)
    if not rows:
        return ''
    spans = tbl.find(attrs={'colspan': True}) or tbl.find(attrs={'rowspan': True})
    if spans:
        # keep as minimal HTML
        out = ['<table>']
        for tr in tbl.find_all('tr'):
            out.append('<tr>' + ''.join(
                '<td%s%s>%s</td>' % (
                    f' colspan="{td["colspan"]}"' if td.get('colspan') else '',
                    f' rowspan="{td["rowspan"]}"' if td.get('rowspan') else '',
                    html.escape(clean(inline_text(td))).replace('\n', '<br>'))
                for td in tr.find_all(['td', 'th'])) + '</tr>')
        out.append('</table>')
        return '\n'.join(out)
    n = max(len(r) for r in rows)
    rows = [r + [''] * (n - len(r)) for r in rows]
    out = ['| ' + ' | '.join(rows[0]) + ' |', '|' + ' --- |' * n]
    for r in rows[1:]:
        out.append('| ' + ' | '.join(r) + ' |')
    return '\n'.join(out)


def is_note(node):
    if not isinstance(node, Tag):
        return False
    cls = node.get('class') or []
    if 'note' in cls:
        return True
    if node.name == 'font' and (node.get('color') or '').upper().lstrip('#') == 'FF0000':
        return True
    return False


def convert_article(article):
    """Return list of blocks: ('h', kind, text) | ('p', text) | ('note', text) | ('raw', md)."""
    blocks = []

    def handle_heading_lines(lines):
        cur = None
        for ln in lines:
            ln = clean(ln)
            if not ln:
                continue
            k = kind_of(ln)
            if k:
                if cur:
                    blocks.append(('h',) + tuple(cur))
                cur = [k, ln]
            elif cur:
                cur[1] += ' ' + ln
            else:
                cur = [None, ln]
        if cur:
            blocks.append(('h',) + tuple(cur))

    def stream(container, in_note=False):
        buf = []
        state = {'note': in_note, 'plain': False}

        def flush():
            if not buf:
                return
            txt = clean(''.join(inline_text(n) for n in buf))
            bold = clean(''.join(inline_text(n) for n in buf if isinstance(n, Tag) and n.name in ('b', 'strong')))
            note = state['note'] and not state['plain']
            buf.clear(); state['note'] = in_note; state['plain'] = False
            if not txt:
                return
            k = kind_of(txt)
            if k and bold == txt:
                handle_heading_lines(txt.split('\n'))
            else:
                for ln in txt.split('\n'):
                    ln = ln.strip()
                    if ln:
                        blocks.append(('note' if note else 'p', ln))

        for node in list(container.children):
            if isinstance(node, NavigableString):
                if node.strip():
                    buf.append(node)
                    if not in_note:
                        state['plain'] = True
                continue
            name = node.name
            if name in ('script', 'style'):
                continue
            if name == 'br':
                flush(); continue
            if name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                flush()
                handle_heading_lines(inline_text(node).split('\n'))
                continue
            if name == 'table':
                flush()
                md = table_md(node)
                if md:
                    blocks.append(('raw', md))
                continue
            if name in ('p', 'div', 'center', 'blockquote', 'ul', 'ol', 'li', 'pre', 'article'):
                flush()
                stream(node, in_note or 'note' in (node.get('class') or []))
                continue
            # inline element (span, a, font, b, i, ...)
            if is_note(node):
                state['note'] = True
            elif name != 'a' and clean(inline_text(node)):
                if not node.find(is_note):
                    state['plain'] = True
            buf.append(node)
        flush()

    stream(article)
    return blocks


def render(blocks):
    present = [k for k in KINDS if any(b[0] == 'h' and b[1] == k for b in blocks)]
    level = {k: min(2 + i, 6) for i, k in enumerate(present)}
    out = []
    for b in blocks:
        if b[0] == 'h':
            k, t = b[1], b[2]
            t = re.sub(r'\s+', ' ', t)
            if k is None:
                out.append(f'**{t}**')
            elif k == 'article' and level[k] == 6 and len(present) > 5:
                out.append(f'###### {t}')
            else:
                out.append('#' * level[k] + ' ' + t)
        elif b[0] == 'p':
            out.append(md_escape(b[1]).replace('\n', '  \n'))
        elif b[0] == 'note':
            out.append('> ' + b[1].replace('\n', '\n> '))
        else:
            out.append(b[1])
    return '\n\n'.join(out) + '\n'


def parse_date(s, lang):
    s = s.replace('i', 'і').replace('I', 'І')   # Adilet mixes Latin i into Kazakh text
    m = re.search(r'(\d{1,2})\s+([А-Яа-яӘәҒғҚқҢңӨөҰұҮүҺһІі]+)\s+(\d{4})', s)
    if m:
        d, mon, y = m.groups()
        mon = mon.lower()
        months = MONTHS_RU if lang == 'rus' else MONTHS_KK
        for k, v in months.items():
            if mon.startswith(k[:5]) or mon == k:
                return f'{int(y):04d}-{v:02d}-{int(d):02d}'
    m = re.search(r'(\d{4})\s+жылғы\s+(\d{1,2})\s+([А-Яа-яӘәҒғҚқҢңӨөҰұҮүҺһІі]+)', s)
    if m:
        y, d, mon = m.groups()
        for k, v in MONTHS_KK.items():
            if mon.lower().startswith(k[:4]):
                return f'{int(y):04d}-{v:02d}-{int(d):02d}'
    return None


def classify(docid, desc, title, lang):
    d = (desc or '').lower()
    t = (title or '').lower()
    if docid.startswith('K') and ('конституци' in t) and ('конституционн' not in d and 'конституциялық заң' not in d):
        if d.startswith('конституция') or 'референдум' in d or t.startswith('конституци'):
            return 'constitution'
    if re.match(r'^(кодекс|.*кодексі\b)', d) or (lang == 'kaz' and 'кодексі' in d[:60]):
        return 'code'
    if 'конституционный закон' in d or 'конституциялық заң' in d:
        return 'constitutional_law'
    if d.startswith('закон') or re.match(r'^қазақстан республикасының\s.*заңы', d) or 'заңы' in d[:80] \
            or 'указ президента республики казахстан, имеющий силу закона' in d \
            or 'заң күші бар' in d:
        return 'law'
    if 'кодекс' in d[:40]:
        return 'code'
    return None


def yaml_str(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def main():
    lang = sys.argv[1] if len(sys.argv) > 1 else 'rus'
    ld = LANGDIR[lang]
    src = os.path.join(RAW, 'html', lang)
    stats = {}
    inforce = []
    skipped = {'repealed': 0, 'other_type': 0, 'no_text': 0}
    for fn in sorted(os.listdir(src)):
        if not fn.endswith('.html.gz'):
            continue
        docid = fn[:-8]
        raw = gzip.open(os.path.join(src, fn)).read()
        first, _, body = raw.partition(b'\n')
        ts = first.decode().strip()
        s = body.decode('utf-8', 'replace')
        soup = BeautifulSoup(s, 'lxml')
        h1 = soup.select_one('.slogan h1') or soup.find('h1')
        title = clean(h1.get_text(' ')) if h1 else docid
        st = soup.select_one('.slogan .status')
        stcls = [c for c in (st.get('class') or []) if c.startswith('status_')] if st else []
        stcls = stcls[0][7:] if stcls else ''
        sttxt = clean(st.get_text()) if st else ''
        desc_p = soup.select_one('.slogan p')
        desc = clean(desc_p.get_text(' ')) if desc_p else ''
        typ = classify(docid, desc, title, lang)
        if typ is None:
            skipped['other_type'] += 1
            continue
        if stcls == 'yts':
            skipped['repealed'] += 1
            continue
        art = soup.find('article')
        if not art:
            skipped['no_text'] += 1
            continue
        blocks = convert_article(art)
        if not blocks:
            skipped['no_text'] += 1
            continue
        date = parse_date(desc, lang)
        num = re.search(r'№\s*([^\s.,]+(?:\s*[-‑]?\s*[IVXLC]+)?(?:\s+(?:ЗРК|ҚРЗ))?)', desc)
        number = clean(num.group(1)) if num else ''
        year = date[:4] if date else 'unknown'
        sub = DIRS[ld][typ]
        rel = os.path.join(ld, sub, year, docid + '.md') if typ == 'law' else os.path.join(ld, sub, docid + '.md')
        url = f'https://adilet.zan.kz/{lang}/docs/{docid}'
        if ts.startswith('cc:'):
            _, cts, cfile, coff, clen = ts.split(':')
            arch = f'https://data.commoncrawl.org/{cfile}'
            archnote = f'Common Crawl WARC record, bytes {coff}+{clen}'
            snap = f'{cts[:4]}-{cts[4:6]}-{cts[6:8]}'
        else:
            arch = f'https://web.archive.org/web/{ts}/{url}'
            archnote = 'Internet Archive'
            snap = f'{ts[:4]}-{ts[4:6]}-{ts[6:8]}'
        fm = ['---', f'title: {yaml_str(title)}', f'identifier: "{docid}"']
        if number:
            fm.append(f'number: {yaml_str(number)}')
        fm += [f'type: {"act" if typ == "law" else typ}', 'jurisdiction: kz', f'language: {"ru" if lang == "rus" else "kk"}']
        if date:
            fm.append(f'date: {date}')
        fm += [f'last_amended: {snap}  # consolidated text as captured on this date',
               'status: in_force', f'adilet_status: {yaml_str(sttxt)}',
               f'description: {yaml_str(desc)}',
               f'source: "{url}"', f'archived_source: "{arch}"', f'archive: "{archnote}"', f'retrieved: {RETRIEVED}', '---', '']
        md = '\n'.join(fm) + f'\n# {title}\n\n' + render(blocks)
        out = os.path.join(REPO, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, 'w', encoding='utf-8', newline='\n') as f:
            f.write(md)
        stats[typ] = stats.get(typ, 0) + 1
        inforce.append((docid, typ, title))
    if lang == 'rus':
        with open(os.path.join(RAW, 'rus_inforce.txt'), 'w') as f:
            for d, t, ti in inforce:
                f.write(f'{d}\t{t}\t{ti}\n')
    print(lang, stats, skipped)


if __name__ == '__main__':
    main()
