"""1º turno 2026: votos de eleitores com biometria que não foram habilitados por ela, por seção (boletim de urna do TSE).

Fonte: dados abertos do TSE, "Resultados - 2026 - Boletim de Urna" (bweb_1t_<UF>_051020261403.zip).
Campo QT_ELEI_BIOM_SEM_HABILITACAO = "Quantidade de eleitoras e eleitores com biometria, mas que não foram habilitados por meio dela"
(leiame do próprio pacote). Baixa um estado por vez (com curl, que precisa estar no PATH), lê só as linhas de Presidente
(uma por seção basta: os totais da seção se repetem em cada linha de candidato), grava bio_1t_secoes.csv e apaga o zip.
O zip é baixado em DADOS/tse/ e a tabela vai para DADOS/derivados/biometria/. Retomável: os estados que já estão no CSV
são pulados.
"""
import csv
import io
import subprocess
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comum"))
import caminhos  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
RAW = caminhos.TSE
RAW.mkdir(parents=True, exist_ok=True)
OUT = caminhos.saida("biometria") / "bio_1t_secoes.csv"
URL = "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb/bweb_1t_{uf}_051020261403.zip"
UFS = "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ".split()
FIELDS = ["uf", "cd_municipio", "nr_zona", "nr_secao", "aptos", "comparecimento", "biom_sem_hab", "tipo_urna", "agregadas"]


def main():
    done = set()
    if OUT.exists():
        done = {r["uf"] for r in csv.DictReader(open(OUT, encoding="utf-8"))}
    new = not OUT.exists()
    with open(OUT, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if new:
            writer.writeheader()
        for uf in UFS:
            if uf in done:
                continue
            t0 = time.time()
            zpath = RAW / f"bweb_1t_{uf}.zip"
            # um arquivo por vez; --retry repete com espera crescente em falha temporária (inclusive HTTP 429)
            subprocess.run(["curl", "-s", "--fail", "--retry", "3", "--max-time", "1800", "-A", caminhos.USER_AGENT, "-o", str(zpath),
                            URL.format(uf=uf)], check=True)
            seen, rows, linhas = set(), 0, []
            with zipfile.ZipFile(zpath) as archive:
                name = next(n for n in archive.namelist() if n.lower().endswith(".csv"))
                with archive.open(name) as raw:
                    reader = csv.DictReader(io.TextIOWrapper(raw, encoding="latin-1", newline=""), delimiter=";")
                    for row in reader:
                        rows += 1
                        if row["CD_CARGO_PERGUNTA"] != "1":
                            continue
                        key = (row["CD_MUNICIPIO"], row["NR_ZONA"], row["NR_SECAO"])
                        if key in seen:
                            continue
                        seen.add(key)
                        linhas.append({"uf": row["SG_UF"], "cd_municipio": row["CD_MUNICIPIO"].zfill(5), "nr_zona": row["NR_ZONA"].zfill(4),
                                       "nr_secao": row["NR_SECAO"].zfill(4), "aptos": row["QT_APTOS"], "comparecimento": row["QT_COMPARECIMENTO"],
                                       "biom_sem_hab": row["QT_ELEI_BIOM_SEM_HABILITACAO"], "tipo_urna": row["DS_TIPO_URNA"],
                                       "agregadas": row["DS_SECOES_AGREGADAS"]})
            # o estado só entra no CSV depois de lido por inteiro: uma execução interrompida não deixa estado pela metade
            writer.writerows(linhas)
            handle.flush()
            zpath.unlink()
            print(f"{uf}: {len(seen)} seções, {rows} linhas, {time.time() - t0:.0f} s", flush=True)
    print("FIM", flush=True)


if __name__ == "__main__":
    main()
