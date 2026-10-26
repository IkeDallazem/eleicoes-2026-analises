"""Controle de ritmo do coletor de logs (coletar_logs.py) para rodar sem supervisão (opcional).

Lê a última linha de collector_status.log a cada 30 s e escreve o teto em max_rate.txt, os dois na pasta do coletor
(padrão caminhos.LOGS; use --out se o coletor rodar com outro --out):
- sem 429 novo: sobe +2 req/s a cada 5 min, só quando o coletor está usando o teto atual, até --max;
- 429 novo: baixa o teto para 60% (mínimo --min) e espera 20 min antes de voltar a subir aos poucos.
- erros subindo (403, conexão recusada, timeout: bloqueio que não vem como 429): mesma reação do 429.
O próprio coletor também reage ao 429 na hora (metade do ritmo e pausa de 90 s). Registra cada mudança em controle_ritmo.log.
Padrão conservador (--min 3, --max 8, o mesmo teto padrão do coletor); tetos maiores ficam por conta e risco de quem roda.
"""
import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comum"))
import caminhos  # noqa: E402

OUT = caminhos.LOGS
STATUS = OUT / "collector_status.log"
CEILING = OUT / "max_rate.txt"
LOG = OUT / "controle_ritmo.log"
LINE = re.compile(r"ritmo ([\d.]+)/([\d.]+) req/s, 429: (\d+)")
ERRORS = re.compile(r"erro (\d+),")


def log(message):
    line = f"[{datetime.now():%H:%M:%S}] {message}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def last_status():
    try:
        with open(STATUS, "rb") as handle:
            handle.seek(0, 2)
            handle.seek(max(0, handle.tell() - 2000))
            tail = handle.read().decode("utf-8", "replace").strip().splitlines()
    except OSError:
        return None
    for line in reversed(tail):
        match = LINE.search(line)
        if match:
            errors = ERRORS.search(line)
            return (float(match.group(1)), float(match.group(2)), int(match.group(3)),
                    int(errors.group(1)) if errors else 0, STATUS.stat().st_mtime)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=caminhos.LOGS, help="pasta do coletor (a mesma do --out de coletar_logs.py)")
    ap.add_argument("--min", type=float, default=3)
    ap.add_argument("--max", type=float, default=8, help="teto máximo em req/s (valores maiores por conta e risco de quem roda)")
    ap.add_argument("--step", type=float, default=2)
    ap.add_argument("--up-every", type=int, default=300, help="segundos entre subidas")
    ap.add_argument("--cooldown", type=int, default=1200, help="segundos sem subir depois de um 429")
    ap.add_argument("--error-jump", type=int, default=50, help="seções novas com erro entre duas leituras que contam como bloqueio")
    args = ap.parse_args()
    global OUT, STATUS, CEILING, LOG
    OUT = args.out.resolve()
    STATUS, CEILING, LOG = OUT / "collector_status.log", OUT / "max_rate.txt", OUT / "controle_ritmo.log"
    current = float(CEILING.read_text().strip()) if CEILING.exists() else args.min
    status = last_status()
    base = status[2] if status else 0
    base_errors = status[3] if status else 0
    last_up, hold_until, warned_stale = time.time(), 0.0, False
    log(f"início: teto {current:g} req/s, faixa {args.min:g}–{args.max:g}, 429 até agora {base}, erros {base_errors}")
    while True:
        time.sleep(30)
        status = last_status()
        if status is None:
            continue
        rate, ceiling, throttles, errors, mtime = status
        now = time.time()
        if now - mtime > 300:
            if not warned_stale:
                log("aviso: o coletor não escreve status há mais de 5 min (parado ou reiniciando?)")
                warned_stale = True
            continue
        warned_stale = False
        if throttles < base:  # coletor reiniciado: o contador voltou a zero
            base = throttles
            continue
        if throttles > base:
            base = throttles
            current = max(args.min, round(current * 0.6))
            CEILING.write_text(f"{current:g}\n")
            hold_until, last_up = now + args.cooldown, now
            log(f"429 detectado (total {throttles}): teto baixou para {current:g} req/s; nova subida em {args.cooldown // 60} min")
            continue
        jump, base_errors = errors - base_errors, errors
        if jump >= args.error_jump:
            current = max(args.min, round(current * 0.6))
            CEILING.write_text(f"{current:g}\n")
            hold_until, last_up = now + args.cooldown, now
            log(f"aviso: +{jump} seções com erro em 30 s (possível bloqueio sem 429): teto baixou para {current:g} req/s; "
                f"nova subida em {args.cooldown // 60} min")
            continue
        if now >= hold_until and now - last_up >= args.up_every and current < args.max and rate >= 0.95 * ceiling:
            current = min(args.max, current + args.step)
            CEILING.write_text(f"{current:g}\n")
            last_up = now
            log(f"sem 429: teto subiu para {current:g} req/s (ritmo atual {rate:g})")


if __name__ == "__main__":
    main()
