# Seções sinalizadas × seções da mesma zona: resultado do 2º turno

Esta análise compara o resultado para presidente nas seções **sinalizadas** por `logs_urna/` (pelo menos 1 voto sem
biometria registrado depois das 17h no log da urna) com o de seções não sinalizadas da mesma zona eleitoral. Ela
mede, para Lula (13) e Flávio (22):

- a porcentagem dos votos no 2º turno, sobre votos 13 + 22;
- a porcentagem no 1º turno, sobre os votos válidos para presidente;
- a variação do 1º para o 2º turno, em pontos percentuais (p.p.).

## Método

- **Amostra** (`amostra.py`): todas as seções sinalizadas e, para cada zona com sinalizada, até 10 seções não
  sinalizadas da mesma UF/município/zona, sorteadas com `random.Random("UF|mun|zona")`. Se a zona não tiver 10, o
  sorteio completa com outras zonas do mesmo município.
- **2º turno**: boletim de urna (BU) binário de cada seção, lido por `bu_parser.py`, um leitor ASN.1 DER sem
  dependências. O `imgbu.dat` em texto não estava publicado.
- **1º turno**: arquivos de votação por seção dos dados abertos do TSE (`NR_TURNO = 1`, `CD_CARGO = 1`).
- **Diferença pareada**: para cada sinalizada, o valor dela menos a média dos controles da mesma zona; depois, a média
  dessas diferenças. Intervalo de 95% por bootstrap percentil (1000 reamostragens, semente 2026). Como as sinalizadas
  de uma zona dividem os mesmos controles, há também um bootstrap que reamostra zonas inteiras
  (`ic95_bootstrap_por_zona`).
- **Conferências**: o BU precisa identificar a mesma seção; o comparecimento do BU é comparado com os votos contados
  no log; votáveis diferentes de 13 e 22 no BU são relatados. Tudo vai para o campo `problemas` do JSON.

## A amostra da comparação publicada (dados_congelados/)

A comparação publicada foi gerada em 25/10/2026, durante a coleta dos logs, quando `secoes_analisadas.csv` ainda era parcial e
tinha **76 seções sinalizadas**. Aquela amostra está congelada nesta pasta e é a entrada padrão dos scripts:

| Arquivo | Conteúdo | SHA-256 |
|---|---|---|
| `dados_congelados/sample.csv` | 76 sinalizadas + 456 linhas de controle (449 seções distintas), com zona de referência e origem do controle | `928d576000e15612c32612c98d17eb3739f62a33826dc1b283ea9b0afad43470` |
| `dados_congelados/download.csv` | 525 seções distintas, com o hash do log de cada uma | `4e642cb1df63c4a7a1149b70ac20d22c8aa739801e7c6b9d73df9c543680eeda` |
| `dados_congelados/t1.csv` | 1º turno dessas 525 seções (saída de `primeiro_turno.py`) | `012300bffa72af4778f7135d76a922ed549a4363293c52ab79b23ee0114a3242` |

Rodar `amostra.py` sobre o `secoes_analisadas.csv` final (5.244 sinalizadas) gera outra amostra: 25.528 seções
(5.244 sinalizadas + 20.284 controles), cerca de 25,5 mil BU para baixar. Para usá-la, passe `--amostra-nova` a
`baixar_bu.py`, `primeiro_turno.py` e `comparar.py`.

## Fontes

| Dado | Origem |
|---|---|
| BU do 2º turno | `https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/dados/{uf}/{mun}/{zona}/{secao}/{hash}/o03221{uf}{mun}{zona}{secao}-bu.dat` (hash do log em `download.csv`) |
| Votos por seção, 1º turno | `https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2026_BR.zip` (162 MB; CSV de ~1,05 GB dentro) |
| Detalhe por seção, 1º turno | `https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_secao/detalhe_votacao_secao_2026.zip` (177 MB; usa só `detalhe_votacao_secao_2026_BRASIL.csv`) |
| Seções analisadas | `DADOS/derivados/logs_urna/secoes_analisadas.csv` (`logs_urna/relatorio_17h.py`) |

Os zips usados foram as versões de 09/10/2026, só com o 1º turno. SHA-256: `votacao_secao_2026_BR.zip`
`2d42006d0f6c6e00bad83f5c23cd3d78cd3e3182dbc1ad6718222b6b132c23e1`; `detalhe_votacao_secao_2026.zip`
`11a62c3a604e8b73fc328617b7688d2c635de1c76df02ba63b8f77879512f573`. Versões mais novas servem, porque o script filtra o
1º turno, a menos que o TSE corrija algum número.

## Pastas de dados

Os scripts usam `comum/caminhos.py`: `dados/` na raiz do repositório ou a pasta da variável `ELEICOES_DADOS`.

- `DADOS/tse/`: os dois zips acima (lidos direto, sem extrair).
- `DADOS/bu_2t/{UF}/{mun}-{zona}-{secao}-bu.dat` e `DADOS/bu_2t/_status.csv`: BUs baixados.
- `DADOS/derivados/comparacao_bu/`: saídas.

## Como rodar

Comandos a partir da raiz do repositório (Python 3.12 ou mais novo):

```bash
# 0. (Opcional) nova amostra a partir do secoes_analisadas.csv atual; grava sample.csv e download.csv em DADOS/derivados/comparacao_bu/.
python comparacao_bu/amostra.py

# 1. BUs do 2º turno (padrão: as 525 seções de dados_congelados/download.csv; ~525 requisições, cerca de 6 min).
python comparacao_bu/baixar_bu.py

# 2. Zips do 1º turno em DADOS/tse/.
python modelo_historico/baixar.py secao2026        # votacao_secao_2026_BR.zip
curl -fL -A "analise-eleicoes-2026/1.0" -o "${ELEICOES_DADOS:-dados}/tse/detalhe_votacao_secao_2026.zip" \
     https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_secao/detalhe_votacao_secao_2026.zip

# 3. 1º turno das seções da amostra -> DADOS/derivados/comparacao_bu/t1.csv (cerca de 30 s).
uv run --no-project --with duckdb python comparacao_bu/primeiro_turno.py

# 4. Comparação, resumo e cartão PNG (sem rede). Use --no-png para pular a imagem.
uv run --no-project --with playwright python comparacao_bu/comparar.py

# Testes do leitor de BU (usa fixtures/01392-0009-0267-bu.dat, o BU público de AC/Rio Branco, zona 9, seção 267).
python comparacao_bu/test_bu_parser.py
```

Sem `--amostra-nova`, `comparar.py` lê `sample.csv` e `t1.csv` de `dados_congelados/`. Com a amostra congelada,
`primeiro_turno.py` gera um `t1.csv` idêntico ao congelado. `comparar.py` também precisa do `secoes_analisadas.csv` de
`logs_urna/` para as colunas do log e para a conferência com o BU.

`baixar_bu.py` usa uma conexão e requisições sequenciais, com no mínimo 0,6 s entre elas (segundo argumento
opcional). A cada HTTP 429 para 10 min e dobra o intervalo; erros de rede e 5xx são repetidos com espera crescente.
Arquivos já baixados (ou com 404 registrado em `_status.csv`) não são pedidos de novo. Intervalos menores que o padrão
ficam por conta e risco de quem roda.

Para o PNG, o Playwright usa o Microsoft Edge instalado, se houver; sem Edge:
`uv run --no-project --with playwright python -m playwright install chromium`.

## Saídas (DADOS/derivados/comparacao_bu/)

| Arquivo | Conteúdo |
|---|---|
| `comparacao_sinalizadas.csv` | Uma linha por seção da amostra: grupo, zona de referência, colunas do log, BU do 2º turno, 1º turno, porcentagens e variações |
| `comparacao_sinalizadas.json` | Definições, contagens (`n`), médias simples, diferença pareada com intervalos, problemas e ressalvas |
| `comparacao_sinalizadas-resumo.txt` | Resumo em texto com os números principais |
| `comparacao-cartao-AAAAMMDD-HHMM.html` / `comparacao-AAAAMMDD-HHMM.png` | Cartão 1200×630 com as médias e as diferenças pareadas |

### Números da comparação publicada

76 sinalizadas × 449 controles, todos com BU e 1º turno; 70 sinalizadas têm controle (da mesma zona ou, quando faltou, de outra zona do
mesmo município), em 60 zonas; 29 controles vêm de outra zona do mesmo município.

| Medida | Sinalizadas | Controles | Diferença pareada | Intervalo de 95% |
|---|---|---|---|---|
| Lula, % no 2º turno | 51,24% | 51,30% | −0,01 p.p. | −2,02 a +2,15 |
| Flávio, % no 2º turno | 48,76% | 48,70% | +0,01 p.p. | −2,10 a +2,22 |
| Lula, variação 1º → 2º | +5,95 p.p. | +6,77 p.p. | −0,51 p.p. | −1,09 a +0,12 |
| Flávio, variação 1º → 2º | +1,57 p.p. | +1,47 p.p. | +0,51 p.p. | −0,03 a +1,12 |

Os intervalos incluem zero.

## Ressalvas

- São poucas seções e a comparação é descritiva: não identifica causa.
- As sinalizadas da mesma zona dividem controles; o bootstrap por zona (`ic95_bootstrap_por_zona`) leva isso em conta
  e dá intervalos um pouco mais largos (Lula no 2º turno: −2,31 a +2,44 p.p.; variação: −1,12 a +0,10 p.p.).
- O 1º turno é comparado sobre todos os votos válidos; a variação "só entre 13 e 22" (`var_lula_2c_pp`) está no JSON.
- Duas seções de controle (PB 20516/77/262 e PR 78158/82/36) têm mais comparecimento no BU do que votos no log. As
  duas tiveram urna de contingência, e só o log da última urna é lido (ver `logs_urna/README.md`). Elas aparecem em
  `problemas` e continuam na comparação, porque os números de voto vêm do BU.
- Os caminhos `arquivo-urna` podem sair do ar depois da eleição; ver a ressalva de disponibilidade em `logs_urna/README.md`.
- O cartão é HTML renderizado com a fonte Segoe UI (com `system-ui` e `sans-serif` como alternativas); sem essa fonte o
  texto muda um pouco de largura, mas os números não mudam.
