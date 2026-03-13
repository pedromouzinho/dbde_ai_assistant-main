# Overall Deep Security and Compliance Assessment

## Contexto

Este documento consolida uma avaliação técnica honesta do stack atual da aplicação `DBDE AI Assistant`, com foco em:

- segurança técnica;
- minimização e retenção de dados;
- prontidão para RGPD;
- uso de dados internos e potencialmente confidenciais;
- maturidade para uma futura passagem para produção séria com apoio da DSI.

Esta avaliação é técnica e operacional. Não substitui aconselhamento jurídico, DPIA formal, ROPA nem aprovação da DSI.

## Escala de avaliação

- `0-40`: protótipo com risco elevado
- `41-60`: aceitável para testes controlados, mas ainda fraco para dados sensíveis
- `61-75`: bom para uso interno controlado, com riscos conhecidos e mitigados parcialmente
- `76-85`: forte para uso interno sério, ainda com alguns gaps de governação/infra
- `86-100`: nível elevado de maturidade técnica e governativa

## Score atual

### Antes das fases “fazer já” e “fazer antes da DSI”

- `68/100` para testes internos controlados
- `54/100` para uso com dados confidenciais

### Depois das fases implementadas nesta vaga

- `76/100` para uso individual ou interno muito controlado
- `63/100` para uso com dados confidenciais

### Score alvo esperado após intervenção da DSI

Se a DSI assumir com sucesso:

- `Entra ID + MFA + Conditional Access + grupos/roles corporativos`
- `Private Endpoints / VNet / fecho de rede`

o score esperado sobe para:

- `82/100` para uso interno sério com dados confidenciais
- `88/100` quando combinado com retenção formal, DSR, auditoria e rollout operacional maduros

## O que melhorou nesta fase

### 1. Minimização e retenção de dados

Foi introduzido controlo explícito de retenção para:

- uploads raw e artefactos intermédios;
- generated files;
- sweep automático de uploads expirados;
- purge seletiva mais cedo do `RawBlobRef` tabular quando já existe artefacto persistente de análise;
- redução do `RawBlobRef` tabular para retenção curta por defeito (`6h`) quando o artefacto persistente já existe;
- encurtamento adicional do `RawBlobRef` tabular para uma janela ainda mais curta (`1h`) quando o upload já ficou completo com artefacto persistente **e** chunks semânticos gerados a partir desse artefacto;
- backfill automático e leve de uploads tabulares históricos que já tinham artefacto persistente, mas ainda não tinham `HasChunks`, evitando depender do `RawBlobRef` para preservar grounding e contexto;
- separação mais clara entre `raw blob` e artefacto tabular persistente, permitindo que o original deixe de ser a base principal de análise assim que o artefacto fica pronto;
- purge de blobs e rows associadas, reduzindo acumulação e retenção desnecessária.

Isto reduz:

- exposição prolongada de dados;
- custo de storage;
- risco operacional e de compliance por retenção excessiva.

### 2. Audit trail técnico mais útil

O registo de auditoria passou a incluir metadados adicionais, como:

- modo;
- modelo usado;
- provider usado;
- conversation id;
- confiança em fluxos relevantes.

Isto melhora rastreabilidade e suporte a troubleshooting e auditoria interna, sem criar nova persistência pesada de conteúdo sensível.

### 3. Preparação para identidade corporativa futura

Foi introduzida uma abstração de `SecurityPrincipal`, com helpers para:

- representar identidade atual de forma mais consistente;
- centralizar checks de role/admin;
- preparar o código para claims/roles futuros vindos de Entra ID.

Isto evita continuar a espalhar dependência direta da auth própria por toda a aplicação.

### 4. Exportação e eliminação de dados do utilizador

Foi acrescentado um fluxo técnico de privacidade com:

- exportação do perímetro de dados associados ao utilizador;
- eliminação de rows e blobs pessoais;
- anonimização de referências globais quando os dados não devem simplesmente desaparecer;
- limpeza de draft blobs, event blobs, upload blobs e conhecimento derivado do utilizador.

Isto é importante para:

- reduzir dívida RGPD;
- apoiar futuros processos de DSR;
- preparar melhor a aplicação para produção séria.

### 5. Pipeline tabular mais robusta e menos dependente do raw

O pipeline tabular passou a apoiar-se muito mais no artefacto persistente (`parquet`) do que no ficheiro original:

- análise integral do dataset em artefacto, sem depender de amostras para cálculos principais;
- uso de `duckdb` para métricas numéricas, sumários categóricos, agrupamentos temporais e comparação de períodos;
- geração de chunks semânticos diretamente a partir do artefacto tabular;
- preferência do artefacto em `run_code` e nos fluxos de email sempre que ele já existe.

Isto melhora ao mesmo tempo:

- performance em ficheiros grandes;
- previsibilidade da análise;
- minimização de dados, porque o `RawBlobRef` deixa de ser necessário durante tanto tempo;
- robustez do produto para cenários com tabelas reais de maior dimensão.

### 6. Governação consultiva de providers

Foi introduzida uma camada explícita de governação consultiva dos providers:

- classificação de sensibilidade por ação/modo;
- identificação de `provider_family` e uso de provider externo;
- registo disso no audit trail;
- exposição do modo de governação no `/api/info`;
- sinalização no fluxo de voz quando entra um fallback externo.

Nesta fase, esta governação é deliberadamente **consultiva** e não bloqueante:

- melhora visibilidade e rastreabilidade;
- não cria retrabalho antes da intervenção da DSI;
- mantém a flexibilidade experimental atual.

## Riscos ainda presentes

### 1. Identidade e controlo de acesso

A aplicação continua com auth própria baseada em JWT local, e não ainda com:

- Entra ID;
- MFA;
- Conditional Access;
- grupos/roles corporativos.

Isto continua a ser um gap importante para produção séria.

### 2. Rede pública aberta

Os serviços ainda não estão fechados por topologia privada end-to-end. Em particular, o alvo continua a ser:

- App Service com acesso privado controlado;
- Key Vault, Storage e Search via Private Endpoints;
- redução ou eliminação de exposição pública desnecessária.

### 3. Uso de múltiplos providers de IA

O stack continua a poder usar múltiplos providers/modelos, incluindo Anthropic via Foundry.

#### Nota explícita sobre Anthropic

O uso de modelos Anthropic é, neste momento, uma **liability conhecida e aceite conscientemente** nesta fase experimental.

Decisão atual:

- manter Anthropic disponível;
- não bloquear a experimentação por esse motivo nesta fase;
- registar isto como risco controlado e temporário;
- rever a política de providers quando a aplicação entrar em preparação real para produção séria.

Isto significa:

- o risco está identificado;
- não está “esquecido”;
- mas também não é o foco prioritário imediato enquanto a aplicação ainda está em fase experimental controlada.

### 4. Governação formal ainda incompleta

Ainda faltam peças não-código importantes, como:

- DPIA formal;
- ROPA;
- política formal de retenção;
- processo formal de DSR;
- classificação explícita de tipos de dados permitidos/proibidos.

## Leitura honesta do risco atual

### Se a aplicação for usada apenas por uma pessoa, com prudência

O risco real baixa bastante, porque:

- reduz muito a superfície humana;
- reduz problemas de partilha indevida;
- diminui o impacto de autorização insuficientemente madura.

Mesmo assim, continuam a existir riscos reais:

- envio de dados para serviços de IA;
- retenção técnica em blobs/tabelas;
- erro humano ao colocar conteúdo demasiado sensível.

Conclusão prática:

- para uso individual e controlado, o risco é aceitável;
- para tratamento confortável de dados bancários muito sensíveis em bruto, ainda não é o estado final desejável.

## O que continua a valer a pena fazer antes da DSI

As seguintes linhas continuam corretas e não criam retrabalho:

1. retenção e purge mais formalizadas;
2. pipeline tabular robusta com artefacto intermédio de análise;
3. governação de providers por sensibilidade;
4. abstração de principal/roles;
5. auditoria técnica mínima;
6. exportação/eliminação de dados do utilizador.

## O que deve ser feito com a DSI

As mudanças mais estruturais e com maior impacto no score continuam a ser:

1. Entra ID + MFA + Conditional Access + grupos;
2. Private Endpoints / VNet / fecho de rede;
3. Storage e Search por identidade/RBAC;
4. maturidade operacional de release, incluindo slot de staging e rollout melhor.

## Conclusão

O stack atual já está claramente acima de um protótipo solto:

- há controlo técnico sério;
- há hardening já relevante;
- há trabalho real de minimização, retenção e privacidade;
- há preparação arquitetural para a futura evolução corporativa.

Mas a honestidade correta continua a ser:

- bom para testes internos controlados;
- aceitável para uso individual ou muito restrito;
- ainda não no ponto ideal para dizer “produção séria com dados confidenciais” sem o bloco DSI.

O ponto mais importante é que o trabalho feito agora **não é desperdício**:

- melhora segurança já hoje;
- melhora compliance já hoje;
- e prepara a transição futura para Entra ID e rede privada sem reescrever a app.
