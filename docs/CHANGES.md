# Radar Solar — Documento de Alterações

## 1. Extração de CSS/JS do `mapa.py`

O arquivo `src/ui/pages/demo/mapa.py` tinha **2.184 linhas**, sendo 260 de CSS inline e 917 de JavaScript inline. A maior função (`_render_demo_mapa_content`) concentrava todo o CSS, HTML e JS da página do mapa.

### O que foi feito

- **CSS extraído** para `src/ui/pages/demo/static/mapa.css` (254 linhas)
  - Carregado via `<link rel="stylesheet" href="/demo/static/mapa.css">` no `ui.add_head_html()`
  - Sem `<style>` tags, CSS puro

- **JavaScript extraído** para `src/ui/pages/demo/static/mapa.js` (913 linhas)
  - O único parâmetro variável (`data_url`) é passado via `window.DATA_URL` setado inline
  - Carregado via `<script src="/demo/static/mapa.js">`
  - `{{ }}` convertidos para `{ }` (escaping de f-string removido)
  - Todo o Leaflet + Chart.js, heatmap quartílico, 7 filtros, tabela paginada, pins de leads/PJs

- **Rota estática** adicionada em `src/main.py`:
  ```python
  app.add_static_files('/demo/static', str(CURRENT_DIR / 'ui' / 'pages' / 'demo' / 'static'))
  ```

### Resultado

| Métrica | Antes | Depois |
|---------|-------|--------|
| `mapa.py` | 2.184 linhas | 1.012 linhas (↓54%) |
| Manutenção CSS/JS | Dentro de string Python | Arquivos .css/.js independentes |
| Editor syntax highlight | Nenhum (string Python) | Completo |

---

## 2. Criação de `src/utils.py` — Funções Compartilhadas

Quatro funções estavam duplicadas em 3-4 arquivos diferentes, totalizando 9 definições idênticas ou quase idênticas.

### O que foi feito

Criado `src/utils.py` com 5 funções:

| Função | Origem (cópias removidas) | Comportamento |
|--------|---------------------------|---------------|
| `_only_digits(value)` | `empresa/perfil.py` | Extrai apenas dígitos |
| `_normalizar_estado(value)` | `cliente/perfil`, `cliente/dashboard`, `empresa/perfil` | Upper case, valida 2 letras (permite vazio) |
| `_normalizar_cep(value)` | `cliente/perfil`, `empresa/perfil` | Remove não-dígitos, valida 8 dígitos |
| `_buscar_endereco_por_cep(cep)` | `cliente/perfil`, `empresa/perfil` | ViaCEP API, retorna logradouro/cidade/estado |
| `_format_datetime_br(value)` | `cliente/dashboard`, `empresa/kanban` | Formata `dd/mm/aaaa às HH:MM` |

### Arquivos modificados para consumir `src.utils`

- `src/ui/pages/cliente/perfil.py` — `_normalizar_estado`, `_normalizar_cep`, `_buscar_endereco_por_cep`
- `src/ui/pages/cliente/dashboard.py` — `_normalizar_estado`, `_format_datetime_br`
- `src/ui/pages/empresa/perfil.py` — `_normalizar_estado`, `_normalizar_cep`, `_buscar_endereco_por_cep`
- `src/ui/pages/empresa/kanban.py` — `_format_datetime_br`

### Resultado

- -1.267 linhas líquidas em 6 arquivos editados
- +3 novos arquivos (mapa.css, mapa.js, utils.py)
- +1 novo script (update_all.py)
- Zero novas dependências externas

---

## 3. Pipeline Integrado `scripts/update_all.py`

Os 3 scripts de atualização de dados foram consolidados em um único orquestrador.

### Fluxo

```
update_all.py
├── 1/3: update_aneel_data.py
│   ├── Baixa CSVs ANEEL (se houver nova versão)
│   ├── Filtra PE + RMR
│   ├── Joins empreendimentos + info_técnica
│   └── Gera 5 parquets (instalações, municípios, bairros, equipamentos, série)
│
├── 2/3: extract_aneel_rmr_csv.py
│   ├── Lê ZIP bruto ANEEL
│   └── Extrai CSVs filtrados RMR
│
└── 3/3: update_cnpj_enderecos.py
    ├── Lê CNPJs não-cacheados do CSV
    ├── Consulta CNPJá (5 req/min)
    ├── Geocodifica Nominatim (1 req/s)
    ├── Popula CnpjCache (SQLite)
    └── Enriquece rmr_instalacoes.parquet com endereços reais
```

### Flags

| Flag | Efeito |
|------|--------|
| `--validate-only` | Verifica dados auxiliares (IBGE, Correios) |
| `--skip-cnpj` | Pula etapa CNPJ (lenta) |
| `--force` | Rebaixa tudo e regenera parquets |
| `--aneel-only` | Só etapa 1 |
| `--csv-only` | Só etapa 2 |
| `--cnpj-only` | Só etapa 3 |
| `--cnpj-limit N` | Limita quantidade de CNPJs pendentes processados |
| `--cnpj-dry-run` | Lista pendências CNPJ sem consultar APIs nem gravar dados |
| `--cnpj-skip-geocode` | Consulta CNPJá sem Nominatim |
| `--cnpj-no-parquet` | Não aplica cache CNPJ no parquet ao final |

### Exemplos de uso

```bash
# Pipeline completo
uv run python scripts/update_all.py

# Rápido (sem CNPJ) — ideal para cron diário
uv run python scripts/update_all.py --skip-cnpj

# Validação
uv run python scripts/update_all.py --validate-only

# Forçar recálculo
uv run python scripts/update_all.py --force
```

---

## 4. Melhorias Adicionais de Qualidade

### Rotas e tipagem

- `src/main.py`: adicionados `-> None` em handlers NiceGUI e `apply_theme()`
- Ajustado espaçamento de comentários inline existentes

### Integridade e migração de banco

- `src/database.py`: ativado `PRAGMA foreign_keys` no SQLite
- `src/models.py`: adicionados `on_delete` nas FKs:
  - `EmpresaPerfil.usuario` → `CASCADE`
  - `InstalacaoSolar.usuario` → `CASCADE`
  - `Fatura.instalacao` → `CASCADE`
  - `Lead.cliente` → `SET NULL`
  - `Lead.empresa_responsavel` → `SET NULL`
- `migrar_lead_empresa_responsavel_nullable()` agora verifica se a tabela existe e bloqueia execução se uma tabela temporária antiga ainda existir
- Campos de modelo planejados para o futuro foram mantidos

### Assets públicos

- `src/ui/pages/public/__init__.py` reduzido de 331 para 25 linhas
- CSS público extraído para `src/ui/assets/public.css`
- JavaScript Firebase extraído para `src/ui/assets/firebase-auth.js`

### Dependências

- `requirements.txt` sincronizado com `pyproject.toml` para manter compatibilidade com ambientes que ainda usam `pip -r requirements.txt`

### Pipeline CNPJ

- `scripts/update_cnpj_enderecos.py` agora aceita:
  - `--limit`
  - `--dry-run`
  - `--skip-geocode`
  - `--parquet-only`
  - `--no-parquet`
- `scripts/update_all.py` repassa flags CNPJ com prefixo `--cnpj-*`
- O orquestrador usa o mesmo interpretador Python (`sys.executable`) em vez de chamar `uv` recursivamente

### Refactors de UI

- `src/ui/pages/empresa/kanban.py`: formulário, resumo, estado vazio, colunas e cards de lead extraídos em helpers
- `src/ui/pages/cliente/faturas.py`: colunas de tabela, listagem e formatação de rows/options extraídas em helpers
- `src/ui/pages/cliente/perfil.py`: limpeza de campos de endereço extraída em helper
- `src/ui/pages/public/homepage.py`: header, hero, painel do produto, cards de perfil e footer extraídos em helpers
- `src/ui/pages/public/login.py`: configuração de perfis, intro e envio de magic link extraídos em helpers
- `src/ui/pages/empresa/perfil.py`: campos comerciais/endereço, busca CNPJ/CEP e salvar perfil separados em helpers
- `src/ui/pages/demo/mapa.py`: blocos HTML do mapa extraídos em helpers de renderização

---

## 5. Decisão: SQLite sem migrações formais no MVP

`PRAGMA foreign_keys=1` já está ativo em `src/database.py`. Para um MVP o SQLite no diretório do projeto é suficiente. Estratégia formal de migração fica postergada para depois do MVP, se necessário.

## 6. Próximas Melhorias (Pendentes)

Priorizadas no `docs/plano_melhorias_codigo.md`:

| Ordem | Item | Esforço | Impacto |
|-------|------|---------|---------|
| 1 | Continuar extraindo funções longas de UI/dados em helpers | 3h | 🟠 Legibilidade |
| 2 | Adicionar fallback CEP nos pins PJ do mapa | 1h | 🟢 UX |
| 3 | Melhorias contínuas de normalização em `normalize_joined_data()` | Contínuo | 🟢 Pipeline |
| 4 | Criar testes unitários para normalização/pipeline | 2h | 🟡 Segurança |
