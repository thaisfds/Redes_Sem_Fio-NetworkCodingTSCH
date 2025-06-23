// common_defs.h
#ifndef COMMON_DEFS_H
#define COMMON_DEFS_H

#include "contiki.h" // Para uint8_t, etc.

#define MAX_PAYLOAD_LEN 30 // Ajuste conforme necessário
#define UDP_PORT 1234
#define SEND_INTERVAL (20 * CLOCK_SECOND) // Tempo entre envios

// Estrutura da mensagem (simplificada sem campos de codificação se preferir, mas podemos mantê-los para padronização)
typedef struct {
  uint8_t sender_id;
  uint8_t seq_num;     // Número de sequência
  // uint8_t is_encoded;  // Não usado neste modelo sem XOR, mas pode manter para padronização
  char payload[MAX_PAYLOAD_LEN]; // O conteúdo da mensagem
  // uint16_t original_len; // Não usado neste modelo sem XOR
} net_coding_message_t;

#endif /* COMMON_DEFS_H */