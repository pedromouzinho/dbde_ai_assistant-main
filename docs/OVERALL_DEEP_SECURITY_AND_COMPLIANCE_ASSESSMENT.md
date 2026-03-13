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

- `80/100` para uso individual ou interno muito controlado
- `67/100` para uso com dados confidenciais

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
- perfil/schema de colunas também sobre o artefacto, reduzindo dependência de amostra até nos pedidos exploratórios;
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

### 7. Voz com leitura dedicada e normalização controlada

O fluxo de voz passou a usar uma separação mais correta entre:

- leitura da fala;
- interpretação do pedido;
- decisão de auto-envio ou queda para texto.

Nesta fase:

- a leitura pode usar Azure Speech;
- a normalização pode usar `azure_openai:gpt-4.1-mini-dz`;
- o fallback para Anthropic continua disponível quando necessário;
- não existe persistência deliberada de áudio bruto.

Isto melhora experiência e previsibilidade, mas não altera a leitura principal do risco:

- continua a existir processamento de dados em serviços de IA;
- o fallback Anthropic continua a ser uma liability conhecida e conscientemente aceite nesta fase experimental.

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

## Queue priorizada e transição

Esta secção consolida o que ainda está em queue, distinguindo:

- o que vale a pena fazer já sem criar retrabalho;
- o que deve ser preparado antes da DSI;
- o que faz sentido executar com a DSI;
- e o que já não tem retorno suficiente nesta fase.

### A. Próximo bloco com maior retorno antes da DSI

#### 1. Fechar melhor o pipeline tabular para ficheiros grandes

Estado atual:

- uploads tabulares já usam artefacto persistente;
- a análise principal já corre muito mais sobre esse artefacto com `duckdb`;
- o `RawBlobRef` já tem retenção curta e backfill de chunks.

Próximo passo recomendado:

- manter esta frente apenas até ao ponto em que o raw deixa de ser residual para os fluxos mais relevantes;
- evitar continuar a otimizar detalhes com retorno marginal baixo.

Objetivo:

- garantir que a app lida bem com ficheiros grandes;
- reduzir ainda mais dependência do raw;
- deixar a transição futura para uma arquitetura mais enterprise sem retrabalho.

#### 2. Passar de governação consultiva de providers para governação configurável

Estado atual:

- existe visibilidade sobre provider/modelo/fallback;
- existem sinais de sensibilidade e provider externo no audit trail;
- Anthropic continua ativo por decisão consciente desta fase experimental.

Próximo passo recomendado:

- introduzir política configurável por modo/fluxo;
- permitir desligar fallback externo por área sensível sem reescrever a app;
- manter Anthropic ligado onde ainda fizer sentido nesta fase experimental.

Isto é particularmente útil porque:

- não choca com a futura arquitetura corporativa;
- melhora governança já hoje;
- permite adaptar a app sem mudanças profundas quando a DSI pedir restrições.

#### 3. Formalizar melhor retenção e purge

Estado atual:

- já existe purge seletiva e retenção curta em blocos críticos.

Próximo passo recomendado:

- consolidar janelas por categoria de dado;
- tornar mais explícita a separação entre raw, artefacto de análise, resultado derivado e memória aprendida;
- alinhar isto com uma futura política formal de retenção.

### B. Fazer antes da DSI porque prepara a migração

#### 1. Abstração final de principal, roles e capabilities

O caminho iniciado com `SecurityPrincipal` deve continuar até ao ponto em que:

- o código dependa o mínimo possível da auth própria atual;
- as autorizações por funcionalidade estejam centralizadas;
- a migração para claims corporativas seja sobretudo uma troca de fonte de identidade, e não uma reescrita transversal da aplicação.

#### 2. DSR técnico e ciclo de vida dos dados

Convém continuar a reforçar:

- exportação de dados do utilizador;
- eliminação por utilizador;
- eliminação por conversa e por upload;
- consistência entre memória local, tabelas e blobs.

Isto ajuda RGPD independentemente da futura solução de identidade.

#### 3. Blueprint e inventário técnico para a DSI

Antes da intervenção da DSI, continua a valer a pena manter um blueprint claro com:

- dependências da aplicação;
- serviços Azure usados;
- settings críticos;
- modelo de dados persistidos;
- fluxo de providers de IA;
- pontos onde a identidade corporativa vai entrar.

### C. O que faz sentido executar com a DSI

Estas continuam a ser as mudanças estruturais com maior impacto no score:

#### 1. Identidade e controlo de acesso

- Entra ID
- MFA
- Conditional Access
- grupos/roles corporativos

#### 2. Fecho de rede

- Private Endpoints
- VNet Integration
- redução ou eliminação de exposição pública desnecessária

#### 3. Serviços por identidade/RBAC

- Storage sem Shared Key como padrão de longo prazo
- Search com controlo mais forte por identidade e rede

#### 4. Maturidade operacional de release

- slot de staging
- rollout melhor
- observabilidade e rollback mais maduros

### D. O que já não merece tanto investimento agora

Nesta fase, já não faz sentido investir muito mais em:

- hardening sofisticado da auth própria atual;
- remendos pontuais sobre rede pública como solução final;
- mais otimizações pequenas no pipeline tabular com retorno marginal baixo;
- reforço excessivo de padrões que serão substituídos por Entra ID e rede privada.

## Leitura executiva do estado atual

Brutalmente honesto:

- a aplicação já não é um protótipo frágil;
- já existe trabalho material e consistente de segurança, privacidade, retenção e minimização;
- a aplicação está melhor preparada para dados reais do que estava no início da auditoria;
- o principal teto atual já não está tanto no código, mas sim em identidade corporativa, fecho de rede e governação formal.

Em resumo:

- **o trabalho feito até aqui continua a fazer sentido**;
- **não é retrabalho**;
- e **prepara corretamente a passagem futura para uma arquitetura aprovada pela DSI**.

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
