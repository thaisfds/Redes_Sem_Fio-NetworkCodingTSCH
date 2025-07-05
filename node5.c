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
#define SEND_INTERVAL (20 * CLOCK_SECOND)

PROCESS(node_process, "RPL Node");
AUTOSTART_PROCESSES(&node_process);

static struct simple_udp_connection udp_conn;
static int msg_received_count = 0;
static int msg_forwarded_count = 0;

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
  
  // No 5 como coordenador processa mensagens
  LOG_INFO("No %d (coordenador) processou mensagem\n", node_id);
}

static void
broadcast_discovery()
{
  uip_ipaddr_t broadcast_addr;
  
  // Endereço de broadcast link-local
  uip_ip6addr(&broadcast_addr, 0xff02, 0, 0, 0, 0, 0, 0, 1);
  
  char broadcast_msg[50];
  snprintf(broadcast_msg, sizeof(broadcast_msg), "DESCOBERTA do no %d (COORDENADOR)", node_id);
  
  simple_udp_sendto(&udp_conn, broadcast_msg, strlen(broadcast_msg), &broadcast_addr);
  LOG_INFO("BROADCAST: '%s' enviado por coordenador %d\n", broadcast_msg, node_id);
}

static void
send_to_node(uint8_t target_node_id, const char *message)
{
  uip_ipaddr_t target_addr;
  
  // Usar endereço link-local para comunicação direta
  uip_ip6addr(&target_addr, 0xfe80, 0, 0, 0, 0, 0, 0, target_node_id);
  
  simple_udp_sendto(&udp_conn, message, strlen(message), &target_addr);
  LOG_INFO("ENVIANDO mensagem '%s' para No %d (link-local)\n", message, target_node_id);
}

PROCESS_THREAD(node_process, ev, data)
{
  static struct etimer periodic_timer;
  static int msg_count = 0;
  
  PROCESS_BEGIN();

  LOG_INFO("Iniciando processo do no %d - Este no e o coordenador\n", node_id);

  /* Inicializa como root do roteamento RPL */
  NETSTACK_ROUTING.root_start();
  
  NETSTACK_MAC.on();
  simple_udp_register(&udp_conn, UDP_PORT, NULL, UDP_PORT, udp_rx_callback);
  
  // Aguardar um pouco antes de iniciar descoberta como coordenador
  etimer_set(&periodic_timer, 2 * CLOCK_SECOND);
  PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&periodic_timer));
  
  // Fazer broadcast inicial do coordenador
  broadcast_discovery();
  
  etimer_set(&periodic_timer, SEND_INTERVAL);

  while(1) {
    PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&periodic_timer));

    LOG_INFO("No %d - Coordenador: %d mensagens recebidas, %d encaminhadas\n", 
             node_id, msg_received_count, msg_forwarded_count);
    
    // Fazer broadcast periodico do coordenador
    if (msg_count % 15 == 0) {
      broadcast_discovery();
    }

    // Imprimir tabela de roteamento e vizinhos periodicamente
    if (msg_count % 10 == 0) {
      LOG_INFO("=== TABELA DE ROTEAMENTO ===\n");
      #if (UIP_MAX_ROUTES != 0)
        LOG_INFO("Numero de rotas RPL: %u\n", uip_ds6_route_num_routes());
      #endif
      #if (UIP_SR_LINK_NUM != 0)
        LOG_INFO("Numero de links SR: %u\n", uip_sr_num_nodes());
      #endif
      LOG_INFO("Vizinhos na tabela de vizinhanca: %u\n", uip_ds6_nbr_num());
      LOG_INFO("============================\n");
    }
    
    // Coordenador pode enviar mensagens de controle ocasionalmente
    if (msg_count % 5 == 0) {
      char msg[50];
      msg_count++;
      
      snprintf(msg, sizeof(msg), "Controle coordenador %d", msg_count);
      send_to_node(1, msg);
      send_to_node(3, msg);
      
      LOG_INFO("No %d enviou mensagem de controle numero %d\n", node_id, msg_count);
    }


    etimer_reset(&periodic_timer);
  }

  PROCESS_END();
}