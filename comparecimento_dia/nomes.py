"""Nomes dos municípios para os rótulos de comparecimento.py: grava nomes.json ({"UF-CDMUN": NM_MUNICIPIO}).

Fonte: dados abertos do TSE, detalhe_votacao_munzona_2026.zip (arquivo detalhe_votacao_munzona_2026_BRASIL.csv, lido direto do
zip), que abstencao/baixar.py baixa para DADOS/tse/. Um nome por (SG_UF, CD_MUNICIPIO), o do maior NR_TURNO presente; ordem por
UF e nome. Inclui o exterior (ZZ). Saída: DADOS/derivados/comparecimento_dia/nomes.json."""
import csv
import io
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comum"))
import caminhos  # noqa: E402

ZIP = caminhos.TSE / "detalhe_votacao_munzona_2026.zip"
CSV = "detalhe_votacao_munzona_2026_BRASIL.csv"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    nomes = {}  # (uf, cd) -> (turno, nome)
    with zipfile.ZipFile(ZIP) as archive, archive.open(CSV) as raw:
        for r in csv.DictReader(io.TextIOWrapper(raw, encoding="latin-1"), delimiter=";"):
            k, turno = (r["SG_UF"], r["CD_MUNICIPIO"]), int(r["NR_TURNO"])
            if k not in nomes or turno > nomes[k][0]:
                nomes[k] = (turno, r["NM_MUNICIPIO"])
    ordem = sorted(nomes, key=lambda k: (k[0], nomes[k][1]))
    out = {f"{uf}-{cd}": nomes[(uf, cd)][1] for uf, cd in ordem}
    json.dump(out, open(caminhos.saida("comparecimento_dia") / "nomes.json", "w", encoding="utf-8"), ensure_ascii=False)
    print("municípios:", len(out), "| exterior:", sum(k.startswith("ZZ-") for k in out))


if __name__ == "__main__":
    main()
