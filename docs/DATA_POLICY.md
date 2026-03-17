# DBDE AI Assistant — Política de Dados
## Versão: 8.0.0 | Atualizado: 2026-03-17

## Fonte de verdade
Política revista contra:
- `config.py`
- `app.py`
- `routes_chat.py`
- `generated_files.py`
- `llm_provider.py`
- `provider_governance.py`
- `docs/THIRD_PARTY_INVENTORY.md`

## 1. Âmbito
Aplica-se ao uso interno do DBDE AI Assistant e ao tratamento de dados suportado pelo código deste repositório.

Se existir política corporativa mais restritiva, a política corporativa prevalece.

## 2. Dados permitidos
- work items, user stories e documentação interna de engenharia/produto
- CSV, TSV e Excel de trabalho interno sem dados proibidos
- documentos técnicos internos
- screenshots e artefactos de UI para análise funcional
- prompts de voz e rascunhos operacionais internos

## 3. Dados proibidos
- dados pessoais de clientes ou colaboradores sem base aprovada para tratamento
- credenciais, passwords, tokens, chaves e secrets
- dumps de produção, exports massivos ou dados regulados fora do âmbito autorizado
- documentos classificados acima do nível permitido para a equipa/utilizador
- prompts ou queries que enviem PII desnecessária para integrações externas

## 4. Regras para fluxos externos
Ver [THIRD_PARTY_INVENTORY.md](./THIRD_PARTY_INVENTORY.md).

### Regras práticas
- Azure OpenAI é o provider Azure preferencial.
- Anthropic pode ser usado para tiers `standard` e `pro` quando configurado.
- O modo de governance do provider é `advisory`, com providers externos marcados como experimentais por omissão.
- Fluxos de maior sensibilidade devem preferir âmbito Azure quando possível.
- Brave Search e Brave Answers só devem receber queries sem dados pessoais.
- Figma e Miro são integrações read-only orientadas a metadados/artefactos de design.

## 5. Retenção derivada do código
### Retenção automática confirmada
- auth cookie: `AUTH_COOKIE_MAX_AGE_SECONDS=86400` por omissão
- ficheiros gerados para download: `GENERATED_FILE_TTL_SECONDS=1800` por omissão
- artefactos de upload: `UPLOAD_ARTIFACT_RETENTION_HOURS=72` por omissão
- raw blobs tabulares: `UPLOAD_TABULAR_RAW_RETENTION_HOURS=6` por omissão
- raw blobs tabulares após chunks prontos: `UPLOAD_TABULAR_READY_RAW_RETENTION_HOURS=1` por omissão
- upload job cache: `24h`
- export job cache: `24h`

### Retenção sem TTL automática explícita no repositório
- `ChatHistory` persistido em Azure Table Storage não tem TTL automático definido no código
- `Users` e `feedback` não têm TTL automático definido no código

### Eliminação manual suportada
- delete de conversa via `/api/chats/{user_id}/{conversation_id}`
- privacy export via `/api/privacy/export`
- privacy delete via `/api/privacy/delete`

## 6. Controles implementados
- JWT auth com role `user/admin`
- `JWT_SECRET` obrigatório em produção
- allowlist de origins via `ALLOWED_ORIGINS`
- rate limiting
- token quotas por tier
- PII masking no pipeline LLM quando `PII_ENABLED=true`
- Prompt Shield / Content Safety opcional
- Document Intelligence opcional
- logging estruturado
- deep health com autenticação admin

## 7. Responsabilidades
- utilizadores: não inserir dados proibidos
- operação: garantir App Settings, logs, quotas e segredos corretos
- owners funcionais: aprovar exceções e rever uso de integrações externas
- segurança/compliance: definir a política corporativa superior e o âmbito permitido
