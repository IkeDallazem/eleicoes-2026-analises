"""Rebaixa o .jez (log) do 2º turno das seções com urna de contingência, para ler também o log da urna original, que vem
aninhado dentro do .jez e não foi lido na coleta. Ritmo baixo (até 3 requisições/s no total, 4 em paralelo), com espera
crescente em erro. Retomável: a seção já completa (arquivo "ok") é pulada.
Uso: refetch.py [lista.json] [pasta_saida]
Padrões: DADOS/derivados/biometria/refetch_list.json (lista_contingencia.py) e DADOS/jez_contingencia.
Em 2026: 1.971 seções, cerca de 4 mil requisições e 397 MB. Aumentar RATE é por conta e risco de quem roda (o servidor do
TSE responde HTTP 429 e pode bloquear acessos em excesso)."""
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comum"))
import caminhos  # noqa: E402

BASE = "https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/dados"
RATE = 3.0  # requisições por segundo, somando as 4 linhas de execução
lock = threading.Lock()
next_at = [0.0]


def get(url):
    for attempt in range(6):
        with lock:
            wait = next_at[0] - time.monotonic()
            next_at[0] = max(next_at[0], time.monotonic()) + 1 / RATE
        if wait > 0:
            time.sleep(wait)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": caminhos.USER_AGENT})
            with urllib.request.urlopen(req, timeout=90) as resp:
                return resp.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise
            time.sleep(min(60, 2 ** attempt * 2))
        except OSError:
            time.sleep(min(60, 2 ** attempt * 2))
    raise RuntimeError(f"falhou: {url}")


def work(key, out):
    uf, mun, zona, secao = key
    target = out / uf / f"{mun}-{zona}-{secao}"
    if (target / "ok").exists():
        return key, "skip"
    u = uf.lower()
    folder = f"{BASE}/{u}/{mun}/{zona}/{secao}"
    try:
        aux = json.loads(get(f"{folder}/p003221-{u}-m{mun}-z{zona}-s{secao}-aux.json").decode("utf-8-sig"))
        target.mkdir(parents=True, exist_ok=True)
        (target / "aux.json").write_text(json.dumps(aux), encoding="utf-8")
        n = 0
        for entry in aux.get("hashes", []):
            item = next((a for a in entry.get("arq", []) if a.get("tp") == "log"), None)
            if not item:
                continue
            (target / f"{entry['hash'][:16]}.jez").write_bytes(get(f"{folder}/{entry['hash']}/{item['nm']}"))
            n += 1
        (target / "ok").write_text(str(n))
        return key, f"ok {n}"
    except Exception as error:  # noqa: BLE001
        return key, f"erro {str(error)[:100]}"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    lista = Path(sys.argv[1]) if len(sys.argv) > 1 else caminhos.saida("biometria") / "refetch_list.json"
    keys = [tuple(k) for k in json.load(open(lista, encoding="utf-8"))]
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else caminhos.DADOS / "jez_contingencia"
    out.mkdir(parents=True, exist_ok=True)
    done = errors = 0
    with ThreadPoolExecutor(4) as pool:
        for key, status in pool.map(lambda k: work(k, out), keys):
            done += 1
            if status.startswith("erro"):
                errors += 1
                print("ERRO", key, status, flush=True)
            if done % 100 == 0:
                print(done, "de", len(keys), "erros", errors, flush=True)
    print("FIM", done, "erros", errors, flush=True)


if __name__ == "__main__":
    main()
