# Modelo histórico: o 2º turno de 2026 comparado aos 2º turnos de 2002 a 2022

Compara, município a município, o resultado do 2º turno presidencial de 2026 com o que o padrão dos 2º turnos anteriores
(2002, 2006, 2010, 2014, 2018 e 2022) indicaria a partir do 1º turno, e compara a variação do comparecimento entre os turnos
com a dos anos anteriores.

## O que é medido

- **Base municipal** (`montar.py`): para cada eleição de 2002 a 2026 e cada município (sem o exterior), votos do 1º e do 2º turno
  em cinco grupos: candidato do PT (número 13, presente em todos os 2º turnos desde 2002), o outro finalista, demais candidatos do
  1º turno, brancos (95) e nulos (96 e 97), além de eleitores aptos e comparecimento em cada turno.
- **Regra de transferência** (`modelo.py`, modelo A): os votos do PT e do adversário no 2º turno, por eleitor apto, são escritos
  como combinação não negativa (NNLS, sem constante) das frações do 1º turno (PT, adversário, outros, brancos e nulos, abstenção),
  com os mesmos coeficientes para o país todo e cada município pesando na proporção do eleitorado (linhas multiplicadas por
  √aptos). É uma inferência ecológica a partir de totais: o voto é secreto e a regra não diz quem votou em quem.
- **Teste deixando um ano de fora**: cada ano de 2002 a 2022 é estimado com a regra ajustada nos outros cinco; 2026 é estimado
  com os seis anos anteriores. A estimativa de cada município é a parte do PT nos válidos do 2º turno; o total do país e das UFs
  soma os municípios pesando pelos votos válidos reais do 2º turno.
- **Medidas** (`resultados.json`): resultado real, estimativa e erro no país; erro médio por município e por UF; e o erro
  "geográfico", que é o que sobra depois de descontar o deslocamento do país inteiro.
- **Outros modelos**, gravados mas não usados nos gráficos: a parte do PT entre os dois finalistas já no 1º turno (`base`), um
  gradient boosting com as mesmas frações mais UF, região e porte (`prev_b`) e um gradient boosting para a variação do
  comparecimento (`prev_dcomp`). `robust_comp.py` mostra que essa estimativa de comparecimento para 2026 depende de incluir 2022
  (−0,07 ponto com 2022, −2,06 sem), e por isso o resumo não a usa.
- **Comparecimento**: votantes ÷ aptos no 1º e no 2º turno de cada eleição, somando os municípios.

Isto não é pesquisa nem previsão feita antes da eleição: as estimativas são calculadas depois, só com o 1º turno, para servir de
régua. A comparação mede o quanto o resultado se afastou do padrão dos anos anteriores; não explica o motivo e não é auditoria.

## Fontes (TSE)

| Arquivo | Endereço | Quem baixa |
|---|---|---|
| Votação por seção, 2002–2022 | `https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_<ano>_BR.zip` | `baixar.py hist` |
| Detalhe por município e zona, 2002–2022 | `https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona/detalhe_votacao_munzona_<ano>.zip` | `baixar.py hist` |
| Votação por seção, 1º turno de 2026 | `https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2026_BR.zip` | `baixar.py secao2026` |
| Detalhe por município e zona, 2026 | `https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_munzona/detalhe_votacao_munzona_2026.zip` | `abstencao/baixar.py` |
| Lista de municípios (abrangência do 2º turno) | `https://resultados.tse.jus.br/oficial/ele2026/6258/dados/<uf>/<uf>-e006258-ab.json` | `abstencao/baixar.py` |
| Resultado do 2º turno de 2026 por município | `https://resultados.tse.jus.br/oficial/ele2026/6258/dados/<uf>/<uf><município>-c0001-e006258-u.json` | `baixar.py res2t` |

Contornos das UFs para o mapa: `comum/ufs.json`, usado por `biometria/bio_charts.py`.

O 2º turno de 2026 vem do site de resultados (um arquivo por município) porque os dados abertos de 2026 usados aqui só trazem o
1º turno. `sha256_entradas.txt` tem o SHA-256 dos zips usados nos resultados publicados.

## Pastas

Todos os dados ficam fora do código, em `DADOS` (padrão: `dados/` na raiz do repositório; para usar outra pasta, defina a variável
de ambiente `ELEICOES_DADOS`). Veja `comum/caminhos.py`.

- Entradas: `DADOS/tse/hist/` (12 zips), `DADOS/tse/votacao_secao_2026_BR.zip`, `DADOS/tse/detalhe_votacao_munzona_2026.zip`,
  `DADOS/tse/ab/<uf>-e006258-ab.json` e `DADOS/tse/res2026_2t/<uf><município>.json`.
- Saídas: `DADOS/derivados/modelo_historico/`.

## Como rodar

Python 3.12 com pandas, numpy, scipy, scikit-learn e matplotlib. Os resultados publicados saíram com pandas 3.1.0, numpy 2.5.4,
scipy 1.18.1, scikit-learn 1.9.1 e matplotlib 3.11.2. Os scripts acham as pastas pelo próprio caminho, então podem ser chamados
de qualquer diretório; os comandos abaixo partem da raiz do repositório.

```
# opcional: export ELEICOES_DADOS=/caminho/para/os/dados   (PowerShell: $env:ELEICOES_DADOS = "...")
python abstencao/baixar.py --so ab zips --turnos 2    # abrangência do 2º turno e detalhe_votacao_munzona_2022/2026.zip
python modelo_historico/baixar.py hist                # 12 zips de 2002 a 2022, cerca de 641 MB
python modelo_historico/baixar.py secao2026           # votacao_secao_2026_BR.zip, cerca de 162 MB
python modelo_historico/baixar.py res2t               # 5.571 JSON, 17,3 MB, cerca de 31 min
python modelo_historico/montar.py                     # municipios.csv
python modelo_historico/modelo.py                     # previsoes.csv e resultados.json
python modelo_historico/robust_comp.py                # opcional: só imprime a checagem do comparecimento esperado
python modelo_historico/graficos.py                   # 5 PNG e exibidos.json
python modelo_historico/texto.py                      # texto.json e texto.txt
```

Com uv, por exemplo: `uv run --with pandas==3.1.0 --with numpy==2.5.4 --with scipy==1.18.1 --with scikit-learn==1.9.1
--with matplotlib==3.11.2 python modelo_historico/montar.py`.

Downloads: arquivos que já existem são pulados (apague para baixar de novo). Os zips são gravados primeiro como `.part` e só
recebem o nome final quando chegam inteiros. Toda requisição se identifica com o `USER_AGENT` de `comum/caminhos.py` e tenta de
novo com espera crescente (até 6 vezes). `res2t` faz no máximo 3 requisições por segundo no total (8 em paralelo para cobrir a
latência); uma resposta 404 é avisada e pulada. Ritmos maiores sobrecarregam o servidor do TSE e podem levar a bloqueio; se
mudar o ritmo, é por sua conta e risco.

Tempos medidos num computador de mesa: `montar.py` cerca de 1,5 min (lê o CSV de 1,05 GB de 2026 de dentro do zip, em blocos de
2 milhões de linhas), `modelo.py` cerca de 20 s, `robust_comp.py` cerca de 15 s, `graficos.py` e `texto.py` alguns segundos.

## Saídas (`DADOS/derivados/modelo_historico/`)

| Arquivo | Conteúdo |
|---|---|
| `municipios.csv` (3,2 MB) | uma linha por ano × município: `pt`, `adv`, `outros`, `branco`, `nulo`, `QT_APTOS`, `QT_COMPARECIMENTO` com sufixo `_1` e `_2` (turno), e `adv_num` (número do outro finalista) |
| `previsoes.csv` (14,7 MB) | o mesmo, mais as frações do 1º turno, `y` (parte do PT nos válidos do 2º turno), `base`, `prev_a`, `prev_b`, `comp1`, `comp2`, `dcomp` e `prev_dcomp` |
| `resultados.json` | por ano: resultado real, medidas de erro de `base`, `prev_a` e `prev_b` (com o erro de cada UF), comparecimento real e estimado; e os coeficientes da regra usada em cada ano |
| `exibidos.json` | os números arredondados mostrados nos gráficos (diferença por ano; comparecimento por turno), lidos por `texto.py` |
| `1-comparecimento.png` | comparecimento no 1º e no 2º turno de cada eleição, uma seta por ano |
| `2-setas.png` | estimativa e resultado do candidato do PT em cada ano, com a faixa dos desvios de 2002 a 2022 aplicada a 2026 |
| `3-municipios.png` | uma nuvem de municípios (estimado × resultado) por ano |
| `4-mapa-2026.png` | 2026: diferença entre resultado e estimativa em cada UF |
| `5-municipios-2026.png` | a nuvem de 2026 ampliada |
| `texto.json`, `texto.txt` | resumo em texto dos números, gerado dos arquivos acima (`texto.json` lista também as imagens 1 a 4 a que o resumo se refere) |

## Ressalvas

- Sem o exterior (UF `ZZ` e `VT` ficam de fora). A contagem de municípios varia um pouco entre os anos (5.565 a 5.594); 2026 tem
  5.571, todos com resultado do 2º turno.
- Fontes diferentes para os dois turnos de 2026: o 1º turno vem dos dados abertos (versão de 09/10/2026) e o 2º turno do site de
  resultados (arquivos gerados em 25/10/2026). Quando os dados abertos do 2º turno saírem, pode haver pequenas diferenças.
- O TSE pode republicar arquivos. Com outra versão, os números podem mudar um pouco e alguns `assert` de `graficos.py` e
  `texto.py`, que conferem fatos do resumo (por exemplo, que 2022 é o único ano anterior com aumento do comparecimento e que Lula
  ficou acima do estimado nas 27 UFs), podem falhar. Confira os zips com `sha256_entradas.txt`. O
  `detalhe_votacao_munzona_2022.zip` de `DADOS/tse/hist/` (usado aqui) e o de `DADOS/tse/` (baixado por `abstencao/baixar.py`)
  podem ser versões diferentes do mesmo arquivo.
- Números escritos à mão: `texto.py` cita −0,1 e −2,1 ponto (comparecimento esperado com e sem 2022, saídas de `robust_comp.py`
  arredondadas) e `graficos.py` cita "+2,3" num rótulo de `3-municipios.png` (a diferença de 2026). Se os dados mudarem, atualize.
- Gráficos e resumo dependem só da regra NNLS (determinística) e de totais. Os modelos de gradient boosting (`prev_b`,
  `prev_dcomp`, `random_state=0`) podem variar um pouco entre versões do scikit-learn.
- Em 2026, `montar.detalhe_csv` remove linhas repetidas sem olhar a zona; nos dados usados isso não remove nenhuma linha (6.106 de
  6.106), e o comparecimento somado é igual ao total de votos por seção (124.934.069).
- Fonte dos gráficos: Segoe UI (Windows). Onde ela não existe, o matplotlib usa DejaVu Sans; as imagens ficam um pouco diferentes,
  os números não.
- Os gráficos usam o estilo de `abstencao/charts_v2.py` e o mapa de `biometria/bio_charts.py`.
