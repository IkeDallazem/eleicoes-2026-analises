"""bio_uf.json = {UF: [votos 1T, biom_sem_hab 1T, votos 2T, biom_sem_hab 2T]}, sem o exterior (ZZ).
1T: boletins de urna (comparecimento, QT_ELEI_BIOM_SEM_HABILITACAO). 2T: contagem nos logs (arquivo dado como argumento).
Entradas e saída em DADOS/derivados/biometria.  Uso: build_uf.py bio_2t_secoes_v2.csv [--check]
(--check compara com o bio_uf.json existente em vez de gravar)"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comum"))
import caminhos  # noqa: E402

PASTA = caminhos.saida("biometria")
acc = defaultdict(lambda: [0, 0, 0, 0])
for r in csv.DictReader(open(PASTA / "bio_1t_secoes.csv", encoding="utf-8")):
    if r["uf"] != "ZZ":
        acc[r["uf"]][0] += int(r["comparecimento"]); acc[r["uf"]][1] += int(r["biom_sem_hab"])
for r in csv.DictReader(open(PASTA / sys.argv[1], encoding="utf-8")):
    if r["uf"] != "ZZ":
        acc[r["uf"]][2] += int(r["votos"]); acc[r["uf"]][3] += int(r["biom_sem_hab"])
out = dict(sorted(acc.items()))
if len(sys.argv) > 2 and sys.argv[2] == "--check":
    print("igual ao bio_uf.json atual:", out == json.load(open(PASTA / "bio_uf.json", encoding="utf-8")))
else:
    json.dump(out, open(PASTA / "bio_uf.json", "w", encoding="utf-8"))
    print("gravado", sum(v[2] for v in out.values()), sum(v[3] for v in out.values()))
