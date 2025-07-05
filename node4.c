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
#define SEND_INTERVAL (30 * CLOCK_SECOND)

PROCESS(node_process, "RPL Node");
AUTOSTART_PROCESSES(&node_process);

static struct simple_udp_connection udp_conn;
static int msg_received_count = 0;

static void
broadcast_discovery()
{
  uip_ipaddr_t broadcast_addr;
  
  // Endereço de broadcast link-local
  uip_ip6addr(&broadcast_addr, 0xff02, 0, 0, 0, 0, 0, 0, 1);
  
  char broadcast_msg[50];
  snprintf(broadcast_msg, sizeof(broadcast_msg), "DESCOBERTA do no %d", node_id);
  
  simple_udp_sendto(&udp_conn, broadcast_msg, strlen(broadcast_msg), &broadcast_addr);
  LOG_INFO("BROADCAST: '%s' enviado por no %d\n", broadcast_msg, node_id);
}

static void
udp_rx_callback(struct simple_udp_connection *c,
                const uip_ipaddr_t *sender_addr,
                uint16_t sender_port,
                const uip_ipaddr_t *receiver_addr,
                uint16_t receiver_port,
                const uint8_t *data,
                uint16_t datalen)
{
  msg_received_count++;
  LOG_INFO("RECEBENDO mensagem '%s' de ", (char *)data);
  LOG_INFO_6ADDR(sender_addr);
  LOG_INFO_(" no porto %d (total recebidas: %d)\n", sender_port, msg_received_count);
}

PROCESS_THREAD(node_process, ev, data)
{
  static struct etimer periodic_timer;
  
  PROCESS_BEGIN();

  LOG_INFO("Iniciando processo do no %d - Este no recebe mensagens\n", node_id);

  NETSTACK_MAC.on();
  simple_udp_register(&udp_conn, UDP_PORT, NULL, UDP_PORT, udp_rx_callback);
  
  // Aguardar um pouco antes de iniciar descoberta
  etimer_set(&periodic_timer, 4 * CLOCK_SECOND);
  PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&periodic_timer));
  
  // Fazer broadcast inicial para descoberta de vizinhos
  broadcast_discovery();
  
  etimer_set(&periodic_timer, SEND_INTERVAL);

  while(1) {
    PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&periodic_timer));

    LOG_INFO("No %d - Status: %d mensagens recebidas ate agora\n", node_id, msg_received_count);
    
    // Fazer broadcast periodico para manter descoberta ativa
    static int cycle_count = 0;
    cycle_count++;
    if (cycle_count % 25 == 0) {
      broadcast_discovery();
    }
    
    // Imprimir tabela de roteamento local periodicamente
    if (cycle_count % 10 == 0) {
      LOG_INFO("=== TABELA ROTEAMENTO NO %d ===\n", node_id);
      #if (UIP_MAX_ROUTES != 0)
        LOG_INFO("Rotas RPL: %u\n", uip_ds6_route_num_routes());
      #endif
      #if (UIP_SR_LINK_NUM != 0)
        LOG_INFO("Links SR: %u\n", uip_sr_num_nodes());
      #endif
      LOG_INFO("Vizinhos: %u\n", uip_ds6_nbr_num());
      LOG_INFO("Root alcancavel: %s\n", NETSTACK_ROUTING.node_is_reachable() ? "SIM" : "NAO");
      LOG_INFO("===============================\n");
    }
    
    etimer_reset(&periodic_timer);
  }

  PROCESS_END();
}