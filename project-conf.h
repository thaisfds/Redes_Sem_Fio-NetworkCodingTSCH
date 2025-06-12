#ifndef __PROJECT_CONF_H__
#define __PROJECT_CONF_H__

/* Define se a segurança do TSCH está habilitada (0 = desabilitada) */
#ifndef WITH_SECURITY
#define WITH_SECURITY 0
#endif /* WITH_SECURITY */

/* Desabilita fragmentação de pacotes 6LoWPAN para economizar espaço */
#define SICSLOWPAN_CONF_FRAG 0

/* Define o tamanho do buffer da pilha de rede */
#define UIP_CONF_BUFFER_SIZE 160

/*******************************************************/
/******************* Configurações TSCH ****************/
/*******************************************************/

/* Define o PAN ID da rede IEEE 802.15.4 (todos os nós devem usar o mesmo) */
#define IEEE802154_CONF_PANID 0x81a5

/* Não inicia o TSCH automaticamente. Ele será ativado manualmente no código C */
#define TSCH_CONF_AUTOSTART 0

/* Define o tamanho do agendamento do TSCH minimalista.
 * Quanto maior o valor, menor a frequência de slots ativos,
 * reduzindo consumo de energia, mas também a capacidade de transmissão */
#define TSCH_SCHEDULE_CONF_DEFAULT_LENGTH 3

#if WITH_SECURITY
/* Habilita segurança de link (criptografia) se WITH_SECURITY for 1 */
#define LLSEC802154_CONF_ENABLED 1
#endif /* WITH_SECURITY */

/* Habilita coleta de estatísticas do TSCH */
#define TSCH_STATS_CONF_ON 1

/* Coleta periódica de RSSI (nível de sinal) para análise do canal */
#define TSCH_STATS_CONF_SAMPLE_NOISE_RSSI 1

/* Intervalo para decaimento das estatísticas TSCH (em segundos) */
#define TSCH_STATS_CONF_DECAY_INTERVAL (60 * CLOCK_SECOND)

/*******************************************************/
/************* Outras configurações do sistema *********/
/*******************************************************/

/* Níveis de log para cada subsistema */
#define LOG_CONF_LEVEL_RPL                         LOG_LEVEL_INFO
#define LOG_CONF_LEVEL_TCPIP                       LOG_LEVEL_WARN
#define LOG_CONF_LEVEL_IPV6                        LOG_LEVEL_WARN
#define LOG_CONF_LEVEL_6LOWPAN                     LOG_LEVEL_WARN
#define LOG_CONF_LEVEL_MAC                         LOG_LEVEL_DBG  // Detalhado para MAC (útil no TSCH)
#define LOG_CONF_LEVEL_FRAMER                      LOG_LEVEL_INFO

/* Ativa logs por slot no TSCH, útil para debug */
#define TSCH_LOG_CONF_PER_SLOT                     1

#endif /* __PROJECT_CONF_H__ */
