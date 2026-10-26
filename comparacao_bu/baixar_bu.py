"""Baixa os boletins de urna (BU binário, o03221...-bu.dat) do 2º turno, com ritmo muito conservador.

Uma conexão, requisições sequenciais, no máximo ~1,7/s (intervalo mínimo configurável, padrão 0,6 s),
User-Agent caminhos.USER_AGENT. HTTP 429: para tudo por 10 minutos e volta com intervalo dobrado; erros de rede e 5xx
são repetidos com espera crescente. Intervalos menores que o padrão ficam por conta e risco de quem roda.
Arquivos ficam em caminhos.DADOS/bu_2t/{UF}/{mun}-{zona}-{secao}-bu.dat (com _status.csv) e não são baixados de novo.

Uso: python baixar_bu.py [LISTA.csv] [intervalo_s]   (colunas uf;mun;zona;secao;hash)
Sem LISTA.csv usa dados_congelados/download.csv (a amostra da comparação publicada, 525 seções);
--amostra-nova usa o download.csv gerado por amostra.py em caminhos.saida("comparacao_bu").
"""
import csv
import http.client
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "comum"))
import caminhos  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
OUT = caminhos.DADOS / "bu_2t"
HOST = "resultados.tse.jus.br"
UA = caminhos.USER_AGENT
KIND = "bu.dat"  # imgbu.dat não está publicado (NoSuchKey); o BU binário (ASN.1) está


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def url_path(uf, mun, zona, secao, h):
    u = uf.lower()
    return f"/oficial/ele2026/arquivo-urna/3221/dados/{u}/{mun}/{zona}/{secao}/{h}/o03221{u}{mun}{zona}{secao}-{KIND}"


def target(uf, mun, zona, secao):
    return OUT / uf / f"{mun}-{zona}-{secao}-{KIND}"


class Client:
    def __init__(self, interval=0.6):
        self.interval = interval
        self.last = 0.0
        self.conn = None
        self.n = 0
        self.throttles = 0

    def _wait(self):
        delay = self.last + self.interval - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        self.last = time.monotonic()

    def get(self, path):
        for attempt in range(4):
            self._wait()
            try:
                if self.conn is None:
                    self.conn = http.client.HTTPSConnection(HOST, timeout=30)
                self.conn.request("GET", path, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
                resp = self.conn.getresponse()
                body = resp.read()
                self.n += 1
            except (OSError, http.client.HTTPException) as e:
                log(f"erro de rede ({e}); nova conexão em {2 ** attempt * 2} s")
                if self.conn is not None:
                    self.conn.close()
                self.conn = None
                time.sleep(2 ** attempt * 2)
                continue
            if resp.status == 429:
                self.throttles += 1
                self.interval = max(self.interval * 2, 1.2)
                log(f"HTTP 429 — pausa total de 10 minutos; depois intervalo de {self.interval:.1f} s")
                self.conn.close()
                self.conn = None
                time.sleep(600)
                continue
            if resp.status in (500, 502, 503, 504):
                time.sleep(min(30, 4 * 2 ** attempt))
                continue
            if resp.headers.get("Connection", "").lower() == "close":
                self.conn.close()
                self.conn = None
            return resp.status, body
        return None, b""


def main():
    args = [a for a in sys.argv[1:] if a != "--amostra-nova"]
    default = (caminhos.saida("comparacao_bu") if "--amostra-nova" in sys.argv else HERE / "dados_congelados") / "download.csv"
    rows = list(csv.DictReader(open(args[0] if args else default, encoding="utf-8-sig"), delimiter=";"))
    client = Client(float(args[1]) if len(args) > 1 else 0.6)
    status_log = OUT / "_status.csv"
    OUT.mkdir(parents=True, exist_ok=True)
    seen = {}
    if status_log.exists():
        for r in csv.DictReader(open(status_log, encoding="utf-8"), delimiter=";"):
            seen[(r["uf"], r["mun"], r["zona"], r["secao"])] = r["status"]
    done = skipped = 0
    with open(status_log, "a", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        if fh.tell() == 0:
            w.writerow(["uf", "mun", "zona", "secao", "hash", "status", "bytes", "at"])
        for i, r in enumerate(rows, 1):
            key = (r["uf"], r["mun"], r["zona"], r["secao"])
            t = target(*key)
            if t.exists() or seen.get(key) == "404":
                skipped += 1
                continue
            st, body = client.get(url_path(*key, r["hash"]))
            if st == 200:
                t.parent.mkdir(parents=True, exist_ok=True)
                tmp = t.with_suffix(".tmp")
                tmp.write_bytes(body)
                tmp.replace(t)
            w.writerow([*key, r["hash"], st, len(body), datetime.now().isoformat(timespec="seconds")])
            fh.flush()
            done += 1
            if done % 50 == 0:
                log(f"{i}/{len(rows)} · {client.n} requisições · 429: {client.throttles}")
    log(f"fim: {done} requisições novas, {skipped} já em cache, 429: {client.throttles}")


if __name__ == "__main__":
    main()
