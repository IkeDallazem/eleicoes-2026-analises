"""Uma passada nos logs do 2º turno (inclui o log da urna original nas seções com urna substituída) e grava, por seção:
votos; tipo de habilitação (digital / biometria cadastrada mas não reconhecida, liberada pelo mesário / sem biometria
cadastrada); votos por hora de Brasília (pela hora da identificação do eleitor), por tipo; tentativas de digital.

Entradas: DADOS/urna_logs (sections.sqlite e day/, de logs_urna/coletar_logs.py) e DADOS/jez_contingencia (.jez completos das
seções com urna substituída, de biometria/refetch.py). Só leitura.
Saída: DADOS/derivados/comparecimento_dia/secoes.jsonl (uma linha por seção). Com --ufs (teste parcial) a saída é
secoes_<UFs>.jsonl, por exemplo secoes_AC-AP-RR.jsonl, e o arquivo completo não é tocado.
Uso: extract.py [--ufs RR,AP,AC] [--workers 8]"""
import argparse
import gzip
import json
import re
import sqlite3
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "comum"))
sys.path.insert(0, str(HERE.parent / "biometria"))
import caminhos  # noqa: E402
from bio_nested import logs_in, other_section  # noqa: E402

ROOT = caminhos.LOGS
NESTED = caminhos.DADOS / "jez_contingencia"

DAY = "25/10/2026"
# Fuso: a votação abre às 8h de Brasília; o relógio da urna fica na hora local (mesma regra de logs_urna/relatorio_17h.py).
TABLE = {"AC": 120, "AM": 60, "RO": 60, "RR": 60, "MT": 60, "MS": 60}
TABLE_MUN = {("PE", "30015"): -60}  # Fernando de Noronha, UTC-2
TRY = re.compile(r"Solicita digital\. Tentativa \[?(\d+)\]? de \[?(\d+)\]?")  # no log: "Tentativa [1] de [4]"
KINDS = ("bio", "falhou", "semcad")


def secs(hms):
    h, m, s = hms.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


def offset(uf, mun, first_hab):
    if (uf, mun) in TABLE_MUN:
        return TABLE_MUN[(uf, mun)] * 60
    off = TABLE.get(uf, 0) * 60
    if first_hab is not None:
        off = max(off, 7200 if first_hab < 6.9 * 3600 else 3600 if first_hab < 7.9 * 3600 else 0)
    return off


def scan(lines, uf, mun):
    """Lista de votos (hora da identificação em s, tipo, tentativas de digital, n de tentativas máximo, timeouts) e 1ª habilitação."""
    votes, first_hab = [], None
    ident = None
    pediu = bio = False
    tries = maxtries = timeouts = 0
    for line in lines:
        r = line.rstrip("\n").split("\t")
        if len(r) < 5 or not r[0].startswith(DAY):
            continue
        msg, t = r[4], r[0][11:19]
        if msg.startswith("Aguardando digitação do identificador"):
            ident, pediu, bio, tries, maxtries, timeouts = None, False, False, 0, 0, 0
        elif msg.startswith("Identificador do eleitor digitado"):
            ident = secs(t)
        elif msg.startswith("Solicita digital. Tentativa"):
            pediu = True
            m = TRY.match(msg)
            if m:
                tries = max(tries, int(m.group(1))); maxtries = max(maxtries, int(m.group(2)))
        elif msg.startswith("Timeout de reconhecimento do dedo"):
            timeouts += 1
        elif msg.startswith("Tipo de habilitação do eleitor [biométrica]"):
            bio = True
        elif msg == "Eleitor foi habilitado":
            if first_hab is None:
                first_hab = secs(t)
        elif msg == "O voto do eleitor foi computado":
            kind = "bio" if bio else "falhou" if pediu else "semcad"
            votes.append((ident if ident is not None else secs(t), kind, tries, maxtries, timeouts))
            ident, pediu, bio, tries, maxtries, timeouts = None, False, False, 0, 0, 0
    return votes, first_hab


def summarize(key, groups):
    uf, mun, zona, secao = key
    out = {"uf": uf, "mun": mun, "zona": zona, "secao": secao, "votos": 0, "n_urnas": 0,
           "tipo": {k: 0 for k in KINDS}, "hora": {}, "tent_ok": [0] * 9, "tent_falhou": [0] * 9, "max_de": {}, "timeouts": 0}
    for lines in groups:
        votes, first_hab = scan(lines, uf, mun)
        if not votes:
            continue
        out["n_urnas"] += 1
        off = offset(uf, mun, first_hab)
        for t, kind, tries, maxtries, timeouts in votes:
            out["votos"] += 1
            out["tipo"][kind] += 1
            h = str(min(23, (t + off) // 3600))
            out["hora"].setdefault(h, {k: 0 for k in KINDS})[kind] += 1
            if kind != "semcad":
                (out["tent_ok"] if kind == "bio" else out["tent_falhou"])[min(tries, 8)] += 1
                out["max_de"][str(maxtries)] = out["max_de"].get(str(maxtries), 0) + 1
            out["timeouts"] += timeouts
    return out


def work(item):
    uf, mun, zona, secao, rel = item
    folder = NESTED / uf / f"{mun}-{zona}-{secao}"
    if (folder / "ok").exists():
        # Seção com urna substituída: logd.dat + .jez aninhados, agrupados por urna, sem repetir linhas (como bio_nested.py).
        urnas, seen = {}, set()
        for jez in sorted(folder.glob("*.jez")):
            for _, lines in logs_in(jez.read_bytes()):
                for line in lines:
                    parts = line.split("\t", 3)
                    urnas.setdefault(parts[2].strip() if len(parts) > 3 else "", []).append(line)
        groups = []
        for uid, lines in urnas.items():
            merged = []
            for line in sorted(lines, key=lambda l: l[:19]):
                if line not in seen:
                    seen.add(line); merged.append(line)
            if not other_section(merged, secao):
                groups.append(merged)
    else:
        with gzip.open(ROOT / rel, "rt", encoding="utf-8") as handle:
            groups = [handle.read().splitlines()]
    return summarize((uf, mun, zona, secao), groups)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Uma linha por seção do 2º turno, a partir dos logs das urnas.")
    ap.add_argument("--ufs", help="só estas UFs, separadas por vírgula (ex.: RR,AP,AC); grava secoes_<UFs>.jsonl")
    ap.add_argument("--workers", type=int, default=8, help="processos em paralelo (padrão: 8)")
    args = ap.parse_args()
    ufs = {u.strip().upper() for u in args.ufs.split(",") if u.strip()} if args.ufs else None
    out = caminhos.saida("comparecimento_dia") / ("secoes.jsonl" if ufs is None else f"secoes_{'-'.join(sorted(ufs))}.jsonl")
    db = sqlite3.connect(f"file:{ROOT / 'sections.sqlite'}?mode=ro", uri=True)
    items = [r for r in db.execute("SELECT uf, mun, zona, secao, path FROM logs ORDER BY uf, mun, zona, secao")
             if (ufs is None or r[0] in ufs) and (ROOT / r[4]).exists()]
    print("seções:", len(items), flush=True)
    with open(out, "w", encoding="utf-8") as handle, ProcessPoolExecutor(args.workers) as pool:
        for i, row in enumerate(pool.map(work, items, chunksize=256), 1):
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")
            if i % 50000 == 0:
                print(i, flush=True)
    print("FIM:", out, flush=True)


if __name__ == "__main__":
    main()
