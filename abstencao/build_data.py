"""Monta a tabela de abstenção por município (1º e 2º turno) para 2026 e 2022.

2026: arquivos de abrangência do TSE (DADOS/tse/ab/<uf>-e<eleição>-ab.json), um por UF e turno — te = aptos, c = comparecimento, a = abstenção.
2022: detalhe_votacao_munzona_2022_BRASIL.csv (cargo 1, Presidente), somado por município (todas as zonas e linhas de voto em trânsito).
Saída: abst_municipios.csv (ano, uf, cd_municipio, aptos/abst de cada turno) e checagem 2026 1º turno contra o CSV oficial do TSE.

Entradas (baixadas por baixar.py): DADOS/tse/ab/*-ab.json e os zips DADOS/tse/detalhe_votacao_munzona_{2022,2026}.zip, lidos direto do zip.
Saída em DADOS/derivados/abstencao/.
"""
import csv
import io
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comum"))
import caminhos  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
RAW = caminhos.TSE / "ab"
UFS = "ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to zz".split()


def zip_munzona(ano):
    return caminhos.TSE / f"detalhe_votacao_munzona_{ano}.zip"


def load_ab(election):
    out = {}
    for uf in UFS:
        data = json.loads((RAW / f"{uf}-e00{election}-ab.json").read_text(encoding="utf-8"))
        for item in data["abr"]:
            if item.get("tpabr") != "mun":
                continue
            e = item["e"]
            te, c, a = int(e["te"]), int(e["c"]), int(e["a"])
            out[(uf.upper(), item["cdabr"])] = (te, c, a, int(e.get("esni") or 0))
    return out


def load_csv(ano, rounds):
    """Soma por município o detalhe_votacao_munzona_<ano>_BRASIL.csv, lido de dentro do zip do TSE (latin-1)."""
    acc = defaultdict(lambda: [0, 0, 0])
    with zipfile.ZipFile(zip_munzona(ano)) as z, \
            io.TextIOWrapper(z.open(f"detalhe_votacao_munzona_{ano}_BRASIL.csv"), encoding="latin-1", newline="") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            if row["CD_CARGO"] != "1" or int(row["NR_TURNO"]) not in rounds:
                continue
            key = (int(row["NR_TURNO"]), row["SG_UF"], row["CD_MUNICIPIO"].zfill(5))
            acc[key][0] += int(row["QT_APTOS"])
            acc[key][1] += int(row["QT_COMPARECIMENTO"])
            acc[key][2] += int(row["QT_ABSTENCOES"])
    return acc


def main():
    t1, t2 = load_ab(6257), load_ab(6258)
    rows = []
    for key in sorted(set(t1) | set(t2)):
        a, b = t1.get(key), t2.get(key)
        if not a or not b:
            print("só num turno:", key, a, b)
            continue
        rows.append({"ano": 2026, "uf": key[0], "cd_municipio": key[1], "aptos_1t": a[0], "abst_1t": a[2], "comp_1t": a[1],
                     "aptos_2t": b[0], "abst_2t": b[2], "comp_2t": b[1]})
    # Checagem: 1º turno 2026 pelo arquivo de abrangência × CSV oficial (detalhe_votacao_munzona). Só imprime; não entra na tabela.
    if zip_munzona(2026).exists():
        csv26 = load_csv(2026, {1})
        diff = [(k, t1[(k[1], k[2])], v) for k, v in csv26.items() if (k[1], k[2]) in t1 and (t1[(k[1], k[2])][0], t1[(k[1], k[2])][2]) != (v[0], v[2])]
        missing = [k for k in csv26 if (k[1], k[2]) not in t1]
        print(f"2026 1T: {len(t1)} municípios no ab, {len(csv26)} no CSV; divergências aptos/abstenção: {len(diff)}; ausentes no ab: {len(missing)}")
        for item in diff[:5]:
            print("  diverge:", item)
    else:
        print("2026 1T: detalhe_votacao_munzona_2026.zip não encontrado; checagem contra o CSV oficial pulada")
    csv22 = load_csv(2022, {1, 2})
    for (uf, mun) in sorted({(k[1], k[2]) for k in csv22}):
        a, b = csv22.get((1, uf, mun)), csv22.get((2, uf, mun))
        if not a or not b:
            continue
        rows.append({"ano": 2022, "uf": uf, "cd_municipio": mun, "aptos_1t": a[0], "abst_1t": a[2], "comp_1t": a[1],
                     "aptos_2t": b[0], "abst_2t": b[2], "comp_2t": b[1]})
    with open(caminhos.saida("abstencao") / "abst_municipios.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for year in (2026, 2022):
        rs = [r for r in rows if r["ano"] == year]
        br = [r for r in rs if r["uf"] != "ZZ"]
        s = lambda k, rr: sum(r[k] for r in rr)
        print(f"{year}: {len(rs)} municípios ({len(br)} no Brasil). Brasil sem exterior: abst 1T {100*s('abst_1t',br)/s('aptos_1t',br):.2f}% "
              f"→ 2T {100*s('abst_2t',br)/s('aptos_2t',br):.2f}%; com exterior {100*s('abst_1t',rs)/s('aptos_1t',rs):.2f}% → {100*s('abst_2t',rs)/s('aptos_2t',rs):.2f}%")


if __name__ == "__main__":
    main()
