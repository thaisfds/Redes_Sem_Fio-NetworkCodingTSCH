#include "contiki.h"
#include "sys/node-id.h"
#include "sys/log.h"
#include "net/ipv6/uip-ds6-route.h"
#include "net/ipv6/uip-sr.h"
#include "net/mac/tsch/tsch.h"
#include "net/routing/routing.h"

#define DEBUG DEBUG_PRINT
#include "net/ipv6/uip-debug.h"

/* Define o processo chamado "RPL Node" */
PROCESS(node_process, "RPL Node");

/* Define que este processo será iniciado automaticamente ao ligar o nó */
AUTOSTART_PROCESSES(&node_process);

/* Corpo do processo */
PROCESS_THREAD(node_process, ev, data)
{
  int is_coordinator; // Flag para verificar se este nó é o coordenador (root)

  PROCESS_BEGIN(); // Início do processo Contiki

  is_coordinator = 0; // Inicialmente assume que não é coordenador

  /* Se estiver rodando no simulador Cooja, define o nó 1 como coordenador */
#if CONTIKI_TARGET_COOJA
  is_coordinator = (node_id == 1); // node_id é definido automaticamente no Cooja
#endif

  /* Se este nó for o coordenador, inicia o roteador RPL como raiz */
  if(is_coordinator) {
    NETSTACK_ROUTING.root_start(); // Este nó vira o root da árvore RPL (DODAG)
  }

  /* Liga a camada MAC (nesse caso, TSCH), que não inicia automaticamente */
  NETSTACK_MAC.on();

  /* Se a flag WITH_PERIODIC_ROUTES_PRINT estiver definida,
     imprime a tabela de roteamento a cada minuto */
#if WITH_PERIODIC_ROUTES_PRINT
  {
    static struct etimer et; // Timer para controlar o intervalo de impressão

    etimer_set(&et, CLOCK_SECOND * 60); // Define o timer para 60 segundos

    while(1) {
      /* Imprime o número de entradas na tabela de rotas */
#if (UIP_MAX_ROUTES != 0)
      PRINTF("Routing entries: %u\n", uip_ds6_route_num_routes());
#endif
      /* Imprime o número de nós na topologia RPL (quando usa Source Routing) */
#if (UIP_SR_LINK_NUM != 0)
      PRINTF("Routing links: %u\n", uip_sr_num_nodes());
#endif
      PROCESS_YIELD_UNTIL(etimer_expired(&et)); // Espera até que o timer expire
      etimer_reset(&et); // Reinicia o timer
    }
  }
#endif /* WITH_PERIODIC_ROUTES_PRINT */

  PROCESS_END(); // Fim do processo Contiki
}
