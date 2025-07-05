# Aprendizados da Implementação TSCH com UDP

## Resumo do Projeto

Este projeto teve como objetivo implementar uma rede wireless usando TSCH (Time Slotted Channel Hopping) com comunicação UDP no Contiki-NG. O desenvolvimento passou por várias fases, desde a configuração básica até implementação avançada com tentativas de network coding.

## Evolução do Desenvolvimento

### Fase 1: Configuração Inicial (commits iniciais)
- **Commit: "project working"** - Estabeleceu a base do projeto
- **Commit: "TSCH básico funcionando"** - Primeira implementação funcional do TSCH
- Configuração básica do Makefile com exclusão de plataformas incompatíveis
- Definição do PAN ID (0x81a5) e configurações iniciais do TSCH

### Fase 2: Refinamento e Logs (commits intermediários)
- **Commit: "adding comments"** - Melhoria na documentação do código
- **Commit: "upgrading log"** - Aprimoramento do sistema de logging
- **Commit: "melhorando log"** - Continuação das melhorias no sistema de logs
- Implementação de logs detalhados para debug do MAC layer (TSCH)

### Fase 3: Separação de Funcionalidades
- **Commit: "tentando separar os nós"** - Tentativa de criar lógica específica para diferentes tipos de nós
- **Commit: "mudando de exemplo"** - Mudança na abordagem de implementação
- **Commit: "exemplos funcionais"** - Estabelecimento de exemplos funcionais

### Fase 4: Implementação UDP Bem-Sucedida
- **Commit: "funcionando TSCH com UDP"** - Marco importante do projeto
- Integração bem-sucedida do protocolo UDP sobre TSCH
- Implementação de comunicação coordenador-nó comum

### Fase 5: Tentativas de Network Coding
- **Commit: "nova simulação"** - Tentativa de implementar network coding
- **Commit: "Create common_defs.h"** - Estruturação para suporte a network coding
- **Commit: "ultima tentativa e desistencia"** - Finalização com desistência do network coding

## Principais Aprendizados Técnicos

### 1. Configuração TSCH
- **Autostart desabilitado**: `TSCH_CONF_AUTOSTART 0` para controle manual
- **Tamanho do schedule**: `TSCH_SCHEDULE_CONF_DEFAULT_LENGTH 3` para eficiência energética
- **Coleta de estatísticas**: Essencial para debug e monitoramento da rede

### 2. Integração UDP sobre TSCH
- **Simple UDP**: API do Contiki-NG facilitou implementação
- **Callback pattern**: Uso de `udp_rx_callback` para processamento de mensagens
- **Verificação de conectividade**: `NETSTACK_ROUTING.node_is_reachable()` antes de enviar

### 3. Arquitetura de Nós
- **Coordenador**: Funciona como root RPL com `NETSTACK_ROUTING.root_start()`
- **Nós comuns**: Enviam mensagens periódicas ao coordenador
- **Diferenciação por node_id**: Lógica condicional baseada no ID do nó

### 4. Logging e Debug
- **Logs estruturados**: Diferentes níveis para cada subsistema
- **TSCH per-slot logging**: `TSCH_LOG_CONF_PER_SLOT 1` para debug detalhado
- **Formatação consistente**: Uso de `LOG_INFO_6ADDR` para endereços IPv6

## Desafios Encontrados

### 1. Complexidade do Network Coding
- Tentativa de implementar XOR-based network coding
- Estrutura `net_coding_message_t` criada mas não finalizada
- Desistência devido à complexidade de implementação

### 2. Sincronização de Nós
- Necessidade de verificar conectividade antes de enviar
- Gerenciamento de timers para envio periódico
- Tratamento de nós que ainda não se conectaram à rede

### 3. Configuração de Plataformas
- Exclusão de plataformas incompatíveis no Makefile
- Configuração específica para simulação no Cooja
- Ajustes de buffer e fragmentação

## Lições Aprendidas

### 1. Desenvolvimento Iterativo
- Importância de commits frequentes para rastreabilidade
- Validação de cada etapa antes de avançar
- Logs detalhados facilitam debug

### 2. Arquitetura Modular
- Separação clara entre coordenador e nós comuns
- Uso de headers comuns (`common_defs.h`) para padronização
- Configuração centralizada em `project-conf.h`

### 3. Limitações Técnicas
- Network coding adiciona complexidade significativa
- TSCH requer configuração cuidadosa para funcionar adequadamente
- Simulação no Cooja tem limitações específicas

## Conclusão

O projeto foi bem-sucedido em implementar comunicação UDP sobre TSCH, demonstrando:
- Viabilidade da integração TSCH + UDP no Contiki-NG
- Importância da configuração adequada dos parâmetros TSCH
- Necessidade de logging detalhado para desenvolvimento em redes wireless

Embora o network coding não tenha sido implementado com sucesso, a base sólida de TSCH+UDP estabelecida oferece uma plataforma robusta para futuras extensões e experimentações em redes wireless IoT.

## Arquivos Principais

- `comumNode.c`: Implementação dos nós comuns
- `coordinatorNode.c`: Implementação do nó coordenador
- `project-conf.h`: Configurações centralizadas do projeto
- `common_defs.h`: Definições compartilhadas (tentativa de network coding)
- `Makefile`: Configuração de build e plataformas