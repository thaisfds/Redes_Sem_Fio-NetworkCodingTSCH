#include "contiki.h"
#include "sys/node-id.h"
#include "sys/log.h"
#include "net/ipv6/uip-ds6-route.h"
#include "net/ipv6/uip-sr.h"
#include "net/mac/tsch/tsch.h"
#include "net/routing/routing.h"
#include "net/ipv6/simple-udp.h"

#define DEBUG DEBUG_PRINT
#include "net/ipv6/uip-debug.h"

#define LOG_MODULE "App"
#define LOG_LEVEL LOG_CONF_LEVEL_APP

#define UDP_PORT 1234
#define SEND_INTERVAL (10 * CLOCK_SECOND)  // tempo entre envios

/*-------------------------------- DEFINIÇÃO DOS PROCESSOS --------------------------------*/

/* Define o processo chamado "RPL Node" */
PROCESS(node_process, "RPL Node");

/* Define que este processo será iniciado automaticamente ao ligar o nó */
AUTOSTART_PROCESSES(&node_process);

/* Adicione a conexão UDP */
static struct simple_udp_connection udp_conn;

/* Variável para armazenar o endereço do coordenador */

/*-------------------------------- Funções de callback para UDP --------------------------------*/

static void
udp_rx_callback(struct simple_udp_connection *c,
                const uip_ipaddr_t *sender_addr,
                uint16_t sender_port,
                const uip_ipaddr_t *receiver_addr,
                uint16_t receiver_port,
                const uint8_t *data,
                uint16_t datalen)
{
  LOG_INFO("Recebido '%s' de ", (char *)data);
  LOG_INFO_6ADDR(sender_addr);
  LOG_INFO_(" no porto %d\n", sender_port);

  // Se este nó for o coordenador, pode querer responder ou processar a mensagem
  // Exemplo: se o coordenador recebe uma mensagem, ele pode logar
  if (node_id == 5) { // Supondo que 5 é o coordenador
      // Faça algo com a mensagem recebida pelo coordenador
  }
}

/*-------------------------------- Processo --------------------------------*/

/* Corpo do processo */
PROCESS_THREAD(node_process, ev, data)
{
  static struct etimer periodic_timer; // Timer para envio periódico

  PROCESS_BEGIN(); // Início do processo Contiki


  /* Loga o início do processo com o ID do nó */
  LOG_INFO("Iniciando processo do no %d\n", node_id);

    LOG_INFO("Este no (%d) e o coordenador\n", node_id);


  /* Se este nó for o coordenador, inicia o roteador RPL como raiz */

    NETSTACK_ROUTING.root_start(); // Este nó vira o root da árvore RPL (DODAG)

  /* Liga a camada MAC (nesse caso, TSCH), que não inicia automaticamente */
  NETSTACK_MAC.on();

  /* Inicializa a conexão UDP */
  simple_udp_register(&udp_conn, UDP_PORT, NULL, UDP_PORT, udp_rx_callback);

  /* Define o timer para envio periódico */
  etimer_set(&periodic_timer, SEND_INTERVAL);

  while(1) {
    PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&periodic_timer));
  
    LOG_INFO("Coordenador aguardando mensagens...\n");

    etimer_reset(&periodic_timer);
  }

  /* Se a flag WITH_PERIODIC_ROUTES_PRINT estiver definida,
     imprime a tabela de roteamento a cada minuto */

  PROCESS_END(); // Fim do processo Contiki
}
