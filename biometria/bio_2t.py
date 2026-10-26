"""2º turno 2026: mesma contagem do boletim de urna (eleitores com biometria não habilitados por ela), seção a seção, a partir
dos logs já baixados em DADOS/urna_logs (só leitura: sections.sqlite e day/). Grava DADOS/derivados/biometria/bio_2t_secoes.csv.
Uso: bio_2t.py [--ufs AC RR ...] [--saida arquivo.csv]
--ufs restringe a alguns estados (para testar); nesse caso, sem --saida, grava bio_2t_secoes_<UFs>.csv e não toca no arquivo
completo."""
import argparse
import csv
import gzip
import sqlite3
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "comum"))
from bio_parse import count_lines  # noqa: E402
import caminhos  # noqa: E402

ROOT = caminhos.LOGS


def work(item):
    uf, mun, zona, secao, rel = item
    with gzip.open(ROOT / rel, "rt", encoding="utf-8") as handle:
        c = count_lines(handle, "25/10/2026")
    return {"uf": uf, "cd_municipio": mun, "nr_zona": zona, "nr_secao": secao, **c}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--ufs", nargs="+", type=str.upper, help="só estes estados (siglas)")
    ap.add_argument("--saida", type=Path, help="arquivo CSV de saída")
    args = ap.parse_args()
    if args.ufs:  # aceita "RR AP AC" e "RR,AP,AC"
        args.ufs = [u for a in args.ufs for u in a.split(",") if u]
    out = args.saida or caminhos.saida("biometria") / (f"bio_2t_secoes_{'-'.join(args.ufs)}.csv" if args.ufs else "bio_2t_secoes.csv")
    db = sqlite3.connect(f"file:{ROOT / 'sections.sqlite'}?mode=ro", uri=True)
    items = [r for r in db.execute("SELECT uf, mun, zona, secao, path FROM logs ORDER BY uf, mun, zona, secao")
             if (not args.ufs or r[0] in args.ufs) and (ROOT / r[4]).exists()]
    print("logs:", len(items), flush=True)
    fields = ["uf", "cd_municipio", "nr_zona", "nr_secao", "votos", "com_biometria", "biom_sem_hab", "habilitados_bio", "sem_bio_total"]
    with open(out, "w", newline="", encoding="utf-8") as handle, ProcessPoolExecutor(8) as pool:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for i, row in enumerate(pool.map(work, items, chunksize=256), 1):
            writer.writerow(row)
            if i % 50000 == 0:
                print(i, flush=True)
    print("FIM", out, flush=True)


if __name__ == "__main__":
    main()
