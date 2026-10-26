"""Coletor dos logs de urna do 2º turno de 2026 publicados pelo TSE (arquivo-urna).

Varre o cs.json de cada UF, baixa o log (.jez = ZIP com logd.dat) de toda seção
já recebida e guarda somente as linhas de 25/10/2026 em diante, em gzip UTF-8.
Por padrão grava em caminhos.LOGS (DADOS/urna_logs): sections.sqlite (WAL) e day/{UF}/*.log.gz,
lidos por relatorio_17h.py. Somente a CLI acessa a rede; Ctrl+C encerra e a próxima execução continua de onde parou.
Ritmo padrão conservador (começa em 3 req/s, teto de 8 req/s, metade do ritmo e pausa a cada HTTP 429);
taxas maiores (--rate, --max-rate, max_rate.txt) ficam por conta e risco de quem roda o coletor.
"""
from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
import gzip
import http.client
import io
import json
from pathlib import Path
import sqlite3
import sys
import threading
import time
import zipfile
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comum"))
import caminhos  # noqa: E402

HOST = "resultados.tse.jus.br"
CICLO, PLEITO = "ele2026", "3221"
PLEITO_ARQ = PLEITO.zfill(6)  # nomes de arquivo usam o pleito com 6 dígitos
UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO ZZ".split()
DAY_PREFIXES = ("25/10/2026", "26/10/2026")
RAW_SAMPLE_MOD = 50  # ~2% das seções guardam também o .jez original
RAW_FIRST_PER_UF = 3
# BU (boletim de urna) junto com o log: opção --bu (ou o arquivo bu_enabled.txt na pasta de saída, lido a cada 30 s,
# para ligar sem reiniciar).
FETCH_BU = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS sections(
  uf TEXT, mun TEXT, zona TEXT, secao TEXT, mun_name TEXT,
  received_at TEXT, status TEXT, error TEXT, fetched_at TEXT,
  attempts INT DEFAULT 0, retry_at REAL DEFAULT 0, sort_key INT,
  PRIMARY KEY(uf, mun, zona, secao));
CREATE TABLE IF NOT EXISTS logs(
  uf TEXT, mun TEXT, zona TEXT, secao TEXT, hash TEXT, path TEXT,
  bytes_raw INT, lines INT, received_at TEXT,
  PRIMARY KEY(uf, mun, zona, secao, hash));
CREATE INDEX IF NOT EXISTS sections_status ON sections(status, sort_key);
CREATE TABLE IF NOT EXISTS bus(
  uf TEXT, mun TEXT, zona TEXT, secao TEXT, hash TEXT, path TEXT, bytes INT,
  PRIMARY KEY(uf, mun, zona, secao, hash));
"""


def utc_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RateLimiter:
    """Ritmo global adaptativo: 429 pausa todas as threads e reduz a taxa; sucessos a recuperam devagar."""

    def __init__(self, rate, ceiling=None, floor=0.5):
        self.rate, self.ceiling, self.floor = rate, max(rate, ceiling or rate), floor
        self.learned = float("inf")  # teto aprendido com o último 429; um teto pedido de fora nunca passa dele
        self.last_throttle = 0.0     # o limite aprendido é esquecido 15 min depois do último 429 (ver Collector.report)
        self.lock = threading.Lock()
        self.next_at = 0.0
        self.paused_until = 0.0
        self.throttles = 0

    def acquire(self):
        with self.lock:
            now = time.time()
            start = max(now, self.next_at, self.paused_until)
            self.next_at = start + 1.0 / self.rate
        time.sleep(max(0.0, start - now))

    def pause(self, seconds):
        with self.lock:
            self.paused_until = max(self.paused_until, time.time() + seconds)

    def throttled(self, retry_after=None):
        with self.lock:
            # Aprende o limite: o teto fica abaixo da taxa que gerou o 429.
            self.learned = min(self.learned, self.rate * 0.8)
            self.last_throttle = time.time()
            self.ceiling = max(self.floor, min(self.ceiling, self.learned))
            self.rate = max(self.floor, self.rate * 0.5)
            self.paused_until = max(self.paused_until, time.time() + (retry_after or 90))
            self.throttles += 1

    def succeeded(self):
        with self.lock:
            self.rate = min(self.ceiling, self.rate + 0.01)

    def set_ceiling(self, value):
        with self.lock:
            self.ceiling = max(self.floor, min(value, self.learned))
            self.rate = min(self.rate, self.ceiling)


class HttpClient:
    """Uma conexão HTTPS persistente por thread, com reconexão e repetição."""

    def __init__(self, timeout=20, rate=3.0, max_rate=None):
        self.timeout = timeout
        self.local = threading.local()
        self.limiter = RateLimiter(rate, max_rate)

    def _conn(self, fresh=False):
        conn = getattr(self.local, "conn", None)
        if fresh or conn is None:
            if conn is not None:
                conn.close()
            conn = http.client.HTTPSConnection(HOST, timeout=self.timeout)
            self.local.conn = conn
        return conn

    def get(self, path, headers=None, tries=6):
        last = None
        for attempt in range(tries):
            self.limiter.acquire()
            try:
                conn = self._conn(fresh=attempt > 0)
                conn.request("GET", path, headers={"User-Agent": caminhos.USER_AGENT, "Accept-Encoding": "identity", **(headers or {})})
                response = conn.getresponse()
                body = response.read()
                if response.status == 429:
                    last = RuntimeError("HTTP 429")
                    retry = response.headers.get("Retry-After")
                    self.limiter.throttled(float(retry) if retry and retry.isdigit() else None)
                    continue
                if response.status in (500, 502, 503, 504):
                    last = RuntimeError(f"HTTP {response.status}")
                    time.sleep(min(30, 2 ** attempt))
                    continue
                self.limiter.succeeded()
                return response.status, body, response.headers
            except (OSError, http.client.HTTPException) as error:
                last = error
                time.sleep(min(10, 0.5 * 2 ** attempt))
        raise RuntimeError(f"{path}: {last}")


def section_dir(uf, mun, zona, secao):
    return f"/oficial/{CICLO}/arquivo-urna/{PLEITO}/dados/{uf.lower()}/{mun}/{zona}/{secao}"


def day_lines(raw_zip):
    """Extrai logd.dat (latin-1) e devolve as linhas do dia da votação."""
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
        name = next((n for n in archive.namelist() if n.lower().endswith(".dat")), archive.namelist()[0])
        text = archive.read(name).decode("latin-1")
    return [line for line in text.splitlines() if line.startswith(DAY_PREFIXES)]


def fetch_section(client, out_dir, row, keep_raw, known_hashes=frozenset(), known_bus=frozenset()):
    """Baixa aux.json e os logs recebidos de uma seção; roda numa thread do pool.

    Logs cujo hash já foi baixado (seção reenfileirada porque o cs.json mudou a hora de recebimento) não são baixados de novo.
    """
    uf, mun, zona, secao = row["uf"], row["mun"], row["zona"], row["secao"]
    folder = section_dir(uf, mun, zona, secao)
    status, body, _ = client.get(f"{folder}/p{PLEITO_ARQ}-{uf.lower()}-m{mun}-z{zona}-s{secao}-aux.json")
    if status == 404:
        return {"row": row, "status": "error", "error": "aux 404", "logs": []}
    if status != 200:
        return {"row": row, "status": "error", "error": f"aux HTTP {status}", "logs": []}
    aux = json.loads(body.decode("utf-8-sig"))
    hashes = [h for h in aux.get("hashes", []) if str(h.get("st", "")).lower().startswith("receb")] or aux.get("hashes", [])
    logs = []
    for entry in hashes:
        item = next((a for a in entry.get("arq", []) if a.get("tp") == "log"), None)
        if item is None or entry["hash"] in known_hashes:
            continue
        status, raw, _ = client.get(f"{folder}/{entry['hash']}/{item['nm']}")
        if status != 200:
            return {"row": row, "status": "error", "error": f"log HTTP {status}", "logs": []}
        stem = f"{mun}-{zona}-{secao}-{entry['hash'][:16]}"
        lines = day_lines(raw)
        rel = Path("day") / uf / f"{stem}.log.gz"
        target = out_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(".tmp")
        with gzip.open(temp, "wt", encoding="utf-8", newline="\n", compresslevel=6) as handle:
            handle.write("\n".join(lines))
            if lines:
                handle.write("\n")
        temp.replace(target)
        # Log sem linhas do dia (relógio errado?) também guarda o original para auditoria.
        if keep_raw or not lines:
            raw_target = out_dir / "raw" / uf / f"{stem}.jez"
            raw_target.parent.mkdir(parents=True, exist_ok=True)
            raw_target.write_bytes(raw)
        logs.append({"hash": entry["hash"], "path": rel.as_posix(), "bytes_raw": len(raw), "lines": len(lines), "received_at": f"{entry.get('dr', '')} {entry.get('hr', '')}".strip()})
    # Boletim de urna (resultado da seção no 2º turno), para comparar com o 1º turno; falha aqui não derruba o log.
    bus = []
    for entry in (hashes if FETCH_BU else []):
        item = next((a for a in entry.get("arq", []) if str(a.get("nm", "")).endswith("-bu.dat")), None)
        if item is None or entry["hash"] in known_bus:
            continue
        status, raw, _ = client.get(f"{folder}/{entry['hash']}/{item['nm']}")
        bus.append(save_bu(out_dir, uf, mun, zona, secao, entry["hash"], raw if status == 200 else None))
    return {"row": row, "status": "fetched" if logs or known_hashes else "nolog", "error": None, "logs": logs, "bus": bus}


def save_bu(out_dir, uf, mun, zona, secao, hash_, raw):
    if raw is None:
        return {"hash": hash_, "path": None, "bytes": 0}
    rel = Path("bu") / uf / f"{mun}-{zona}-{secao}-{hash_[:16]}-bu.dat"
    target = out_dir / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return {"hash": hash_, "path": rel.as_posix(), "bytes": len(raw)}


def fetch_bu_only(client, out_dir, row):
    """Só o BU de uma seção cujo log já foi baixado (o hash já é conhecido): uma requisição."""
    uf, mun, zona, secao = row["uf"], row["mun"], row["zona"], row["secao"]
    name = f"o{PLEITO_ARQ[1:]}{uf.lower()}{mun}{zona}{secao}-bu.dat"
    status, raw, _ = client.get(f"{section_dir(uf, mun, zona, secao)}/{row['hash']}/{name}")
    return {"row": row, "status": "bu", "error": None, "logs": [], "bus": [save_bu(out_dir, uf, mun, zona, secao, row["hash"], raw if status == 200 else None)]}


class Collector:
    def __init__(self, out_dir, workers, scan_interval, rate, max_rate):
        self.out_dir = out_dir
        self.fetch_bu = False
        self.workers = workers
        self.scan_interval = scan_interval
        self.client = HttpClient(rate=rate, max_rate=max_rate)
        out_dir.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(out_dir / "sections.sqlite", timeout=30)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(SCHEMA)
        self.etags = {}
        self.raw_count = {uf: 0 for uf in UFS}
        self.stats = {"ok": 0, "err": 0, "bytes": 0, "t0": time.time()}

    def scan(self):
        """Lê o cs.json de cada UF e enfileira seções recebidas ou com novo recebimento."""
        changed = 0
        for uf in UFS:
            path = f"/oficial/{CICLO}/arquivo-urna/{PLEITO}/config/{uf.lower()}/{uf.lower()}-p{PLEITO_ARQ}-cs.json"
            try:
                status, body, headers = self.client.get(path, {"If-None-Match": self.etags[uf]} if uf in self.etags else None)
            except RuntimeError as error:
                print(f"[scan] {uf}: {error}", flush=True)
                continue
            if status == 304:
                continue
            if status != 200:
                print(f"[scan] {uf}: HTTP {status}", flush=True)
                continue
            if headers.get("ETag"):
                self.etags[uf] = headers["ETag"]
            config = json.loads(body.decode("utf-8-sig"))
            known = {(m, z, s): (r, st) for m, z, s, r, st in self.db.execute("SELECT mun, zona, secao, received_at, status FROM sections WHERE uf=?", (uf,))}
            inserts, requeue = [], []
            for abr in config.get("abr", []):
                for mu in abr.get("mu", []):
                    for zon in mu.get("zon", []):
                        for sec in zon.get("sec", []):
                            key = (mu["cd"], zon["cd"], sec["ns"])
                            received = f"{sec['da']} {sec['ha']}" if sec.get("da") else None
                            old = known.get(key)
                            if old is None:
                                sort_key = zlib.crc32(f"{uf}{key}".encode()) & 0x7FFFFFFF
                                inserts.append((uf, *key, mu.get("nm"), received, "queued" if received else "waiting", sort_key))
                            elif received and received != old[0]:
                                requeue.append((received, uf, *key))
            with self.db:
                self.db.executemany("INSERT OR IGNORE INTO sections(uf, mun, zona, secao, mun_name, received_at, status, sort_key) VALUES (?,?,?,?,?,?,?,?)", inserts)
                self.db.executemany("UPDATE sections SET received_at=?, status='queued', attempts=0, retry_at=0 WHERE uf=? AND mun=? AND zona=? AND secao=?", requeue)
            changed += len(inserts) + len(requeue)
        return changed

    def pending(self, limit):
        # Metade das vagas para o BU das seções cujo log já temos (1 requisição cada, hash conhecido), metade para a fila
        # normal: os logs não param enquanto o BU atrasado é baixado.
        backfill = self.db.execute(
            "SELECT l.uf, l.mun, l.zona, l.secao, l.hash FROM logs l WHERE NOT EXISTS (SELECT 1 FROM bus b WHERE b.uf=l.uf AND b.mun=l.mun "
            "AND b.zona=l.zona AND b.secao=l.secao AND b.hash=l.hash) LIMIT ?", (limit // 2,)).fetchall() if FETCH_BU else []
        # sort_key pseudoaleatório espalha a coleta entre UFs e municípios desde o início.
        rows = self.db.execute(
            "SELECT uf, mun, zona, secao FROM sections WHERE (status='queued') OR (status='error' AND retry_at<=? AND (attempts<8 OR error LIKE '%404%')) ORDER BY sort_key LIMIT ?",
            (time.time(), limit - len(backfill))).fetchall()
        return ([dict(zip(("uf", "mun", "zona", "secao", "hash"), r)) for r in backfill]
                + [dict(zip(("uf", "mun", "zona", "secao"), r)) for r in rows])

    def save(self, result):
        row = result["row"]
        key = (row["uf"], row["mun"], row["zona"], row["secao"])
        with self.db:
            for bu in result.get("bus", []):
                self.db.execute("INSERT OR REPLACE INTO bus(uf, mun, zona, secao, hash, path, bytes) VALUES (?,?,?,?,?,?,?)", (*key, bu["hash"], bu["path"], bu["bytes"]))
            if "hash" in row:
                # Linha de BU avulso: a seção já está baixada; uma falha só fica registrada no BU (path NULL), sem nova tentativa.
                if result["status"] == "error":
                    self.db.execute("INSERT OR REPLACE INTO bus(uf, mun, zona, secao, hash, path, bytes) VALUES (?,?,?,?,?,NULL,0)", (*key, row["hash"]))
                return
            if result["status"] == "error":
                # Log 404: o TSE marca a seção como recebida antes de publicar o arquivo. Espera crescente
                # (10, 20, 40, 60 min) para que as retentativas não tomem o ritmo das seções ainda não baixadas.
                is_404 = "404" in (result["error"] or "")
                self.db.execute("UPDATE sections SET status='error', error=?, retry_at=? + CASE WHEN ? THEN min(3600, 600 * (1 << min(attempts, 3))) ELSE 120 END, "
                                "attempts=attempts+1 WHERE uf=? AND mun=? AND zona=? AND secao=?",
                                (result["error"], time.time(), is_404, *key))
                self.stats["err"] += 1
                return
            for log in result["logs"]:
                self.db.execute("INSERT OR REPLACE INTO logs(uf, mun, zona, secao, hash, path, bytes_raw, lines, received_at) VALUES (?,?,?,?,?,?,?,?,?)",
                                (*key, log["hash"], log["path"], log["bytes_raw"], log["lines"], log["received_at"]))
                self.stats["bytes"] += log["bytes_raw"]
            self.db.execute("UPDATE sections SET status=?, error=NULL, fetched_at=? WHERE uf=? AND mun=? AND zona=? AND secao=?",
                            (result["status"], utc_iso(), *key))
            self.stats["ok"] += 1

    def report(self):
        global FETCH_BU
        FETCH_BU = self.fetch_bu or (self.out_dir / "bu_enabled.txt").exists()
        # 15 min sem 429: esquece o limite aprendido e deixa o controle de ritmo (max_rate.txt) subir de novo aos poucos.
        limiter = self.client.limiter
        if limiter.last_throttle and time.time() - limiter.last_throttle > 900 and limiter.learned != float("inf"):
            limiter.learned = float("inf")
        # Teto ajustável sem reiniciar: max_rate.txt na pasta de saída (nunca acima do limite aprendido com 429).
        try:
            wanted = float((self.out_dir / "max_rate.txt").read_text().strip())
            if abs(wanted - self.client.limiter.ceiling) > 0.01:
                self.client.limiter.set_ceiling(wanted)
        except (OSError, ValueError):
            pass
        counts = dict(self.db.execute("SELECT status, COUNT(*) FROM sections GROUP BY status").fetchall())
        elapsed = max(1, time.time() - self.stats["t0"])
        total = sum(counts.values())
        line = (f"[{datetime.now():%H:%M:%S}] seções {total}: baixadas {counts.get('fetched', 0)}, fila {counts.get('queued', 0)}, "
                f"aguardando TSE {counts.get('waiting', 0)}, erro {counts.get('error', 0)}, sem log {counts.get('nolog', 0)} | "
                f"{self.stats['ok'] / elapsed:.1f} seções/s, {self.stats['bytes'] / elapsed / 1e6:.1f} MB/s, ritmo {self.client.limiter.rate:.1f}/{self.client.limiter.ceiling:.1f} req/s, 429: {self.client.limiter.throttles}")
        print(line, flush=True)
        with open(self.out_dir / "collector_status.log", "a", encoding="utf-8") as status_log:
            status_log.write(line + "\n")

    def run(self, once=False):
        last_scan = 0.0
        last_report = 0.0
        inflight = {}
        with ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="urna") as pool:
            while True:
                now = time.time()
                if now - last_scan >= self.scan_interval and now >= self.client.limiter.paused_until:
                    changed = self.scan()
                    last_scan = time.time()
                    print(f"[scan] {changed} seções novas ou recebidas de novo.", flush=True)
                if len(inflight) < self.workers * 4:
                    busy = {tuple(r[k] for k in ("uf", "mun", "zona", "secao")) for r in inflight.values()}
                    for row in self.pending(self.workers * 8):
                        key = tuple(row[k] for k in ("uf", "mun", "zona", "secao"))
                        if key in busy:
                            continue
                        if "hash" in row:
                            inflight[pool.submit(fetch_bu_only, self.client, self.out_dir, row)] = row
                            busy.add(key)
                            continue
                        keep = self.raw_count[row["uf"]] < RAW_FIRST_PER_UF or zlib.crc32("-".join(key).encode()) % RAW_SAMPLE_MOD == 0
                        if keep:
                            self.raw_count[row["uf"]] += 1
                        known = {h for (h,) in self.db.execute("SELECT hash FROM logs WHERE uf=? AND mun=? AND zona=? AND secao=?", key)}
                        known_bus = {h for (h,) in self.db.execute("SELECT hash FROM bus WHERE uf=? AND mun=? AND zona=? AND secao=?", key)}
                        inflight[pool.submit(fetch_section, self.client, self.out_dir, row, keep, known, known_bus)] = row
                        busy.add(key)
                if not inflight:
                    if once:
                        break
                    time.sleep(5)
                    continue
                done, _ = wait(list(inflight), timeout=5, return_when=FIRST_COMPLETED)
                for future in done:
                    row = inflight.pop(future)
                    try:
                        self.save(future.result())
                    except Exception as error:  # noqa: BLE001 - registra e segue
                        self.save({"row": row, "status": "error", "error": str(error)[:300], "logs": []})
                if time.time() - last_report >= 30:
                    self.report()
                    last_report = time.time()
        self.report()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=caminhos.LOGS, help="pasta de saída (padrão: DADOS/urna_logs)")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--rate", type=float, default=3, help="requisições por segundo no início (cai pela metade a cada HTTP 429)")
    parser.add_argument("--max-rate", type=float, default=8,
                        help="teto de requisições por segundo; sobe devagar até ele sem 429 (valores maiores por conta e risco de quem roda)")
    parser.add_argument("--scan-interval", type=float, default=120, help="segundos entre varreduras dos cs.json")
    parser.add_argument("--once", action="store_true",
                        help="encerra quando a fila esvazia; seções com erro que ainda aguardam nova tentativa ficam para a próxima execução")
    parser.add_argument("--bu", action="store_true",
                        help="baixa também o boletim de urna (BU) de cada seção, em bu/<UF>/ (usado em biometria/conferir_bu_2t.py)")
    parser.add_argument("--start-at", help="HH:MM local; nenhuma requisição ao TSE antes desse horário")
    args = parser.parse_args(argv)
    if args.start_at:
        start = datetime.combine(datetime.now().date(), datetime.strptime(args.start_at, "%H:%M").time())
        wait_seconds = (start - datetime.now()).total_seconds()
        if wait_seconds > 0:
            print(f"Aguardando até {args.start_at} para começar (nenhuma requisição ao TSE até lá).", flush=True)
            try:
                time.sleep(wait_seconds)
            except KeyboardInterrupt:
                print("\nCancelado antes de começar.", flush=True)
                return 0
    if sys.platform == "win32":
        # Enquanto o coletor roda, pede ao Windows para não suspender por inatividade (ES_CONTINUOUS | ES_SYSTEM_REQUIRED).
        # Vale só enquanto o processo roda; a tela pode desligar.
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    collector = Collector(args.out.resolve(), max(1, args.workers), max(30, args.scan_interval), max(0.5, args.rate), max(0.5, args.max_rate))
    collector.fetch_bu = args.bu
    try:
        collector.run(once=args.once)
    except KeyboardInterrupt:
        print("\nColeta interrompida; o progresso está salvo.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
