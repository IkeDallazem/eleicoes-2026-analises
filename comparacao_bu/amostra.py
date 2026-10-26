"""Amostra: todas as seções sinalizadas + até 10 controles não sinalizados por zona (completa no município).

Entradas: secoes_analisadas.csv em caminhos.saida("logs_urna") (logs_urna/relatorio_17h.py) e o hash do log de cada seção
em caminhos.LOGS/sections.sqlite (logs_urna/coletar_logs.py).
Saídas em caminhos.saida("comparacao_bu"): sample.csv (uf;mun;zona;secao;hash;grupo;grupo_zona;origem) e download.csv
(lista única para baixar). Sorteio determinístico (random.Random(semente fixa por zona)).

A comparação publicada NÃO usa uma amostra gerada agora: ela foi gerada em 25/10/2026, durante a coleta, quando o
secoes_analisadas.csv ainda era parcial e tinha 76 seções sinalizadas. Aquela amostra está congelada em
dados_congelados/sample.csv e dados_congelados/download.csv (76 sinalizadas + 449 controles distintos, 525 seções), e é a
que primeiro_turno.py e comparar.py usam por padrão. Rodar este script sobre o secoes_analisadas.csv final (5.244
sinalizadas) gera outra amostra, muito maior; para usá-la, passe --amostra-nova a baixar_bu.py, primeiro_turno.py e comparar.py.
"""
import csv
import random
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comum"))
import caminhos  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
UL = caminhos.LOGS
N_CTRL = 10


def main():
    rows = [r for r in csv.DictReader(open(caminhos.saida("logs_urna") / "secoes_analisadas.csv", encoding="utf-8-sig"), delimiter=";") if r["uf"] != "ZZ"]
    flagged = [r for r in rows if r["sinalizada"] == "1"]
    db = sqlite3.connect(f"file:{(UL / 'sections.sqlite').as_posix()}?mode=ro", uri=True)
    hashes = {}
    for uf, mun, zona, secao, h in db.execute("select uf, mun, zona, secao, hash from logs order by received_at"):
        hashes[(uf, mun, zona, secao)] = h  # se houver mais de um, fica o último recebido
    by_zona, by_mun = defaultdict(list), defaultdict(list)
    for r in rows:
        if r["sinalizada"] != "1":
            by_zona[(r["uf"], r["mun"], r["zona"])].append(r)
            by_mun[(r["uf"], r["mun"])].append(r)
    key = lambda r: (r["uf"], r["mun"], r["zona"], r["secao"])
    sample, zones_done = [], {}
    stats = {"sinalizadas": len(flagged), "zonas": 0, "ctrl_mesma_zona": 0, "ctrl_mesmo_mun": 0, "sinalizadas_com_menos_de_10": 0, "sinalizadas_sem_controle": 0}
    for f in flagged:
        z = (f["uf"], f["mun"], f["zona"])
        sample.append({**dict(zip(("uf", "mun", "zona", "secao"), key(f))), "hash": hashes.get(key(f), ""), "grupo": "sinalizada", "grupo_zona": "|".join(z), "origem": ""})
        if z in zones_done:
            continue
        rng = random.Random("|".join(z))
        same = sorted(by_zona[z], key=lambda r: r["secao"])
        pick = rng.sample(same, min(N_CTRL, len(same)))
        origem = {key(r): "zona" for r in pick}
        if len(pick) < N_CTRL:
            extra = sorted((r for r in by_mun[(f["uf"], f["mun"])] if r["zona"] != f["zona"]), key=key)
            more = rng.sample(extra, min(N_CTRL - len(pick), len(extra)))
            origem.update({key(r): "municipio" for r in more})
            pick += more
        zones_done[z] = pick
        stats["zonas"] += 1
        for r in pick:
            sample.append({**dict(zip(("uf", "mun", "zona", "secao"), key(r))), "hash": hashes.get(key(r), ""), "grupo": "controle", "grupo_zona": "|".join(z), "origem": origem[key(r)]})
            stats["ctrl_mesma_zona" if origem[key(r)] == "zona" else "ctrl_mesmo_mun"] += 1
    for f in flagged:
        n = len(zones_done[(f["uf"], f["mun"], f["zona"])])
        stats["sinalizadas_com_menos_de_10"] += n < N_CTRL
        stats["sinalizadas_sem_controle"] += n == 0
    fields = ["uf", "mun", "zona", "secao", "hash", "grupo", "grupo_zona", "origem"]
    out = caminhos.saida("comparacao_bu")
    with open(out / "sample.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, delimiter=";")
        w.writeheader()
        w.writerows(sample)
    uniq = {}
    for s in sample:
        uniq.setdefault((s["uf"], s["mun"], s["zona"], s["secao"]), s["hash"])
    # sinalizadas primeiro, depois controles
    order = sorted(uniq, key=lambda k: (0 if any(s["grupo"] == "sinalizada" and key(s) == k for s in sample) else 1, k))
    with open(out / "download.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["uf", "mun", "zona", "secao", "hash"])
        for k in order:
            w.writerow([*k, uniq[k]])
    missing_hash = sum(1 for k in uniq if not uniq[k])
    print(stats, "| linhas na amostra:", len(sample), "| seções únicas:", len(uniq), "| sem hash:", missing_hash)


if __name__ == "__main__":
    main()
