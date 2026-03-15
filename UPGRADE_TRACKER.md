# 🚀 DBDE AI Assistant — Plano de Melhorias

> **Última atualização:** 2026-03-15
> **Ambiente:** Azure Web App `millennium-ai-assistant` · `https://dbdeai.pt`
> **App Service Plan:** P1v3 PREMIUMV3 (8 GB RAM, 2 vCPU)

---

## Estado Geral

| # | Feature | Estado | Commits | Testes |
|---|---------|--------|---------|--------|
| 0 | Infraestrutura P1v3 | ✅ Concluído | `a967512` | — |
| 1 | Perguntas de Clarificação | ✅ Concluído | `57a5226` | ✅ Pass |
| 2 | PowerPoint Branded (BCP) | ✅ Concluído | `56f215c` `2fd4d25` `06275ac` `61ffc02` | ✅ 33 testes |
| 3 | Excel Avançado | ✅ Concluído | `0b8acd2` | ✅ 56 testes |
| 4 | Auto-Rule Generation | ⬜ Não iniciado | — | — |
| 5 | SQL Server Connector | ⬜ Não iniciado | — | — |
| 6 | Semantic Search v2 | ⬜ Não iniciado | — | — |
| — | Deploy | ✅ Live | — | — |

**Total testes:** 481 (392 existentes + 33 PPTX + 56 XLSX) · Todos a passar ✅

---

## Detalhe por Feature

### ✅ Feature 0 — Infraestrutura P1v3
- Upgrade de S2 → P1v3 PREMIUMV3 (8 GB RAM)
- Uvicorn 3 workers otimizado
- **Commit:** `a967512`

### ✅ Feature 1 — Perguntas de Clarificação Inteligentes
- Quick-reply buttons no frontend
- TTS integrado
- Sistema de clarificação antes de executar tools
- **Commit:** `57a5226`

### ✅ Feature 2 — PowerPoint Branded (Millennium BCP)
Arquitetura de 3 camadas:

| Camada | Descrição |
|--------|-----------|
| **Opus AI Planner** | Claude Opus 4.6 planeia slides com 10 regras gold-standard |
| **Validation Layer** | Auto-correção: split overloaded slides, truncate, remove empty |
| **Render Engine** | 8 tipos de slide com branding Millennium BCP |

**8 tipos de slide:** Title · Section Divider · Content · Two-Column · KPI Cards · Table · Agenda · Closing

**Branding:** Montserrat font · `#D1005D` accent · 13.333×7.5" widescreen · Badge "DIGITAL EMPRESAS"

**Smart validation rules:**
- Max 7 bullets/slide → auto-split com "(cont.)"
- Max 150 chars/bullet → truncate com "…"
- Max 80 chars/título → truncate
- Max 4 KPIs/slide → auto-split
- Max 12 rows/table → auto-split
- Max 8 colunas/table → trim
- Remove slides vazios, section dividers consecutivos

**Commits:**
1. `56f215c` — Core engine + 8 slide types + branding (19 testes)
2. `2fd4d25` — Smart validation layer (11 testes novos)
3. `06275ac` — Opus 4.6 AI slide planner (3 testes novos)
4. `61ffc02` — Upgrade LLM tiers em tools quality-critical

**LLM Tier Upgrades (commit `61ffc02`):**
| Tool | Antes | Depois |
|------|-------|--------|
| `analyze_patterns` (DevOps) | standard (Sonnet) | **pro (Opus)** |
| `generate_user_stories` (DevOps) | standard (Sonnet) | **pro (Opus)** |
| `refine_workitem` (DevOps) | standard (Sonnet) | **pro (Opus)** |
| `analyze_feedback` (App) | fast (GPT-4.1) | **standard (Sonnet)** |
| `classify_emails` (Email) | standard (Sonnet) | standard *(mantido — bom custo/qualidade)* |

### ✅ Feature 3 — Excel Avançado
Arquitetura de 3 camadas (mesma do PPTX):

| Camada | Descrição |
|--------|-----------|
| **Opus AI Planner** | Claude Opus 4.6 planeia estrutura do workbook (quantas sheets, gráficos, KPIs) |
| **Validation Layer** | Max 20 sheets, max 10K rows/sheet (auto-split), max 50 cols, dedup nomes |
| **Render Engine** | Multi-sheet com tipos nativos, fórmulas, gráficos, formatação condicional |

**Capacidades:**
- Multi-sheet workbooks com separação inteligente
- Tipos de dados nativos: números, datas (DD/MM/YYYY), percentagens (0.0%), moeda (€), URLs com hyperlink
- Fórmulas Excel nativas: SUM, AVERAGE, COUNTA automáticos em colunas numéricas
- Gráficos embebidos: Bar, Line, Pie (na sheet ou em sheet separada)
- Formatação condicional (color scale) em colunas numéricas
- Auto-filter + freeze panes em todas as sheets
- Sheet de resumo executivo com KPIs (cards com valor grande + label)
- Branding Millennium BCP (cor, fontes, zebra stripes)

**Nova tool:** `generate_spreadsheet` (vs `generate_file` para exports simples)
- Modo content (Opus planeia) — preferido
- Modo sheets (estrutura pré-definida)

**Commit:** `0b8acd2` — 56 testes

### ⬜ Feature 4 — Auto-Rule Generation
- Geração automática de PromptRules a partir de padrões de feedback
- Aprendizagem contínua do sistema
- **Estado:** Não iniciado

### ⬜ Feature 5 — SQL Server Connector
- Conexão direta a bases de dados SQL Server
- Query builder assistido
- **Estado:** Não iniciado

### ⬜ Feature 6 — Semantic Search v2
- Melhorias no sistema de embeddings
- Busca semântica mais precisa
- **Estado:** Não iniciado

---

## Deploy

**Último deploy:** 2026-03-15 10:22 UTC
**Estado:** ✅ Live em https://dbdeai.pt

---

## Pilar 0 — Segurança (VNet/Private Endpoints/SSO)
> ⛔ **BLOQUEADO pela DSI** — aguarda aprovação. Não tocar.

---

## Princípios
1. **Segurança é #1** — dados confidenciais, zero compromissos
2. **Opus para qualidade** — operações críticas usam Claude Opus 4.6
3. **Testes obrigatórios** — cada feature tem test suite completa
4. **Deploy só após validação** — todos os 481 testes devem passar
