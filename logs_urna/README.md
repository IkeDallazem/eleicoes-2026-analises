# Logs de urna do 2º turno: votos após as 17h e habilitação sem biometria

Esta análise lê o log de cada urna do 2º turno de 2026 (25/10/2026), publicado pelo TSE, e conta para cada seção
do Brasil (o exterior fica de fora):

- quantos votos foram registrados antes e depois das 17h, no horário de Brasília;
- quantos desses eleitores foram habilitados sem biometria: habilitação pelo mesário, conferência de dado pessoal ou
  ano de nascimento;
- a mesma divisão antes/depois das 17h, mas pela hora em que o identificador do eleitor foi digitado;
- se a seção teve urna de contingência (urna trocada durante o dia).

Uma seção é **sinalizada** quando tem pelo menos 1 voto sem biometria registrado depois das 17h. A lista das
sinalizadas serve de entrada para a comparação de resultados em `comparacao_bu/`.

## Método (relatorio_17h.py)

- Voto = linha `O voto do eleitor foi computado`. O tipo de habilitação vem das mensagens da sessão do eleitor, que
  começa em `Aguardando digitação do identificador`: `Tipo de habilitação do eleitor [biométrica]`,
  `Mesário ... habilitou o eleitor`, `Dado digitado confere` ou `Ano de nascimento digitado é igual`. Sem nenhuma
  delas, o tipo fica "não identificado".
- Só entram as linhas datadas de 25/10/2026.
- Hora do relógio da urna convertida para Brasília: AC +120 min; AM, RO, RR, MT e MS +60 min; Fernando de Noronha
  (PE, município 30015, UTC−2) −60 min. Fora de Noronha, o ajuste também é deduzido do primeiro
  `Eleitor foi habilitado` do log: antes de 6h54 no relógio da urna dá +2 h, antes de 7h54 dá +1 h. Vale o maior
  entre o ajuste da tabela e o deduzido.
- Corte: voto com hora ajustada ≥ 17:00:00 conta como "após 17h". Pela hora da identificação, o corte é aplicado à
  linha `Identificador do eleitor digitado` da mesma sessão (sem essa linha, vale a hora do voto).
- Totais oficiais (seções e comparecimento por UF) vêm dos arquivos de abrangência do TSE. Eles definem o total de
  seções do Brasil e a fração do comparecimento que não aparece nos logs lidos.

## Fontes

| Dado | Origem |
|---|---|
| Lista de seções por UF | `https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/config/{uf}/{uf}-p003221-cs.json` (28 arquivos, com ZZ) |
| Arquivos de cada seção | `https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3221/dados/{uf}/{mun}/{zona}/{secao}/p003221-{uf}-m{mun}-z{zona}-s{secao}-aux.json` |
| Log da urna | `.../dados/{uf}/{mun}/{zona}/{secao}/{hash}/{arquivo .logjez indicado no aux.json}` (ZIP com `logd.dat`, latin-1) |
| Totais oficiais do 2º turno | `https://resultados.tse.jus.br/oficial/ele2026/6258/dados/{uf}/{uf}-e006258-ab.json` (abrangência; entrada `tpabr="uf"`: `s.ts`, `s.st`, `e.c`), baixados por `abstencao/baixar.py` para `DADOS/tse/ab/` |

## Pastas de dados

Todos os scripts usam `comum/caminhos.py`. Os dados ficam em `dados/` na raiz do repositório ou na pasta indicada pela
variável de ambiente `ELEICOES_DADOS`:

```powershell
$env:ELEICOES_DADOS = "D:\eleicoes-dados"      # PowerShell
```
```bash
export ELEICOES_DADOS=/mnt/dados/eleicoes      # bash
```

- `DADOS/urna_logs/`: saída do coletor (`sections.sqlite`, `day/{UF}/*.log.gz`, `raw/` (cópia de ~2% dos `.jez`,
  sempre gravada), `bu/` (só com `--bu`), `collector_status.log`; `max_rate.txt` e `controle_ritmo.log` são do
  `controle_ritmo.py`).
- `DADOS/tse/ab/`: arquivos de abrangência (ver `abstencao/`).
- `DADOS/derivados/logs_urna/`: tudo o que `relatorio_17h.py` gera.

## Como rodar

Python 3.12 ou mais novo. A coleta e o cálculo usam só a biblioteca padrão; a imagem usa Playwright (o resumo em texto é gravado
depois da imagem). Comandos a partir
da raiz do repositório:

```bash
# 1. Coleta dos logs (horas; Ctrl+C interrompe e uma nova execução continua de onde parou).
#    Rode até não restar seção "fila" nem "erro" no status impresso a cada 30 s. Com --once, encerra quando a fila
#    esvazia (rode de novo até zerar); sem ele, continua varrendo a cada 120 s.
python logs_urna/coletar_logs.py
#    Opcional, em outro terminal: ajusta o teto de requisições lendo o status do coletor.
python logs_urna/controle_ritmo.py
#    Opcional (Windows): reinicia o coletor se ele parar; os argumentos são repassados.
powershell -File logs_urna/coletar_em_loop.ps1
#    Opcional: --bu baixa também o boletim de urna de cada seção (bu/<UF>/), usado em biometria/conferir_bu_2t.py.

# 2. Totais oficiais por UF do 2º turno (modo final do relatório): 28 arquivos pequenos (27 UFs e exterior).
python abstencao/baixar.py --so ab --turnos 2

# 3. Contagem, tabelas, relatório HTML/PNG e resumo em texto.
uv run --no-project --with playwright python logs_urna/relatorio_17h.py

# Teste rápido em poucas UFs (saídas e cache próprios em DADOS/derivados/logs_urna/ufs-AC-AP-RR/):
uv run --no-project --with playwright python logs_urna/relatorio_17h.py --ufs AC,AP,RR
```

Para a imagem, o Playwright usa o Microsoft Edge instalado, se houver; sem Edge, instale o Chromium do Playwright
uma vez: `uv run --no-project --with playwright python -m playwright install chromium`.

Opções do relatório: `--if-changed` não gera nada se nenhuma seção nova foi analisada desde a última execução
(útil durante a coleta); `--draft` grava relatório e tabelas em `relatorios/rascunho/`.

### Ritmo das requisições

O padrão do coletor é conservador: começa em 3 req/s, sobe devagar até o teto de 8 req/s e, a cada HTTP 429, cai pela
metade e pausa 90 s (ou o `Retry-After`). Erros 5xx e de rede são repetidos com espera crescente. `controle_ritmo.py`
fica, por padrão, entre 3 e 8 req/s. Taxas maiores (`--rate`, `--max-rate`, `controle_ritmo.py --max`) ficam por conta
e risco de quem roda a coleta. Todas as requisições usam o User-Agent de `comum/caminhos.py`.

## Saídas (DADOS/derivados/logs_urna/)

| Arquivo | Conteúdo |
|---|---|
| `secoes_analisadas.csv` | Uma linha por seção (`;`, UTF-8 com BOM): `uf, mun, mun_name, zona, secao, votos, votos_antes_17h, votos_apos_17h, pct_votos_apos_17h, sem_bio_antes, pct_sem_bio_antes, sem_bio_apos, pct_sem_bio_apos, sinalizada, logs, votos_apos_17h_ident, sem_bio_apos_ident, urna_contingencia` |
| `secoes_sinalizadas.csv` | Mesmas colunas, só as seções com `sinalizada = 1` |
| `cache_logs.json` | Resultado da leitura de cada log (evita reler os ~498 mil arquivos) |
| `relatorios/biometria-provisorio-AAAAMMDD-HHMM.html` / `.png` | Relatório por UF e as 15 seções sinalizadas com mais votos sem biometria após 17h (o nome com "provisorio" vale também para o relatório final) |
| `relatorios/biometria-provisorio-AAAAMMDD-HHMM-resumo.txt` | Resumo em texto com os mesmos números |

O relatório entra no modo final (título com "coleta completa") quando nenhuma seção do Brasil está na fila ou com
erro em `sections.sqlite` e os arquivos de abrangência das 27 UFs estão em `DADOS/tse/ab/`. Sem eles, sai no modo
provisório (cobertura em %).

### Números do relatório final (coleta completa)

| Medida | Valor |
|---|---|
| Seções analisadas | 497.895 de 497.897 (2 sem log publicado) |
| Votos após 17h, pela hora do voto | 0,03% (34.330 de 127.697.270) |
| Sem biometria entre os votos após 17h | 15,9% (5.469) |
| Sem biometria antes das 17h | 12,4% (15.852.958 de 127.662.940) |
| Sem biometria após 17h, pela hora da identificação | 13,1% (3.359 de 25.676); antes: 12,4% |
| Tempo médio entre identificação e voto | 67 s sem biometria, 29 s com biometria |
| Seções sinalizadas | 5.244 (3.195 pela hora da identificação) |
| Comparecimento oficial fora dos logs lidos | 0,1% |

## Tamanho e tempo

- Requisições: cerca de 517 mil seções listadas nos `cs.json` (cerca de 18 mil entradas nunca recebem arquivos), um `aux.json`
  e um log por seção, ou seja cerca de 1 milhão de requisições. No teto padrão de 8 req/s, isso leva mais de 30 h.
- Download: 499.176 logs, 90,35 GB de `.logjez` (soma dos tamanhos originais), 1,82 bilhão de linhas do dia.
- Disco: `day/` com cerca de 32,7 GB (só as linhas de 25 e 26/10, gzip); `sections.sqlite` cerca de 255 MB;
  `raw/` (cópia de ~2% dos `.jez` originais e dos logs sem linhas do dia) cerca de 1,9 GB.
- `relatorio_17h.py`: a primeira leitura de todos os logs usa 8 processos (cerca de 40 min se fosse sequencial);
  com `cache_logs.json` (~144 MB) pronto, uma nova execução leva menos de 1 min. `secoes_analisadas.csv` tem ~34 MB.

## Ressalvas

- A hora usada no corte principal é a do registro do voto. A habilitação sem biometria demora mais (67 s contra 29 s,
  em média), então parte dos eleitores identificados antes das 17h só vota depois. Isso aumenta a fatia sem biometria
  após 17h (15,9% pela hora do voto, 13,1% pela hora da identificação, contra 12,4% antes das 17h).
- Em seções com urna trocada durante o dia, só o log da última urna é lido. Os logs internos das urnas substituídas,
  guardados dentro do log da urna de contingência, são ignorados. Por isso cerca de 0,1% do comparecimento oficial não
  entra na conta. Essas seções têm `urna_contingencia = 1`.
- O ajuste de fuso depende da tabela por UF e da hora da primeira habilitação. Um relógio de urna muito errado pode
  deslocar votos para o lado errado do corte.
- Habilitação sem biometria é procedimento previsto (eleitor sem biometria cadastrada ou digital não reconhecida), e
  votar depois das 17h é permitido a quem já estava na fila. Os números descrevem os registros; não indicam causa nem
  irregularidade.
- Disponibilidade: os caminhos `arquivo-urna` do site de resultados podem ser retirados depois da eleição (os de 2022
  já respondem 404). Em eleições anteriores, os mesmos arquivos ficaram nos zips por UF do conjunto
  "arquivos transmitidos para totalização" no Portal de Dados Abertos do TSE
  (`https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes{ano}/arqurnatot/bu_imgbu_logjez_rdv_vscmr_{ano}_{turno}t_{UF}.zip`).
  O coletor não lê esses zips; para usá-los é preciso adaptar a leitura.
- As imagens são HTML renderizado com a fonte Segoe UI (com `system-ui` e `sans-serif` como alternativas). Em sistemas
  sem essa fonte o texto muda um pouco de largura, mas os números não mudam.
