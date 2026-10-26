"""Compara os votos contados nos logs do 2º turno com o comparecimento oficial do TSE (arquivo de resultado por município)
e grava cobertura.json; lista seções com log possivelmente incompleto (log com bem menos votos que o comparecimento do 1º turno, em município com
falta) que ainda não foram relidas -> refetch_list2.json (só diagnóstico).  Uso: reconcile.py bio_2t_secoes_v2.csv
Comparecimento oficial: DADOS/tse/ab/<uf>-e006258-ab.json (baixados por abstencao/baixar.py), campo e.c dos municípios.
Os demais arquivos (o CSV do argumento, bio_1t_secoes.csv, refetch_list.json) e as saídas ficam em DADOS/derivados/biometria."""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comum"))
import caminhos  # noqa: E402

PASTA = caminhos.saida("biometria")
RAW = caminhos.TSE / "ab"
UFS = "ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to".split()
official = {}
for uf in UFS:
    for item in json.loads((RAW / f"{uf}-e006258-ab.json").read_text(encoding="utf-8"))["abr"]:
        if item.get("tpabr") == "mun":
            official[(uf.upper(), item["cdabr"])] = int(item["e"]["c"])
logs = defaultdict(int)
sec2 = {}
for r in csv.DictReader(open(PASTA / sys.argv[1], encoding="utf-8")):
    if r["uf"] == "ZZ":
        continue
    logs[(r["uf"], r["cd_municipio"])] += int(r["votos"])
    sec2[(r["uf"], r["cd_municipio"], r["nr_zona"], r["nr_secao"])] = int(r["votos"])
c1 = {(r["uf"], r["cd_municipio"], r["nr_zona"], r["nr_secao"]): int(r["comparecimento"])
      for r in csv.DictReader(open(PASTA / "bio_1t_secoes.csv", encoding="utf-8")) if r["uf"] != "ZZ"}
tot_o, tot_l = sum(official.values()), sum(logs.values())
short = {k: official[k] - logs.get(k, 0) for k in official if official[k] > logs.get(k, 0)}
over = {k: logs[k] - official.get(k, 0) for k in logs if logs[k] > official.get(k, 0)}
print(f"oficial {tot_o:,} logs {tot_l:,} falta {tot_o - tot_l:,} ({100 * (tot_o - tot_l) / tot_o:.3f}%)")
print("municípios com falta", len(short), "soma", sum(short.values()), "| com sobra", len(over), "soma", sum(over.values()))
print("maiores faltas", sorted(short.items(), key=lambda kv: -kv[1])[:8])
print("sobras", sorted(over.items(), key=lambda kv: -kv[1])[:8])
done = {tuple(k) for k in json.load(open(PASTA / "refetch_list.json"))}
cand = sorted(k for k, v in sec2.items() if (k[0], k[1]) in short and k in c1 and v < 0.85 * c1[k] and k not in done)
print("candidatas a reler", len(cand), "falta 1T-2T nelas", sum(c1[k] - sec2[k] for k in cand))
json.dump(cand, open(PASTA / "refetch_list2.json", "w"))
pct = 100 * tot_l / tot_o
json.dump({"oficial": tot_o, "logs": tot_l, "falta": tot_o - tot_l, "pct": pct,
           "texto": f"faltam {tot_o - tot_l:,} dos {tot_o:,} votos do comparecimento oficial".replace(",", ".")},
          open(PASTA / "cobertura.json", "w", encoding="utf-8"), ensure_ascii=False)
