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
#define SEND_INTERVAL (10 * CLOCK_SECOND)  // Time between transmissions

/*-------------------------------- PROCESS DEFINITIONS --------------------------------*/

/* Defines the process named "RPL Node" */
PROCESS(node_process, "RPL Node");

/* Defines that this process will be automatically started when the node boots */
AUTOSTART_PROCESSES(&node_process);

/* Add the UDP connection */
static struct simple_udp_connection udp_conn;

/* Variable to store the coordinator's IP address */
static uip_ipaddr_t coordinator_ipaddr;

/*-------------------------------- UDP callback functions --------------------------------*/

static void
udp_rx_callback(struct simple_udp_connection *c,
                const uip_ipaddr_t *sender_addr,
                uint16_t sender_port,
                const uip_ipaddr_t *receiver_addr,
                uint16_t receiver_port,
                const uint8_t *data,
                uint16_t datalen)
{
  LOG_INFO("Received '%s' from ", (char *)data);
  LOG_INFO_6ADDR(sender_addr);
  LOG_INFO_(" on port %d\n", sender_port);

  // If this node is the coordinator, it might want to reply or process the message
  // Example: if the coordinator receives a message, it can log it
  if (node_id == 5) { // Assuming 5 is the coordinator
      // Do something with the message received by the coordinator
  }
}

/*-------------------------------- Process --------------------------------*/

/* Process body */
PROCESS_THREAD(node_process, ev, data)
{
  static struct etimer periodic_timer; // Timer for periodic sending

  PROCESS_BEGIN(); // Start of the Contiki process

  /* Log the start of the process with the node ID */
    LOG_INFO("Starting process for node %d - This node is a common node\n", node_id);


  /* Turn on the MAC layer (in this case, TSCH), which does not start automatically */
  NETSTACK_MAC.on();

  /* Initialize the UDP connection */
  simple_udp_register(&udp_conn, UDP_PORT, NULL, UDP_PORT, udp_rx_callback);

  /* Set the timer for periodic sending */
  etimer_set(&periodic_timer, SEND_INTERVAL);

  while(1) {
    PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&periodic_timer));

        if (NETSTACK_ROUTING.node_is_reachable()) {
            LOG_INFO("'%d' - Root reachable, attempting to send UDP.\n", node_id);
            NETSTACK_ROUTING.get_root_ipaddr(&coordinator_ipaddr);
            LOG_INFO_6ADDR(&coordinator_ipaddr); // Print the root address to verify
            char msg[30];
            snprintf(msg, sizeof(msg), "Hello from node %d!", node_id);
            simple_udp_sendto(&udp_conn, msg, strlen(msg), &coordinator_ipaddr);
            LOG_INFO("'%d' - SENDING message: '%s'\n", node_id, msg);
        } else {
            LOG_INFO("'%d' - Root not reachable yet. Not sending.\n", node_id);
        }
    etimer_reset(&periodic_timer);
  }

  PROCESS_END(); // End of the Contiki process
}