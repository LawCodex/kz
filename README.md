# Kazakhstan — legislation as Markdown (LawCodex)

Legislation of the Republic of Kazakhstan (Қазақстан Республикасы) as Markdown, in Kazakh
(`kk/`, state language) and Russian (`ru/`, official language). Part of
[LawCodex](https://github.com/LawCodex).

Retrieved: **2026-10-12**.

## Coverage

| Path | Contents | Files |
|---|---|---:|
| `ru/konstitutsiya/` | Constitution of 2026 (Russian) | 1 |
| `ru/kodeksy/` | Codes (Russian) | 27 |
| `ru/konstitutsionnye-zakony/` | Constitutional laws (Russian) | 88 |
| `ru/zakony/<year>/` | Laws (Russian) | 2,818 |
| `kk/konstitutsiya/` | Constitution of 2026 (Kazakh) | 1 |
| `kk/kodekster/` | Codes (Kazakh) | 24 |
| `kk/konstitutsiyalyq-zandar/` | Constitutional laws (Kazakh) | 87 |
| `kk/zandar/<year>/` | Laws (Kazakh) | 2,550 |
| **Total** | | **5,596** |

3,428 archived Russian `K…`/`Z…` pages were examined: 332 were marked repealed and 150 were not
codes/laws (presidential addresses etc.). Kazakh pages were fetched only for the acts kept in Russian;
345 of them have no archived Kazakh page.

Capture dates (`last_amended`) of the Russian texts: 2026: 1,122 · 2025: 1,082 · 2024: 239 ·
2021–2023: 74 · **2019–2020: 417** (rarely crawled acts — these texts may be outdated, and some of these
acts may have been repealed since).

* **Constitution** — the Constitution adopted by referendum on 15 March 2026 (in force since
  1 July 2026, Adilet ID `K2600000000`). The 1995 Constitution is repealed and not included.
* **Codes** and **laws** (including constitutional laws, and the 1995 presidential decrees having the
  force of (constitutional) law that Adilet files under `Z…`): every act with an Adilet `K…`/`Z…`
  identifier for which an archived copy of its Adilet page could be found and whose page did **not**
  carry the status *Утративший силу / Күшін жойған* (repealed). Acts marked *Новый*, *Обновленный*,
  *Исправление ошибки* etc. are kept; the Adilet status label is copied to `adilet_status`.
* Texts are the **consolidated versions** maintained by the Institute of Legislation and Legal
  Information (ИЗПИ / ZQAI), including its footnotes ("Сноска…", "Примечание ИЗПИ") which are rendered
  as block quotes. `last_amended` is the date of the archived capture the text was taken from (the
  text is the consolidated version as published on that day).

## How the texts were obtained — and why from archives

The official database is **Әділет / Adilet** (https://adilet.zan.kz, Ministry of Justice / ИЗПИ).
In September 2026 the site was rebuilt as a JavaScript single-page application: document pages no
longer contain any text, which is loaded from `/api/…` — and `robots.txt` disallows `/api/` for all
robots (it also explicitly disallows `ClaudeBot`, `GPTBot`, `CCBot` etc. for AI-training crawls).
The user agreement (`/legal/polzovatelskoe-soglashenie.docx`) forbids automated collection that
overloads the system and unauthorised copying of its databases. LawCodex therefore did **not**
query the live site or its API at all. The other official sources (`law.gov.kz` — the Reference
Control Bank, `zan.gov.kz`) answer HTTP 403 from outside Kazakhstan.

Instead, the texts were taken from public web-archive captures of the **old, server-rendered Adilet
document pages** (`https://adilet.zan.kz/{rus,kaz}/docs/<ID>`), made before the redesign
(captures up to 2026-09-10):

1. **Common Crawl** (https://commoncrawl.org) — 2024–2026 crawls; the zipnum URL index
   (`cluster.idx`) is scanned for `adilet.zan.kz/{rus,kaz}/docs/` and the pages are read with HTTP
   range requests from the WARC files. Each file records the WARC file and byte range in
   `archived_source` / `archive`.
2. **Internet Archive Wayback Machine** for documents not found in Common Crawl (CDX API +
   `id_` raw playback); `archived_source` is the Wayback URL.

The newest capture of each document is used, so most texts are as of 2025–2026, but a document that
was rarely crawled may be older: always check `last_amended` and the archived source.

## Not covered / gaps

* Documents never captured by either archive, and acts adopted or amended after the redesign
  (September 2026). Status is the one shown at capture time.
* Kazakh (`kk/`) versions exist only for acts whose Kazakh page was archived.
* Presidential addresses to the nation (also filed under `K…`) are skipped.
* Secondary legislation (presidential decrees `U…`, government resolutions `P…`, registered
  ministerial orders `V…`, etc.) is not included.

## Licence

Under art. 8 of the Law of the Republic of Kazakhstan "On Copyright and Related Rights", official
documents (laws and other normative legal acts, court decisions and other texts of a legislative,
administrative and judicial nature) are not objects of copyright. The Markdown conversion is
published without additional restrictions.

## Structure

```
ru/konstitutsiya/K2600000000.md                 Constitution (2026)
ru/kodeksy/<ID>.md                              codes
ru/konstitutsionnye-zakony/<ID>.md              constitutional laws
ru/zakony/<year>/<ID>.md                        laws, by year of adoption
kk/konstitutsiya/  kk/kodekster/  kk/konstitutsiyalyq-zandar/  kk/zandar/<year>/   same, Kazakh
scripts/                                        fetch + convert code
```

`<ID>` is the Adilet document identifier (e.g. `K1400000226` = Criminal Code,
`Z2100000062`). Headings map the act structure: part / section (раздел, бөлім) / chapter (глава,
тарау) / paragraph (параграф) / article (статья, бап).

## Regenerate

```
python3 -m pip install -r scripts/requirements.txt
python3 scripts/kz_cdx.py 2019                 # Wayback CDX -> ../_raw/kz/snapshots.tsv
python3 scripts/kz_cc.py index CC-MAIN-2026-34 CC-MAIN-2026-30 ...   # Common Crawl index
python3 scripts/kz_cc.py fetch rus             # Common Crawl pages
python3 scripts/kz_fetch.py rus                # Wayback for the rest (slow, ~15 req/min)
python3 scripts/kz_convert.py rus              # writes ru/ and ../_raw/kz/rus_inforce.txt
python3 scripts/kz_cc.py fetch kaz ../_raw/kz/rus_inforce.txt
python3 scripts/kz_fetch.py kaz
python3 scripts/kz_convert.py kaz
```
