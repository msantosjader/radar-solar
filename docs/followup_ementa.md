# Radar Solar — Mapeamento dos Tópicos da Ementa vs Código

## Disciplina: Fundamentos de Programação (BD004)
## Docente: Flávio da Silva Neves

Mapeamento de cada tópico do conteúdo programático da ementa para
trechos de código do projeto Radar Solar, com exemplos práticos.

---

## 1. Apresentação da Disciplina e Conceitos Fundamentais de Algoritmos

**Conteúdo:** Conceitos fundamentais de algoritmos, exemplos do cotidiano.

**No projeto:** Todo o sistema é uma materialização do conceito de algoritmo:
sequência de passos para transformar dados brutos da ANEEL em inteligência
comercial. O pipeline de dados ilustra isso claramente.

**Exemplo:** `scripts/update_aneel_data.py`
- Algoritmo de download, extração e transformação de dados da ANEEL
- Cada etapa é um passo bem definido: baixar ZIP → extrair CSV →
  filtrar RMR → cruzar equipamentos → gerar parquet

---

## 2. Lógica de Programação e Resolução de Problemas

**Conteúdo:** Raciocínio lógico, decomposição de problemas.

**No projeto:** Decomposição do problema "mapa comercial de energia solar"
em módulos: login, dashboard B2C, dashboard B2B, mapa, kanban, cache CNPJ.

**Exemplo:** `src/ui/pages/demo/mapa.py:702-760` — `carregar_pjs_mapa()`

```
def carregar_pjs_mapa(data: dict) -> list[dict]:
    # 1. Agregar instalações de todos os municípios
    # 2. Filtrar apenas PJ com CNPJ
    # 3. Consultar cache CNPJá
    # 4. Montar endereço completo (com fallback)
    # 5. Montar pin com dados + coordenadas
```

Cada etapa resolve um subproblema específico.

---

## 3. Representação de Algoritmos: Pseudocódigo e Fluxogramas

**Conteúdo:** Estrutura sequencial, representação de soluções.

**No projeto:** A estrutura do código-fonte funciona como pseudocódigo
executável. As funções são nomeadas de forma descritiva, servindo como
documentação do algoritmo.

**Exemplo:** `src/ui/pages/cliente/faturas.py:143-350`
O fluxo de criação de fatura segue uma sequência lógica clara:
1. Validar dados de entrada
2. Verificar duplicidade de competência (`_usuario_ja_tem_fatura_na_competencia`, linha 95)
3. Salvar no banco
4. Atualizar listagem
5. Exibir feedback ao usuário

---

## 4. Introdução ao Python e Ambiente de Desenvolvimento

**Conteúdo:** Primeiros programas, entrada/saída de dados.

**No projeto:** Uso intensivo de funções built-in do Python.

**Exemplos:**
- `src/normalize.py:9-11` — normalização de string
```python
def _strip_accents(value: str) -> str:
    nfkd = unicodedata.normalize('NFKD', value)
    return ''.join(char for char in nfkd if not unicodedata.combining(char))
```

- `scripts/update_cnpj_enderecos.py:30-31`
```python
def only_digits(value: object) -> str:
    return ''.join(ch for ch in str(value) if ch.isdigit())
```

- `src/ui/pages/demo/mapa.py:122-124`
```python
def _number(value: object) -> float:
    try:
        return float(str(value).replace(',', '.').strip())
    except (ValueError, TypeError):
        return 0.0
```

---

## 5. Variáveis, Tipos de Dados e Operadores

**Conteúdo:** Tipos primitivos (int, float, str, bool), operadores aritméticos,
relacionais e lógicos.

**No projeto:**

**Operadores aritméticos:**
- `src/ui/pages/cliente/dashboard.py:111`
```python
queda_percentual = ((anterior - atual) / anterior) * 100
```

- `src/ui/pages/cliente/perfil.py:50`
```python
if dados['cep'] and len(_normalizar_cep(dados['cep'])) == 8:
```

**Operadores relacionais e lógicos (if/else):**
- `src/ui/pages/cliente/dashboard.py:112-118` — alerta de queda de geração
```python
if queda_percentual >= LIMIAR_QUEDA_GERACAO_PERCENT:  # 20%
    alertas.append(f'Queda de geracao acima do limite...')
else:
    status.append('Geracao dentro da faixa esperada...')
```

**Operadores lógicos (`and`, `&`, `|`):**
- `src/auth.py:56-63` — combinação de condições em Python puro
```python
if usuario_existente and usuario_existente.tipo_perfil != tipo_perfil:
    raise PerfilConflitanteError(...)
```

- `src/ui/pages/empresa/kanban.py:35-38` — AND/OR em consulta Peewee
```python
Lead.select().where(
    (Lead.status.in_(STATUS_KANBAN))
    & ((Lead.empresa_responsavel.is_null(True)) | (Lead.empresa_responsavel == empresa_id))
)
```

**Concatenação de strings:**
- `src/ui/pages/demo/mapa.py:729`
```python
endereco_rel = ', '.join(p for p in [logradouro_rel, numero_rel,
                         bairro_rel, cache.cidade or '', cache.estado or ''] if p)
```

---

## 6. Estruturas de Decisão: if, elif, else

**Conteúdo:** Tomada de decisão com condicionais.

**No projeto:** Uso abundante em validações, autorizações, formatação condicional.

**Exemplos:**

- `src/ui/pages/empresa/kanban.py:33-37` — filtro de leads (abertos + da empresa)
```python
Lead.select().where(
    (Lead.status.in_(STATUS_KANBAN))
    & ((Lead.empresa_responsavel.is_null(True)) | (Lead.empresa_responsavel == empresa_id))
)
```

- `src/auth.py:56-63` — bloqueio de perfil conflitante
```python
if usuario_existente and usuario_existente.tipo_perfil != tipo_perfil:
    perfil_existente = TIPO_TO_LABEL.get(usuario_existente.tipo_perfil, ...)
    perfil_solicitado = TIPO_TO_LABEL.get(tipo_perfil, ...)
    raise PerfilConflitanteError(
        f'Este e-mail ja esta cadastrado como {perfil_existente}. '
        f'Para acessar como {perfil_solicitado}, use outro e-mail.'
    )
```

- `src/ui/pages/demo/mapa.py:732-734` — fallback de endereço
```python
if bairro_rel and bairro_rel != 'Nao identificado':
    endereco_rel = f'{inst["municipio"]}, {bairro_rel}'
```

---

## 7. Estruturas de Repetição: while

**Conteúdo:** Laço while, controle de repetição.

**No projeto:**

- `scripts/update_cnpj_enderecos.py:72-75` — retry em rate limit
```python
if exc.code == 429:
    print('  Rate limited. Aguardando 60s...')
    time.sleep(60)
    return consultar_cnpja(cnpj)  # recursão simulando while
```

**Nota:** O `while` é usado indiretamente via recursão no retry da API.
No mapa, o loop principal é o `forEach`/`map` do JavaScript (que equivale
a um `while`/`for`), mas no backend Python optamos por `for` com iteráveis
por ser mais idiomático.

---

## 8. Estruturas de Repetição: for

**Conteúdo:** Laço for, iteração sobre intervalos e coleções.

**No projeto:** O `for` é a estrutura de repetição mais usada no sistema.

**Exemplos:**

- `scripts/update_cnpj_enderecos.py:139-147` — iterar CNPJs do DataFrame
```python
for _, row in df.iterrows():
    cnpj = only_digits(row['NumCPFCNPJ'])
    if len(cnpj) == 14:
        mapa[str(row['CodEmpreendimento']).strip()] = cnpj
```

- `src/ui/pages/demo/mapa.py:704-705` — agregar instalações por município
```python
for lista in data['instalacoesPorMunicipio'].values():
    instalacoes.extend(lista)
```

- `src/ui/pages/demo/mapa.py:713-716` — iterar PJs e montar pins
```python
for inst in pjs:
    cnpj = ''.join(ch for ch in inst['cpf_cnpj'] if ch.isdigit())
    if len(cnpj) != 14:
        continue
```

- `scripts/update_cnpj_enderecos.py:51-57` — ler CSV linha a linha
```python
for linha in linhas[1:]:
    partes = linha.split(';')
    if idx >= len(partes):
        continue
    cnpj_raw = only_digits(partes[idx])
    if len(cnpj_raw) == 14:
        cnpjs_unicos.add(cnpj_raw)
```

---

## 9. Estruturas Básicas de Dados: Listas

**Conteúdo:** Criação, manipulação, percurso, operações básicas.

**No projeto:**

- `src/ui/pages/demo/mapa.py:708` — lista de pins
```python
pins: list[dict] = []
```

- `src/ui/pages/demo/mapa.py:739-758` — append e manipulação de listas
```python
pins.append({
    'codigo': inst['codigo'],
    'titular': inst['titular'],
    'cnpj': cnpj,
    ...
})
```

- `scripts/update_cnpj_enderecos.py:59` — list comprehension com set
```python
return sorted(cnpjs_unicos)  # set convertido em lista ordenada
```

- `src/normalize.py:27-29` — list comprehension com filtro
```python
conectores = {'DE', 'DO', 'DA', 'DAS', 'DOS', 'E'}
return ' '.join(part for part in value.split() if part not in conectores)
```

---

## 10. Estruturas de Dados Complementares: Tuplas e Dicionários

**Conteúdo:** Tuplas, dicionários, aplicações práticas.

**No projeto:**

**Dicionários** — estrutura mais usada depois de listas:
- `src/ui/pages/demo/mapa.py:23-38` — conjunto de municípios da RMR (set)
```python
RMR_MUNICIPIOS = {
    '2600054',  # Abreu e Lima
    '2601052',  # Aracoiaba
    '2602902',  # Cabo de Santo Agostinho
    ...
}
```

- `src/ui/pages/demo/mapa.py:709-711` — dict comprehension
```python
cnpj_cache: dict[str, CnpjCache] = {
    c.cnpj: c for c in CnpjCache.select()
}
```

- `src/models.py:102-118` — campos do modelo `CnpjCache` via Peewee

**Tuplas** — usadas para coordenadas, retorno de funções, pares chave-valor:
- `src/ui/pages/demo/mapa.py:736-737`
```python
lat, lng = cache.latitude, cache.longitude
```

- `src/ui/pages/demo/mapa.py:763-766`
```python
def _estimar_coordenada_por_cep(
    municipio_codigo: str, cep_digits: str, prefixo: str,
    ...
) -> tuple[float | None, float | None]:
```

- `src/normalize.py:27-29` — tuplas de conectores (set)
```python
conectores = {'DE', 'DO', 'DA', 'DAS', 'DOS', 'E'}
```

---

## 11. Funções e Modularização

**Conteúdo:** Definição e uso de funções, parâmetros, retorno e escopo.

**No projeto:** Todo o sistema é estruturado em funções e módulos.

**Exemplos:**

- `src/normalize.py` — módulo dedicado a normalização
```python
def normalizar_modulo(value: str | None) -> str: ...  # linha 687
def normalizar_inversor(value: str | None) -> str: ...  # linha 690
```

- `src/ui/pages/demo/mapa.py` — funções auxiliares no mapa
```python
def _text(value: object) -> str: ...                # linha 128
def _number(value: object) -> float: ...             # linha 122
def _date_br(value) -> str: ...                     # linha 134
def _bairro_key(value: str) -> str: ...             # linha 166
def _shape_centroid(geometry: dict) -> ...           # linha 88
```

- `scripts/update_cnpj_enderecos.py` — pipeline modularizado
```python
def carregar_cnpjs_do_csv() -> list[str]: ...         # linha 34
def consultar_cnpja(cnpj: str) -> dict | None: ...    # linha 62
def extrair_dados_cnpj(dados: dict) -> dict: ...      # linha 83
def geocodificar(endereco: str) -> tuple[...]: ...     # linha 125
def atualizar_parquet() -> None: ...                   # linha 151
def main() -> int: ...                                 # linha 224
```

---

## 12. Algoritmos Estruturados e Boas Práticas

**Conteúdo:** Organização, legibilidade, reuso de código, refatoração.

**No projeto:**

**Organização:** Separação clara em módulos: `src/models.py` (dados),
`src/ui/` (interface), `scripts/` (utilitários), `src/normalize.py` (lógica),
`src/auth.py` (autenticação), `src/utils.py` (compartilhados).

**Reuso:**
- `src/normalize.py` é importado por `src/ui/pages/demo/mapa.py:21`
```python
from src.normalize import normalizar_inversor, normalizar_modulo
```

- `src/utils.py` é compartilhado entre cliente e empresa:
```python
from src.utils import _buscar_endereco_por_cep, _normalizar_cep, _normalizar_estado
```

**Refatoração:**
- `src/ui/pages/demo/mapa.py:295-323` — função que monta instalações é
  reusada tanto pelo mapa quanto pela tabela e gráficos
- `scripts/update_cnpj_enderecos.py:151-180` — `atualizar_parquet()` é
  reusada no final do script e também chamada quando não há pendentes

**Legibilidade:**
- Nomes descritivos: `carregar_pjs_mapa`, `geocodificar`, `_normalizar_telefone_whatsapp`
- Type hints em todas as funções
- Constantes nomeadas: `LIMIAR_QUEDA_GERACAO_PERCENT = 20.0`, `STATUS_KANBAN = ['Novo', 'Em Contato', 'Concluído']`

---

## 13. Integração de Conceitos

**Conteúdo:** Uso combinado de estruturas de controle e dados.

**No projeto:** O mapa `/demo/mapa` é o melhor exemplo de integração:

1. **Sets** para configurar municípios (`RMR_MUNICIPIOS`)
2. **Dicionários** para consultas de cache (CNPJ cache dict comprehension)
3. **Listas** para coleções de instalações e pins
4. **For** para iterar e montar dados
5. **If/else** para filtros e formatação condicional
6. **Funções** para modularizar o código
7. **Tuplas** para retorno de coordenadas
8. **Arquivos** (parquet/CSV/shapefile) para persistência
9. **API externa** para geocoding (Nominatim) e consulta CNPJ (CNPJá)
10. **JSON** para serialização e envio ao frontend

**Exemplo no pipeline de dados (`scripts/update_aneel_data.py`):**
1. Download de ZIP com `urllib`
2. Extração com `zipfile`
3. Leitura com `pandas`
4. Filtro com expressões booleanas
5. Agrupamento com `groupby`
6. Normalização com dicionários
7. Escrita em parquet

**Leitura de dados e arquivos no projeto:**
- `src/ui/pages/demo/mapa.py:281` — leitura de Parquet com instalações ANEEL
```python
df = pd.read_parquet(INSTALACOES_PARQUET, columns=colunas)
```

- `src/ui/pages/demo/mapa.py:398` — leitura de shapefile do IBGE
```python
municipio_reader = shapefile.Reader(str(MUNICIPIOS_SHP), encoding='cp1252')
```

- `scripts/update_cnpj_enderecos.py:39` — leitura de CSV como texto
```python
linhas = EMPREENDIMENTOS_CSV.read_text(encoding='latin1').splitlines()
```

---

## 14. Desenvolvimento de Algoritmos Aplicados

**Conteúdo:** Implementação de um problema completo em Python.

**No projeto:** O projeto completo é a aplicação prática. Dois algoritmos
de destaque:

**Algoritmo de geocoding com fallback** (`src/ui/pages/demo/mapa.py:763-799`):
```
1. Tentar CEP exato → buscar bairro no shapefile
2. Se não achar, tentar prefixo do CEP (5 dígitos) → buscar bairro
3. Se não achar, usar centróide do bairro fallback
4. Se não achar, usar centróide do município
5. Retornar (lat, lng) ou (None, None)
```

**Algoritmo de normalização de fabricantes** (`src/normalize.py:32-686`):
```
1. Dicionário de ~200 sinônimos de módulo + ~170 de inversor
2. Normalizar string (upper case, remover acentos)
3. Busca por prefixo no sinônimo
4. Fallback: similaridade fuzzy (difflib)
5. Retornar nome normalizado ou título original
```

---

## 15. Testes e Validação de Algoritmos

**Conteúdo:** Testes e validação das soluções, correção lógica.

**No projeto:** A validação é feita de forma prática:

- **Validação de dados** em `src/ui/pages/cliente/faturas.py:185-190`:
```python
if not mes_referencia.value or not consumo_kwh.value or not valor_fatura_rs.value:
    ui.notify('Preencha mes de referencia, consumo e valor da fatura', type='warning')
    return
```

- **Validação de CPF/CNPJ** em `src/ui/pages/demo/mapa.py:714-715`:
```python
cnpj = ''.join(ch for ch in inst['cpf_cnpj'] if ch.isdigit())
if len(cnpj) != 14:
    continue
```

- **Validação de coordenadas** em `src/ui/pages/demo/mapa.py:718-719`:
```python
if not cache or cache.latitude is None or cache.longitude is None:
    continue
```

- **Tratamento de erros de API** em `scripts/update_cnpj_enderecos.py:68-80`:
```python
except HTTPError as exc:
    if exc.code == 404:
        return {'taxId': cnpj, 'company': {}}
    if exc.code == 429:
        time.sleep(60)
        return consultar_cnpja(cnpj)
except (URLError, TimeoutError, json.JSONDecodeError) as exc:
    return None
```

**Observação:** Testes unitários formais com `pytest` ainda não foram
implementados (pendente para próximas sprints).

---

## Resumo por Aula

| Aula | Data | Conteúdo | Onde usamos no projeto |
|------|------|----------|----------------------|
| 1 | 11/2 | Apresentação, algoritmos | Todo o sistema |
| 2 | 25/2 | Lógica, decomposição | `carregar_pjs_mapa()` — quebra em 5 passos (`mapa.py:702`) |
| 3 | 4/3 | Pseudocódigo, fluxogramas | Nomes descritivos de funções (`_estimar_coordenada_por_cep`) |
| 4 | 11/3 | Python, I/O | `only_digits()` (`cnpj_enderecos.py:30`), `_number()` (`mapa.py:122`) |
| 5 | 18/3 | Variáveis, tipos, operadores | `dashboard.py:111` (queda_percentual = ((anterior - atual) / anterior) * 100) |
| 6 | 25/3 | if/elif/else | Filtro de leads, PerfilConflitanteError (`auth.py:56`) |
| 7 | 1/4 | while | Retry de rate limit (recursão, `cnpj_enderecos.py:72`) |
| 8 | 8/4 | for | `for inst in pjs` (`mapa.py:713`), `for linha in linhas` (`cnpj_enderecos.py:51`) |
| 9 | 15/4 | **AV1** | — |
| 10 | 22/4 | Listas | `pins.append({...})` (`mapa.py:739`), list comprehensions |
| 11 | 29/4 | Tuplas, dicionários | `tuple[float, float]` (`mapa.py:763`), `RMR_MUNICIPIOS` (`mapa.py:23`), dict comprehensions |
| 12 | 6/5 | Funções, modularização | `normalizar_modulo()`, `geocodificar()`, `extrair_dados_cnpj()` |
| 13 | 13/5 | Boas práticas, refatoração | Separação em módulos, type hints, reuso via `src/normalize.py`, `src/utils.py` |
| 14 | 20/5 | Integração de conceitos | Mapa completo (listas + dicts + for + if + funções + API + JSON) |
| 15 | 27/5 | Algoritmos aplicados | Pipeline ANEEL + geocoding com fallback (`mapa.py:763`) |
| 16 | 3/6 | Revisão prática | — |
| **17** | **10/6** | **Apresentação do projeto** | **Radar Solar — este repositório** |
| 18 | 17/6 | **AV2** | — |
| — | 13/6 | **SR2** | **Entrega do projeto + pitch** |
| — | 20/6 | **Mostra TechDesign** | **Exposição do projeto** |
