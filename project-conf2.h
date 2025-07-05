#ifndef __PROJECT_CONF2_H__
#define __PROJECT_CONF2_H__

/* Define if TSCH security is enabled (0 = disabled) */
#ifndef WITH_SECURITY
#define WITH_SECURITY 0
#endif /* WITH_SECURITY */

/* Disable 6LoWPAN packet fragmentation to save space */
#define SICSLOWPAN_CONF_FRAG 0

/* Network stack buffer size */
#define UIP_CONF_BUFFER_SIZE 160

/*******************************************************/
/******************* TSCH Configurations ****************/
/*******************************************************/

/* IEEE 802.15.4 PAN ID (all nodes must use the same) */
#define IEEE802154_CONF_PANID 0x81a5

/* Enable TSCH */
#define TSCH_CONF_AUTOSTART 1

/* TSCH minimal schedule length */
#define TSCH_SCHEDULE_CONF_DEFAULT_LENGTH 3

#if WITH_SECURITY
/* Enable link-layer security if WITH_SECURITY=1 */
#define LLSEC802154_CONF_ENABLED 1
#endif /* WITH_SECURITY */

/* Enable TSCH statistics */
#define TSCH_STATS_CONF_ON 1

/* Enable periodic RSSI noise sampling */
#define TSCH_STATS_CONF_SAMPLE_NOISE_RSSI 1

/* TSCH stats decay interval in seconds */
#define TSCH_STATS_CONF_DECAY_INTERVAL (60 * CLOCK_SECOND)

/*******************************************************/
/******************* UDP Configurations *****************/
/*******************************************************/

/* Enable UDP */
#define UIP_CONF_UDP 1

/* UDP buffer size */
#define UIP_CONF_UDP_CONNS 10

/* Default IPv6 prefix for nodes */
#define UIP_DS6_DEFAULT_PREFIX 0xfd00

/*******************************************************/
/************* System-wide Settings *********************/
/*******************************************************/

/* Log levels for subsystems */
#define LOG_CONF_LEVEL_RPL                         LOG_LEVEL_INFO
#define LOG_CONF_LEVEL_TCPIP                       LOG_LEVEL_WARN
#define LOG_CONF_LEVEL_IPV6                        LOG_LEVEL_WARN
#define LOG_CONF_LEVEL_6LOWPAN                     LOG_LEVEL_WARN
#define LOG_CONF_LEVEL_MAC                         LOG_LEVEL_INFO
#define LOG_CONF_LEVEL_FRAMER                      LOG_LEVEL_INFO
#define LOG_CONF_LEVEL_APP                         LOG_LEVEL_INFO

/* Enable per-slot TSCH logging */
#define TSCH_LOG_CONF_PER_SLOT                     1

/* Increase max routes and neighbors for routing table */
#define UIP_CONF_MAX_ROUTES    20
#define UIP_CONF_MAX_NEIGHBORS 20

/* Contiki target flag */
#ifndef CONTIKI_TARGET_COOJA
#define CONTIKI_TARGET_COOJA 1
#endif

/* Enable RPL */
#define UIP_CONF_IPV6_RPL 1

/* RPL configuration */
#define RPL_CONF_OF_OCP RPL_OCP_MRHOF
#define RPL_CONF_DIO_INTERVAL_MIN 12
#define RPL_CONF_DIO_INTERVAL_DOUBLINGS 8

/* Enable periodic routing table printing */
#define WITH_PERIODIC_ROUTES_PRINT 1

#endif /* __PROJECT_CONF2_H__ */