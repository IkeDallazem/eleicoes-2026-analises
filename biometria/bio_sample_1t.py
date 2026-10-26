"""Validação: baixa o log do 1º turno (pleito 3220) de uma amostra aleatória de seções, conta como bio_parse.count_lines
e grava bio_sample_1t.csv, para comparar seção a seção com o campo do boletim de urna (QT_ELEI_BIOM_SEM_HABILITACAO).
Ritmo baixo (até 3 requisições/s, com nova tentativa e espera crescente em erro): são só ~600 requisições.
A amostra (300 seções, semente 20261004) sai da tabela sections de DADOS/urna_logs/sections.sqlite (só leitura); o CSV vai
para DADOS/derivados/biometria. Lê só o primeiro .dat de cada .jez: numa seção com urna substituída, o log da urna original
(aninhado) fica de fora. Em 2026, 299 das 300 seções bateram com o boletim (votos = comparecimento e mesmo biom_sem_hab);
a outra (DF 97012/0014/0068) é de urna substituída e bate (297 votos, 21) quando o log aninhado também é contado."""
import csv
import io
import json
import random
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "comum"))
from bio_parse import count_lines  # noqa: E402
import caminhos  # noqa: E402

DB = caminhos.LOGS / "sections.sqlite"
BASE = "https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados"
N = 300


def get(url):
    for attempt in range(5):
        time.sleep(1 / 3)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": caminhos.USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as error:
            if error.code == 404 or attempt == 4:
                raise
        except OSError:
            if attempt == 4:
                raise
        time.sleep(min(60, 2 ** attempt * 2))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = db.execute("SELECT uf, mun, zona, secao FROM sections WHERE uf<>'ZZ' AND status='fetched'").fetchall()
    sample = random.Random(20261004).sample(rows, N)
    fields = ["uf", "cd_municipio", "nr_zona", "nr_secao", "votos", "com_biometria", "biom_sem_hab", "habilitados_bio", "sem_bio_total", "erro"]
    with open(caminhos.saida("biometria") / "bio_sample_1t.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for i, (uf, mun, zona, secao) in enumerate(sample, 1):
            u = uf.lower()
            folder = f"{BASE}/{u}/{mun}/{zona}/{secao}"
            out = {"uf": uf, "cd_municipio": mun, "nr_zona": zona, "nr_secao": secao}
            try:
                aux = json.loads(get(f"{folder}/p003220-{u}-m{mun}-z{zona}-s{secao}-aux.json").decode("utf-8-sig"))
                totals = None
                for entry in aux.get("hashes", []):
                    item = next((a for a in entry.get("arq", []) if a.get("tp") == "log"), None)
                    if not item:
                        continue
                    raw = get(f"{folder}/{entry['hash']}/{item['nm']}")
                    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                        name = next((nm for nm in archive.namelist() if nm.lower().endswith(".dat")), archive.namelist()[0])
                        text = archive.read(name).decode("latin-1")
                    c = count_lines(text.splitlines(), "04/10/2026")
                    totals = c if totals is None else {k: totals[k] + c[k] for k in c}
                out.update(totals or {"erro": "sem log"})
            except Exception as error:  # noqa: BLE001 - registra e segue
                out["erro"] = str(error)[:120]
            writer.writerow(out)
            if i % 50 == 0:
                print(i, flush=True)
    print("FIM", flush=True)


if __name__ == "__main__":
    main()
