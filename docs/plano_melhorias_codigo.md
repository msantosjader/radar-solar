# Radar Solar — Plano Atual de Melhorias do Código

Branch de trabalho: `refactor/code-quality-pipeline`

## Objetivo

Melhorar manutenibilidade, segurança operacional e clareza do código sem alterar regras de negócio já implementadas. Campos de modelo planejados para o futuro devem ser mantidos.

---

## Concluído Nesta Branch

| Item | Status | Arquivos principais |
|------|--------|---------------------|
| Extrair CSS/JS do mapa demo | ✅ Concluído | `src/ui/pages/demo/mapa.py`, `src/ui/pages/demo/static/mapa.css`, `src/ui/pages/demo/static/mapa.js` |
| Centralizar utilitários duplicados | ✅ Concluído | `src/utils.py`, perfis, dashboard, kanban |
| Criar pipeline único de atualização | ✅ Concluído | `scripts/update_all.py` |
| Extrair assets públicos inline | ✅ Concluído | `src/ui/pages/public/__init__.py`, `src/ui/assets/public.css`, `src/ui/assets/firebase-auth.js` |
| Adicionar type hints nas rotas | ✅ Concluído | `src/main.py` |
| Ativar `PRAGMA foreign_keys` | ✅ Concluído | `src/database.py` |
| Declarar `on_delete` nas FKs | ✅ Concluído | `src/models.py` |
| Tornar migração de lead mais defensiva | ✅ Concluído | `src/models.py` |
| Sincronizar `requirements.txt` | ✅ Concluído | `requirements.txt`, `pyproject.toml` |
| Refatorar Kanban B2B em helpers | ✅ Concluído | `src/ui/pages/empresa/kanban.py` |
| Reduzir duplicação no perfil cliente | ✅ Concluído | `src/ui/pages/cliente/perfil.py` |
| Extrair helpers parciais em faturas | ✅ Concluído | `src/ui/pages/cliente/faturas.py` |
| Adicionar flags operacionais no CNPJ | ✅ Concluído | `scripts/update_cnpj_enderecos.py`, `scripts/update_all.py` |

Verificações executadas:

```bash
python3 -m compileall -q src scripts
uv run python3 -u scripts/update_all.py --validate-only
```

---

## Decisões Mantidas

### Campos futuros nos models

Manter campos como `codigo_aneel`, `conta_contrato_celpe`, `modalidade_geracao`, `potencia_instalada_kwp` e `valor_estimado_rs`. Eles fazem parte do roadmap do domínio e serão preenchidos gradualmente pelo pipeline/telas futuras.

### Pins PJ no mapa

Manter pins PJ baseados em `CnpjCache` com latitude/longitude geocodificada. Evitar fallback por CEP enquanto ele gerar pontos aproximados demais ou cards com poucos dados úteis.

### Normalização

Evoluir `normalize_joined_data()` incrementalmente conforme novos casos reais aparecerem nos dados ANEEL. O pipeline integrado já permite que melhorias futuras entrem no ciclo completo.

---

## Melhorias Ainda Recomendadas

### 🔴 Alta Prioridade

| Item | Motivo | Próxima ação |
|------|--------|--------------|
| Criar testes unitários para normalização | O pipeline depende de parsing de datas, números BR, CEP e fabricantes | Testar `normalize_joined_data()`, `parse_float_series()`, `parse_int_series()` e `src.utils` |
| Criar testes do pipeline CNPJ sem bater em APIs reais | CNPJá/Nominatim têm rate limit e tempo alto | Mockar `consultar_cnpja()` e `geocodificar()` |
| Definir migrações reais de SQLite | `on_delete` declarado no model não altera constraints já criadas em banco existente | Criar estratégia de migração ou script versionado antes de produção |

### 🟠 Média Prioridade

| Item | Estado atual | Próxima ação |
|------|--------------|--------------|
| Reduzir funções longas restantes | Ainda há renderers e loaders grandes | Extrair helpers por seção, sem alterar callbacks |
| Unificar geração de CSV RMR no pipeline ANEEL | `update_all.py` ainda roda `extract_aneel_rmr_csv.py` depois de `update_aneel_data.py` | Fazer `update_aneel_data.py` também gerar os CSVs RMR usados pelo CNPJ |
| Tornar `update_cnpj_enderecos.py` ainda mais configurável | Já tem `--limit`, `--dry-run`, `--skip-geocode`, `--parquet-only`, `--no-parquet` | Avaliar `--refresh-days` para reconsultar cache antigo |
| Melhorar observabilidade do cron | Cron precisa logs claros e status | Logar início/fim/duração por etapa e saída estruturada simples |
| Revisar nullability de endereço em `InstalacaoSolar` | Campos obrigatórios usam `''` como placeholder em cadastro manual | Decidir se haverá migração para `null=True` antes de alterar schema |

### 🟢 Baixa Prioridade

| Item | Motivo | Próxima ação |
|------|--------|--------------|
| Padronizar idioma de nomes internos | Código mistura português/inglês | Manter domínio em português e helpers técnicos em inglês, documentando convenção |
| Reexportar páginas em `__init__.py` | Importações poderiam ficar mais curtas | Só fazer se começar a reduzir acoplamento nos imports |
| Cache busting de assets estáticos | CSS/JS externo pode ficar em cache no browser | Adicionar versão na URL se houver problema em deploy |

---

## Funções Ainda Longas

Lista atual após os refactors já feitos:

| Função | Arquivo | Situação recomendada |
|--------|---------|----------------------|
| `render_dashboard` | `src/ui/pages/cliente/dashboard.py` | Extrair cards, alertas, gráficos e dialogs |
| `render_faturas` | `src/ui/pages/cliente/faturas.py` | Continuar separando handlers e blocos UI |
| `render_perfil` | `src/ui/pages/cliente/perfil.py` | Separar card contato, card endereço, handlers CEP/salvar |
| `render_perfil_empresa` | `src/ui/pages/empresa/perfil.py` | Separar busca CNPJ, busca CEP, campos comerciais/endereço |
| `render_homepage` | `src/ui/pages/public/homepage.py` | Separar header, hero, cards e footer |
| `render_login` | `src/ui/pages/public/login.py` | Separar configuração de perfil, abas e painel |
| `carregar_instalacoes_aneel` | `src/ui/pages/demo/mapa.py` | Extrair serialização de linhas e cálculo de charts |
| `carregar_geojson_rmr` | `src/ui/pages/demo/mapa.py` | Extrair leitura de municípios, bairros, métricas e fallback |
| `carregar_leads_mapa` | `src/ui/pages/demo/mapa.py` | Extrair resolução de coordenadas e serialização do lead |
| `_render_demo_mapa_content` | `src/ui/pages/demo/mapa.py` | Mover blocos HTML para constantes/helpers |

---

## Próxima Sequência Sugerida

1. Adicionar testes unitários de normalização e utilitários.
2. Integrar a geração dos CSVs RMR dentro de `update_aneel_data.py`.
3. Refatorar `render_dashboard` e `render_faturas` em helpers menores.
4. Avaliar `--refresh-days` no cache CNPJ.
5. Definir estratégia formal de migrações SQLite antes do deploy OCI.
