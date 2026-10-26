"""Seções sinalizadas × controles da mesma zona: Lula e Flávio no 2º turno e variação desde o 1º turno.

Entradas: sample.csv e t1.csv (por padrão os de dados_congelados/, a amostra da comparação publicada; com --amostra-nova,
os gerados por amostra.py e primeiro_turno.py em caminhos.saida("comparacao_bu")), BUs em
caminhos.DADOS/bu_2t/{UF}/{mun}-{zona}-{secao}-bu.dat (baixar_bu.py) e secoes_analisadas.csv em caminhos.saida("logs_urna").
Saídas em caminhos.saida("comparacao_bu"): comparacao_sinalizadas.csv/.json, resumo em texto (-resumo.txt),
cartão HTML e PNG 1200×630. Nenhuma requisição de rede. Uso: python comparar.py [--no-png] [--amostra-nova]
"""
import csv
import html
import json
import random
import statistics
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "comum"))
import bu_parser as bp  # noqa: E402
import caminhos  # noqa: E402

UL = caminhos.saida("logs_urna")  # secoes_analisadas.csv (logs_urna/relatorio_17h.py)
BU_DIR = caminhos.DADOS / "bu_2t"
OUT = caminhos.saida("comparacao_bu")
AMOSTRA = OUT if "--amostra-nova" in sys.argv else HERE / "dados_congelados"  # sample.csv e t1.csv
N_BOOT, SEED = 1000, 2026
LULA, FLAVIO = "#c0392b", "#2c63b8"


def ikey(uf, mun, zona, secao):
    return (uf, int(mun), int(zona), int(secao))


def pct(a, b):
    return 100 * a / b if b else None


def mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.fmean(xs) if xs else None


def bootstrap(diffs, rng):
    if len(diffs) < 2:
        return None, None
    means = sorted(statistics.fmean(rng.choices(diffs, k=len(diffs))) for _ in range(N_BOOT))
    return means[int(0.025 * N_BOOT)], means[int(0.975 * N_BOOT) - 1]


def bootstrap_cluster(groups, rng):
    """Reamostra zonas (todas as sinalizadas da zona juntas), pois elas dividem os mesmos controles."""
    groups = [g for g in groups if g]
    if len(groups) < 2:
        return None, None
    means = []
    for _ in range(N_BOOT):
        pick = [x for g in rng.choices(groups, k=len(groups)) for x in g]
        means.append(statistics.fmean(pick))
    means.sort()
    return means[int(0.025 * N_BOOT)], means[int(0.975 * N_BOOT) - 1]


def load():
    analis = {ikey(r["uf"], r["mun"], r["zona"], r["secao"]): r
              for r in csv.DictReader(open(UL / "secoes_analisadas.csv", encoding="utf-8-sig"), delimiter=";")}
    t1 = {ikey(r["uf"], r["mun"], r["zona"], r["secao"]): r for r in csv.DictReader(open(AMOSTRA / "t1.csv", encoding="utf-8"), delimiter=";")}
    status = {}
    if (BU_DIR / "_status.csv").exists():
        for r in csv.DictReader(open(BU_DIR / "_status.csv", encoding="utf-8"), delimiter=";"):
            status[ikey(r["uf"], r["mun"], r["zona"], r["secao"])] = r["status"]
    sample = list(csv.DictReader(open(AMOSTRA / "sample.csv", encoding="utf-8"), delimiter=";"))
    return analis, t1, status, sample


def section_metrics(s, analis, t1, status, problems):
    k = ikey(s["uf"], s["mun"], s["zona"], s["secao"])
    a, f1 = analis.get(k, {}), t1.get(k)
    row = {"grupo": s["grupo"], "grupo_zona": s["grupo_zona"].replace("|", "-"), "origem_controle": s["origem"],
           "uf": s["uf"], "mun": s["mun"], "mun_name": a.get("mun_name", ""), "zona": s["zona"], "secao": s["secao"],
           "votos_log": a.get("votos"), "votos_apos_17h": a.get("votos_apos_17h"), "sem_bio_apos": a.get("sem_bio_apos")}
    path = BU_DIR / s["uf"] / f"{s['mun']}-{s['zona']}-{s['secao']}-bu.dat"
    p = None
    if path.exists():
        try:
            bu = bp.parse_bu(path.read_bytes())
            if (bu.municipio, bu.zona, bu.secao) != k[1:]:
                raise ValueError(f"BU identifica {bu.municipio}/{bu.zona}/{bu.secao}")
            p = bu.presidente()
            row["bu_status"] = "ok"
        except Exception as e:  # noqa: BLE001 — qualquer falha de leitura vira "erro" e é relatada
            row["bu_status"] = "erro"
            problems.append(f"{'-'.join(map(str, k))}: BU ilegível ({e})")
    else:
        row["bu_status"] = f"http_{status[k]}" if k in status else "nao_baixado"
    if p:
        v2 = p.votos.get(13, 0) + p.votos.get(22, 0)
        row.update(aptos_2t=p.aptos, comparecimento_2t=p.comparecimento, lula_2t=p.votos.get(13, 0), flavio_2t=p.votos.get(22, 0),
                   brancos_2t=p.brancos, nulos_2t=p.nulos, validos_2t=v2, pct_lula_2t=pct(p.votos.get(13, 0), v2), pct_flavio_2t=pct(p.votos.get(22, 0), v2))
        if a.get("votos") and int(a["votos"]) != p.comparecimento:
            problems.append(f"{'-'.join(map(str, k))}: comparecimento no BU ({p.comparecimento}) ≠ votos no log ({a['votos']})")
        outros = set(p.votos) - {13, 22}
        if outros:
            problems.append(f"{'-'.join(map(str, k))}: BU com votáveis inesperados {sorted(outros)}")
    if f1 and int(f1["n_votaveis"] or 0) > 0:
        l1, fl1, v1 = int(f1["lula1"]), int(f1["flavio1"]), int(f1["validos1_det"] or f1["validos1_vot"])
        row.update(aptos_1t=int(f1["aptos1"]) if f1["aptos1"] else None, comparecimento_1t=int(f1["comp1"]) if f1["comp1"] else None,
                   lula_1t=l1, flavio_1t=fl1, validos_1t=v1, pct_lula_1t=pct(l1, v1), pct_flavio_1t=pct(fl1, v1),
                   pct_lula_1t_2c=pct(l1, l1 + fl1), pct_flavio_1t_2c=pct(fl1, l1 + fl1))
    if row.get("pct_lula_2t") is not None and row.get("pct_lula_1t") is not None:
        row["var_lula_pp"] = row["pct_lula_2t"] - row["pct_lula_1t"]
        row["var_flavio_pp"] = row["pct_flavio_2t"] - row["pct_flavio_1t"]
        row["var_lula_2c_pp"] = row["pct_lula_2t"] - row["pct_lula_1t_2c"]
    return row


METRICS = [("pct_lula_2t", "Lula · % dos válidos no 2º turno"), ("pct_flavio_2t", "Flávio · % dos válidos no 2º turno"),
           ("pct_lula_1t", "Lula · % dos válidos no 1º turno"), ("pct_flavio_1t", "Flávio · % dos válidos no 1º turno"),
           ("var_lula_pp", "Lula · variação 1º → 2º turno (p.p.)"), ("var_flavio_pp", "Flávio · variação 1º → 2º turno (p.p.)"),
           ("var_lula_2c_pp", "Lula · variação 1º → 2º, 1º turno só entre 13 e 22 (p.p.)")]


def compare(rows):
    rng = random.Random(SEED)
    flagged = [r for r in rows if r["grupo"] == "sinalizada"]
    controls = [r for r in rows if r["grupo"] == "controle"]
    by_zone = {}
    for c in controls:
        by_zone.setdefault(c["grupo_zona"], []).append(c)
    uniq_ctrl = {(c["uf"], c["mun"], c["zona"], c["secao"]): c for c in controls}
    out = {"medias_simples": {}, "diferenca_pareada": {}}
    for m, label in METRICS:
        fs = [r[m] for r in flagged if r.get(m) is not None]
        cs = [c[m] for c in uniq_ctrl.values() if c.get(m) is not None]
        diffs, zones, per_zone = [], set(), {}
        for r in flagged:
            if r.get(m) is None:
                continue
            cm = mean([c.get(m) for c in by_zone.get(r["grupo_zona"], [])])
            if cm is None:
                continue
            diffs.append(r[m] - cm)
            zones.add(r["grupo_zona"])
            per_zone.setdefault(r["grupo_zona"], []).append(r[m] - cm)
        lo, hi = bootstrap(diffs, rng)
        zlo, zhi = bootstrap_cluster(list(per_zone.values()), rng)
        out["medias_simples"][m] = {"rotulo": label, "sinalizadas": mean(fs), "n_sinalizadas": len(fs), "controles": mean(cs), "n_controles": len(cs),
                                    "diferenca_das_medias": (mean(fs) - mean(cs)) if fs and cs else None}
        out["diferenca_pareada"][m] = {"rotulo": label, "media": mean(diffs), "mediana": statistics.median(diffs) if diffs else None,
                                       "ic95_bootstrap": [lo, hi], "ic95_bootstrap_por_zona": [zlo, zhi], "n_pares": len(diffs), "n_zonas": len(zones),
                                       "intervalo_inclui_zero": None if lo is None else lo <= 0 <= hi}
    return out


def fnum(x, d=1, sign=False):
    if x is None:
        return "—"
    if round(x, d) == 0:
        return f"{0:.{d}f}".replace(".", ",")  # sem sinal, evita "−0,0"
    return (f"{x:+.{d}f}" if sign else f"{x:.{d}f}").replace(".", ",").replace("-", "−")


def card_svg(summary, w=1110):
    rows = [("pct_lula_2t", "Lula · % válidos no 2º turno", LULA), ("pct_flavio_2t", "Flávio · % válidos no 2º turno", FLAVIO),
            ("var_lula_pp", "Lula · variação 1º → 2º turno", LULA), ("var_flavio_pp", "Flávio · variação 1º → 2º turno", FLAVIO)]
    top, row_h = 58, 64
    h = top + row_h * len(rows) + 30
    pd = summary["diferenca_pareada"]
    ext = max(2.0, *(abs(v) for m, _, _ in rows for v in (pd[m]["ic95_bootstrap"] or []) if v is not None),
              *(abs(pd[m]["media"]) for m, _, _ in rows if pd[m]["media"] is not None))
    ext = (int(ext) // 2 + 1) * 2  # eixo simétrico em passos de 2 p.p.
    x0, x1 = 640, w - 96
    sx = lambda v: x0 + (v + ext) / (2 * ext) * (x1 - x0)
    o = [f"<svg viewBox='0 0 {w} {h}' width='{w}' height='{h}' font-family='Segoe UI,system-ui,sans-serif' role='img' aria-label='Diferença pareada sinalizadas menos controles'>",
         f"<text x='405' y='24' text-anchor='middle' font-size='15' font-weight='700' fill='#1d1f23'>Sinalizadas</text>",
         f"<text x='530' y='24' text-anchor='middle' font-size='15' font-weight='700' fill='#1d1f23'>Controles</text>",
         f"<text x='467' y='42' text-anchor='middle' font-size='12' fill='#7a7d83'>médias simples</text>",
         f"<text x='{(x0 + x1) / 2:.0f}' y='22' text-anchor='middle' font-size='16' font-weight='700' fill='#1d1f23'>Diferença pareada por zona (p.p.) · intervalo de 95%</text>"]
    step = 1 if ext <= 4 else 2 if ext <= 10 else 5
    for t in range(-ext, ext + 1, step):
        o.append(f"<line x1='{sx(t):.1f}' x2='{sx(t):.1f}' y1='{top - 8}' y2='{h - 26}' stroke='{'#9aa0a8' if t == 0 else '#e4dfd4'}' stroke-width='{1.6 if t == 0 else 1}'/>"
                 f"<text x='{sx(t):.1f}' y='{top - 14 + 0}' text-anchor='middle' font-size='12' fill='#7a7d83'>{fnum(t, 0, sign=t != 0)}</text>")
    o.append(f"<text x='{sx(-ext) + 4:.1f}' y='{h - 8}' font-size='12' fill='#7a7d83'>← menor nas sinalizadas</text>"
             f"<text x='{sx(ext) - 4:.1f}' y='{h - 8}' text-anchor='end' font-size='12' fill='#7a7d83'>maior nas sinalizadas →</text>")
    for i, (m, label, color) in enumerate(rows):
        y = top + i * row_h + 22
        if i % 2 == 0:
            o.append(f"<rect x='0' y='{y - 26}' width='{w}' height='{row_h - 4}' rx='6' fill='#f7f4ee'/>")
        ms, d = summary["medias_simples"][m], pd[m]
        unit = "%" if m.startswith("pct") else " p.p."
        sgn = not m.startswith("pct")
        o.append(f"<text x='12' y='{y + 6}' font-size='16' font-weight='600' fill='#1d1f23'>{html.escape(label)}</text>")
        o.append(f"<text x='405' y='{y + 6}' text-anchor='middle' font-size='18' font-weight='700' fill='{color}'>{fnum(ms['sinalizadas'], sign=sgn)}{unit}</text>")
        o.append(f"<text x='530' y='{y + 6}' text-anchor='middle' font-size='18' font-weight='600' fill='#5b6470'>{fnum(ms['controles'], sign=sgn)}{unit}</text>")
        lo, hi = d["ic95_bootstrap"]
        if lo is not None:
            o.append(f"<line x1='{sx(lo):.1f}' x2='{sx(hi):.1f}' y1='{y}' y2='{y}' stroke='{color}' stroke-opacity='.45' stroke-width='6' stroke-linecap='round'/>")
        if d["media"] is not None:
            o.append(f"<circle cx='{sx(d['media']):.1f}' cy='{y}' r='8' fill='{color}'/>")
            o.append(f"<text x='{x1 + 12:.1f}' y='{y + 6}' font-size='16' font-weight='700' fill='{color}'>{fnum(d['media'], sign=True)}</text>")
        if lo is not None:
            o.append(f"<text x='{sx(d['media']):.1f}' y='{y + 24}' text-anchor='middle' font-size='12' fill='#5b5f66'>{fnum(lo, sign=True)} a {fnum(hi, sign=True)}</text>")
    o.append("</svg>")
    return "".join(o), h


STYLE = """body{margin:0;font:15px/1.35 'Segoe UI',system-ui,sans-serif;background:#f6f4ef;color:#1d1f23}
.w{padding:22px 30px} h1{font-size:26px;margin:0} .sub{color:#5b5f66;margin:4px 0 14px}
.card{background:#fff;border-radius:12px;padding:12px 14px 6px;box-shadow:0 1px 2px #0001;margin-bottom:14px}
.kpis{display:grid;grid-template-columns:1fr 1fr 1.25fr;gap:12px} .kpi{background:#fff;border-radius:12px;padding:12px 16px;box-shadow:0 1px 2px #0001}
.kpi span{font-size:14px;color:#5b5f66} .kpi b{display:block;font-size:24px;line-height:1.2} .kpi small{font-size:13px;color:#3c4046}
body{width:1200px;height:630px;overflow:hidden}"""


def build_card(summary, n, now):
    svg, _ = card_svg(summary)
    pd = summary["diferenca_pareada"]
    dl, dv = pd["pct_lula_2t"], pd["var_lula_pp"]
    kpis = ("<div class=kpis>"
            f"<div class=kpi><span>Seções comparadas</span><b>{n['sinalizadas_com_resultado']} × {n['controles_com_resultado']}</b>"
            f"<small>sinalizadas × controles; {n['sinalizadas_pareadas']} sinalizadas com controle, em {n['zonas_pareadas']} zonas</small></div>"
            f"<div class=kpi><span>Lula no 2º turno · diferença pareada</span><b style='color:{LULA}'>{fnum(dl['media'], sign=True)} p.p.</b>"
            f"<small>intervalo de 95%: {fnum(dl['ic95_bootstrap'][0], sign=True)} a {fnum(dl['ic95_bootstrap'][1], sign=True)} p.p.</small></div>"
            f"<div class=kpi><span>Como ler</span><small style='display:block;margin-top:4px;font-size:13px;line-height:1.35'>Sinalizada = seção cujo log da urna tem ≥1 voto sem biometria depois das 17h. "
            f"Cada uma é comparada com até 10 seções não sinalizadas da mesma zona (ou do município). Comparação descritiva, com poucas seções; não indica causa.</small></div>"
            "</div>")
    return f"""<!doctype html><html lang=pt-BR><meta charset=utf-8><style>{STYLE}</style><div class=w>
<h1>Seções sinalizadas × seções da mesma zona · 2º turno para presidente</h1>
<div class=sub>TSE · boletins de urna do 2º turno e resultado oficial do 1º turno · {now:%d/%m/%Y %H:%M}</div>
<div class=card>{svg}</div>{kpis}</div></html>"""


def resumo_texto(summary, n):
    ms, pd = summary["medias_simples"], summary["diferenca_pareada"]
    l2, v = pd["pct_lula_2t"], pd["var_lula_pp"]

    def ic(d):
        return f"{fnum(d['ic95_bootstrap'][0], sign=True)} a {fnum(d['ic95_bootstrap'][1], sign=True)}"

    zeros = [l2["intervalo_inclui_zero"], v["intervalo_inclui_zero"]]
    leitura = ("Os dois intervalos incluem zero. " if all(zeros) else "Nenhum dos dois intervalos inclui zero. " if not any(zeros)
               else f"O intervalo {'do 2º turno' if zeros[0] else 'da variação'} inclui zero; o {'da variação' if zeros[0] else 'do 2º turno'}, não. ")

    return (f"Comparação do 2º turno entre {n['sinalizadas_com_resultado']} seções cujo log da urna registra ao menos 1 voto sem biometria depois das 17h "
            f"e {n['controles_com_resultado']} seções da mesma zona (ou município) sem esse registro. "
            f"Lula teve em média {fnum(ms['pct_lula_2t']['sinalizadas'])}% dos válidos nas primeiras e {fnum(ms['pct_lula_2t']['controles'])}% nas demais. "
            f"Comparando dentro de cada zona ({l2['n_pares']} seções com controle), a diferença é de {fnum(l2['media'], sign=True)} p.p. (intervalo de 95%: {ic(l2)}). "
            f"Na variação desde o 1º turno: {fnum(v['media'], sign=True)} p.p. ({ic(v)}). {leitura}"
            f"São poucas seções e é uma comparação descritiva; não indica causa.")


def abrir_navegador(p):
    """Microsoft Edge instalado no sistema, se houver; senão o Chromium do Playwright (python -m playwright install chromium)."""
    try:
        return p.chromium.launch(channel="msedge")
    except Exception:  # noqa: BLE001 - Edge ausente
        return p.chromium.launch()


def main():
    analis, t1, status, sample = load()
    problems = []
    rows = [section_metrics(s, analis, t1, status, problems) for s in sample]
    summary = compare(rows)
    flagged = [r for r in rows if r["grupo"] == "sinalizada"]
    uniq_ctrl = {(r["uf"], r["mun"], r["zona"], r["secao"]): r for r in rows if r["grupo"] == "controle"}
    ok = lambda r: r.get("pct_lula_2t") is not None and r.get("pct_lula_1t") is not None
    no_bu = sorted({f"{r['uf']}-{r['mun']}-{r['zona']}-{r['secao']} ({r['grupo']}, {r['bu_status']})" for r in rows if r["bu_status"] != "ok"})
    no_t1 = sorted({f"{r['uf']}-{r['mun']}-{r['zona']}-{r['secao']} ({r['grupo']})" for r in rows if r.get("pct_lula_1t") is None})
    zero_valid = sorted({f"{r['uf']}-{r['mun']}-{r['zona']}-{r['secao']}" for r in rows if r["bu_status"] == "ok" and not r.get("validos_2t")})
    n = {"sinalizadas_total": len(flagged), "sinalizadas_com_resultado": sum(ok(r) for r in flagged),
         "sinalizadas_pareadas": summary["diferenca_pareada"]["pct_lula_2t"]["n_pares"],
         "zonas_pareadas": summary["diferenca_pareada"]["pct_lula_2t"]["n_zonas"],
         "controles_amostrados": len(uniq_ctrl), "controles_com_resultado": sum(ok(r) for r in uniq_ctrl.values()),
         "controles_de_outra_zona_do_municipio": sum(1 for r in uniq_ctrl.values() if r["origem_controle"] == "municipio"),
         "secoes_sem_bu": no_bu, "secoes_sem_1t": no_t1, "secoes_com_zero_validos_2t": zero_valid}
    now = datetime.now()
    stamp = f"{now:%Y%m%d-%H%M}"
    summary = {"gerado_em": now.isoformat(timespec="seconds"),
               "fonte": {"2t": "BU binário (o03221...-bu.dat) do arquivo-urna do TSE, pleito 3221, eleição 6258 (presidente); o imgbu.dat não estava publicado (NoSuchKey)",
                         "1t": "votacao_secao_2026_BR.csv e detalhe_votacao_secao_2026_BRASIL.csv, dos zips de dados abertos do TSE (NR_TURNO=1, CD_CARGO=1)"},
               "definicao": {"sinalizada": "seção com ≥1 voto sem biometria depois das 17h no log da urna (secoes_sinalizadas.csv)",
                             "controles": "até 10 seções não sinalizadas analisadas da mesma UF/município/zona (sorteio com semente fixa); se faltarem, completa com outras zonas do mesmo município",
                             "pct_2t": "votos ÷ (votos 13 + votos 22)", "pct_1t": "votos ÷ votos válidos para presidente no 1º turno (todos os candidatos)",
                             "pct_1t_2c": "votos ÷ (votos 13 + votos 22) no 1º turno", "variacao": "pct_2t − pct_1t, em pontos percentuais",
                             "diferenca_pareada": "para cada sinalizada: valor da sinalizada − média dos controles do mesmo grupo de zona; média dessas diferenças",
                             "ic95": f"bootstrap percentil, {N_BOOT} reamostragens das diferenças pareadas (por sinalizada), semente {SEED}"},
               "n": n, **summary, "problemas": problems,
               "ressalvas": ["Poucas seções sinalizadas; o intervalo é amplo.",
                             "Comparação descritiva entre seções; não identifica causa.",
                             "Sinalizadas da mesma zona dividem controles; o campo ic95_bootstrap_por_zona reamostra zonas inteiras como verificação."]}
    fields = ["grupo", "grupo_zona", "origem_controle", "uf", "mun", "mun_name", "zona", "secao", "votos_log", "votos_apos_17h", "sem_bio_apos", "bu_status",
              "aptos_2t", "comparecimento_2t", "lula_2t", "flavio_2t", "brancos_2t", "nulos_2t", "validos_2t", "pct_lula_2t", "pct_flavio_2t",
              "aptos_1t", "comparecimento_1t", "lula_1t", "flavio_1t", "validos_1t", "pct_lula_1t", "pct_flavio_1t", "pct_lula_1t_2c", "pct_flavio_1t_2c",
              "var_lula_pp", "var_flavio_pp", "var_lula_2c_pp"]
    with open(OUT / "comparacao_sinalizadas.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["grupo_zona"], r["grupo"] != "sinalizada", r["secao"])):
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})
    (OUT / "comparacao_sinalizadas.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    text = resumo_texto(summary, n)
    (OUT / "comparacao_sinalizadas-resumo.txt").write_text(text + "\n", encoding="utf-8")
    card_html = OUT / f"comparacao-cartao-{stamp}.html"
    card_html.write_text(build_card(summary, n, now), encoding="utf-8")
    png = OUT / f"comparacao-{stamp}.png"
    if "--no-png" not in sys.argv:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = abrir_navegador(p)
            page = browser.new_page(viewport={"width": 1200, "height": 630})
            page.goto(card_html.as_uri())
            page.screenshot(path=str(png))
            browser.close()
    print(json.dumps({"n": {k: v for k, v in n.items() if not isinstance(v, list)}, "sem_bu": len(no_bu), "sem_1t": len(no_t1), "problemas": len(problems)}, ensure_ascii=False))
    for m in ("pct_lula_2t", "pct_flavio_2t", "var_lula_pp", "var_flavio_pp", "var_lula_2c_pp", "pct_lula_1t"):
        ms, d = summary["medias_simples"][m], summary["diferenca_pareada"][m]
        print(f"{m:16s} sinal={fnum(ms['sinalizadas'], 2)} (n={ms['n_sinalizadas']}) ctrl={fnum(ms['controles'], 2)} (n={ms['n_controles']}) "
              f"pareada={fnum(d['media'], 2, True)} IC=[{fnum(d['ic95_bootstrap'][0], 2, True)}; {fnum(d['ic95_bootstrap'][1], 2, True)}] ICzona=[{fnum(d['ic95_bootstrap_por_zona'][0], 2, True)}; {fnum(d['ic95_bootstrap_por_zona'][1], 2, True)}] pares={d['n_pares']}")
    print(text)
    print("cartao:", card_html, "| png:", png if "--no-png" not in sys.argv else "(não gerado)")
    for pr in problems[:20]:
        print("problema:", pr)


if __name__ == "__main__":
    main()
