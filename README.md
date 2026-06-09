# Radar Solar

Plataforma digital para aproximar consumidores de energia solar (B2C) de empresas integradoras e prestadoras de serviços de manutenção (B2B). Desenvolvido como artefato avaliativo da disciplina **Projetos 1 (2026.1)** — Curso de Banco de Dados com ênfase em Ciência de Dados e IA, CESAR School.

---

## Problema

- Clientes com energia solar não conseguem monitorar consumo, injeção e performance da geração de forma simples.
- Integradores solares não têm visibilidade do mercado instalado na região metropolitana do Recife para direcionar campanhas e prospecção.

## Solução

Uma aplicação web com dois perfis de acesso:

- **B2C (Cliente):** dashboard com faturas, alertas de anomalia na geração e solicitação de manutenção.
- **B2B (Empresa/Integrador):** mapa de calor interativo com dados reais da ANEEL, pins de empresas PJ com dados da Receita (CNPJá), e kanban de leads.

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Framework web | NiceGUI (Python) |
| ORM | Peewee |
| Banco | SQLite |
| Dados | Pandas, PyArrow (Parquet) |
| Mapas | Leaflet.js + Chart.js |
| Shapefiles | PyShp (IBGE + Correios) |
| Autenticação | Firebase Magic Link |
| APIs externas | CNPJá (consulta CNPJ), Nominatim (geocoding), ViaCEP, BrasilAPI |
| Pipeline | Scripts Python com CLI flags |

---

## Arquitetura

```
run.py
  └── src.main
        ├── src.database       (SQLite + PRAGMA foreign_keys)
        ├── src.models         (6 modelos: Usuario, InstalacaoSolar,
        │                       Fatura, Lead, EmpresaPerfil, CnpjCache)
        ├── src.auth           (Firebase Magic Link + perfis)
        ├── src.utils          (utilitários compartilhados)
        ├── src.normalize      (normalização de fabricantes solares)
        └── src.ui.pages
              ├── public/      (homepage, login, auth_confirm)
              ├── cliente/     (dashboard, faturas, perfil)
              ├── empresa/     (kanban, perfil, mapa)
              └── demo/        (mapa público interativo)

scripts/
  ├── update_all.py            (orquestrador do pipeline)
  ├── update_aneel_data.py     (download ANEEL + parquet)
  ├── extract_aneel_rmr_csv.py (CSVs filtrados RMR)
  ├── update_cnpj_enderecos.py (enriquecimento CNPJ)
  └── init_db.py               (criação das tabelas)
```

### Estrutura de diretórios

```
radar-solar/
├── run.py              # Chave de ignição
├── src/                # Código fonte
│   ├── main.py         # Rotas e inicialização
│   ├── models.py       # Modelos do banco
│   ├── database.py     # Conexão SQLite
│   ├── utils.py        # Utilitários
│   ├── normalize.py    # Normalização de fabricantes
│   └── ui/             # Interface
│       ├── assets/     # CSS, JS, imagens
│       └── pages/      # Páginas por contexto
├── scripts/            # Pipeline de dados
├── docs/               # Documentação
└── data/               # Dados (não versionados)
```

---

## Funcionalidades

| # | Funcionalidade | Perfil | Status |
|---|---------------|--------|--------|
| RF01 | Login com Firebase Magic Link + seleção de perfil | Público | ✅ |
| RF02 | Mapa de calor interativo com dados ANEEL (RMR) | Público + B2B | ✅ |
| RF03 | Dashboard B2C com alertas de anomalia | Cliente | ✅ |
| RF04 | CRUD manual de faturas | Cliente | ✅ |
| RF05 | Solicitação de manutenção (cria lead) | Cliente | ✅ |
| RF06 | Kanban de leads B2B (Novo → Em Contato → Concluído) | Empresa | ✅ |
| RF07 | Gestão de clientes convertidos + WhatsApp | Empresa | 🔶 |
| RF09 | Pins de CNPJ no mapa com geocoding real | Empresa | ✅ |
| RNF02 | Modelagem SQLite + Peewee | — | ✅ |

---

## Como executar

```bash
# Instalar dependências
uv sync

# Inicializar banco
uv run python scripts/init_db.py

# Iniciar servidor
uv run python run.py
# Acessar http://localhost:8080

# Pipeline de dados (opcional, para atualizar mapa)
uv run python scripts/update_all.py

# Apenas validação
uv run python scripts/update_all.py --validate-only
```

---

## Documentação complementar

| Documento | Conteúdo |
|-----------|----------|
| `docs/followup_ementa.md` | Mapeamento de cada tópico da ementa para trechos de código |
| `docs/followup_requisitos.md` | Comparativo requisitos × implementado |
| `docs/plano_melhorias_codigo.md` | Plano de refatoração e melhorias |
| `docs/CHANGES.md` | Registro de alterações |
| `docs/der_radarsolar.png` | Diagrama Entidade-Relacionamento |

---

## Licença

MIT © 2026 Jader Santos
