# DBDE AI Assistant — Plano de Melhorias v2

> **Ultima atualizacao:** 2026-03-15
> **Ambiente:** Azure Web App `millennium-ai-assistant` · `https://dbdeai.pt`
> **App Service Plan:** P1v3 PREMIUMV3 (8 GB RAM, 2 vCPU)
> **Total testes:** 481 (392 base + 33 PPTX + 56 XLSX) · Todos a passar

---

## Estado Geral

### Fase 1 — Features Originais (Concluidas)

| # | Feature | Estado | Commits | Testes |
|---|---------|--------|---------|--------|
| 0 | Infraestrutura P1v3 | DONE | `a967512` | — |
| 1 | Perguntas de Clarificacao | DONE | `57a5226` | Pass |
| 2 | PowerPoint Branded (BCP) | DONE | `56f215c` `2fd4d25` `06275ac` `61ffc02` | 33 |
| 3 | Excel Avancado | DONE | `0b8acd2` | 56 |
| — | Deploy | LIVE | — | — |

### Fase 2 — Bugfixes e Polish (Prioridade Alta)

| # | Issue | Estado | Severidade | Ficheiros |
|---|-------|--------|------------|-----------|
| B1 | Run Code mostra "N/A" e "0 resultados" | TODO | Media | `agent.py` |
| B2 | Markdown (#, **, etc) aparece em raw | TODO | Alta | `frontend/src/utils/markdown.js` |
| B3 | Clarification nao bloqueia input | TODO | Media | `QuickReplyBar.jsx`, `App.jsx` |
| B4 | PII Hardening mascara numeros do utilizador | TODO | Alta | `pii_shield.py` |
| B5 | PPTX sem bullets formatados / estetica fraca | TODO | Alta | `pptx_engine.py` |
| B6 | Excel Dashboard sheet sem freeze/autofilter | TODO | Baixa | `xlsx_engine.py` |

### Fase 3 — Melhorias Arquiteturais

| # | Melhoria | Estado | Prioridade | Ficheiros |
|---|----------|--------|------------|-----------|
| A1 | Persistencia write-through | TODO | ALTA | `agent.py` |
| A2 | Separar app.py (5400+ linhas) | TODO | ALTA | `app.py` |
| A3 | Frontend CDN / Azure Front Door | TODO | Media | infra |
| A4 | Resumo automatico pos-upload | TODO | Media | `app.py`, `agent.py` |
| A5 | Multi-file analysis (cross-file joins) | TODO | Media | `tools.py` |
| A6 | Dashboards persistentes | TODO | Baixa | novo |
| A7 | Autoscale P1v3 (1-3 instancias) | TODO | Baixa | infra |
| A8 | Streaming progresso upload (SSE) | TODO | Baixa | `app.py`, frontend |
| A9 | Versionamento de conhecimento | TODO | Baixa | `app.py` |

---

## Fase 2 — Diagnostico e Solucoes

### B1 — Run Code mostra "N/A resultados" e "0 resultados"

**Diagnostico:**
Em `agent.py:1948-1952`, o `result_summary` tenta extrair `total_count` de chaves
como `total_count`, `total_results`, `total_found`. Tools como `run_code` nao retornam
nenhuma dessas chaves — o resultado e um dict com `stdout`, `stderr`, `exit_code`.
Resultado: `total_count = "N/A"` e `items_returned = 0`.

Depois em `agent.py:2337-2338`:
```python
count = d["result_summary"].get("total_count", d["result_summary"].get("items_returned", ""))
yield _sse({"type": "tool_result", "tool": d["tool"], "text": f"{d['tool']}: {count} resultados"})
```

**Solucao:**
1. Criar mapeamento de tool -> label personalizado para o SSE
2. Para tools sem contagem (run_code, generate_presentation, generate_file, etc.):
   - tool_start: "Run Code..." (sem "resultados")
   - tool_result: "Run Code (concluido)" — sem mostrar contagem
3. So mostrar "X resultados" quando `total_count` e um numero real (int > 0)
4. Fallback: se count == "N/A" ou 0, mostrar apenas "concluido"

```python
# Proposta:
if isinstance(count, int) and count > 0:
    text = f"{d['tool']}: {count} resultados"
elif isinstance(count, str) and count not in ("N/A", "0", ""):
    text = f"{d['tool']}: {count} resultados"
else:
    text = f"{d['tool']}"  # sem contagem
```

---

### B2 — Markdown (#, **, etc) aparece em raw

**Diagnostico:**
O `markdown.js` so processa `**bold**`, links `[text](url)` e tabelas.
Faltam: headings (#, ##, ###), listas (- , * , 1.), italic (*text*),
code blocks (```), inline code (`code`), horizontal rules (---).

O `escapeHtml()` na linha 17 escapa `<` e `>` ANTES de processar markdown,
mas os simbolos markdown nao sao HTML — sao texto. O problema e que o parser
e demasiado simples e nao cobre a sintaxe completa.

**Solucao:**
Reescrever `renderInlineMarkdown()` e `renderMarkdown()` para suportar:
- `# Heading 1` → `<h3>`, `## Heading 2` → `<h4>`, `### Heading 3` → `<h5>`
  (usar h3-h5 para nao conflitar com o layout da pagina)
- `- item` e `* item` → `<ul><li>` agrupadas
- `1. item` → `<ol><li>` agrupadas
- `` `code` `` → `<code>`
- `*italic*` → `<em>`
- ` ``` ` code blocks → `<pre><code>`
- `---` → `<hr>`
- Manter **bold**, links, tabelas como estao

Nao usar bibliotecas externas (marked.js etc.) para manter o bundle leve
e o controlo de sanitizacao. Expandir o parser existente.

---

### B3 — Clarification nao bloqueia input (estilo AskUserQuestion)

**Diagnostico:**
Atualmente o `QuickReplyBar` renderiza pills que auto-enviam via `onSelect(opt)`.
O input fica livre para o utilizador escrever ao mesmo tempo.
O comportamento ideal (estilo Claude) e:
- Input fica bloqueado/disabled com placeholder "Seleciona uma opcao..."
- Pills aparecem acima ou dentro do input
- Clicar preenche o input e envia automaticamente

**Solucao:**
1. Quando o agente envia clarification options, guardar em state `pendingQuickReplies`
2. O input textarea fica `disabled` com placeholder "Escolhe uma opcao ou escreve..."
3. As pills aparecem numa barra fixa acima do input (nao no bubble da mensagem)
4. Clicar numa pill: preenche o input + envia
5. O utilizador pode tambem clicar no input para desbloquear e escrever algo custom
6. Apos enviar, limpar `pendingQuickReplies` e restaurar input normal

Componentes a modificar:
- `App.jsx`: novo state `pendingQuickReplies`, logica de disable/enable
- `QuickReplyBar.jsx`: mover para junto do input, estilo diferente
- Remover as pills de dentro do `MessageBubble`

---

### B4 — PII Hardening mascara numeros do utilizador

**Diagnostico:**
Em `pii_shield.py:29`, a categoria `"Quantity"` esta na lista `PII_CATEGORIES`.
O Azure AI Language deteta numeros como "85", "12", "3.2%", "28", "6" como
entidades `Quantity` com confidence >= 0.8 (threshold na linha 60).

Resultado: o prompt que chega ao LLM tem `[QUANTITY_1]`, `[QUANTITY_2]` em vez
dos numeros reais. O LLM ve placeholders e pede ao utilizador para "preencher".

**Solucao:**
1. **Remover `"Quantity"` de `PII_CATEGORIES`** — numeros nao sao PII.
   Quantidades como "85 user stories" ou "3.2%" sao dados de negocio, nao dados pessoais.
2. **Remover `"DateTime"` tambem** — datas como "Sprint 14" ou "Abril" nao sao PII.
   Datas de nascimento sao apanhadas pela categoria `Person` indiretamente.
3. **Remover `"URL"` da lista** — URLs de projetos internos nao sao PII.
   Manter apenas nas `_REGEX_PATTERNS` para URLs com dados sensíveis especificos.
4. Manter todas as categorias financeiras e de identidade (NIF, IBAN, CC, NISS, etc.)

Impacto: zero risco de seguranca — `Quantity`, `DateTime`, `URL` nao sao dados pessoais.
As categorias realmente sensíveis (Person, PhoneNumber, Email, financeiras) ficam intactas.

---

### B5 — PPTX estetica fraca / bullets sem formatacao

**Diagnostico:**
Analisei o PPTX "Boas Praticas de Code Review" gerado:
- 19 slides, branding OK (cor, fonte, badge, KPIs) ✓
- MAS: bullets sao texto plain sem caractere de bullet (sem •)
- Sem XML `buChar` / `buFont` no paragrafo
- O `p.level = 0` define indentacao mas o python-pptx nao adiciona
  bullet character automaticamente sem layout master
- Usamos layout 6 (Blank) → nao ha bullet defaults herdados
- Espacamento entre bullets e 6pt — pouco
- Sem contraste visual entre titulo e corpo (mesma escala)

**Solucao:**
1. **Adicionar bullet character via XML** — injetar `buChar` e `buFont` no
   paragrafo XML para forcar o bullet character "•" (nível 0) e "–" (nível 1)

```python
from pptx.oxml.ns import qn
from lxml import etree

def _add_bullet_formatting(paragraph, level=0):
    """Add proper bullet character to paragraph via XML manipulation."""
    pPr = paragraph._p.get_or_add_pPr()
    # Remove existing bullet settings
    for child in list(pPr):
        if child.tag.endswith(('buNone', 'buChar', 'buAutoNum')):
            pPr.remove(child)

    if level == 0:
        buChar = etree.SubElement(pPr, qn('a:buChar'))
        buChar.set('char', '\u2022')  # bullet •
    else:
        buChar = etree.SubElement(pPr, qn('a:buChar'))
        buChar.set('char', '\u2013')  # en-dash -

    # Bullet font
    buFont = etree.SubElement(pPr, qn('a:buFont'))
    buFont.set('typeface', 'Arial')

    # Bullet color
    buClr = etree.SubElement(pPr, qn('a:buClr'))
    srgbClr = etree.SubElement(buClr, qn('a:srgbClr'))
    srgbClr.set('val', BRAND_ACCENT_HEX if level == 0 else BRAND_DARK_TEXT_HEX)

    # Indentation
    indent = -228600 if level == 0 else -171450  # negative = bullet hangs left
    margin = 457200 if level == 0 else 685800
    pPr.set('indent', str(indent))
    pPr.set('marL', str(margin))
```

2. **Melhorar espacamento** — `space_after = Pt(10)` em vez de 6
3. **Adicionar `space_before`** no primeiro bullet para dar respiro ao titulo
4. **Titulo de conteudo maior** — usar 28pt bold em vez de 24pt
5. **Subtitulo nos content slides** — suportar campo `subtitle` opcional
6. **Line spacing** — 1.2x para melhor legibilidade

---

### B6 — Excel Dashboard sheet sem freeze/autofilter

**Diagnostico:**
No ficheiro "Dashboard Equipas", a sheet "Dashboard" nao tem freeze panes nem
auto-filter. As outras sheets (Dados por Equipa, Velocity) tem.
Parece ser um bug no engine onde a sheet de resumo/dashboard e tratada
diferentemente das data sheets.

**Solucao:**
Garantir que `freeze_panes` e `auto_filter` sao aplicados em TODAS as sheets
que tenham headers, incluindo a sheet de dashboard/resumo.

---

## Fase 3 — Melhorias Arquiteturais (Detalhe)

### A1 — Persistencia Write-Through

**Problema:** Deploys apagam conversas em memoria. `ConversationStore` e in-memory
com persist fire-and-forget (timeout 8s + fallback async). Se o persist falha
e o container reinicia, a conversa perde-se.

**Solucao:**
- Write-through: persistir para Table Storage imediatamente apos cada mensagem
- Read-through: ao fazer `get()`, se nao esta em memoria, ir buscar ao Table Storage
- Cache LRU em memoria para performance (atual), mas o Table Storage e source of truth
- Estimativa: ~2 horas de trabalho

### A2 — Separar app.py (5400+ linhas)

**Problema:** Monolito dificil de manter. Qualquer mudanca e arriscada.

**Solucao:** Separar em modulos:
- `routes_chat.py` — SSE streaming, agent_chat, agent_chat_stream
- `routes_upload.py` — upload, processing, artifacts
- `routes_export.py` — download, export, file generation
- `routes_admin.py` — debug, health, config endpoints
- `routes_auth.py` — SSO, tokens, session management
- `app.py` — apenas startup, middleware, imports dos routers
- Estimativa: ~4 horas de trabalho (refactoring puro, zero mudancas funcionais)

### A3 — Frontend CDN / Azure Front Door

**Problema:** Assets JS/CSS servidos pelo Web App. Latencia desnecessaria.

**Solucao:** Azure Front Door ou CDN para assets estaticos. Reduz carga no server.
- Estimativa: ~1 hora (config Azure + build pipeline adjustment)

### A4 — Resumo automatico pos-upload

**Problema:** Ficheiro processado, utilizador nao sabe o que perguntar.

**Solucao:** Apos upload concluido, gerar automaticamente:
- Schema (colunas, tipos, nulls)
- Estatisticas basicas (count, media, min, max)
- Top insights (outliers, padroes)
- Estimativa: ~3 horas

### A5 — Multi-file analysis

**Problema:** Pipeline processa ficheiro a ficheiro. Sem cross-file joins.

**Solucao:** DuckDB suporta multi-table queries nativamente. Montar os artifacts
de multiplos ficheiros como tabelas e permitir JOINs.
- Estimativa: ~2 horas

### A6 — Dashboards persistentes

**Problema:** Graficos Plotly morrem com a conversa.

**Solucao:** "Fixar" grafico como dashboard reutilizavel em Azure Blob + URL.
- Estimativa: ~4 horas

### A7 — Autoscale P1v3

**Problema:** Instancia unica, sem escala.

**Solucao:** Config autoscale 1-3 instancias baseado em CPU/Memory.
- Estimativa: ~30 minutos (config Azure)
- Requer: A1 (persistencia write-through) primeiro para nao perder conversas

### A8 — Streaming progresso upload

**Problema:** Polling para saber estado do upload.

**Solucao:** SSE para feedback real-time ("a ler XLSX... 50%... embeddings... 80%")
- Estimativa: ~3 horas

### A9 — Versionamento de conhecimento

**Problema:** Upload de ficheiro atualizado substitui o anterior.

**Solucao:** Manter versoes anteriores em Blob Storage com diff.
- Estimativa: ~4 horas

---

## Ordem de Execucao Recomendada

```
Fase 2 (Bugfixes — impacto imediato):
  B4 PII Hardening numeros    ← 15 min, fix critico
  B2 Markdown rendering        ← 1-2 horas
  B1 Run Code N/A resultados   ← 30 min
  B5 PPTX bullets/estetica     ← 1-2 horas
  B3 Clarification input block ← 2 horas
  B6 Excel freeze/autofilter   ← 15 min
  >>> DEPLOY <<<

Fase 3 (Arquitectura):
  A1 Persistencia write-through ← pre-requisito para A7
  A2 Separar app.py             ← facilita tudo o resto
  A4 Resumo pos-upload          ← UX win rapido
  A5 Multi-file analysis        ← extensao natural do DuckDB
  A7 Autoscale                  ← config rapida
  A3 CDN/Front Door             ← performance
  A8 Streaming upload           ← nice to have
  A6 Dashboards persistentes    ← diferenciador
  A9 Versionamento              ← auditoria
  >>> DEPLOY <<<
```

---

## Deploy

**Ultimo deploy:** 2026-03-15 10:22 UTC
**Estado:** LIVE em https://dbdeai.pt

```bash
az webapp up --name millennium-ai-assistant --resource-group rg-MS_Access_Chabot --runtime "PYTHON:3.12"
```

---

## Pilar 0 — Seguranca (VNet/Private Endpoints/SSO)
> BLOQUEADO pela DSI — aguarda aprovacao. Nao tocar.

---

## Principios
1. **Seguranca e #1** — dados confidenciais, zero compromissos
2. **Opus para qualidade** — operacoes criticas usam Claude Opus 4.6
3. **Testes obrigatorios** — cada feature tem test suite completa
4. **Deploy so apos validacao** — todos os testes devem passar
5. **Bugfixes antes de features** — nunca construir sobre base instavel
