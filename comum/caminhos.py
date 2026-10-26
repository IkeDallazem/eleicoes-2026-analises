"""Pastas de dados usadas por todas as análises.

Nada do que é baixado ou gerado fica junto do código: tudo vai para DADOS, que por padrão é a pasta dados/ na raiz do
repositório. Para usar outra pasta (por exemplo, um disco com mais espaço), defina a variável de ambiente ELEICOES_DADOS.

    DADOS/urna_logs/      logs das urnas do 2º turno (logs_urna/coletar_logs.py): sections.sqlite e day/
    DADOS/tse/            arquivos do TSE baixados pelos scripts (JSON de resultado e zips de dados abertos)
    DADOS/jez_contingencia/  logs completos das seções com urna substituída (biometria/refetch.py)
    DADOS/bu_2t/          boletins de urna do 2º turno baixados por comparacao_bu/baixar_bu.py
    DADOS/derivados/X/    tudo o que a análise X gera (tabelas intermediárias, imagens e textos)
"""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(os.environ.get("ELEICOES_DADOS") or RAIZ / "dados").resolve()
LOGS = DADOS / "urna_logs"
TSE = DADOS / "tse"

# Identificação enviada ao servidor do TSE em todas as requisições.
USER_AGENT = "analise-eleicoes-2026/1.0"


def saida(analise):
    """Pasta de saída de uma análise (criada se não existir)."""
    pasta = DADOS / "derivados" / analise
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta
