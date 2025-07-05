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
#define SEND_INTERVAL (10 * CLOCK_SECOND)

PROCESS(node_process, "RPL Node");
AUTOSTART_PROCESSES(&node_process);

static struct simple_udp_connection udp_conn;

static void
udp_rx_callback(struct simple_udp_connection *c,
                const uip_ipaddr_t *sender_addr,
                uint16_t sender_port,
                const uip_ipaddr_t *receiver_addr,
                uint16_t receiver_port,
                const uint8_t *data,
                uint16_t datalen)
{
  LOG_INFO("RECEBENDO mensagem '%s' de ", (char *)data);
  LOG_INFO_6ADDR(sender_addr);
  LOG_INFO_(" no porto %d\n", sender_port);
}

static void
send_to_node(uint8_t target_node_id, const char *message)
{
  uip_ipaddr_t target_addr;
  
  // Usar endereço link-local para comunicação direta
  uip_ip6addr(&target_addr, 0xfe80, 0, 0, 0, 0, 0, 0, target_node_id);
  
  simple_udp_sendto(&udp_conn, message, strlen(message), &target_addr);
  LOG_INFO("ENVIANDO mensagem '%s' para no %d (link-local)\n", message, target_node_id);
}

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

PROCESS_THREAD(node_process, ev, data)
{
  static struct etimer periodic_timer;
  static int msg_count = 0;
  
  PROCESS_BEGIN();

  LOG_INFO("Iniciando processo do no %d - Este no envia mensagens\n", node_id);

  NETSTACK_MAC.on();
  simple_udp_register(&udp_conn, UDP_PORT, NULL, UDP_PORT, udp_rx_callback);
  
  // Aguardar um pouco antes de iniciar descoberta
  etimer_set(&periodic_timer, 5 * CLOCK_SECOND);
  PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&periodic_timer));
  
  // Fazer broadcast inicial para descoberta de vizinhos
  broadcast_discovery();
  
  etimer_set(&periodic_timer, SEND_INTERVAL);

  while(1) {
    PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&periodic_timer));

    // Fazer broadcast periodico para manter descoberta ativa
    if (msg_count % 20 == 0) {
      broadcast_discovery();
    }

    // Imprimir tabela de roteamento local periodicamente
    if (msg_count % 15 == 0) {
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

    if (NETSTACK_ROUTING.node_is_reachable()) {
      char msg[50];
      msg_count++;
      
      // Enviar para no 2
      snprintf(msg, sizeof(msg), "Mensagem %d do no %d", msg_count, node_id);
      send_to_node(2, msg);
      
      // Enviar para no 4
      snprintf(msg, sizeof(msg), "Mensagem %d do no %d", msg_count, node_id);
      send_to_node(4, msg);
      
      LOG_INFO("No %d enviou mensagem numero %d\n", node_id, msg_count);
    } else {
      LOG_INFO("No %d - Root ainda nao alcancavel. Nao enviando.\n", node_id);
    }
    
    etimer_reset(&periodic_timer);
  }

  PROCESS_END();
}