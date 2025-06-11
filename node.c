/*
 * Copyright (c) 2015, SICS Swedish ICT.
 * Copyright (c) 2018, University of Bristol - http://www.bristol.ac.uk
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 * notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 * notice, this list of conditions and the following disclaimer in the
 * documentation and/or other materials provided with the distribution.
 * 3. Neither the name of the Institute nor the names of its contributors
 * may be used to endorse or promote products derived from this software
 * without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE INSTITUTE AND CONTRIBUTORS ``AS IS'' AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE INSTITUTE OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 *
 */
/**
 * \file
 * A RPL+TSCH node.
 *
 * \author Simon Duquennoy <simonduq@sics.se>
 * Atis Elsts <atis.elsts@bristol.ac.uk>
 */

 #include "contiki.h"
 #include "sys/node-id.h"
 #include "sys/log.h"
 #include "net/ipv6/uip-ds6-route.h"
 #include "net/ipv6/uip-sr.h"
 #include "net/mac/tsch/tsch.h"
 #include "net/routing/routing.h"

// Adicione esta biblioteca para funcionalidades UDP simples
 #include "net/ipv6/simple-udp.h"
 #include <string.h> // Para memcpy e outras operações de string/memória

// Adicione estas duas linhas AQUI, antes de qualquer uso de LOG_INFO, LOG_DBG, etc.
#define LOG_MODULE "App" // Nome do módulo de log para este arquivo (pode ser "Node", "Main", etc.)
#define LOG_LEVEL LOG_CONF_LEVEL_APP // Usa o nível de log definido em project-conf.h para o módulo APP

 #define DEBUG DEBUG_PRINT // Esta linha é para a macro PRINTF, que é diferente do sistema de log padrão
 #include "net/ipv6/uip-debug.h"

/*---------------------------------------------------------------------------*/
// Definições para a aplicação UDP
#define UDP_LOCAL_PORT  8765 // Porta que este nó irá escutar
#define UDP_REMOTE_PORT 8765 // Porta para a qual este nó irá enviar (assumindo a mesma porta no destino)
#define SEND_INTERVAL   (10 * CLOCK_SECOND) // Intervalo de envio para o exemplo

static struct simple_udp_connection udp_conn;
static uip_ipaddr_t dest_ipaddr; // Endereço IP do destino para o envio

/*---------------------------------------------------------------------------*/
PROCESS(node_process, "RPL Node");
AUTOSTART_PROCESSES(&node_process);

/*---------------------------------------------------------------------------*/
// Callback para pacotes UDP recebidos
static void
udp_rx_callback(struct simple_udp_connection *c,
                const uip_ipaddr_t *sender_addr,
                uint16_t sender_port,
                const uip_ipaddr_t *receiver_addr,
                uint16_t receiver_port,
                const uint8_t *data,
                uint16_t datalen)
{
  // Obtenha o ID do nó remetente
  uint8_t sender_node_id = sender_addr->u8[sizeof(uip_ipaddr_t)-1]; // Assumindo que o último byte do IP indica o ID do nó

  // Converte o payload para string para log. Cuidado com payloads não-string!
  // Para payloads binários, você pode logar em formato hexadecimal ou similar.
  // Aqui, assumimos que o payload é uma string simples para o exemplo de log.
  char received_message[datalen + 1];
  memcpy(received_message, data, datalen);
  received_message[datalen] = '\0'; // Garante terminação nula para a string

  LOG_INFO("RECEBENDO MENSAGEM DE %d: %s\n", sender_node_id, received_message);
}

/*---------------------------------------------------------------------------*/
PROCESS_THREAD(node_process, ev, data)
{
  static struct etimer periodic_timer;
  int is_coordinator;

  PROCESS_BEGIN();

  is_coordinator = 0;

#if CONTIQUI_TARGET_COOJA
  is_coordinator = (node_id == 1); // Exemplo: Nó 1 como border router
#endif

  if(is_coordinator) {
    NETSTACK_ROUTING.root_start();
    LOG_INFO("RPL Border Router (Node ID: %d) started\n", node_id);
  } else {
    LOG_INFO("RPL Node (Node ID: %d) started\n", node_id);
  }
  NETSTACK_MAC.on();
  LOG_INFO("TSCH MAC enabled on Node ID: %d\n", node_id);

  // Registrar a conexão UDP para o nó receber pacotes
  simple_udp_register(&udp_conn, UDP_LOCAL_PORT, NULL, UDP_REMOTE_PORT, udp_rx_callback);

  // Exemplo de envio de pacotes periódicos (se este nó não for o coordenador)
  // No seu cenário de Network Coding, o envio será mais complexo e baseado em eventos.
  // Este é apenas um exemplo de como usar o LOG_INFO para envio.
  if(!is_coordinator) {
    etimer_set(&periodic_timer, SEND_INTERVAL);
    while(1) {
      PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&periodic_timer));

      // Exemplo: Este nó (qualquer um exceto o border router) envia para o Nó 1 (coordenador)
      // No seu cenário de Network Coding, você enviaria para o Nó 5.
      uip_ip6addr(&dest_ipaddr, 0xaaaa, 0, 0, 0, 0, 0, 0, 1); // Exemplo: Enviando para o Nó 1

      // Mensagem de exemplo
      static char message[32];
      snprintf(message, sizeof(message), "Hello from Node %d!", node_id);

      // Envia a mensagem
      simple_udp_sendto(&udp_conn, message, strlen(message), &dest_ipaddr);
      LOG_INFO("ENVIANDO MENSAGEM PARA %d: %s\n", dest_ipaddr.u8[sizeof(uip_ipaddr_t)-1], message);

      etimer_reset(&periodic_timer);
    }
  }

#if WITH_PERIODIC_ROUTES_PRINT
  // ... (código existente para impressão de rotas, se você quiser mantê-lo)
#endif /* WITH_PERIODIC_ROUTES_PRINT */

  PROCESS_END();
}
/*---------------------------------------------------------------------------*/