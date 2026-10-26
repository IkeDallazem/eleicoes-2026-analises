# Abstenção entre o 1º e o 2º turno (2026, com 2022 como referência)

Mede quanto a abstenção na eleição para Presidente mudou do 1º para o 2º turno de 2026, no país, em cada UF e em cada
município, e compara com a mesma variação em 2022.

- **Abstenção** = eleitores aptos que não votaram ÷ aptos, calculada em cada turno com os aptos daquele turno.
- **Variação** = abstenção no 2º turno − abstenção no 1º turno, em pontos percentuais (p.p.). Negativa: a abstenção caiu.
- Os gráficos e as taxas por UF e por município não incluem o exterior. O exterior entra só na conta de quantos eleitores
  a mais votaram no 2º turno (diferença entre as abstenções dos dois turnos, em número de eleitores) e na margem nacional.

Principais números obtidos (arquivos do TSE listados em `sha256_entradas.txt`):

| | 2026 | 2022 |
|---|---|---|
| Abstenção no país, sem exterior, 1º → 2º turno | 20,84% → 18,99% (−1,85 p.p.) | 20,79% → 20,43% (−0,36 p.p.) |
| Eleitores a mais votando no 2º turno, com exterior | 2.960.239 | 570.424 |
| Municípios com queda da abstenção | 4.440 de 5.571 (80%) | |
| Variação no município típico (mediana) | −1,88 p.p. | −0,49 p.p. |
| Correlação entre a variação de 2022 e a de 2026, por município | Norte e Nordeste 0,89; Centro-Sul 0,48 | |

A margem nacional do 2º turno de 2026 (4.430.191 votos, do arquivo de resultado do TSE) aparece ao lado do saldo de
eleitores a mais apenas como ordem de grandeza: o saldo não diz quem são esses eleitores nem em quem votaram.

## Fontes (TSE)

| Arquivo | URL | Uso |
|---|---|---|
| Abrangência ("ab") de cada UF, 1º turno | `https://resultados.tse.jus.br/oficial/ele2026/6257/dados/<uf>/<uf>-e006257-ab.json` | aptos (`te`), comparecimento (`c`) e abstenção (`a`) por município (`tpabr = "mun"`) |
| Abrangência ("ab") de cada UF, 2º turno | `https://resultados.tse.jus.br/oficial/ele2026/6258/dados/<uf>/<uf>-e006258-ab.json` | idem |
| Resultado nacional do 2º turno, Presidente | `https://resultados.tse.jus.br/oficial/ele2026/6258/dados/br/br-c0001-e006258-u.json` | votos de cada candidato (`carg → agr → par → cand`: `nmu`, `vap`) e situação da totalização (`f`, `s.ts`, `s.st`, `s.snt`) |
| Dados abertos 2022 | `https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona/detalhe_votacao_munzona_2022.zip` | `detalhe_votacao_munzona_2022_BRASIL.csv` (latin-1, separador `;`), cargo 1, somado por município |
| Dados abertos 2026 | `https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona/detalhe_votacao_munzona_2026.zip` | só uma checagem: o 1º turno dos arquivos "ab" contra o CSV oficial |

`<uf>` percorre as 27 UFs em minúsculas e `zz` (exterior): 28 arquivos por turno. 6257 e 6258 são os códigos da eleição
presidencial de 2026 no 1º e no 2º turno. Os CSV são lidos direto de dentro dos zips (não é preciso extrair).

## Requisitos

- Python 3.12.
- `baixar.py` e `build_data.py`: só a biblioteca padrão.
- `charts.py` e `charts_v2.py`: matplotlib (≥ 3.7; as imagens de referência foram geradas com 3.11.2).
- Fonte dos gráficos: Segoe UI (Windows). Onde ela não existir, o matplotlib usa DejaVu Sans; os números e o desenho são os
  mesmos, mas o texto muda de largura e as imagens não ficam idênticas às de referência.

## Como rodar

Tudo o que é baixado ou gerado fica em `DADOS`, que é a pasta `dados/` na raiz do repositório ou a pasta indicada na
variável de ambiente `ELEICOES_DADOS` (veja `comum/caminhos.py`). Os comandos abaixo partem da raiz do repositório.

```
python abstencao/baixar.py          # 1) baixa os 56 JSON "ab", o JSON nacional e os 2 zips para DADOS/tse/
python abstencao/build_data.py      # 2) monta DADOS/derivados/abstencao/abst_municipios.csv
python abstencao/charts.py          # 3) primeira série de gráficos: DADOS/derivados/abstencao/v1/
python abstencao/charts_v2.py       # 4) série final (capa + 4 gráficos) e resumo.md: DADOS/derivados/abstencao/final/
```

Com uv, por exemplo: `uv run --with matplotlib==3.11.2 python abstencao/charts_v2.py`.

Opções de `baixar.py`:

- `--so ab br zips`: escolhe o que baixar (padrão: tudo).
- `--ufs ac rr ...` e `--turnos 1 2`: limitam os arquivos "ab".
- `--ritmo N`: requisições por segundo (padrão 1, máximo 3).

Arquivos que já existem são pulados. As requisições usam o User-Agent de `comum/caminhos.py`, com novas tentativas e
espera crescente em caso de erro; em HTTP 403/429 a espera é longa (ou a pedida pelo servidor em `Retry-After`) e, se o
bloqueio continuar, o script para. Rodar acima do ritmo padrão é por conta e risco de quem roda. Ao final, o script compara
o SHA-256 de cada arquivo com `sha256_entradas.txt` e avisa quais diferem.

Este `baixar.py` também é o que baixa os arquivos "ab", o JSON nacional e os zips `detalhe_votacao_munzona` usados por
outras análises deste repositório.

## Saídas (em `DADOS/derivados/abstencao/`)

- `abst_municipios.csv`: uma linha por município e ano, com `ano, uf, cd_municipio, aptos_1t, abst_1t, comp_1t, aptos_2t,
  abst_2t, comp_2t`. 11.508 linhas: 2026 com 5.757 (5.571 municípios + 186 localidades do exterior, `uf = ZZ`) e 2022 com
  5.751 (5.570 + 181 do exterior). Em 2026 o código é o do TSE (5 dígitos), como nos arquivos "ab"; em 2022, o
  `CD_MUNICIPIO` do CSV com zeros à esquerda (os dois anos usam o mesmo código do TSE).
- `v1/`: primeira série de gráficos — `1-estados.png` (variação por UF, 2026 × 2022), `2-municipios-histograma.png`,
  `3-municipios-por-estado.png` e `4-municipios-2022x2026.png`.
- `final/`: série final — `0-capa.png` (números-chave), `1-estados.png`, `2-municipios.png`, `3-dentro-dos-estados.png`,
  `4-municipios-2022x2026.png` e `resumo.md` (um parágrafo por imagem e um texto corrido, gerados dos mesmos números).

`build_data.py` também imprime a checagem do 1º turno de 2026 (arquivos "ab" × CSV de dados abertos: 5.757 municípios,
0 divergências de aptos e abstenção) e as taxas nacionais com e sem exterior. `charts.py` e `charts_v2.py` imprimem os
números usados nos títulos e textos.

## Tamanho e tempo

- Download: 56 JSON "ab" (~9,6 MB no total), 1 JSON nacional (~3 KB) e 2 zips (4,4 MB e 2,5 MB). Ao ritmo padrão,
  cerca de 1 minuto.
- `build_data.py` e cada script de gráficos: poucos segundos.

## Reprodutibilidade

- Com os arquivos de `sha256_entradas.txt`, Python 3.12, matplotlib 3.11.2 e a fonte Segoe UI, `abst_municipios.csv` e as
  9 imagens saem idênticas, byte a byte, às de referência.
- O TSE pode republicar arquivos (novo `idg` nos JSON, zip de dados abertos atualizado). O zip de 2026 usado era a versão
  de 09/10/2026, só com o 1º turno; versões mais novas também servem, porque só o 1º turno é lido dele.
- A distribuição dos pontos em `3-municipios-por-estado.png` e `3-dentro-dos-estados.png` usa deslocamento vertical
  aleatório com semente fixa (`random.Random(26)`).

## Ressalvas

- 2026 vem dos arquivos de resultado ("ab") e 2022 dos dados abertos. A checagem do 1º turno de 2026 mostra que as duas
  fontes dão os mesmos aptos e abstenções por município, mas para 2022 só foram usados os dados abertos.
- A comparação município a município (gráfico 4) usa os 5.570 municípios presentes nos dois anos; o único município sem
  dados em 2022 (MT, código TSE 73709) entra só nas contagens de 2026.
- A queda da abstenção é um saldo entre os turnos: quem se absteve no 1º e votou no 2º, menos quem votou no 1º e se
  absteve no 2º. Os dados agregados não mostram quantos eleitores há de cada lado nem em quem votaram.
- Municípios fora da faixa do eixo aparecem encostados na borda (gráficos de pontos) ou somados nas barras das pontas
  (histogramas), como indicado em cada gráfico.
- Os quartis em `v1/` são tomados por posição na lista ordenada; em `final/`, por `statistics.quantiles` (método
  "inclusive"). Por isso alguns valores de "metade central" podem diferir na casa decimal entre as duas séries.
- Norte = AC, AP, AM, PA, RO, RR, TO; Nordeste = AL, BA, CE, MA, PB, PE, PI, RN, SE; Centro-Sul = as demais UFs.

## Uso por outras análises

`charts_v2.py` também é o módulo de estilo dos gráficos de `biometria/`, `comparecimento_dia/` e `modelo_historico/`
(`import charts_v2 as cv`: cores, `br`, `n`, `figure`, `frame`, `axes_below`, `xstyle` etc.). Importá-lo só define o estilo
do matplotlib; não lê dados nem cria pastas.
