"""Lista as seções do 2º turno com urna de contingência (urna substituída durante a votação), para refetch.py.

A coleta (logs_urna/coletar_logs.py) guarda só o logd.dat principal do .jez de cada seção. Quando a urna foi trocada, esse é o
log da urna de contingência, que traz no dia da votação a linha "Log interno da urna de contingência"; o log da urna original
vem aninhado no .jez e precisa ser baixado de novo (refetch.py) e recontado (bio_nested.py).

Regra: seções do Brasil (sem o exterior, ZZ) cujo log do dia 25/10/2026 tem uma linha cuja mensagem (5ª coluna) começa com
"Log interno da urna de contingência", mais as seções do Brasil com 0 votos em bio_2t_secoes.csv (se o arquivo já existir).
Na coleta de 2026 são 1.971 seções; as 16 com 0 votos já estão entre elas.
Lê DADOS/urna_logs (só leitura). Grava DADOS/derivados/biometria/refetch_list.json: [[uf, mun, zona, secao], ...] em ordem.
Uso: lista_contingencia.py [--ufs AC RR ...] [--saida arquivo.json]
--ufs restringe a alguns estados (para testar); nesse caso, sem --saida, grava refetch_list_<UFs>.json."""
import argparse
import csv
import gzip
import json
import sqlite3
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "comum"))
import caminhos  # noqa: E402

ROOT = caminhos.LOGS
DAY = "25/10/2026"
MSG = "Log interno da urna de contingência"


def work(item):
    """A chave da seção se o log do dia tem a linha da urna de contingência; senão None."""
    uf, mun, zona, secao, rel = item
    with gzip.open(ROOT / rel, "rt", encoding="utf-8") as handle:
        for line in handle:
            r = line.rstrip("\n").split("\t")
            if len(r) >= 5 and r[0].startswith(DAY) and r[4].startswith(MSG):
                return (uf, mun, zona, secao)
    return None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--ufs", nargs="+", type=str.upper, help="só estes estados (siglas)")
    ap.add_argument("--saida", type=Path, help="arquivo JSON de saída")
    args = ap.parse_args()
    if args.ufs:  # aceita "RR AP AC" e "RR,AP,AC"
        args.ufs = [u for a in args.ufs for u in a.split(",") if u]
    pasta = caminhos.saida("biometria")
    out = args.saida or pasta / (f"refetch_list_{'-'.join(args.ufs)}.json" if args.ufs else "refetch_list.json")
    db = sqlite3.connect(f"file:{ROOT / 'sections.sqlite'}?mode=ro", uri=True)
    items = [r for r in db.execute("SELECT uf, mun, zona, secao, path FROM logs WHERE uf<>'ZZ' ORDER BY uf, mun, zona, secao")
             if not args.ufs or r[0] in args.ufs]
    print("logs:", len(items), flush=True)
    contig = set()
    with ProcessPoolExecutor(8) as pool:
        for i, key in enumerate(pool.map(work, items, chunksize=256), 1):
            if key:
                contig.add(key)
            if i % 50000 == 0:
                print(i, flush=True)
    zero = set()
    csv2 = pasta / "bio_2t_secoes.csv"
    if csv2.exists():
        zero = {(r["uf"], r["cd_municipio"], r["nr_zona"], r["nr_secao"]) for r in csv.DictReader(open(csv2, encoding="utf-8"))
                if r["uf"] != "ZZ" and int(r["votos"]) == 0 and (not args.ufs or r["uf"] in args.ufs)}
    else:
        print("aviso: bio_2t_secoes.csv ainda não existe; só a regra da urna de contingência", flush=True)
    print(f"urna de contingência: {len(contig)} | 0 votos: {len(zero)}, {len(zero - contig)} delas sem a linha de contingência", flush=True)
    json.dump(sorted(contig | zero), open(out, "w"))
    print("FIM", len(contig | zero), "seções ->", out, flush=True)


if __name__ == "__main__":
    main()
