# Radar Solar — Comparativo: Ementa vs Realizado

## Objetivo

Confrontar os Requisitos Funcionais (RF) e Não Funcionais (RNF) definidos no Trello
(`radar_solar_export.json`) com o que foi efetivamente implementado no projeto, apontando
o que está feito, o que foi melhorado em relação ao especificado e o que ainda está pendente.

---

## Convenções

| Símbolo | Significado |
|---------|-------------|
| ✅ | Implementado conforme o especificado |
| ✅+ | Implementado com melhorias/ampliações |
| 🔶 | Parcialmente implementado |
| ❌ | Não implementado |

---

## Requisitos Funcionais (RF)

### RF01 — Login Firebase Magic Link

**Especificado:**
- Usuário recebe link de acesso por e-mail (Firebase Magic Link)
- Dashboard separados para Cliente (B2C) e Empresa (B2B)
- Direcionamento correto com base no perfil

**Status: ✅+**

**O que foi implementado:**
Login com Firebase Magic Link em `/login`. Seleção de perfil (Cliente/Empresa)
antes do envio do link. Tratamento de perfil conflitante (bloqueia e informa
o perfil correto). Toda a autenticação em `src/ui/pages/public/`.

**Melhorias em relação ao especificado:**
- Interface de seleção de perfil antes do magic link (RF01.1 absorvida)
- Sistema de perfil conflitante: se o e-mail já tem conta, o login direciona
  automaticamente e avisa
- Bloqueio de login com perfil incorreto via `PerfilConflitanteError`
- Perfil Comercial (Integrador) adicionado ao lado de Empresa

---

### RF02 — Painel B2B: Mapa de Calor (Dados ANEEL)

**Especificado:**
- Mapa visualiza áreas com maior potencial solar para direcionar campanhas

**Status: ✅+**

**O que foi implementado:**
Mapa interativo Leaflet em `/demo/mapa` (público) e `/empresa/mapa` (logado).
Camadas: municípios + bairros com heatmap quartílico, 7 gráficos Chart.js
(evolução temporal, pizza por classe/tipo/modalidade/porte, PF/PJ),
tabela com 16 colunas, filtros por classe/tipo/porte/bairro/fabricante/modalidade.

**Melhorias em relação ao especificado:**
- Heatmap hierárquico: RMR → município → bairro (zoom interativo)
- Normalização de fabricantes de módulo/inversor
- Carregamento via HTTP (~30 MB) em vez de websocket, evitando timeout
- Endpoints separados: demo público (cache 5 min) e empresa (autenticado por token)
- Cache do payload base em memória (`lru_cache`)
- Toggle de nomes e toggle de empresas

---

### RF03 — Dashboard B2C (Consumo, Injeção e Alertas de Anomalia)

**Especificado:**
- Tela com tradução simples da fatura (consumo, injeção e créditos)
- Alerta visual se detectar queda de performance na geração

**Status: ✅+**

**O que foi implementado:**
Dashboard B2C em `/cliente/dashboard` com cartões de consumo, injeção,
créditos acumulados, saldo do mês, economia, geração estimada,
e alerta de anomalia (vermelho quando geração estimada < consumo * 0.8).

**Melhorias em relação ao especificado:**
- Botão "Solicitar Manutenção" no próprio dashboard (gatilho de lead)
- Cálculo de economia acumulada e payback estimado
- Visão mensal com tabela de histórico
- Score de oportunidade para o cliente

---

### RF04 — CRUD Manual de Fatura B2C

**Especificado:**
- Interface para entrada manual de dados da conta de energia
- Cliente consegue corrigir dados inseridos
- Sistema salva no SQLite vinculado ao usuário

**Status: ✅**

**O que foi implementado:**
CRUD completo em `/cliente/faturas`: formulário com consumo, valor,
injeção, créditos recebidos, competência (mês/ano). Validações de
duplicidade por competência. Edição e exclusão.

---

### RF05 — Botão Solicitar Manutenção (Criação de Lead)

**Especificado:**
- Dashboard B2C possui botão claro para solicitar manutenção
- Ao clicar, dados do cliente enviados como lead qualificado

**Status: ✅**

**O que foi implementado:**
Botão "Solicitar Manutenção" no dashboard B2C. Cria lead vinculado ao
cliente e à primeira empresa disponível. Lead aparece no kanban B2B
e como pin no mapa da empresa.

---

### RF06 — Painel B2B: Funil Kanban de Leads

**Especificado:**
- Gestão de leads via quadro Kanban
- Colunas: Novo, Em Contato e Concluído
- Empresa pode adicionar leads
- Leads aparecem como pin no mapa

**Status: ✅+**

**O que foi implementado:**
Kanban completo em `/empresa/kanban` com arrastar e soltar entre colunas
Novo → Em Contato → Concluído. Leads aparecem como pins coloridos no mapa
(azul = Novo, laranja = Em Contato, verde = Concluído).

**Melhorias em relação ao especificado:**
- Criação de lead manual com e-mail (cria usuário B2C automaticamente se não existir)
- Filtro por empresa responsável: mostra leads sem empresa + leads do integrador
- Integrador pode criar leads manuais por e-mail
- Botão WhatsApp no card do lead (abre wa.me/{telefone})

---

### RF07 — Gestão de Clientes B2B + Botão WhatsApp

**Especificado:**
- Lista de clientes convertidos no painel da empresa
- Botão de redirecionamento para API do WhatsApp

**Status: 🔶**

**O que foi implementado:**
Botão WhatsApp existe no Kanban (nos cards de lead). Não há uma lista
específica de "clientes convertidos" separada do kanban.

**Diferença:** O WhatsApp foi implementado antes de uma tela de clientes
ativos. A lista de clientes convertidos está implícita no kanban
(leads em "Concluído"), mas não há uma tela dedicada de gestão de
clientes ativos.

---

### RF08 — Upload de PDF da Fatura (OCR)

**Status: ❌**

**Não implementado.** A inserção de faturas é puramente manual.
Não há upload de PDF nem extração OCR.

**Observação:** RF04 (CRUD manual) foi priorizado como MVP para validar
o fluxo sem depender de integração complexa de OCR.

---

### RF09 — Mapa B2B: Pins de CNPJ para Prospecção

**Especificado:**
- Backend consulta lat/lng dos usuários na base
- Pin sobreposto ao heatmap da ANEEL
- Balão com identificação básica ao clicar

**Status: ✅+**

**O que foi implementado:**
Pins roxos de PJ no mapa empresa (e demo). Card completo com:
ID, CNPJ formatado, razão social, endereço uppercase, CEP formatado,
data de instalação, módulos/potência, telefone e e-mail (via CNPJá).

**Melhorias em relação ao especificado:**
- Geocodificação real (Nominatim) em vez de coordenada aproximada
- Cache CNPJ (CNPJá) com telefone e e-mail reais da Receita
- Filtro por município selecionado
- Toggle Mostrar/Ocultar empresas
- Card seccionado (ID, Empresa, Endereço, Instalação, Contato)

---

### RF12 — Automação Total: Faturas via E-mail

**Status: ❌**

**Não implementado.** Não há webhook de e-mail nem processamento
automático de anexos.

---

### RF13 — Algoritmo Inteligente de Clima (Z-Score / Open-Meteo)

**Status: ❌**

**Não implementado.** Não há integração com Open-Meteo nem cálculo
de Z-Score. O alerta de anomalia atual é baseado em regra simples
(geração estimada < consumo * 0.8).

---

## Requisitos Não Funcionais (RNF)

### RNF01 — Setup de Ferramentas (Git, Trello, NiceGUI)

**Status: ✅**

Repositório GitHub criado, Trello com colunas/etiquetas/cartões,
projeto NiceGUI configurado com `pyproject.toml` e `uv`.

---

### RNF02 — Modelagem do Banco de Dados (SQLite + Peewee)

**Especificado:**
- Arquivo `models.py` criado
- Classe `Usuario` com Firebase UID e tipo de perfil
- Classe `EnderecoInstalacao` com FK para Usuário
- Classes `Fatura` e `Lead` implementadas

**Status: ✅+**

**O que foi implementado:**
`src/models.py` com `Usuario`, `EmpresaPerfil`, `InstalacaoSolar`,
`Fatura`, `Lead`, `CnpjCache`. Banco SQLite gerado via Peewee.

**Melhorias em relação ao especificado:**
- `CnpjCache` adicionado (cache de consultas CNPJá)
- `InstalacaoSolar` com latitude/longitude para geocoding
- `EmpresaPerfil` com perfil do integrador
- Migração automática de colunas nullable

---

### RNF03 — Deploy Inicial na Oracle Cloud

**Status: ❌**

**Não implementado.** Nenhuma configuração de deploy, Docker,
ou acesso à OCI foi realizada.

---

### RNF04 — CI/CD com GitHub Actions

**Status: ❌**

**Não implementado.** Não há diretório `.github/workflows/` nem
arquivos de pipeline.

---

### RNF05 — Caça a Bugs, Testes e Ajustes Finais de UI

**Status: 🔶**

Em andamento. Vários bugs de UI corrigidos ao longo das sprints.
Falta o teste end-to-end formalizado.

---

### RNF06 — Preparação para SR2 (Pitch e Demonstração)

**Status: 🔶**

O sistema está funcional e demonstrável. Falta preparar os slides
e o vídeo de demonstração conforme os critérios do SR2 (13/6).

---

### RNF07 — Testes Unitários com Pytest

**Status: ❌**

**Não implementado.** Não há diretório `tests/`, `conftest.py`,
nem dependência `pytest` no projeto.

---

## Resumo

### Implementado ✅ (total ou com melhorias)

| # | Item | Observação |
|---|------|------------|
| RF01 | Login Firebase + Perfil | + bloqueio de perfil conflitante |
| RF02 | Mapa de calor ANEEL | + heatmap hierárquico, gráficos, filtros |
| RF03 | Dashboard B2C | + alerta, economia, botão manutenção |
| RF04 | CRUD fatura manual | conforme especificado |
| RF05 | Solicitar manutenção | conforme especificado |
| RF06 | Kanban B2B | + lead manual por e-mail, WhatsApp |
| RF09 | Pins CNPJ no mapa | + geocoding, cache CNPJá, card completo |
| RNF01 | Setup Git/Trello/NiceGUI | concluído |
| RNF02 | Modelagem banco | + CnpjCache, EmpresaPerfil, geocoding |

### Parcialmente implementado 🔶

| # | Item | Pendência |
|---|------|-----------|
| RF07 | Gestão clientes B2B | Falta tela dedicada de clientes ativos |
| RNF05 | Testes e ajustes UI | Falta teste E2E formal |
| RNF06 | Preparação SR2 | Falta slides e vídeo |

### Não implementado ❌

| # | Item | Prioridade |
|---|------|------------|
| RF08 | Upload PDF + OCR | Média (diferencial de usabilidade) |
| RF12 | Faturas via e-mail | Baixa (visão de futuro) |
| RF13 | Z-Score + Open-Meteo | Baixa (inteligência avançada) |
| RNF03 | Deploy Oracle Cloud | **Alta (necessário para apresentação)** |
| RNF04 | CI/CD GitHub Actions | Média |
| RNF07 | Testes unitários pytest | Média |

---

## O que fizemos melhor que o especificado

1. **Cache CNPJ com CNPJá**: a especificação original pedia pins no mapa com
   dados básicos. Criamos um pipeline completo de consulta à CNPJá + geocoding
   Nominatim + cache SQLite, resultando em pins com telefone, e-mail e endereço
   real, não apenas coordenadas aproximadas.

2. **Perfil Integrador**: não previsto no Trello. Adicionamos o perfil Comercial/
   Integrador com tela própria e permissão para criar leads manuais.

3. **Leads manuais por e-mail**: a especificação só previa leads vindos do
   botão "Solicitar Manutenção". Implementamos criação manual com auto-cadastro
   de cliente B2C se o e-mail não existir.

4. **Mapa hierárquico**: a especificação pedia "um mapa com heatmap".
   Implementamos zoom RMR → município → bairro com heatmap quartílico em
   cada nível, além de 7 gráficos Chart.js dinâmicos.

5. **Normalização de fabricantes**: tratamento de dezenas de variações
   ortográficas de fabricantes de módulo/inversor (ex: "Jinko", "JINKO",
   "Jinkosolar" → "Jinko").

6. **Card completo do pin**: a especificação pedia "balão com identificação
   básica". Criamos card seccionado com endereço uppercase, CNPJ formatado,
   CEP formatado, data de instalação, mod/potência, telefone e e-mail.

---

## Próximos passos prioritários (para SR2)

1. **RNF03 — Deploy na Oracle Cloud** (imprescindível para demonstração ao vivo)
2. **RNF06 — Slides e vídeo do SR2** (obrigatório, prazo 13/6)
3. **RNF07 — Testes unitários básicos** (critério de avaliação)
4. **RF07 — Lista de clientes ativos B2B** (diferencial)
5. **RNF05 — Teste end-to-end e ajustes finais**
