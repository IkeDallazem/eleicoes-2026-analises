"""Baixa os dados de presidente usados pelo modelo histórico: 2002–2022, 1º turno de 2026 e resultado municipal do 2º turno de 2026.

1) hist: CDN do TSE (dados abertos): votacao_secao_<ano>_BR.zip (presidente por seção, 1º e 2º turno) e
   detalhe_votacao_munzona_<ano>.zip (aptos, comparecimento, brancos e nulos por município/zona), de 2002 a 2022.
   Saída: DADOS/tse/hist/ (12 arquivos, cerca de 641 MB).
2) secao2026: CDN do TSE: votacao_secao_2026_BR.zip (votos por seção do 1º turno de 2026, cerca de 162 MB). Saída: DADOS/tse/.
3) res2t: site de resultados: <uf><mun>-c0001-e006258-u.json de cada município (2º turno de 2026), no ritmo de 3 por segundo, com
   retentativa. Saída: DADOS/tse/res2026_2t/. A lista de municípios sai de DADOS/tse/ab/<uf>-e006258-ab.json, baixados por
   abstencao/baixar.py.
O detalhe_votacao_munzona_2026.zip (aptos e comparecimento do 1º turno de 2026, em DADOS/tse/) também vem de abstencao/baixar.py.
Arquivos já baixados são pulados.
Uso: python baixar.py hist | secao2026 | res2t
"""
import http.client
import json
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comum"))
import caminhos  # noqa: E402

ANOS = (2002, 2006, 2010, 2014, 2018, 2022)
CDN = "https://cdn.tse.jus.br/estatistica/sead/odsele"
UFS = "ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to".split()


def baixar_arquivo(url, alvo):
    """Baixa um zip do CDN em alvo.part e renomeia no fim (um download interrompido não fica parecendo completo)."""
    if alvo.exists() and alvo.stat().st_size > 0:
        return
    t0 = time.time()
    parcial = alvo.with_name(alvo.name + ".part")
    for tentativa in range(6):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": caminhos.USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as resp, open(parcial, "wb") as f:
                shutil.copyfileobj(resp, f, 1 << 20)
                total = resp.headers.get("Content-Length")
            if total is not None and parcial.stat().st_size != int(total):
                raise OSError(f"incompleto: {parcial.stat().st_size} de {total} bytes")
            parcial.replace(alvo)
            print(alvo.name, alvo.stat().st_size, f"{time.time() - t0:.0f} s", flush=True)
            return
        except urllib.error.HTTPError as erro:
            if erro.code == 404:
                raise
            time.sleep(min(60, 2 ** tentativa * 2))
        except (OSError, http.client.HTTPException):  # rede, tempo esgotado ou conexão cortada no meio
            time.sleep(min(60, 2 ** tentativa * 2))
    raise RuntimeError(url)


def hist():
    out = caminhos.TSE / "hist"
    out.mkdir(parents=True, exist_ok=True)
    for ano in ANOS:
        for pasta, nome in (("detalhe_votacao_munzona", f"detalhe_votacao_munzona_{ano}.zip"), ("votacao_secao", f"votacao_secao_{ano}_BR.zip")):
            baixar_arquivo(f"{CDN}/{pasta}/{nome}", out / nome)
    print("FIM hist", flush=True)


def secao2026():
    caminhos.TSE.mkdir(parents=True, exist_ok=True)
    baixar_arquivo(f"{CDN}/votacao_secao/votacao_secao_2026_BR.zip", caminhos.TSE / "votacao_secao_2026_BR.zip")
    print("FIM secao2026", flush=True)


LOCK = threading.Lock()
PROXIMO = [0.0]


def get(url):
    for tentativa in range(6):
        with LOCK:  # no máximo 3 requisições por segundo no total, mesmo com várias em paralelo
            espera = PROXIMO[0] - time.monotonic()
            PROXIMO[0] = max(PROXIMO[0], time.monotonic()) + 1 / 3
        if espera > 0:
            time.sleep(espera)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": caminhos.USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as erro:
            if erro.code == 404:
                return None
            time.sleep(min(60, 2 ** tentativa * 2))
        except OSError:
            time.sleep(min(60, 2 ** tentativa * 2))
    raise RuntimeError(url)


def res2t():
    out = caminhos.TSE / "res2026_2t"
    out.mkdir(parents=True, exist_ok=True)
    ab = caminhos.TSE / "ab"
    faltam = [uf for uf in UFS if not (ab / f"{uf}-e006258-ab.json").exists()]
    if faltam:
        sys.exit(f"faltam os arquivos de abrangência do 2º turno em {ab} ({', '.join(faltam)}): rode antes abstencao/baixar.py")
    base = "https://resultados.tse.jus.br/oficial/ele2026/6258/dados"
    todos = [(uf, i["cdabr"]) for uf in UFS for i in json.load(open(ab / f"{uf}-e006258-ab.json", encoding="utf-8"))["abr"]
             if i.get("tpabr") == "mun"]
    pendentes = [(uf, cd) for uf, cd in todos if not (out / f"{uf}{cd}.json").exists()]
    print("municípios", len(todos), "pendentes", len(pendentes), flush=True)

    def um(item):
        uf, cd = item
        body = get(f"{base}/{uf}/{uf}{cd}-c0001-e006258-u.json")
        if body is not None:
            (out / f"{uf}{cd}.json").write_bytes(body)
        return item, body is not None

    n = falta = 0
    with ThreadPoolExecutor(8) as pool:  # 8 em paralelo para cobrir a latência; o teto continua 3 por segundo
        for (uf, cd), ok in pool.map(um, pendentes):
            n += ok
            if not ok:
                falta += 1
                print("404", uf, cd, flush=True)
            if n and n % 500 == 0:
                print(n, flush=True)
    print("FIM res2t", n, "faltando", falta, flush=True)


if __name__ == "__main__":
    passos = {"hist": hist, "secao2026": secao2026, "res2t": res2t}
    if len(sys.argv) != 2 or sys.argv[1] not in passos:
        sys.exit("uso: python baixar.py hist | secao2026 | res2t")
    passos[sys.argv[1]]()
