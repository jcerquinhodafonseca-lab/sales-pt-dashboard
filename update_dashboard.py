#!/usr/bin/env python3
"""
Reads the latest CSV in the repo root and regenerates index.html.
Runs inside GitHub Actions on every push that changes a .csv file.
"""
import csv, json, gzip, base64, re, glob, os
from collections import defaultdict
from datetime import date, timedelta

# ── Find CSV: prefer sales_data.csv, else pick alphabetically last ────────────
if os.path.exists("sales_data.csv"):
    CSV_FILE = "sales_data.csv"
else:
    csv_files = sorted(glob.glob("*.csv"))
    if not csv_files:
        raise SystemExit("No CSV file found in repo root.")
    CSV_FILE = csv_files[-1]
print(f"Using CSV: {CSV_FILE}")

EI_ORDER = ['01. 2025-2026','02. 2021-2024','03. 2017-2020','04. 2013-2016','05. < 2013']
EK_ORDER = ['1. 0-50k','2. 50-100k','3. 100-150k','4. 150-200k','5. 200-250k','6. 250k+']

rows = []
with open(CSV_FILE, 'r', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        rows.append(row)
print(f"Loaded {len(rows):,} rows")

# ── Derive reference date from latest row ────────────────────────────────────
max_date = max(date.fromisoformat(r['data_venda']) for r in rows)
TODAY = max_date
WTD_START = TODAY - timedelta(days=TODAY.weekday())
print(f"Data through: {TODAY}  |  WTD start: {WTD_START}")

# ── Helpers ───────────────────────────────────────────────────────────────────
def filter_rows(rws, pk):
    if pk == 'all':   return rws
    if pk == 'ytd':   return [r for r in rws if r['data_venda'].startswith(str(TODAY.year))]
    if pk == 'mtd':   return [r for r in rws if r['data_venda'].startswith(TODAY.strftime('%Y-%m'))]
    if pk == 'wtd':   return [r for r in rws if date.fromisoformat(r['data_venda']) >= WTD_START]
    return [r for r in rws if r['data_venda'].startswith(pk)]

def compute_stats(rws, ms):
    from collections import Counter
    brands, models, ei_cnt, ek_cnt, cb_cnt, pr_cnt = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    ey = defaultdict(lambda: defaultdict(int))
    for r in rws:
        brands[r['marca']] += 1; models[r['modelo']] += 1
        ei_cnt[r['escalao_idade']] += 1; ek_cnt[r['escalao_kms']] += 1
        ey[r['escalao_idade']][str(r['ano_exato'])] += 1
        cb_cnt[r['combustivel']] += 1; pr_cnt[r['price_range']] += 1
    return {
        't': len(rws),
        'b': sorted([[b,c] for b,c in brands.items()], key=lambda x:-x[1]),
        'm': sorted([[m,c] for m,c in models.items()], key=lambda x:-x[1])[:20],
        'ei': {k: ei_cnt[k] for k in EI_ORDER if k in ei_cnt},
        'ek': {k: ek_cnt[k] for k in EK_ORDER if k in ek_cnt},
        'ey': {k: dict(sorted(ey[k].items())) for k in EI_ORDER if k in ey},
        'cb': dict(cb_cnt), 'pr': dict(pr_cnt), 'ms': ms,
    }

all_ym = sorted(set(r['data_venda'][:7] for r in rows))
years   = sorted(set(m[:4] for m in all_ym))

def get_ms(pk):
    if pk == 'all':            return all_ym
    if pk in ('ytd','mtd','wtd'): return [m for m in all_ym if m.startswith(str(TODAY.year))]
    if len(pk) == 4:           return [m for m in all_ym if m.startswith(pk)]
    return [pk] if pk in all_ym else []

def cf_entry(rws, with_bek=True):
    from collections import Counter
    brands, models, ei_cnt, ek_cnt, cb_cnt, pr_cnt = Counter(), Counter(), Counter(), Counter(), Counter(), Counter()
    bek_ei = defaultdict(lambda: defaultdict(int))
    for r in rws:
        brands[r['marca']] += 1; models[r['modelo']] += 1
        ei_cnt[r['escalao_idade']] += 1; ek_cnt[r['escalao_kms']] += 1
        cb_cnt[r['combustivel']] += 1; pr_cnt[r['price_range']] += 1
        bek_ei[r['escalao_kms']][r['escalao_idade']] += 1
    e = {'t': len(rws),
         'b': sorted([[b,c] for b,c in brands.items()],key=lambda x:-x[1])[:10],
         'm': sorted([[m,c] for m,c in models.items()],key=lambda x:-x[1])[:5],
         'ei': [ei_cnt.get(k,0) for k in EI_ORDER],
         'ek': [ek_cnt.get(k,0) for k in EK_ORDER],
         'cb': dict(cb_cnt), 'pr': dict(pr_cnt)}
    if with_bek:
        e['bek_ei'] = {ek:[bek_ei[ek].get(ei,0) for ei in EI_ORDER] for ek in EK_ORDER if ek in bek_ei}
    return e

# ── Build all periods ─────────────────────────────────────────────────────────
period_keys = ['all','ytd','mtd','wtd'] + years + all_ym
p = {pk: compute_stats(filter_rows(rows,pk), get_ms(pk)) for pk in period_keys}

mo = dict(sorted({ym:0 for ym in all_ym}.items()))
for r in rows: mo[r['data_venda'][:7]] += 1

ytd_r = filter_rows(rows,'ytd'); mtd_r = filter_rows(rows,'mtd'); wtd_r = filter_rows(rows,'wtd')
kpi = {'ytd': len(ytd_r), 'mtd': len(mtd_r), 'wtd': len(wtd_r), 'total': len(rows)}
print("KPI:", kpi)

cat_bm = defaultdict(lambda: defaultdict(int))
for r in rows: cat_bm[r['marca']][r['modelo']] += 1
cat = {b: sorted([[m,c] for m,c in ms.items()],key=lambda x:-x[1]) for b,ms in cat_bm.items()}

CF_PERIODS = ['all','ytd','mtd','wtd'] + years
cf = {}
for cp in CF_PERIODS:
    pr_ = filter_rows(rows,cp)
    bg,eg,ekg,cbg,prg = defaultdict(list),defaultdict(list),defaultdict(list),defaultdict(list),defaultdict(list)
    for r in pr_:
        bg[r['marca']].append(r); eg[r['escalao_idade']].append(r)
        ekg[r['escalao_kms']].append(r); cbg[r['combustivel']].append(r); prg[r['price_range']].append(r)
    cf[cp] = {
        'b':  {b: cf_entry(g,True)  for b,g in bg.items()},
        'ei': {k: cf_entry(g,False) for k,g in eg.items()},
        'ek': {k: cf_entry(g,False) for k,g in ekg.items()},
        'cb': {k: cf_entry(g,False) for k,g in cbg.items()},
        'pr': {k: cf_entry(g,False) for k,g in prg.items()},
    }

bmo_d = defaultdict(lambda: defaultdict(int))
cmo_d = defaultdict(lambda: defaultdict(int))
prmo_d = defaultdict(lambda: defaultdict(int))
for r in rows:
    ym = r['data_venda'][:7]
    bmo_d[r['marca']][ym] += 1; cmo_d[r['combustivel']][ym] += 1; prmo_d[r['price_range']][ym] += 1

obj_new = {
    'p': p, 'mo': mo, 'kpi': kpi, 'cat': cat, 'cf': cf,
    'bmo': {b: dict(sorted(m.items())) for b,m in bmo_d.items()},
    'cmo': {c: dict(sorted(m.items())) for c,m in cmo_d.items()},
    'prmo': {p2: dict(sorted(m.items())) for p2,m in prmo_d.items()},
}

json_str   = json.dumps(obj_new, ensure_ascii=False, separators=(',',':'))
compressed = gzip.compress(json_str.encode('utf-8'), compresslevel=9)
b64_new    = base64.b64encode(compressed).decode('ascii')
print(f"New B64 length: {len(b64_new):,}")

# ── Patch the template HTML ───────────────────────────────────────────────────
with open('index.html','r',encoding='utf-8') as f:
    html = f.read()

old_b64 = re.search(r'const B64="([^"]+)"', html).group(1)
html = html.replace(f'const B64="{old_b64}"', f'const B64="{b64_new}"')

# Update KPI date labels
month_pt = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']
ytd_label = month_pt[TODAY.month - 1]  # e.g. "Mai"
mtd_label = month_pt[TODAY.month - 1]
wtd_end   = TODAY.day
wtd_start = WTD_START.day

# Replace dynamic labels (handles any previous month name)
html = re.sub(r'Jan&ndash;\w+', f'Jan&ndash;{ytd_label}', html)
html = re.sub(r'MTD \w+', f'MTD {mtd_label}', html)
html = re.sub(r'\d+&ndash;\d+ \w+(?=</div>)', f'1&ndash;{TODAY.day} {mtd_label}', html, count=1)
# WTD range
for pat in [r'\d+&ndash;\d+ \w+(?=</div>)']:
    html = re.sub(pat, f'{wtd_start}&ndash;{wtd_end} {mtd_label}', html, count=1)

with open('index.html','w',encoding='utf-8') as f:
    f.write(html)

print(f"index.html updated. Data through {TODAY}.")
