"""Relatório (imagem): votos após 17h e sem biometria por UF — só Brasil, exterior excluído.

Lê sections.sqlite e day/ em caminhos.LOGS (gerados por coletar_logs.py) e grava em caminhos.saida("logs_urna"):
cache_logs.json (cache da leitura dos logs), secoes_analisadas.csv, secoes_sinalizadas.csv (≥1 voto sem biometria após 17h,
para comparar com o resultado final) e relatorios/biometria-provisorio-<data-hora>.html, .png e -resumo.txt.
Modo final (título "coleta completa"): coleta sem seções pendentes e totais oficiais por UF disponíveis em
caminhos.TSE/ab/{uf}-e006258-ab.json (baixados por abstencao/baixar.py); sem esses arquivos o relatório sai como provisório.
--if-changed: não gera imagem se nenhuma seção nova foi analisada desde o último relatório.
--ufs AC,AP,RR: lê só essas UFs (teste rápido); as saídas vão para a subpasta ufs-AC-AP-RR, com cache próprio.
"""
import argparse
import collections
import csv
import gzip
import html
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comum"))
import caminhos  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
# Logs de entrada (só leitura); as pastas de saída são definidas em main(), dentro de caminhos.saida("logs_urna").
ROOT = caminhos.LOGS
SAIDA = OUT = CACHE = None
UFS_BR = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split()
TABLE = {"AC": 120, "AM": 60, "RO": 60, "RR": 60, "MT": 60, "MS": 60}
# Fernando de Noronha é UTC-2: as urnas abrem às 09:00 locais (08:00 de Brasília), então o ajuste é negativo.
TABLE_MUN = {("PE", "30015"): -60}
# Muda quando parse() muda: o cache guardado com outra versão é descartado e todos os logs são lidos de novo.
PARSE_VERSION = 2
KIND_LABEL = {"mesario": "mesário habilitou", "dado_pessoal": "dado pessoal conferido", "ano_nascimento": "ano de nascimento", "desconhecido": "não identificado"}


def secs(hms):
    h, m, s = hms.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def parse(path, uf, mun):
    votes, sess, first_hab, ident, contig = [], set(), None, None, False
    for line in gzip.open(path, "rt", encoding="utf-8"):
        r = line.rstrip("\n").split("\t")
        if len(r) < 5 or not r[0].startswith("25/10/2026"):
            continue
        msg, t = r[4], r[0][11:19]
        if msg.startswith("Aguardando digitação do identificador"):
            sess, ident = set(), None
        elif msg.startswith("Identificador do eleitor digitado"):
            ident = t
        elif msg.startswith("Log interno da urna de contingência"):
            contig = True
        elif msg.startswith("Tipo de habilitação do eleitor [biométrica]"):
            sess.add("bio")
        elif msg.startswith("Ano de nascimento digitado é igual"):
            sess.add("ano_nascimento")
        elif msg.startswith("Dado digitado confere"):
            sess.add("dado_pessoal")
        elif msg.startswith("Mesário") and msg.endswith("habilitou o eleitor"):
            sess.add("mesario")
        elif msg == "Eleitor foi habilitado":
            first_hab = first_hab or t
        elif msg == "O voto do eleitor foi computado":
            kind = next((k for k in ("bio", "mesario", "dado_pessoal", "ano_nascimento") if k in sess), "desconhecido")
            votes.append((secs(t), secs(ident) if ident else secs(t), kind))
            sess, ident = set(), None
    if (uf, mun) in TABLE_MUN:
        off = TABLE_MUN[(uf, mun)] * 60
    else:
        off = TABLE.get(uf, 0) * 60
        if first_hab:
            fh = secs(first_hab)
            off = max(off, 7200 if fh < 6.9 * 3600 else 3600 if fh < 7.9 * 3600 else 0)
    c = collections.Counter()
    for t, t_id, kind in votes:
        when = "depois" if t + off >= 17 * 3600 else "antes"
        c[f"{when}_votos"] += 1
        if kind != "bio":
            c[f"{when}_sembio"] += 1
            c[f"{when}_k_{kind}"] += 1
        # A habilitação sem biometria demora mais; pela hora em que o eleitor foi identificado, quem chegou antes das 17h conta como antes.
        if t_id + off >= 17 * 3600:
            c["depois_id_votos"] += 1
            c["depois_id_sembio"] += kind != "bio"
        if t_id != t:
            group = "bio" if kind == "bio" else "sembio"
            c[f"espera_{group}_s"] += t - t_id
            c[f"espera_{group}_n"] += 1
    c["contingencia"] = int(contig)
    c["offset_min"] = off // 60
    return dict(c)


def parse_item(item):
    rel, uf, mun = item
    return rel, parse(ROOT / rel, uf, mun)


def totais_tse(ufs):
    """(seções apuradas, total de seções) e comparecimento somados das UFs, pelos arquivos de abrangência do TSE
    (2º turno, eleição 6258; entrada tpabr='uf' de cada arquivo). (None, None) se algum arquivo faltar."""
    st = ts = comp = 0
    try:
        for uf in ufs:
            dados = json.loads((caminhos.TSE / "ab" / f"{uf.lower()}-e006258-ab.json").read_text(encoding="utf-8"))
            total = next(a for a in dados["abr"] if a["tpabr"] == "uf")
            st, ts, comp = st + int(total["s"]["st"]), ts + int(total["s"]["ts"]), comp + int(total["e"]["c"])
    except (OSError, ValueError, KeyError, StopIteration):
        return None, None
    return (st, ts), comp


def pct(a, b):
    if not b:
        return "—"
    v = 100 * a / b
    return (f"{v:.2f}%" if 0 < v < 1 else f"{v:.1f}%").replace(".", ",")


def n(x):
    return f"{x:,}".replace(",", ".")


def abrir_navegador(p):
    """Microsoft Edge instalado no sistema, se houver; senão o Chromium do Playwright (python -m playwright install chromium)."""
    try:
        return p.chromium.launch(channel="msedge")
    except Exception:  # noqa: BLE001 - Edge ausente
        return p.chromium.launch()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--if-changed", action="store_true")
    ap.add_argument("--draft", action="store_true", help="grava relatório e tabelas em relatorios/rascunho, sem substituir as tabelas principais")
    ap.add_argument("--ufs", help="UFs separadas por vírgula (ex.: AC,AP,RR) para um teste rápido; saídas em ufs-<UFs>/, com cache próprio")
    args = ap.parse_args()
    global OUT, CACHE, SAIDA
    ufs_sel = [u.strip().upper() for u in args.ufs.split(",") if u.strip()] if args.ufs else None
    if ufs_sel and not set(ufs_sel) <= set(UFS_BR):
        ap.error(f"UF desconhecida: {sorted(set(ufs_sel) - set(UFS_BR))}")
    SAIDA = caminhos.saida("logs_urna")
    if ufs_sel:
        SAIDA = SAIDA / f"ufs-{'-'.join(ufs_sel)}"

    def onde(col="uf"):
        # Sem --ufs: todas as UFs do Brasil (exterior = ZZ, excluído).
        return f"{col}<>'ZZ'" if not ufs_sel else f"{col} IN ({', '.join(repr(u) for u in ufs_sel)})"

    OUT = SAIDA / "relatorios"
    CACHE = SAIDA / "cache_logs.json"
    if args.draft:
        OUT = OUT / "rascunho"
    OUT.mkdir(parents=True, exist_ok=True)
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    meta = cache.pop("__meta__", {})
    if meta.get("v") != PARSE_VERSION:
        cache, meta = {}, {}
    db = sqlite3.connect(f"file:{ROOT / 'sections.sqlite'}?mode=ro", uri=True)
    total_br = db.execute(f"SELECT COUNT(*) FROM sections WHERE {onde()}").fetchone()[0]
    recv_br = db.execute(f"SELECT COUNT(*) FROM sections WHERE {onde()} AND received_at IS NOT NULL").fetchone()[0]
    # Seções já consultadas cujo log o TSE ainda não publicou (404) e que não têm nenhum log baixado.
    log_404 = db.execute(f"SELECT COUNT(*) FROM sections s WHERE {onde('s.uf')} AND s.status='error' AND s.error LIKE '%404%' AND NOT EXISTS "
                         "(SELECT 1 FROM logs l WHERE l.uf=s.uf AND l.mun=s.mun AND l.zona=s.zona AND l.secao=s.secao)").fetchone()[0]
    # Coleta completa: nenhuma seção publicada pelo TSE ainda na fila ou com erro (as 'waiting' nunca recebem arquivos).
    pending = db.execute(f"SELECT COUNT(*) FROM sections WHERE {onde()} AND status IN ('queued', 'error')").fetchone()[0]
    no_log = db.execute(f"SELECT COUNT(*) FROM sections WHERE {onde()} AND status='nolog'").fetchone()[0]
    # Seções apuradas, total de seções e comparecimento oficiais, lidos dos arquivos de resultado do TSE.
    apurado, turnout = totais_tse(ufs_sel or UFS_BR)
    if apurado:
        # O cs.json lista ~18 mil entradas que nunca recebem arquivos (sem urna própria); o total real de seções é o da apuração.
        total_br = apurado[1]
    names = {(u, m): nm for u, m, nm in db.execute(f"SELECT DISTINCT uf, mun, mun_name FROM sections WHERE {onde()}")}
    logs = db.execute(f"SELECT uf, mun, zona, secao, path FROM logs WHERE {onde()} ORDER BY uf, mun, zona, secao").fetchall()
    if args.if_changed and meta.get("logs") == len(logs):
        print(f"sem novidades: {len(logs)} seções", flush=True)
        CACHE.write_text(json.dumps({**cache, "__meta__": meta}), encoding="utf-8")
        return
    per_uf = collections.defaultdict(collections.Counter)
    by_section = {}
    todo = [(rel, uf, mun) for uf, mun, zona, secao, rel in logs if rel not in cache and (ROOT / rel).exists()]
    if len(todo) > 2000:
        # Releitura completa (cache novo): em paralelo, senão leva ~40 min.
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(8) as pool:
            for rel, result in pool.map(parse_item, todo, chunksize=256):
                cache[rel] = result
    for uf, mun, zona, secao, rel in logs:
        path = ROOT / rel
        if not path.exists():
            continue
        if rel not in cache:
            cache[rel] = parse(path, uf, mun)
        key = (uf, mun, zona, secao)
        acc = by_section.setdefault(key, collections.Counter())
        acc.update({k: v for k, v in cache[rel].items() if k != "offset_min"})
        acc["logs"] += 1
    for (uf, *_), c in by_section.items():
        for scope in (uf, "BR"):
            per_uf[scope].update(c)
            per_uf[scope]["secoes"] += 1
            per_uf[scope]["sinalizadas"] += c.get("depois_sembio", 0) > 0
    CACHE.write_text(json.dumps({**cache, "__meta__": {"logs": len(logs), "v": PARSE_VERSION}}), encoding="utf-8")

    # Lista completa (com a marca) e lista só das sinalizadas, para comparar com o resultado final.
    fields = ["uf", "mun", "mun_name", "zona", "secao", "votos", "votos_antes_17h", "votos_apos_17h", "pct_votos_apos_17h",
              "sem_bio_antes", "pct_sem_bio_antes", "sem_bio_apos", "pct_sem_bio_apos", "sinalizada", "logs",
              "votos_apos_17h_ident", "sem_bio_apos_ident", "urna_contingencia"]
    table_rows = []
    for (uf, mun, zona, secao), c in sorted(by_section.items()):
        va, vd, sa, sd = c.get("antes_votos", 0), c.get("depois_votos", 0), c.get("antes_sembio", 0), c.get("depois_sembio", 0)
        table_rows.append({"uf": uf, "mun": mun, "mun_name": names.get((uf, mun), ""), "zona": zona, "secao": secao, "votos": va + vd,
                           "votos_antes_17h": va, "votos_apos_17h": vd, "pct_votos_apos_17h": round(100 * vd / (va + vd), 2) if va + vd else "",
                           "sem_bio_antes": sa, "pct_sem_bio_antes": round(100 * sa / va, 2) if va else "", "sem_bio_apos": sd,
                           "pct_sem_bio_apos": round(100 * sd / vd, 2) if vd else "", "sinalizada": int(sd > 0), "logs": c["logs"],
                           "votos_apos_17h_ident": c.get("depois_id_votos", 0), "sem_bio_apos_ident": c.get("depois_id_sembio", 0),
                           "urna_contingencia": int(c.get("contingencia", 0) > 0)})
    for name, rows in (("secoes_analisadas.csv", table_rows), ("secoes_sinalizadas.csv", [r for r in table_rows if r["sinalizada"]])):
        with open((OUT if args.draft else SAIDA) / name, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)

    br = per_uf["BR"]
    done = br["secoes"]
    total_votes = br["antes_votos"] + br["depois_votos"]
    now = datetime.now()
    final = pending == 0 and apurado is not None
    rest = max(0, total_br - done)
    # "N de M" em vez de porcentagem no final: 497.895 de 497.897 apareceria como "100,0%".
    cover_final = f"{n(done)} de {n(total_br)} seções" if rest else f"todas as {n(done)} seções"
    # Mesma divisão antes/depois das 17h, mas pela hora em que o mesário digitou o identificador do eleitor.
    id_votes, id_sb = br["depois_id_votos"], br["depois_id_sembio"]
    id_before_v, id_before_s = total_votes - id_votes, br["antes_sembio"] + br["depois_sembio"] - id_sb
    wait_bio = br["espera_bio_s"] / br["espera_bio_n"] if br["espera_bio_n"] else 0
    wait_sb = br["espera_sembio_s"] / br["espera_sembio_n"] if br["espera_sembio_n"] else 0
    flag_id = sum(1 for c in by_section.values() if c.get("depois_id_sembio", 0) > 0)
    # Votos que não aparecem nos logs lidos (urna trocada: só lemos o log da última urna), contra o comparecimento oficial.
    missing = 1 - total_votes / turnout if turnout else None
    missing_txt = (f"{100 * missing:.1f}%".replace(".", ",") if missing and missing >= 0.0005 else "menos de 0,1%") if missing is not None else None
    ufs = [(uf, c) for uf, c in per_uf.items() if uf != "BR"]
    ufs.sort(key=lambda item: (-item[1]["depois_votos"] / max(1, item[1]["antes_votos"] + item[1]["depois_votos"]), item[0]))
    max_share = max([100 * c["depois_votos"] / max(1, c["antes_votos"] + c["depois_votos"]) for _, c in ufs] + [1])
    scale_a = max(5, min(100, (int(max_share / 5) + 1) * 5))

    def chart_row(uf, c):
        tot = c["antes_votos"] + c["depois_votos"]
        share = 100 * c["depois_votos"] / tot if tot else 0
        nb_after = 100 * c["depois_sembio"] / c["depois_votos"] if c["depois_votos"] else None
        nb_before = 100 * c["antes_sembio"] / c["antes_votos"] if c["antes_votos"] else None
        bar_b = (f"<i class=b style='width:{nb_after:.2f}%'></i>" if nb_after is not None else "") + \
                (f"<s style='left:{nb_before:.2f}%' title='antes das 17h'></s>" if nb_before is not None else "")
        label_b = f"<b>{pct(c['depois_sembio'], c['depois_votos'])}</b> ({n(c['depois_sembio'])}) · antes {pct(c['antes_sembio'], c['antes_votos'])}" if c["depois_votos"] else f"sem votos após 17h · antes {pct(c['antes_sembio'], c['antes_votos'])}"
        return (f"<div class=uf>{uf}</div>"
                f"<div class=cell><div class=track><i class=a style='width:{100 * share / scale_a:.2f}%'></i></div><span><b>{pct(c['depois_votos'], tot)}</b> ({n(c['depois_votos'])} de {n(tot)})</span></div>"
                f"<div class=cell><div class=track>{bar_b}</div><span>{label_b}</span></div>"
                f"<div class=num>{n(c['secoes'])}</div>")

    chart = "".join(chart_row(uf, c) for uf, c in ufs)
    flagged = sorted((r for r in table_rows if r["sinalizada"]), key=lambda r: (-r["sem_bio_apos"], -r["votos_apos_17h"]))
    flag_rows = "".join(
        f"<tr><td>{r['uf']}</td><td>{html.escape(r['mun_name'])}{' <small>(urna trocada: só o log da última urna)</small>' if r['urna_contingencia'] else ''}</td><td>{r['zona']}/{r['secao']}</td><td>{n(r['votos'])}</td><td>{n(r['votos_apos_17h'])}</td>"
        f"<td><b>{n(r['sem_bio_apos'])}</b></td><td>{pct(r['sem_bio_apos'], r['votos_apos_17h'])}</td><td>{pct(r['sem_bio_antes'], r['votos_antes_17h'])}</td></tr>"
        for r in flagged[:15]) or "<tr><td colspan=8>Nenhuma seção sinalizada ainda.</td></tr>"
    kinds = " · ".join(f"{KIND_LABEL[k]}: {n(br.get(f'antes_k_{k}', 0))} antes / {n(br.get(f'depois_k_{k}', 0))} após" for k in KIND_LABEL if br.get(f"antes_k_{k}") or br.get(f"depois_k_{k}"))
    page = f"""<!doctype html><html lang=pt-BR><meta charset=utf-8><style>
body{{margin:0;font:15px/1.35 'Segoe UI',system-ui,sans-serif;background:#f6f4ef;color:#1d1f23}}
.w{{width:1040px;padding:26px 30px}} h1{{font-size:25px;margin:0}} .sub{{color:#5b5f66;margin:4px 0 14px}}
.card{{background:#fff;border-radius:12px;padding:14px 18px;box-shadow:0 1px 2px #0001;margin-bottom:14px}}
.hero{{background:#1f3a5f;color:#fff;font-size:21px;line-height:1.45}} .hero b{{font-size:30px}} .hero small{{font-size:14px;opacity:.8}}
.bar{{height:9px;background:#e2ddd2;border-radius:6px;overflow:hidden;margin-top:6px}} .bar i{{display:block;height:100%;background:#1f3a5f;width:{100 * done / total_br if total_br else 0:.2f}%}}
.chart{{display:grid;grid-template-columns:42px 1fr 1fr 64px;gap:5px 14px;align-items:center}}
.chart .h{{font-size:13px;font-weight:600;color:#5b5f66}} .uf{{font-weight:700}} .num{{text-align:right;color:#5b5f66;font-size:13px}}
.track{{position:relative;height:14px;background:#efebe3;border-radius:4px;overflow:visible}} .track i{{position:absolute;left:0;top:0;bottom:0;border-radius:4px}}
.a{{background:#2f6f9f}} .b{{background:#c0603a}} .track s{{position:absolute;top:-3px;bottom:-3px;width:3px;margin-left:-1px;background:#1d1f23;border-radius:2px}}
.cell span{{font-size:12.5px;color:#3c4046}}
table{{width:100%;border-collapse:collapse;font-size:13.5px}} th,td{{padding:5px 8px;text-align:right;border-bottom:1px solid #eee}}
th:nth-child(-n+3),td:nth-child(-n+3){{text-align:left}} th{{background:#ece8df;font-weight:600}}
h2{{font-size:17px;margin:4px 0 10px}} .note{{font-size:12.3px;color:#5b5f66}} .leg{{font-size:12.5px;color:#5b5f66;margin:-4px 0 10px}}
.leg i{{display:inline-block;width:12px;height:10px;border-radius:2px;vertical-align:-1px;margin-right:4px}}
</style><div class=w>
<h1>Votos após 17h e sem biometria · 2º turno 2026 · Brasil (sem exterior){' · coleta completa' if final else ''}</h1>
<div class=sub>{now:%d/%m/%Y %H:%M} · logs de urna do TSE · horário oficial de Brasília (encerramento às 17h)</div>
<div class="card hero">Depois das 17h entrou <b>{pct(br['depois_votos'], total_votes)}</b> dos votos <small>({n(br['depois_votos'])} de {n(total_votes)})</small>.<br>
Desses votos após 17h, <b>{pct(br['depois_sembio'], br['depois_votos'])}</b> foram sem biometria <small>({n(br['depois_sembio'])} votos)</small> · antes das 17h: <b style="font-size:24px">{pct(br['antes_sembio'], br['antes_votos'])}</b> <small>({n(br['antes_sembio'])} de {n(br['antes_votos'])})</small><br>
<span style="font-size:17px;line-height:1.4;display:block;margin-top:6px">Pela hora em que o eleitor foi identificado: <b style="font-size:22px">{pct(id_sb, id_votes)}</b> sem biometria após 17h <small>({n(id_sb)} de {n(id_votes)})</small> · antes das 17h: <b style="font-size:22px">{pct(id_before_s, id_before_v)}</b>.
A habilitação sem biometria demora mais (em média {wait_sb:.0f} s, contra {wait_bio:.0f} s com biometria), então parte de quem foi identificado antes das 17h só votou depois.</span></div>
<div class=card>Cobertura: <b>{n(done)}</b> seções analisadas de {n(total_br)} no Brasil ({(n(rest) + ' sem log no site do TSE') if final and rest else 'coleta completa' if final else pct(done, total_br)}) · {'' if final else n(recv_br) + ' publicadas pelo TSE · '}<b>{n(br['sinalizadas'])}</b> seções sinalizadas<div class=bar><i></i></div></div>
<div class=card><h2>Por estado</h2>
<div class=leg><i style="background:#2f6f9f"></i>% dos votos da UF que entraram após 17h (escala 0–{scale_a}%) &nbsp; <i style="background:#c0603a"></i>% sem biometria entre os votos após 17h (escala 0–100%) &nbsp; ▮ = % sem biometria antes das 17h</div>
<div class=chart><div class=h>UF</div><div class=h>Votos após 17h / total</div><div class=h>Sem biometria após 17h</div><div class="h num">seções</div>{chart}</div></div>
<div class=card><h2>Seções sinalizadas (≥1 voto sem biometria após 17h) — {n(len(flagged))} no total</h2>
<table><tr><th>UF</th><th>Município</th><th>Zona/Seção</th><th>Votos</th><th>Após 17h</th><th>S/ bio após</th><th>% s/ bio após</th><th>% s/ bio antes</th></tr>{flag_rows}</table>
<div class=note style="margin-top:6px">Lista completa guardada para comparar o resultado dessas seções com o das demais{'' if final else ' ao fim da apuração'}</div></div>
<div class=note>Tipos de habilitação sem biometria — {kinds or '—'}.<br>
{f"Coleta completa: {cover_final} do Brasil (sem exterior) analisadas" + (f"; {n(rest)} sem log no site do TSE" if rest else "") + "." if final else "Amostra = seções cujos logs já foram baixados, em ordem aleatória entre as publicadas."} Hora = relógio da urna no registro do voto, convertida para Brasília. Em seções com urna trocada durante o dia lemos só o log da última urna{f' ({missing_txt} dos votos do comparecimento oficial não entram na conta)' if missing_txt else ''}; essas seções aparecem marcadas na tabela. Habilitação sem biometria é procedimento previsto (eleitor sem biometria cadastrada, digital não reconhecida → conferência de dado pessoal ou habilitação pelo mesário); votar após 17h é permitido a quem estava na fila. {'Contagem a partir dos logs públicos.' if final else 'Números provisórios.'}</div>
</div></html>"""
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = f"{now:%Y%m%d-%H%M}"
    page_path = OUT / f"biometria-provisorio-{stamp}.html"
    page_path.write_text(page, encoding="utf-8")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = abrir_navegador(p)
        tab = browser.new_page(viewport={"width": 1100, "height": 800}, device_scale_factor=2)
        tab.goto(page_path.as_uri())
        png = OUT / f"biometria-provisorio-{stamp}.png"
        tab.screenshot(path=str(png), full_page=True)
        browser.close()
    # Resumo em texto, com os mesmos números da imagem.
    lead = [(uf, c) for uf, c in ufs if c["depois_votos"]][:3]
    lead_text = "; ".join(f"{uf} ({pct(c['depois_votos'], c['antes_votos'] + c['depois_votos'])} dos votos após 17h, {pct(c['depois_sembio'], c['depois_votos'])} deles sem biometria)" for uf, c in lead)
    small = br["depois_votos"] < 1000
    # Estimativa dos logs já disponibilizados pelo TSE: seções sem arquivos no cs.json não têm log; entre as recebidas,
    # a ordem de coleta é pseudoaleatória, então a fração com log entre as consultadas estima a fração geral.
    pub_share = min(1, recv_br / total_br) * done / (done + log_404) if done + log_404 else None
    # Acima de 99,5% "cerca de 100%" soa estranho: diz "praticamente todas".
    near_all = pub_share is not None and pub_share >= 0.995
    pub_long = "praticamente todas as seções" if near_all else f"cerca de {100 * pub_share:.0f}% das seções" if pub_share is not None else "parte das seções"
    # Apuração com duas casas, truncada, para 99,96% não aparecer como 100,0%.
    apur_txt = (f"{int(10000 * apurado[0] / apurado[1]) / 100:.2f}%".replace(".", ",")) if apurado else None
    rest_txt = (f"; {'a seção restante não tem' if rest == 1 else f'as {n(rest)} restantes não têm'} log no site do TSE" if rest else "")
    if final:
        # Coleta completa: sem "ainda não temos" nem a promessa de novas atualizações, e com a ressalva sobre a hora do voto.
        text = "\n".join(filter(None, [
            f"**Terminamos de analisar os logs de urna do próprio TSE.** (resultado das {now:%H:%M})",
            "Para cada seção, contamos quantos votos entraram depois das 17h e quantos desses eleitores foram habilitados sem biometria. Os logs são públicos e qualquer pessoa pode conferir.",
            f"Analisamos os logs de {cover_final} do Brasil (sem o exterior){rest_txt}. "
            f"Em seções onde a urna foi trocada durante o dia, lemos só o log da última urna"
            + (f"; por isso {missing_txt} dos votos não entram na conta." if missing_txt else "."),
            f"Resultado: {pct(br['depois_votos'], total_votes)} dos votos foram registrados depois das 17h ({n(br['depois_votos'])} votos). "
            f"Desses, {pct(br['depois_sembio'], br['depois_votos'])} foram sem biometria ({n(br['depois_sembio'])} votos), contra {pct(br['antes_sembio'], br['antes_votos'])} antes das 17h.",
            f"Atenção ao comparar: a hora acima é a do registro do voto, e a habilitação sem biometria demora mais (em média {wait_sb:.0f} s, contra {wait_bio:.0f} s com biometria). "
            f"Por isso, parte de quem foi identificado antes das 17h só votou depois. Pela hora em que o eleitor foi identificado, "
            f"{pct(id_sb, id_votes)} dos votos após 17h foram sem biometria ({n(id_sb)} de {n(id_votes)}), contra {pct(id_before_s, id_before_v)} antes das 17h.",
            f"Estados com maior fatia de votos depois das 17h: {lead_text}." if lead else "",
            f"{n(len(flagged))} seções tiveram votos sem biometria registrados depois das 17h ({n(flag_id)} pela hora da identificação) e foram sinalizadas, "
            "para comparar o resultado delas com o das demais.",
        ]))
        (OUT / f"biometria-provisorio-{stamp}-resumo.txt").write_text(text, encoding="utf-8")
        print(f"FINAL {png}\tseções={done} de {total_br} (sem log {no_log})\tapós17h={br['depois_votos']} ({pct(br['depois_votos'], total_votes)})\t"
              f"sembio_após={br['depois_sembio']} ({pct(br['depois_sembio'], br['depois_votos'])})\tantes={pct(br['antes_sembio'], br['antes_votos'])}\tsinalizadas={len(flagged)}\t"
              f"ident: após={id_votes} sembio={id_sb} ({pct(id_sb, id_votes)}) antes={pct(id_before_s, id_before_v)} sinalizadas={flag_id}\t"
              f"espera bio={wait_bio:.0f}s sembio={wait_sb:.0f}s\tfora da conta={missing_txt} (comparecimento {turnout})", flush=True)
        return
    text = "\n".join(filter(None, [
        f"**Estamos analisando os logs de urna do próprio TSE em tempo real.** (atualização das {now:%H:%M})",
        "Para cada seção, contamos quantos votos entraram depois das 17h e quantos desses eleitores foram habilitados sem biometria. Os logs são públicos e qualquer pessoa pode conferir.",
        f"Ainda não temos os logs de todas as urnas: analisamos {n(done)} até agora ({pct(done, total_br)} das seções do Brasil). "
        f"Pela amostra que consultamos, o TSE já disponibilizou os logs de {pub_long}"
        + (f" (o resultado já saiu para {apur_txt})" if apur_txt else "")
        + "; baixamos os logs aos poucos, para não sobrecarregar o site do TSE.",
        f"Até agora ({n(done)} seções, {pct(done, total_br)} do Brasil, sem contar o exterior): {pct(br['depois_votos'], total_votes)} dos votos entraram depois das 17h ({n(br['depois_votos'])} votos). "
        f"Desses, {pct(br['depois_sembio'], br['depois_votos'])} foram sem biometria ({n(br['depois_sembio'])} votos), contra {pct(br['antes_sembio'], br['antes_votos'])} antes das 17h."
        + (f" A amostra ainda é pequena (só {n(br['depois_votos'])} votos depois das 17h); os números ficam mais firmes conforme analisamos mais logs." if small else ""),
        f"Estados com maior fatia de votos depois das 17h: {lead_text}." if lead else "",
        f"{n(len(flagged))} seções com votos sem biometria depois das 17h estão sendo sinalizadas, para comparar o resultado delas com o das demais no fim da apuração.",
    ]))
    txt = OUT / f"biometria-provisorio-{stamp}-resumo.txt"
    txt.write_text(text, encoding="utf-8")
    print(f"{png}\ttexto={txt}\tseções={done}\tapós17h={br['depois_votos']} ({pct(br['depois_votos'], total_votes)})\tsembio_após={br['depois_sembio']} ({pct(br['depois_sembio'], br['depois_votos'])})\tantes={pct(br['antes_sembio'], br['antes_votos'])}\tsinalizadas={len(flagged)}", flush=True)


if __name__ == "__main__":
    main()
