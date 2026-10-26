"""Baixa do TSE os arquivos usados pela análise de abstenção (e por outras análises deste repositório).

    DADOS/tse/ab/<uf>-e006257-ab.json   abrangência do 1º turno de 2026 (27 UFs + zz = exterior): aptos, comparecimento e
    DADOS/tse/ab/<uf>-e006258-ab.json   abstenção por município; o mesmo para o 2º turno (56 arquivos, ~9,6 MB no total)
    DADOS/tse/br-c0001-e006258-u.json   resultado nacional oficial do 2º turno para Presidente (votos de cada candidato)
    DADOS/tse/detalhe_votacao_munzona_2022.zip   dados abertos: votação por município e zona, 2022 (~4,4 MB)
    DADOS/tse/detalhe_votacao_munzona_2026.zip   o mesmo para 2026 (~2,5 MB; checagem do 1º turno e nomes dos municípios em comparecimento_dia/nomes.py)

Arquivos que já existem são pulados (apague o arquivo para baixar de novo). Cada arquivo é gravado primeiro como .part e só
recebe o nome final depois de conferido (JSON que abre / zip íntegro com o CSV esperado).

Ritmo: 1 requisição por segundo por padrão (--ritmo aceita até 3). Em erro temporário tenta de novo com espera crescente;
em HTTP 403/429 espera bem mais (ou o Retry-After do servidor) e, se continuar, para tudo.

Depois de baixar, compara o SHA-256 de cada arquivo com sha256_entradas.txt (os arquivos usados nos resultados publicados).
O TSE pode republicar arquivos (novo idg, zip atualizado); nesse caso aparece "difere" e os números podem mudar um pouco.

Uso:
    python abstencao/baixar.py                       # tudo
    python abstencao/baixar.py --so ab br            # só os JSON de resultados.tse.jus.br
    python abstencao/baixar.py --so ab --ufs ac rr --turnos 2
"""
import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "comum"))
import caminhos  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
RESULTADOS = "https://resultados.tse.jus.br/oficial/ele2026"
DADOS_ABERTOS = "https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona"
UFS = "ac al am ap ba ce df es go ma mg ms mt pa pb pe pi pr rj rn ro rr rs sc se sp to zz".split()
ELEICOES = {1: 6257, 2: 6258}  # código da eleição presidencial de 2026 em cada turno
TENTATIVAS = 5
TIMEOUT = 60


def lista_arquivos(so, ufs, turnos):
    """(url, destino, tipo) de cada arquivo pedido."""
    itens = []
    if "ab" in so:
        for t in turnos:
            e = ELEICOES[t]
            for uf in ufs:
                itens.append((f"{RESULTADOS}/{e}/dados/{uf}/{uf}-e00{e}-ab.json", caminhos.TSE / "ab" / f"{uf}-e00{e}-ab.json", "ab"))
    if "br" in so:
        itens.append((f"{RESULTADOS}/6258/dados/br/br-c0001-e006258-u.json", caminhos.TSE / "br-c0001-e006258-u.json", "u"))
    if "zips" in so:
        for ano in (2022, 2026):
            nome = f"detalhe_votacao_munzona_{ano}.zip"
            itens.append((f"{DADOS_ABERTOS}/{nome}", caminhos.TSE / nome, "zip"))
    return itens


def confere(caminho, tipo):
    """Levanta erro se o arquivo baixado não tem a cara esperada."""
    if tipo == "zip":
        with zipfile.ZipFile(caminho) as z:
            nome = caminho.name.replace(".zip", "_BRASIL.csv")
            if nome not in z.namelist():
                raise ValueError(f"{nome} não está no zip")
            if z.testzip() is not None:
                raise ValueError("zip corrompido")
        return
    data = json.loads(caminho.read_bytes().decode("utf-8-sig"))
    if tipo == "ab" and not isinstance(data.get("abr"), list):
        raise ValueError("JSON sem a lista 'abr'")
    if tipo == "u" and not isinstance(data.get("carg"), list):
        raise ValueError("JSON sem a lista 'carg'")


class Bloqueado(Exception):
    pass


def baixa(url, destino, tipo, intervalo, ultimo):
    """Baixa um arquivo respeitando o intervalo mínimo entre requisições. Devolve o horário da última requisição."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_name(destino.name + ".part")
    for tentativa in range(1, TENTATIVAS + 1):
        espera = intervalo - (time.monotonic() - ultimo)
        if espera > 0:
            time.sleep(espera)
        ultimo = time.monotonic()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": caminhos.USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp, open(parcial, "wb") as out:
                while True:
                    bloco = resp.read(1 << 20)
                    if not bloco:
                        break
                    out.write(bloco)
            confere(parcial, tipo)
            parcial.replace(destino)
            return ultimo
        except urllib.error.HTTPError as err:
            if err.code == 404:
                raise
            if err.code in (403, 429):
                if tentativa >= 3:
                    raise Bloqueado(f"HTTP {err.code} repetido em {url}: o servidor está recusando; tente mais tarde") from err
                pausa = max(int(err.headers.get("Retry-After") or 0), 120 * tentativa)
            else:
                pausa = 5 * 2 ** (tentativa - 1)
            motivo = f"HTTP {err.code}"
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError, zipfile.BadZipFile) as err:
            pausa = 5 * 2 ** (tentativa - 1)
            motivo = f"{type(err).__name__}: {err}"
        parcial.unlink(missing_ok=True)
        if tentativa == TENTATIVAS:
            raise RuntimeError(f"falhou após {TENTATIVAS} tentativas: {url} ({motivo})")
        print(f"  {motivo}; nova tentativa em {pausa} s")
        time.sleep(pausa)
    return ultimo


def sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def hashes_publicados():
    arquivo = HERE / "sha256_entradas.txt"
    if not arquivo.exists():
        return {}
    pares = (linha.split(None, 1) for linha in arquivo.read_text(encoding="utf-8").splitlines() if linha.strip() and not linha.startswith("#"))
    return {nome.strip(): h for h, nome in pares}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--so", nargs="+", choices=["ab", "br", "zips"], default=["ab", "br", "zips"], help="o que baixar (padrão: tudo)")
    ap.add_argument("--ufs", nargs="+", default=UFS, type=str.lower, help="UFs dos arquivos ab (padrão: as 27 e zz)")
    ap.add_argument("--turnos", nargs="+", type=int, choices=[1, 2], default=[1, 2], help="turnos dos arquivos ab (padrão: 1 e 2)")
    ap.add_argument("--ritmo", type=float, default=1.0, help="requisições por segundo (padrão 1; no máximo 3)")
    args = ap.parse_args()
    if not 0 < args.ritmo <= 3:
        ap.error("--ritmo precisa ficar entre 0 e 3 requisições por segundo")
    desconhecidas = sorted(set(args.ufs) - set(UFS))
    if desconhecidas:
        ap.error(f"UF desconhecida: {', '.join(desconhecidas)}")
    intervalo = 1 / args.ritmo
    publicados = hashes_publicados()
    itens = lista_arquivos(args.so, args.ufs, args.turnos)
    print(f"Destino: {caminhos.TSE}  ({len(itens)} arquivos pedidos, {args.ritmo:g} req/s)")
    baixados = pulados = 0
    diferentes, falhas = [], []
    ultimo = 0.0
    for url, destino, tipo in itens:
        rel = destino.relative_to(caminhos.DADOS).as_posix()
        if destino.exists():
            pulados += 1
        else:
            print(f"baixando {url}")
            try:
                ultimo = baixa(url, destino, tipo, intervalo, ultimo)
                baixados += 1
            except Bloqueado as err:
                print(f"PARANDO: {err}")
                falhas.append(rel)
                break
            except (urllib.error.HTTPError, RuntimeError) as err:
                print(f"  ERRO: {err}")
                falhas.append(rel)
                continue
        if rel in publicados and sha256(destino) != publicados[rel]:
            diferentes.append(rel)
    print(f"{baixados} baixados, {pulados} já existiam, {len(falhas)} com erro.")
    if publicados:
        conferidos = sum(1 for _, destino, _ in itens if destino.exists() and destino.relative_to(caminhos.DADOS).as_posix() in publicados)
        print(f"SHA-256 conferido em {conferidos} arquivos: {conferidos - len(diferentes)} iguais aos usados nos resultados publicados, "
              f"{len(diferentes)} difere(m)" + (": " + ", ".join(diferentes) if diferentes else "."))
    if falhas:
        print("Com erro: " + ", ".join(falhas))
        sys.exit(1)


if __name__ == "__main__":
    main()
