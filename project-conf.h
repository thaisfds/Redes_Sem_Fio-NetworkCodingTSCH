#ifndef __PROJECT_CONF_H__
#define __PROJECT_CONF_H__

/* Defines if TSCH security is enabled (0 = disabled) */
#ifndef WITH_SECURITY
#define WITH_SECURITY 0
#endif /* WITH_SECURITY */

/* Disables 6LoWPAN packet fragmentation to save space */
#define SICSLOWPAN_CONF_FRAG 0

/* Defines the size of the network stack buffer */
#define UIP_CONF_BUFFER_SIZE 160

/*******************************************************/
/******************* TSCH Configurations ***************/
/*******************************************************/

/* Defines the IEEE 802.15.4 network's PAN ID (all nodes must use the same) */
#define IEEE802154_CONF_PANID 0x81a5

/* Does not start TSCH automatically. It will be activated manually in the C code */
#define TSCH_CONF_AUTOSTART 0

/* Defines the length of the minimalist TSCH schedule.
 * The higher the value, the lower the frequency of active slots,
 * reducing power consumption, but also transmission capacity */
#define TSCH_SCHEDULE_CONF_DEFAULT_LENGTH 3

#if WITH_SECURITY
/* Enables link security (encryption) if WITH_SECURITY is 1 */
#define LLSEC802154_CONF_ENABLED 1
#endif /* WITH_SECURITY */

/* Enables TSCH statistics collection */
#define TSCH_STATS_CONF_ON 1

/* Periodic RSSI (signal level) collection for channel analysis */
#define TSCH_STATS_CONF_SAMPLE_NOISE_RSSI 1

/* Interval for TSCH statistics decay (in seconds) */
#define TSCH_STATS_CONF_DECAY_INTERVAL (60 * CLOCK_SECOND)

/*******************************************************/
/************* Other system configurations *************/
/*******************************************************/

/* Log levels for each subsystem */
#define LOG_CONF_LEVEL_RPL                         LOG_LEVEL_INFO
#define LOG_CONF_LEVEL_TCPIP                       LOG_LEVEL_WARN
#define LOG_CONF_LEVEL_IPV6                        LOG_LEVEL_WARN
#define LOG_CONF_LEVEL_6LOWPAN                     LOG_LEVEL_WARN
#define LOG_CONF_LEVEL_MAC                         LOG_LEVEL_DBG  // Detailed for MAC (useful in TSCH)
#define LOG_CONF_LEVEL_FRAMER                      LOG_LEVEL_INFO
#define LOG_CONF_LEVEL_APP                         LOG_LEVEL_INFO // Log level for your application
 
/* Activates per-slot logs in TSCH, useful for debugging */
#define TSCH_LOG_CONF_PER_SLOT                     1

/* Contiki */
#ifndef CONTIKI_TARGET_COOJA
#define CONTIKI_TARGET_COOJA 1 // Ensures the flag is defined
#endif

#endif /* __PROJECT_CONF_H__ */