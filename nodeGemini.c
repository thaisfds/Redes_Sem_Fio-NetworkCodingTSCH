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
 * A RPL+TSCH node for Network Coding demonstration.
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
 
 // NOVO: Incluir simple-udp e string.h para a aplicação
 #include "net/ipv6/simple-udp.h"
 #include <string.h>
 
 #define LOG_MODULE "App"
 #define LOG_LEVEL LOG_CONF_LEVEL_APP
 
 #define DEBUG DEBUG_PRINT
 #include "net/ipv6/uip-debug.h"
 
 /*---------------------------------------------------------------------------*/
 // Definições para a aplicação UDP
 #define UDP_PORT        8765 // Porta UDP que todos os nós usarão
 #define SEND_INTERVAL   (5 * CLOCK_SECOND) // Intervalo de envio para nós fonte (Nó 1 e Nó 3)
 
 // Tamanho do payload para P1, P2 e o pacote codificado
 // Usaremos 4 bytes para um uint32_t que representará o conteúdo (e número de sequência)
 #define PAYLOAD_SIZE 4
 
 static struct simple_udp_connection udp_conn; // Estrutura para gerenciar a conexão UDP
 
 // Variáveis de estado para o Nó 5 (Codificador)
 static uint8_t p1_data_at_node5[PAYLOAD_SIZE];
 static uint8_t p2_data_at_node5[PAYLOAD_SIZE];
 static bool p1_received_at_node5 = false;
 static bool p2_received_at_node5 = false;
 static uint32_t p1_seq_at_node5 = 0;
 static uint32_t p2_seq_at_node5 = 0;
 
 // Variáveis de estado para o Nó 2 (Destino de P1)
 static uint8_t p2_data_at_node2[PAYLOAD_SIZE]; // P2 recebido diretamente do Nó 3
 static bool p2_received_at_node2 = false;
 static uint32_t p2_seq_at_node2 = 0;
 
 // Variáveis de estado para o Nó 4 (Destino de P2)
 static uint8_t p1_data_at_node4[PAYLOAD_SIZE]; // P1 recebido diretamente do Nó 1
 static bool p1_received_at_node4 = false;
 static uint32_t p1_seq_at_node4 = 0;
 
 /*---------------------------------------------------------------------------*/
 // Declarações forward para funções auxiliares e do processo
 void print_hex_data(const char *label, const uint8_t *data, uint16_t len);
 static void udp_rx_callback(struct simple_udp_connection *c,
                             const uip_ipaddr_t *sender_addr,
                             uint16_t sender_port,
                             const uip_ipaddr_t *receiver_addr,
                             uint16_t receiver_port,
                             const uint8_t *data,
                             uint16_t datalen);
 
 PROCESS_THREAD(node_process, ev, data); // Declaração da função do processo
 
 /*---------------------------------------------------------------------------*/
 PROCESS(node_process, "RPL Node"); // Declaração do processo Contiki
 AUTOSTART_PROCESSES(&node_process); // Inicia o processo automaticamente
 
 /*---------------------------------------------------------------------------*/
 // Implementação da função auxiliar de log de dados hexadecimais
 void print_hex_data(const char *label, const uint8_t *data, uint16_t len) {
     LOG_INFO("%s [", label);
     for(int i = 0; i < len; i++) {
         LOG_INFO_("%02X ", data[i]);
     }
     LOG_INFO_("]\n");
 }
 
 /*---------------------------------------------------------------------------*/
 // Implementação do callback para pacotes UDP recebidos
 static void
 udp_rx_callback(struct simple_udp_connection *c,
                 const uip_ipaddr_t *sender_addr,
                 uint16_t sender_port,
                 const uip_ipaddr_t *receiver_addr,
                 uint16_t receiver_port,
                 const uint8_t *data,
                 uint16_t datalen)
 {
     uint8_t sender_node_id = sender_addr->u8[sizeof(uip_ipaddr_t)-1];
     uint32_t received_seq_num = 0;
 
     if (datalen >= sizeof(uint32_t)) {
         memcpy(&received_seq_num, data, sizeof(uint32_t));
     }
 
     LOG_INFO("RECEBENDO PACOTE DE %d (Seq: %lu) em Nó %d\n", sender_node_id, (unsigned long)received_seq_num, node_id);
     print_hex_data("  Conteúdo do pacote", data, datalen);
 
     // Lógica específica para o Nó 5 (Codificador Central)
     if (node_id == 5) {
         if (sender_node_id == 1) { // Pacote P1 recebido do Nó 1
             if (received_seq_num > p1_seq_at_node5) {
                 memcpy(p1_data_at_node5, data, MIN(datalen, PAYLOAD_SIZE));
                 p1_received_at_node5 = true;
                 p1_seq_at_node5 = received_seq_num;
                 LOG_INFO("  Nó 5: Recebeu P1 (Seq: %lu) do Nó 1\n", (unsigned long)received_seq_num);
             } else {
                 LOG_INFO("  Nó 5: P1 antigo recebido (Seq: %lu <= %lu), ignorando.\n", (unsigned long)received_seq_num, (unsigned long)p1_seq_at_node5);
             }
         } else if (sender_node_id == 3) { // Pacote P2 recebido do Nó 3
             if (received_seq_num > p2_seq_at_node5) {
                 memcpy(p2_data_at_node5, data, MIN(datalen, PAYLOAD_SIZE));
                 p2_received_at_node5 = true;
                 p2_seq_at_node5 = received_seq_num;
                 LOG_INFO("  Nó 5: Recebeu P2 (Seq: %lu) do Nó 3\n", (unsigned long)received_seq_num);
             } else {
                 LOG_INFO("  Nó 5: P2 antigo recebido (Seq: %lu <= %lu), ignorando.\n", (unsigned long)received_seq_num, (unsigned long)p2_seq_at_node5);
             }
         }
 
         // Se ambos P1 e P2 (com o mesmo número de sequência) foram recebidos, codifica e retransmite
         if (p1_received_at_node5 && p2_received_at_node5 && (p1_seq_at_node5 == p2_seq_at_node5)) {
             uint8_t coded_data[PAYLOAD_SIZE];
             for (int i = 0; i < PAYLOAD_SIZE; i++) {
                 coded_data[i] = p1_data_at_node5[i] ^ p2_data_at_node5[i];
             }
             LOG_INFO("  Nó 5: Codificou P1 (Seq %lu) XOR P2 (Seq %lu)\n", (unsigned long)p1_seq_at_node5, (unsigned long)p2_seq_at_node5);
             print_hex_data("    Conteúdo Codificado", coded_data, PAYLOAD_SIZE);
 
             uip_ipaddr_t dest_addr_2;
             uip_ip6addr(&dest_addr_2, 0xaaaa, 0, 0, 0, 0, 0, 0, 2);
             simple_udp_sendto(&udp_conn, coded_data, PAYLOAD_SIZE, &dest_addr_2);
             LOG_INFO("ENVIANDO PACOTE CODIFICADO PARA O NO 2 (Seq %lu)\n", (unsigned long)p1_seq_at_node5);
 
             uip_ipaddr_t dest_addr_4;
             uip_ip6addr(&dest_addr_4, 0xaaaa, 0, 0, 0, 0, 0, 0, 4);
             simple_udp_sendto(&udp_conn, coded_data, PAYLOAD_SIZE, &dest_addr_4);
             LOG_INFO("ENVIANDO PACOTE CODIFICADO PARA O NO 4 (Seq %lu)\n", (unsigned long)p1_seq_at_node5);
 
             p1_received_at_node5 = false;
             p2_received_at_node5 = false;
         }
 
     } else if (node_id == 2) { // Lógica específica para o Nó 2 (Destino de P1)
         if (sender_node_id == 3) { // Recebe P2 diretamente do Nó 3
             if (received_seq_num > p2_seq_at_node2) {
                 memcpy(p2_data_at_node2, data, MIN(datalen, PAYLOAD_SIZE));
                 p2_received_at_node2 = true;
                 p2_seq_at_node2 = received_seq_num;
                 LOG_INFO("  Nó 2: Recebeu P2 (Seq: %lu) diretamente do Nó 3\n", (unsigned long)received_seq_num);
             } else {
                 LOG_INFO("  Nó 2: P2 antigo recebido (Seq: %lu <= %lu), ignorando.\n", (unsigned long)received_seq_num, (unsigned long)p2_seq_at_node2);
             }
         } else if (sender_node_id == 5) { // Recebe P1 XOR P2 do Nó 5
             if (p2_received_at_node2 && (received_seq_num == p2_seq_at_node2)) {
                 uint8_t decoded_p1[PAYLOAD_SIZE];
                 for (int i = 0; i < PAYLOAD_SIZE; i++) {
                     decoded_p1[i] = data[i] ^ p2_data_at_node2[i];
                 }
                 uint32_t decoded_p1_seq = 0;
                 memcpy(&decoded_p1_seq, decoded_p1, sizeof(uint32_t));
                 LOG_INFO("  Nó 2: Decodificou P1 (Seq: %lu). VERIFICADO: %s\n", (unsigned long)decoded_p1_seq, (decoded_p1_seq == p2_seq_at_node2) ? "SUCESSO" : "FALHA");
                 print_hex_data("    Conteúdo Decodificado de P1", decoded_p1, PAYLOAD_SIZE);
             } else {
                 LOG_INFO("  Nó 2: Recebeu pacote codificado (Seq: %lu) mas ainda não tem P2 compatível (P2 Seq: %lu). Esperando...\n", (unsigned long)received_seq_num, (unsigned long)p2_seq_at_node2);
             }
         }
 
     } else if (node_id == 4) { // Lógica específica para o Nó 4 (Destino de P2)
         if (sender_node_id == 1) { // Recebe P1 diretamente do Nó 1
             if (received_seq_num > p1_seq_at_node4) {
                 memcpy(p1_data_at_node4, data, MIN(datalen, PAYLOAD_SIZE));
                 p1_received_at_node4 = true;
                 p1_seq_at_node4 = received_seq_num;
                 LOG_INFO("  Nó 4: Recebeu P1 (Seq: %lu) diretamente do Nó 1\n", (unsigned long)received_seq_num);
             } else {
                 LOG_INFO("  Nó 4: P1 antigo recebido (Seq: %lu <= %lu), ignorando.\n", (unsigned long)received_seq_num, (unsigned long)p1_seq_at_node4);
             }
         } else if (sender_node_id == 5) { // Recebe P1 XOR P2 do Nó 5
             if (p1_received_at_node4 && (received_seq_num == p1_seq_at_node4)) {
                 uint8_t decoded_p2[PAYLOAD_SIZE];
                 for (int i = 0; i < PAYLOAD_SIZE; i++) {
                     decoded_p2[i] = data[i] ^ p1_data_at_node4[i];
                 }
                 uint32_t decoded_p2_seq = 0;
                 memcpy(&decoded_p2_seq, decoded_p2, sizeof(uint32_t));
                 LOG_INFO("  Nó 4: Decodificou P2 (Seq: %lu). VERIFICADO: %s\n", (unsigned long)decoded_p2_seq, (decoded_p2_seq == p1_seq_at_node4) ? "SUCESSO" : "FALHA");
                 print_hex_data("    Conteúdo Decodificado de P2", decoded_p2, PAYLOAD_SIZE);
             } else {
                 LOG_INFO("  Nó 4: Recebeu pacote codificado (Seq: %lu) mas ainda não tem P1 compatível (P1 Seq: %lu). Esperando...\n", (unsigned long)received_seq_num, (unsigned long)p1_seq_at_node4);
             }
         }
     }
 }
 
 /*---------------------------------------------------------------------------*/
 // Implementação do processo Contiki
 PROCESS_THREAD(node_process, ev, data)
 {
   static struct etimer periodic_timer;
   static uint32_t packet_seq_num = 0;
   uip_ipaddr_t dest_ipaddr;
 
   PROCESS_BEGIN();
 
   NETSTACK_MAC.on();
   LOG_INFO("TSCH MAC enabled on Node ID: %d\n", node_id);
 
   simple_udp_register(&udp_conn, UDP_PORT, NULL, UDP_PORT, udp_rx_callback);
 
   // Lógica de envio periódica para Nós Fonte (Nó 1 e Nó 3)
   if (node_id == 1 || node_id == 3) {
     etimer_set(&periodic_timer, SEND_INTERVAL);
     while(1) {
       PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&periodic_timer));
       packet_seq_num++;
 
       uint8_t payload[PAYLOAD_SIZE];
       memcpy(payload, &packet_seq_num, sizeof(packet_seq_num));
 
       if (node_id == 1) { // Lógica para o Nó 1
         uip_ip6addr(&dest_ipaddr, 0xaaaa, 0, 0, 0, 0, 0, 0, 5);
         simple_udp_sendto(&udp_conn, payload, PAYLOAD_SIZE, &dest_ipaddr);
         LOG_INFO("ENVIANDO P1 (Seq: %lu) PARA O NO 5\n", (unsigned long)packet_seq_num);
 
         uip_ip6addr(&dest_ipaddr, 0xaaaa, 0, 0, 0, 0, 0, 0, 4);
         simple_udp_sendto(&udp_conn, payload, PAYLOAD_SIZE, &dest_ipaddr);
         LOG_INFO("ENVIANDO P1 (Seq: %lu) DIRETAMENTE PARA O NO 4\n", (unsigned long)packet_seq_num);
 
       } else if (node_id == 3) { // Lógica para o Nó 3
         uip_ip6addr(&dest_ipaddr, 0xaaaa, 0, 0, 0, 0, 0, 0, 5);
         simple_udp_sendto(&udp_conn, payload, PAYLOAD_SIZE, &dest_ipaddr);
         LOG_INFO("ENVIANDO P2 (Seq: %lu) PARA O NO 5\n", (unsigned long)packet_seq_num);
 
         uip_ip6addr(&dest_ipaddr, 0xaaaa, 0, 0, 0, 0, 0, 0, 2);
         simple_udp_sendto(&udp_conn, payload, PAYLOAD_SIZE, &dest_ipaddr);
         LOG_INFO("ENVIANDO P2 (Seq: %lu) DIRETAMENTE PARA O NO 2\n", (unsigned long)packet_seq_num);
       }
 
       etimer_reset(&periodic_timer);
     }
   } else {
     // Nós 2, 4 e 5 aguardam eventos de recepção.
     while(1) {
       PROCESS_WAIT_EVENT();
     }
   }
 
   PROCESS_END();
 }