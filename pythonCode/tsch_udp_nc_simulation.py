import time
import threading
import random
from collections import deque
from enum import Enum
from dataclasses import dataclass, field
import dataclasses
from typing import Dict, List, Set, Optional, Union
import re
import sys
import os
import csv
import functools

# --- Adicionando bibliotecas para visualização e animação ---
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
# -----------------------------------------------------------

# Lista global para armazenar os eventos da simulação para a animação
simulation_events = []
simulation_events_lock = threading.Lock()


# Classe para redirecionar a saída APENAS para o arquivo
class DuplicarSaida:
    def __init__(self, stdout_original_nao_usado, file):
        self.file = file

    def write(self, data):
        self.file.write(data)
        self.file.flush()

    def flush(self):
        self.file.flush()


class NodeState(Enum):
    IDLE = "idle"
    TRANSMITTING = "transmitting"
    RECEIVING = "receiving"


@dataclass
class Message:
    id: int
    source: int
    destination: Union[int, List[int]]
    data: str
    timestamp: float
    hop_count: int = 0
    path: List[int] = field(default_factory=list)
    is_nc_coded: bool = False
    original_message_ids: List[int] = field(default_factory=list)
    nc_intended_destinations: List[int] = field(default_factory=list)
    is_nc_precursor: bool = False
    # NOVO: Adiciona o destino final original da mensagem precursora, útil para o coder
    nc_precursor_original_final_dest: Optional[Union[int, List[int]]] = None 


class TSCHSlot:
    def __init__(self, slot_id: int, channel: int, tx_node: int, rx_node: int):
        self.slot_id = slot_id
        self.channel = channel
        self.tx_node = tx_node
        self.rx_node = rx_node


class TSCHSchedule:
    def __init__(self, slotframe_length: int = 10):
        self.slotframe_length = slotframe_length
        self.slots: List[TSCHSlot] = []
        self.current_slot = 0

    def add_slot(self, slot: TSCHSlot):
        self.slots.append(slot)

    def get_current_slot(self) -> Optional[TSCHSlot]:
        if self.slots:
            return self.slots[self.current_slot % len(self.slots)]
        return None

    def advance_slot(self):
        self.current_slot = (self.current_slot + 1) % len(self.slots) if self.slots else 0


class TSCHNode:
    def __init__(self, node_id: int, neighbors: List[int]):
        self.node_id = node_id
        self.neighbors = set(neighbors)
        self.state = NodeState.IDLE
        self.message_queue = deque()
        self.received_messages = []
        self.schedule = TSCHSchedule()
        self.network = None
        self.message_counter = 0
        self.lock = threading.Lock()
        self.transmitted_messages_by_channel: Dict[int, int] = {}
        # Buffer NC armazena mensagens precursoras por seu global_id original
        self.nc_buffer: Dict[int, Message] = {}


    def set_network(self, network):
        self.network = network

    def add_neighbor(self, neighbor_id: int):
        self.neighbors.add(neighbor_id)

    def send_message(self, destination: Union[int, List[int]], data: str, is_nc_precursor: bool = False,
                     original_message_global_id: Optional[int] = None,
                     is_nc_coded: bool = False, nc_intended_destinations: Optional[List[int]] = None,
                     original_message_ids_coded: Optional[List[int]] = None,
                     # NOVO: Para precursor, qual era o destino final original completo (seja int ou list)
                     nc_precursor_original_final_dest: Optional[Union[int, List[int]]] = None): 
        with self.lock:
            self.message_counter += 1
            current_message_local_id = self.message_counter

            msg_original_ids = []
            if is_nc_precursor and original_message_global_id is not None:
                msg_original_ids = [original_message_global_id]
            elif is_nc_coded and original_message_ids_coded is not None:
                msg_original_ids = original_message_ids_coded

            message = Message(
                id=current_message_local_id,
                source=self.node_id,
                destination=destination, # Para precursor, é o CODER. Para regular, é o destino(s) final(is).
                data=data,
                timestamp=time.time(),
                path=[self.node_id],
                is_nc_precursor=is_nc_precursor,
                original_message_ids=msg_original_ids,
                nc_intended_destinations=nc_intended_destinations if nc_intended_destinations else [],
                is_nc_coded=is_nc_coded,
                # Atribui o destino final original se for precursor.
                nc_precursor_original_final_dest=nc_precursor_original_final_dest
            )

            if not message.is_nc_precursor: # Só conta mensagens "originais" (não o hop para o coder)
                self.network.total_messages_initiated += 1


            print(f"\n--- Node {self.node_id} - Sending Message ---")
            print(f"  Message ID (local): {message.id}")
            print(f"  Source: {self.node_id}")
            print(f"  Destination(s): {message.destination}")
            print(f"  Data: '{message.data}'")
            print(f"  Initial Path: {message.path}")
            print(f"  Is NC Precursor: {message.is_nc_precursor}")
            print(f"  Is NC Coded: {message.is_nc_coded}")
            print(f"  Original Message Global IDs: {message.original_message_ids}")
            print(f"  NC Intended Dests: {message.nc_intended_destinations}")
            print(f"  NC Precursor Original Final Dest: {message.nc_precursor_original_final_dest}") # NOVO LOG

            # Roteamento: determine o próximo hop com base no 'destination' da função (não do objeto Message)
            next_hop_for_routing = None
            if isinstance(destination, list) and destination: # Se o destino imediato é uma lista (ex: multicast direto)
                # Para fins de cálculo do next_hop, pegamos o primeiro da lista.
                # O deliver_message lidará com a entrega para todos os destinos na lista.
                next_hop_for_routing = self.get_next_hop(destination[0]) 
            elif isinstance(destination, int): # Se o destino imediato é um único nó
                next_hop_for_routing = self.get_next_hop(destination)

            if next_hop_for_routing:
                print(f"  Forwarding via next hop: {next_hop_for_routing}.")
                event_type = "sending_regular"
                optional_data_for_animation = None 
                if message.is_nc_precursor:
                    event_type = "sending_nc_precursor"
                    if message.original_message_ids:
                        optional_data_for_animation = message.original_message_ids[0]
                elif message.is_nc_coded:
                    event_type = "sending_nc_coded"
                    optional_data_for_animation = message.nc_intended_destinations

                with simulation_events_lock:
                    simulation_events.append((time.time(), message.id, self.node_id, next_hop_for_routing, event_type, optional_data_for_animation))
                
                # A função deliver_message recebe o objeto Message completo e o *destino imediato*.
                # Se `destination` (parâmetro da send_message) é uma lista, deliver_message já sabe como lidar.
                # Se `destination` é um int (como o Coder), deliver_message lida com unicast.
                self.network.deliver_message(message, destination) # Passa o destino original ou coder
                
                current_slot = self.schedule.get_current_slot()
                if current_slot:
                    self.transmitted_messages_by_channel[current_slot.channel] = \
                        self.transmitted_messages_by_channel.get(current_slot.channel, 0) + 1
            else:
                print(f"  ERROR: No route to destination {message.destination} from node {self.node_id}.")
                self.network.messages_not_sent_no_route += 1
            print("-----------------------------------\n")

    def get_next_hop(self, destination: int) -> Optional[int]:
        if destination in self.neighbors:
            return destination

        for neighbor in self.neighbors:
            if self.network and neighbor in self.network.nodes:
                neighbor_node = self.network.nodes[neighbor]
                if destination in neighbor_node.neighbors:
                    return neighbor

        return list(self.neighbors)[0] if self.neighbors else None


    def process_nc_coding(self, original_nc_message_commands: List[Dict]):
        with self.lock:
            if self.node_id != self.network.nc_coder_node_id:
                print(f"WARNING: Node {self.node_id} is not the NC Coder. Cannot process NC coding.")
                return

            original_commands_map = {cmd["global_id"]: cmd for cmd in original_nc_message_commands}

            # Lógica de verificação do buffer para saber se é hora de XORar:
            # Precisa ter recebido as mensagens precursoras de TODOS os NC Senders relevantes
            # para esta rodada de NC.
            
            # Aqui, original_nc_message_commands contém os comandos (origem, destino_final, data, global_id)
            # que foram classificados como NC-beneficial e enviados para o coder.
            # O coder deve XORar todas elas assim que todas chegam.
            
            # Conta quantos precursores *realmente elegíveis para esta rodada* o coder está esperando
            num_expected_precursors_in_this_cycle = len(original_nc_message_commands)
            
            # Verifica se o buffer tem mensagens para todos os global_ids que foram enviados como precursores
            all_expected_precursors_received = True
            if num_expected_precursors_in_this_cycle == 0: # Não há mensagens para codificar
                all_expected_precursors_received = False
            else:
                for original_cmd in original_nc_message_commands:
                    if original_cmd["global_id"] not in self.nc_buffer:
                        all_expected_precursors_received = False
                        break

            if all_expected_precursors_received and len(self.nc_buffer) >= 2: # Mínimo 2 mensagens para XOR
                print(f"  Node {self.node_id} (Coder) has all expected NC precursor messages! Performing XOR.")
                messages_to_xor_data = []
                original_global_ids_for_nc = []
                nc_intended_destinations = [] # Coleta os destinos finais de TODAS as mensagens XORadas

                for global_id in sorted(self.nc_buffer.keys()):
                    precursor_msg = self.nc_buffer[global_id]
                    messages_to_xor_data.append(precursor_msg.data)
                    original_global_ids_for_nc.append(global_id)

                    # Pega o destino final original da mensagem precursora do objeto Message
                    original_dest_from_precursor = precursor_msg.nc_precursor_original_final_dest
                    if isinstance(original_dest_from_precursor, list):
                        nc_intended_destinations.extend(original_dest_from_precursor)
                    elif original_dest_from_precursor is not None:
                        nc_intended_destinations.append(original_dest_from_precursor)
                    else:
                        print(f"  WARNING: Coder precursor msg {precursor_msg.id} has no valid Original Final Dest. Skipping its destination.")
                
                if len(messages_to_xor_data) < 2:
                    print(f"  WARNING: Not enough messages in buffer for XOR. Need at least 2. Got: {len(messages_to_xor_data)}")
                    return

                def binary_string_xor(s1, s2):
                    max_len = max(len(s1), len(s2))
                    s1 = s1.zfill(max_len)
                    s2 = s2.zfill(max_len)
                    
                    result = ''.join(['1' if bit1 != bit2 else '0' for bit1, bit2 in zip(s1, s2)])
                    return result

                try:
                    xor_result_data = functools.reduce(binary_string_xor, messages_to_xor_data)
                    print(f"  XOR Result: {xor_result_data} from {messages_to_xor_data}")
                except Exception as e:
                    print(f"  ERROR: Failed to perform binary string XOR: {e}. Falling back to concatenation.")
                    xor_result_data = "XOR_CODED(" + " | ".join(messages_to_xor_data) + ")"

                coded_message_id = self.message_counter + 1 
                coded_message = Message(
                    id=coded_message_id,
                    source=self.node_id,
                    destination=self.network.broadcast_id,
                    data=xor_result_data,
                    timestamp=time.time(),
                    path=[self.node_id],
                    is_nc_coded=True,
                    original_message_ids=list(set(original_global_ids_for_nc)),
                    nc_intended_destinations=list(set(nc_intended_destinations)) # Garante destinos únicos
                )
                self.message_counter = coded_message_id

                print(f"  Node {self.node_id} (Coder) sending NC-coded message {coded_message.id} (Data: '{coded_message.data}') to destinations {coded_message.nc_intended_destinations}.")
                with simulation_events_lock:
                    simulation_events.append((time.time(), coded_message.id, self.node_id, coded_message.destination, "sending_nc_coded", coded_message.nc_intended_destinations))
                
                self.network.deliver_message(coded_message, coded_message.destination) 
                
                current_slot = self.schedule.get_current_slot()
                if current_slot:
                    self.transmitted_messages_by_channel[current_slot.channel] = \
                        self.transmitted_messages_by_channel.get(current_slot.channel, 0) + 1
                
                self.network.total_nc_coded_messages_sent += 1
                self.nc_buffer.clear()
            else:
                print(f"  Node {self.node_id} (Coder) waiting for more NC precursor messages. Buffer size: {len(self.nc_buffer)}. Expected in this cycle: {num_expected_precursors_in_this_cycle}")


    def receive_message(self, message: Message):
        with self.lock:
            print(f"\n--- Node {self.node_id} - Receiving Message ---")
            print(f"  Message ID (local): {message.id}")
            print(f"  Source: {message.source}")
            print(f"  Destination(s): {message.destination}")
            print(f"  Is NC Precursor: {message.is_nc_precursor}")
            print(f"  Is NC Coded: {message.is_nc_coded}")
            print(f"  Original Message Global IDs: {message.original_message_ids}")
            print(f"  NC Intended Dests: {message.nc_intended_destinations}")
            print(f"  NC Precursor Original Final Dest: {message.nc_precursor_original_final_dest}") # NOVO LOG

            if self.node_id == self.network.nc_coder_node_id and message.is_nc_precursor:
                print(f"  Node {self.node_id} (Coder) received NC precursor message {message.id} from {message.source} (Data: '{message.data}').")
                if message.original_message_ids and message.original_message_ids[0] is not None:
                    global_original_id = message.original_message_ids[0]
                    if global_original_id not in self.nc_buffer:
                        self.nc_buffer[global_original_id] = message
                        print(f"  NC Coder Buffer updated. Current buffer original Global IDs: {list(self.nc_buffer.keys())}")
                    else:
                        print(f"  NC Coder already has message with original Global ID {global_original_id}. Ignoring duplicate precursor {message.id}.")
                else:
                    print(f"  WARNING: NC Precursor message {message.id} from {message.source} has no valid Original Message Global ID. Ignoring.")
                return


            if message.is_nc_coded:
                print(f"  Node {self.node_id} received NC-coded message {message.id} (Data: '{message.data}').")
                if self.node_id in message.nc_intended_destinations:
                    print(f"  Node {self.node_id} is an intended destination. Simulating decoding and delivery.")
                    
                    decoded_original_data_for_this_node = "N/A - Original Data Not Directly Available"
                    decoded_original_id_for_this_node = None

                    # NOVO: Ao decodificar, o nó precisa saber qual era o data original que ele esperava
                    # para mostrar no log. O message.nc_intended_destinations lista os destinos finais
                    # que se beneficiam do NC. Usaremos o original_message_data_map para encontrar
                    # qual dado original corresponde a este nó.
                    
                    # original_message_ids da mensagem NC-coded contém os IDs globais de todas as mensagens XORadas.
                    # Precisamos encontrar QUAL dessas mensagens era destinada a este nó.
                    for original_global_id_in_nc in message.original_message_ids:
                        if original_global_id_in_nc in self.network.original_message_data_map:
                            original_info = self.network.original_message_data_map[original_global_id_in_nc]
                            original_dest = original_info["destination"]
                            
                            # Se este nó é o destino original (ou um dos destinos na lista)
                            if (isinstance(original_dest, int) and original_dest == self.node_id) or \
                               (isinstance(original_dest, list) and self.node_id in original_dest):
                                decoded_original_data_for_this_node = original_info["data"]
                                decoded_original_id_for_this_node = original_global_id_in_nc
                                break # Encontrou o dado original que este nó decodificou

                    if decoded_original_id_for_this_node is None:
                         print(f"  WARNING: Could not identify specific original message to decode for node {self.node_id} from NC message {message.id}.")


                    decoded_msg_for_this_node = Message(
                        id=message.id,
                        source=message.source,
                        destination=self.node_id, # Destino da mensagem decodificada é o próprio nó
                        data=f"DECODED '{decoded_original_data_for_this_node}' (from NC msg '{message.data}')",
                        timestamp=time.time(),
                        hop_count=message.hop_count,
                        path=message.path + [self.node_id],
                        is_nc_coded=False,
                        is_nc_precursor=False,
                        original_message_ids=[decoded_original_id_for_this_node] if decoded_original_id_for_this_node is not None else []
                    )
                    
                    self.received_messages.append(decoded_msg_for_this_node)
                    with simulation_events_lock:
                        animation_msg_id = decoded_msg_for_this_node.original_message_ids[0] if decoded_msg_for_this_node.original_message_ids else message.id
                        
                        last_hop_node = decoded_msg_for_this_node.path[-2] if len(decoded_msg_for_this_node.path) >= 2 else decoded_msg_for_this_node.source
                        simulation_events.append((time.time(), animation_msg_id, last_hop_node, self.node_id, "received_final_nc_decoded"))
                    print(f"  SUCCESS: Node {self.node_id} successfully decoded and received its part of NC message. Data: '{decoded_msg_for_this_node.data}'")
                    print(f"  Final Path (decoded): {decoded_msg_for_this_node.path}")
                else:
                    print(f"  Node {self.node_id} received NC-coded message {message.id}, but is not an intended final destination. Dropping.")
                    self.network.messages_dropped_not_intended_nc_dest += 1
                return


            # Lógica para encaminhamento ou recebimento final de mensagens regulares
            is_final_destination = False
            if isinstance(message.destination, list):
                if self.node_id in message.destination:
                    is_final_destination = True
            elif self.node_id == message.destination: # Unicast simples
                is_final_destination = True


            if is_final_destination:
                if self.node_id not in message.path:
                    message.path.append(self.node_id)
                self.received_messages.append(message)
                with simulation_events_lock:
                    animation_msg_id = message.id
                    last_hop_node = message.path[-2] if len(message.path) >= 2 else message.source
                    simulation_events.append((time.time(), animation_msg_id, last_hop_node, self.node_id, "received_final"))
                print(f"  SUCCESS: Node {self.node_id} received final message: '{message.data}'")
                print(f"  Final Path: {message.path}")
            else: # Este nó é um intermediário
                print(f"  Node {self.node_id} (intermediate) is forwarding message {message.id}.")
                message.hop_count += 1
                message.path.append(self.node_id)
                if message.hop_count < 5:
                    next_hop_target = None
                    if isinstance(message.destination, list):
                        for dest_id in message.destination:
                            if dest_id != self.node_id and dest_id not in message.path:
                                next_hop_target = dest_id
                                break
                    elif isinstance(message.destination, int):
                        next_hop_target = message.destination
                    
                    next_hop = None
                    if next_hop_target:
                        next_hop = self.get_next_hop(next_hop_target)
                    
                    if next_hop and next_hop != message.source:
                        self.network.total_forwarded_messages += 1
                        with simulation_events_lock:
                            simulation_events.append((time.time(), message.id, self.node_id, next_hop, "forwarding"))
                        print(f"  Forwarding to next_hop: {next_hop}. Hop count: {message.hop_count}")
                        print(f"  Current Path: {message.path}")
                        self.network.deliver_message(message, next_hop)
                    else:
                        print(f"  WARNING: Cannot forward message {message.id}. No suitable next_hop or message returning to source.")
                        self.network.messages_dropped_no_forward_path += 1
                else:
                    print(f"  WARNING: Message {message.id} dropped due to hop limit ({message.hop_count}).")
                    self.network.messages_dropped_hop_limit += 1
            print("-------------------------------------\n")

    def process_tsch_slot(self):
        current_slot = self.schedule.get_current_slot()
        if current_slot:
            if current_slot.tx_node == self.node_id:
                self.state = NodeState.TRANSMITTING
            elif current_slot.rx_node == self.node_id:
                self.state = NodeState.RECEIVING
            else:
                self.state = NodeState.IDLE

        self.schedule.advance_slot()


class TSCHNetwork:
    def __init__(self):
        self.nodes: Dict[int, TSCHNode] = {}
        self.running = False
        self.slot_duration = 0.1
        self.topology_data = {}
        self.simulation_commands = []
        self.original_message_commands: List[Dict] = []
        self.num_nodes_config = 0
        self.num_messages_config = 0
        self.available_channels = list(range(10))
        
        # --- Inicialização CORRETA das variáveis de Network Coding ---
        self.nc_coder_node_id: Optional[int] = None
        self.nc_senders_nodes_list: List[int] = []
        self.broadcast_id = -1
        self.total_nc_coded_messages_sent = 0
        self.messages_dropped_not_intended_nc_dest = 0 # A métrica que causou o erro

        self.original_message_data_map: Dict[int, Dict] = {} # Usado para dados originais em NC
        self.network_coding_enabled: Optional[int] = 0 # Será 1 se o cabeçalho NC for lido

        # --- Contadores de Métricas Comuns ---
        self.total_messages_initiated = 0
        self.total_forwarded_messages = 0
        self.messages_not_sent_no_route = 0
        self.messages_dropped_hop_limit = 0
        self.messages_dropped_no_forward_path = 0


    def add_node(self, node: TSCHNode):
        self.nodes[node.node_id] = node
        node.set_network(self)

    def parse_config_file(self, filename: str):
        """
        Lê e parseia o arquivo de configuração.
        Suporta múltiplos destinos na mesma linha para comandos de mensagem.
        Sempre espera e lê o cabeçalho NC nas duas primeiras linhas para o script NC.
        """
        try:
            with open(filename, 'r') as f:
                lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]

                if len(lines) < 3: # Para script NC, deve ter pelo menos 3 linhas (coder, senders, num_nodes_config)
                    print(f"ERROR: Configuration file '{filename}' for NC simulation must contain NC Coder and Senders on the first two lines, followed by topology info.")
                    sys.exit(1)
                
                # Para o script NC, SEMPRE esperamos o cabeçalho NC nas 2 primeiras linhas.
                self.nc_coder_node_id = int(lines[0])
                self.nc_senders_nodes_list = [int(x) for x in lines[1].split()]
                self.network_coding_enabled = 1 # Marcar que NC está sendo usado
                
                lines_to_read_topology_from = lines[2:] # Agora, o restante das linhas (a partir do num_nodes_config)
                start_parsing_from_line_index = 0 # O índice inicial dentro de lines_to_read_topology_from

                print(f"INFO: NC Header found. Coder: {self.nc_coder_node_id}, Senders: {self.nc_senders_nodes_list}")
                
                # O 'num_nodes_config' é sempre a PRIMEIRA linha do BLOCO DE TOPOLOGIA (após o cabeçalho NC).
                self.num_nodes_config = int(lines_to_read_topology_from[start_parsing_from_line_index])
                current_line_idx = start_parsing_from_line_index + 1 # Começa a ler a topologia em si
                self.topology_data = {}
                for i in range(self.num_nodes_config):
                    parts = [int(p) for p in lines_to_read_topology_from[current_line_idx + i].split()]
                    node_id = parts[0]
                    neighbors = parts[1:]
                    self.topology_data[node_id] = neighbors
                current_line_idx += self.num_nodes_config # current_line_idx agora é o índice do num_command_lines

                num_command_lines = int(lines_to_read_topology_from[current_line_idx]) 
                current_line_idx += 1
                
                self.simulation_commands = []
                self.original_message_commands = []
                self.original_message_data_map = {} # Reinicia o mapa, importante para NC
                
                global_message_id_counter = 0

                message_line_pattern = re.compile(r'(\d+)\s+((?:\d+\s+)*)\[(.*?)\]')

                for i in range(num_command_lines): 
                    line = lines_to_read_topology_from[current_line_idx + i]
                    
                    match = message_line_pattern.match(line.strip())
                    
                    if match:
                        source_str = match.group(1)
                        destinations_str = match.group(2).strip()
                        data = match.group(3)
                        
                        source = int(source_str)
                        destinations = [int(d) for d in destinations_str.split()] if destinations_str else []

                        if not destinations:
                            print(f"WARNING: Line '{line}' has no specified destinations. Ignoring this command.")
                            continue

                        global_message_id_counter += 1
                        
                        cmd = {
                            "type": "send",
                            "source": source,
                            "destination": destinations,
                            "data": data,
                            "global_id": global_message_id_counter 
                        }
                        self.simulation_commands.append(cmd)
                        self.original_message_commands.append(cmd)
                        self.original_message_data_map[global_message_id_counter] = {
                            'data': data,
                            'destination': destinations
                        }
                    elif line.strip().lower().startswith("wait"):
                        wait_time_match = re.match(r'wait\s+(\d+\.?\d*)', line.strip().lower())
                        if wait_time_match:
                            wait_time = float(wait_time_match.group(1))
                            self.simulation_commands.append({"type": "wait", "time": wait_time})
                        else:
                            print(f"WARNING: Could not parse wait command from line: '{line}'")
                    else:
                        print(f"WARNING: Could not parse command from line: '{line}' - Invalid format or unknown command type. This line will be ignored.")

                self.num_messages_config = global_message_id_counter 

                if not any(cmd["type"] == "wait" for cmd in self.simulation_commands):
                     self.simulation_commands.append({"type": "wait", "time": 2.0})

        except FileNotFoundError:
            print(f"ERROR: Configuration file '{filename}' not found.")
            print("Please ensure the file exists and the path is correct.")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: Error parsing configuration file '{filename}': {e}")
            sys.exit(1)

    def create_topology(self):
        if not self.topology_data:
            print("ERROR: Topology data not loaded. Please call parse_config_file first.")
            sys.exit(1)
            
        for node_id, neighbors in self.topology_data.items():
            node = TSCHNode(node_id, neighbors)
            self.add_node(node)

        if self.network_coding_enabled:
            if self.nc_coder_node_id and self.nc_coder_node_id not in self.nodes:
                print(f"ERROR: NC Coder Node {self.nc_coder_node_id} specified in config file does not exist in the topology.")
                sys.exit(1)
            for sender_id in self.nc_senders_nodes_list:
                if sender_id not in self.nodes:
                    print(f"ERROR: NC Sender Node {sender_id} specified in config file does not exist in the topology.")
                    sys.exit(1)

        self.setup_tsch_schedule()
        
    def setup_tsch_schedule(self):
        num_available_channels = len(self.available_channels)
        if num_available_channels == 0:
            print("WARNING: No channels available. All transmissions will use channel 0 (default fallback).")
            num_available_channels = 1
            self.available_channels = [0]


        for node_id, node in self.nodes.items():
            slot_id_counter = 0
            for neighbor in node.neighbors:
                assigned_channel_tx = self.available_channels[(slot_id_counter + node_id) % num_available_channels]
                assigned_channel_rx = self.available_channels[(slot_id_counter + neighbor) % num_available_channels]

                tx_slot = TSCHSlot(slot_id_counter, assigned_channel_tx, node_id, neighbor)
                node.schedule.add_slot(tx_slot)

                rx_slot = TSCHSlot(slot_id_counter + 1, assigned_channel_rx, neighbor, node_id)
                node.schedule.add_slot(rx_slot)

                slot_id_counter += 2

    def deliver_message(self, message: Message, target_node_or_list: Union[int, List[int]]):
        if message.is_nc_coded and target_node_or_list == self.broadcast_id:
            print(f"  Delivering NC Coded message {message.id} (broadcast from coder) to intended destinations: {message.nc_intended_destinations}")
            for final_dest_nc in message.nc_intended_destinations:
                if final_dest_nc in self.nodes:
                     threading.Thread(
                        target=self._delayed_delivery,
                        args=(message, final_dest_nc), # Entrega o mesmo objeto Message para cada destino final
                        daemon=True
                    ).start()
                else:
                    print(f"WARNING: NC Coded message intended for non-existent node {final_dest_nc}. Dropping.")
            return

        if isinstance(target_node_or_list, int): 
            if target_node_or_list in self.nodes:
                threading.Thread(
                    target=self._delayed_delivery,
                    args=(message, target_node_or_list),
                    daemon=True
                ).start()
            else:
                print(f"WARNING: Attempted to deliver message {message.id} to non-existent node {target_node_or_list}. Dropping.")
        elif isinstance(target_node_or_list, list): 
            print(f"  Delivering message {message.id} (direct multicast from source) to destinations: {target_node_or_list}")
            for final_dest in target_node_or_list:
                if final_dest in self.nodes:
                    threading.Thread(
                        target=self._delayed_delivery,
                        args=(message, final_dest),
                        daemon=True
                    ).start()
                else:
                    print(f"WARNING: Message {message.id} intended for non-existent node {final_dest}. Dropping.")
        else:
            print(f"WARNING: Invalid destination type passed to deliver_message: {type(target_node_or_list)}. Expected int or list. Dropping message {message.id}.")


    def _delayed_delivery(self, message: Message, destination: int):
        time.sleep(random.uniform(0.01, 0.05))
        self.nodes[destination].receive_message(message)

    def start_tsch_timer(self):
        def tsch_timer():
            while self.running:
                for node in self.nodes.values():
                    node.process_tsch_slot()
                time.sleep(self.slot_duration)

        self.running = True
        threading.Thread(target=tsch_timer, daemon=True).start()

    def stop(self):
        self.running = False

    def run_simulation(self, output_base_path: str, output_file_base_name: str, results_csv_file_obj):
        global simulation_events
        simulation_events = []

        print("=" * 60)
        print("        INICIANDO SIMULAÇÃO TSCH + UDP com NETWORK CODING")
        print(f"        Topologia da Rede: Carregada de '{output_file_base_name}.txt'")
        print(f"        Canais Disponíveis: {len(self.available_channels)}")
        print(f"        Nó Codificador NC: {self.nc_coder_node_id}")
        print(f"        Nós Emissores NC: {self.nc_senders_nodes_list}")
        print("        TODAS AS MENSAGENS ENVIADAS SIMULTANEAMENTE NO INÍCIO!")
        print("============================================================")

        self.start_tsch_timer()

        time.sleep(0.5)

        nc_precursor_commands_for_coder_this_run: List[Dict] = []
        
        print("\n--- Fase Principal: Enviando Mensagens Agrupadas por Nó ---")
        
        last_processed_source_id: Optional[int] = None
        
        commands_to_process = self.original_message_commands + [{"type": "sentinel", "source": -1, "destination": [], "data": ""}]
        
        current_batch_commands: List[Dict] = []
        current_batch_source_id: Optional[int] = None

        for command_template in commands_to_process:
            if command_template["type"] == "wait":
                if current_batch_commands:
                    source_node = self.nodes.get(current_batch_source_id)
                    if source_node:
                        print(f"  Node {current_batch_source_id} sending {len(current_batch_commands)} message(s) in batch:")
                        for cmd in current_batch_commands:
                            # NOVO: Lógica de divisão do envio no nó de origem
                            self._process_and_send_split_message(source_node, cmd, nc_precursor_commands_for_coder_this_run)
                        time.sleep(0.05)
                    current_batch_commands = []
                    current_batch_source_id = None
                
                print(f"\n--- Waiting for {command_template['time']} seconds (During Send Phase) ---")
                time.sleep(command_template['time'])
                last_processed_source_id = None
                continue

            source_id = command_template.get("source")

            if current_batch_source_id is not None and (source_id != current_batch_source_id or command_template["type"] == "sentinel"):
                if current_batch_commands:
                    source_node = self.nodes.get(current_batch_source_id)
                    if source_node:
                        if last_processed_source_id is not None and current_batch_source_id != last_processed_source_id:
                             time.sleep(0.1) 
                        
                        print(f"  Node {current_batch_source_id} sending {len(current_batch_commands)} message(s) in batch:")
                        for cmd in current_batch_commands:
                            # NOVO: Lógica de divisão do envio no nó de origem
                            self._process_and_send_split_message(source_node, cmd, nc_precursor_commands_for_coder_this_run)
                        time.sleep(0.05)
                    
                current_batch_commands = []
                current_batch_source_id = None
                
                if command_template["type"] == "sentinel":
                    break

            if command_template["type"] == "send":
                current_batch_commands.append(command_template)
                current_batch_source_id = source_id
                last_processed_source_id = source_id
        
        # --- Fim do Loop de Envio Principal ---

        # --- Atraso para permitir que todos os precursores cheguem ao codificador ---
        if nc_precursor_commands_for_coder_this_run:
            print("\n--- Waiting for precursors to reach coder (1.0s) ---")
            time.sleep(1.0) 

        # --- Fase de Codificação (apenas uma vez, após todos os precursores serem enviados) ---
        print("\n--- Fase de Codificação: Codificando e Enviando Mensagem XORada ---")
        coder_node = self.nodes.get(self.nc_coder_node_id)
        if coder_node and nc_precursor_commands_for_coder_this_run:
            coder_node.process_nc_coding(nc_precursor_commands_for_coder_this_run) 
        elif not coder_node:
            print("ERROR: NC Coder node not found or not initialized.")
        else:
            print("INFO: No NC precursor messages were collected for coding in this run. Skipping NC coding phase.")
        
        time.sleep(0.05)

        for command in self.simulation_commands:
            if command["type"] == "wait":
                print(f"\n--- Waiting for {command['time']} seconds (Final Processing) ---")
                time.sleep(command['time'])
        
        print("\n" + "=" * 60)
        print("        SIMULAÇÃO CONCLUÍDA")
        print("        Resumo de Mensagens Recebidas:")
        print("=" * 60)

        total_paths_found = 0
        for node_id, node in self.nodes.items():
            print(f"\nNó {node_id}:")
            if node.received_messages:
                num_received_by_this_node = 0
                for msg in node.received_messages:
                    if (isinstance(msg.destination, list) and node_id in msg.destination) or \
                       (isinstance(msg.destination, int) and node_id == msg.destination) or \
                       (msg.is_nc_coded and node_id in msg.nc_intended_destinations and "DECODED" in msg.data):
                        num_received_by_this_node += 1
                total_paths_found += num_received_by_this_node

                print(f"  Total de mensagens recebidas: {num_received_by_this_node}")
                for i, msg in enumerate(node.received_messages):
                    path_str = " -> ".join(map(str, msg.path))
                    display_dest = ""
                    if isinstance(msg.destination, list):
                        display_dest = f"[{','.join(map(str, msg.destination))}]"
                    elif isinstance(msg.destination, int):
                        display_dest = str(msg.destination)
                    
                    status_nc = ""
                    if msg.is_nc_coded:
                        status_nc = f"(NC Coded - Raw Packet, Orig Global IDs: {msg.original_message_ids}, Intended Dests: {msg.nc_intended_destinations})"
                    elif msg.is_nc_precursor:
                        status_nc = f"(NC Precursor - Raw Packet, Original Global ID: {msg.original_message_ids[0] if msg.original_message_ids else 'N/A'})"
                    elif msg.destination == node_id and "DECODED" in msg.data and msg.original_message_ids:
                        status_nc = f"(NC Decoded - Original Msg, Orig Global ID: {msg.original_message_ids[0]}, From Coder {msg.source})"
                    else:
                         status_nc = "(Regular)"

                    print(f"    - Mensagem {i+1} (ID local: {msg.id}, Origem: {msg.source}, Destino(s): {display_dest}, Hops: {msg.hop_count}, Caminho: {path_str}) {status_nc}: '{msg.data}'")
            else:
                print("  Nenhuma mensagem recebida.")

        print("\n--- Informações Adicionais da Simulação TSCH ---")
        slotframe_length = self.nodes[list(self.nodes.keys())[0]].schedule.slotframe_length if self.nodes else "N/A"
        print(f"Tamanho do Slotframe: {slotframe_length}")

        total_transmissions_by_channel = {}
        for node_id, node in self.nodes.items():
            for channel, count in node.transmitted_messages_by_channel.items():
                total_transmissions_by_channel[channel] = \
                    total_transmissions_by_channel.get(channel, 0) + count

        print("\nNúmero de Mensagens Transmitidas por Canal (Agregado):")
        total_transmissions = sum(total_transmissions_by_channel.values())
        num_channels_used = len(total_transmissions_by_channel)

        if total_transmissions_by_channel:
            for channel, count in sorted(total_transmissions_by_channel.items()):
                print(f"  Canal {channel}: {count} transmissões")
        else:
            print("  Nenhuma transmissão registrada por canal.")
        print(f"Total de transmissões em todos os canais: {total_transmissions}")
        print(f"Número total de canais utilizados: {num_channels_used}")

        print("\n--- Desempenho de Mensagens ---")
        print(f"Mensagens originadas (tentadas): {self.total_messages_initiated}")
        print(f"Mensagens entregues com sucesso: {total_paths_found}")
        print(f"Mensagens não enviadas (sem rota inicial): {self.messages_not_sent_no_route}")
        print(f"Mensagens descartadas por limite de hops: {self.messages_dropped_hop_limit}")
        print(f"Mensagens descartadas (sem caminho para frente): {self.messages_dropped_no_forward_path}")
        print(f"Mensagens descartadas (não é destino NC pretendido): {self.messages_dropped_not_intended_nc_dest}")
        print(f"Total de mensagens reencaminhadas (hops intermediários): {self.total_forwarded_messages}")
        print(f"Total de mensagens NC codificadas enviadas pelo codificador: {self.total_nc_coded_messages_sent}")

        print("--------------------------------------------------\n")

        self.stop()
        print("\n" + "=" * 60)

        if results_csv_file_obj:
            results_csv_writer = csv.writer(results_csv_file_obj)
            row_data = [
                output_file_base_name,
                self.num_nodes_config,
                self.num_messages_config,
                total_paths_found,
                slotframe_length,
                total_transmissions,
                num_channels_used,
                1, # Network_Coding setado como 1
                self.total_messages_initiated,
                self.messages_not_sent_no_route,
                self.messages_dropped_hop_limit,
                self.messages_dropped_no_forward_path,
                self.total_forwarded_messages
            ]
            results_csv_writer.writerow(row_data)
            print(f"Dados da simulação adicionados ao CSV: {row_data}")

        topology_image_path_final = os.path.join(output_base_path, f"{output_file_base_name}_nc_topology_final.png")
        self.plot_network_topology(save_path=topology_image_path_final)
        print(f"Imagem da topologia final salva como '{output_file_base_name}_nc_topology_final.png'.")

        gif_output_path = os.path.join(output_base_path, f"{output_file_base_name}_nc_traffic.gif")
        print("Gerando animação da rede. Isso pode levar um tempo...")
        self.animate_network_traffic(save_path=gif_output_path)
        print(f"Animação concluída! O arquivo '{output_file_base_name}_nc_traffic.gif' foi gerado.")

    def _process_and_send_split_message(self, source_node: 'TSCHNode', cmd: Dict, nc_precursor_commands_for_coder_this_run: List[Dict]):
        """
        Processa um comando de mensagem (cmd) e decide se o envia diretamente ou como precursor NC.
        Para mensagens multicast, ele pode disparar vários envios a partir de um único comando.
        """
        original_source_id = cmd["source"]
        original_global_id = cmd["global_id"]
        original_data = cmd["data"]
        original_destinations = cmd["destination"] # Esta é uma lista ou int

        # Destinos que podem ser alcançados diretamente
        direct_destinations = []
        # Destinos que precisam de hop intermediário e são candidatos a NC
        nc_eligible_destinations = []

        # Classifica os destinos
        if isinstance(original_destinations, list):
            for dest_id in original_destinations:
                if dest_id in source_node.neighbors:
                    direct_destinations.append(dest_id)
                else:
                    nc_eligible_destinations.append(dest_id)
        elif isinstance(original_destinations, int): # Caso de unicast
            if original_destinations in source_node.neighbors:
                direct_destinations.append(original_destinations)
            else:
                nc_eligible_destinations.append(original_destinations)

        # 1. Enviar para destinos diretos (se houver)
        if direct_destinations:
            print(f"    - Sending direct regular message from {original_source_id} to {direct_destinations} (Global ID: {original_global_id})...")
            source_node.send_message(
                direct_destinations, # Passa a lista de destinos diretos
                original_data,
                is_nc_precursor=False,
                original_message_global_id=original_global_id,
                nc_intended_destinations=direct_destinations # Mesmos que os destinos
            )

        # 2. Enviar para o codificador (se houver destinos NC elegíveis e o codificador for acessível)
        if nc_eligible_destinations and self.nc_coder_node_id:
            coder_node = self.nodes.get(self.nc_coder_node_id)
            if coder_node:
                # Verifica se o codificador é acessível pela fonte
                is_coder_accessible = False
                if self.nc_coder_node_id in source_node.neighbors or \
                   any(self.nc_coder_node_id in self.nodes[n].neighbors for n in source_node.neighbors):
                    is_coder_accessible = True

                if is_coder_accessible:
                    print(f"    - Sending NC precursor (Global ID: {original_global_id}) from {original_source_id} to Coder {self.nc_coder_node_id} (Original Final Dests: {nc_eligible_destinations})...")
                    source_node.send_message(
                        self.nc_coder_node_id, # Destino IMEDIATO é o codificador
                        original_data,
                        is_nc_precursor=True,
                        original_message_global_id=original_global_id,
                        nc_intended_destinations=nc_eligible_destinations, # Passa APENAS os destinos que vão via NC
                        nc_precursor_original_final_dest=original_destinations # NOVO: Passa o destino final original COMPLETO
                    )
                    nc_precursor_commands_for_coder_this_run.append(cmd) # Coleta para a fase de codificação
                else:
                    print(f"    - WARNING: Coder {self.nc_coder_node_id} not accessible from {original_source_id}. NC eligible messages for {nc_eligible_destinations} dropped.")
                    # Opcional: Contabilizar como dropped se o coder não é acessível
                    # self.messages_dropped_no_forward_path += 1 * len(nc_eligible_destinations)
            else:
                print(f"    - WARNING: NC Coder {self.nc_coder_node_id} not found. NC eligible messages for {nc_eligible_destinations} dropped.")
                # Opcional: Contabilizar como dropped
                # self.messages_dropped_no_forward_path += 1 * len(nc_eligible_destinations)


    def plot_network_topology(self, save_path: Optional[str] = None):
        G = nx.Graph()

        for node_id, neighbors in self.topology_data.items():
            G.add_node(node_id)
            for neighbor_id in neighbors:
                if neighbor_id in self.topology_data:
                    if not G.has_edge(node_id, neighbor_id):
                        G.add_edge(node_id, neighbor_id)

        plt.figure(figsize=(8, 6))
        pos = nx.spring_layout(G, seed=42)

        node_colors = ['lightblue'] * len(G.nodes)
        node_sizes = [1000] * len(G.nodes)
        
        if self.nc_coder_node_id in G.nodes:
            node_colors[list(G.nodes).index(self.nc_coder_node_id)] = 'orange'
            node_sizes[list(G.nodes).index(self.nc_coder_node_id)] = 1500

        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes)
        nx.draw_networkx_edges(G, pos, edge_color='gray', width=1.5)
        nx.draw_networkx_labels(G, pos, font_size=12, font_weight='bold')

        plt.title("Topologia da Rede TSCH Carregada com NC Coder", fontsize=16)
        plt.axis('off')

        if save_path:
            plt.savefig(save_path, bbox_inches='tight', dpi=300)
            plt.close()
        else:
            plt.show()

    def animate_network_traffic(self, save_path: Optional[str] = None):
        if not simulation_events:
            print("Nenhum evento de simulação para animar.")
            return

        G = nx.Graph()
        for node_id, neighbors in self.topology_data.items():
            G.add_node(node_id)
            for neighbor_id in neighbors:
                if neighbor_id in self.topology_data:
                    if not G.has_edge(node_id, neighbor_id):
                        G.add_edge(node_id, neighbor_id)

        pos = nx.spring_layout(G, seed=42)

        fig, ax = plt.subplots(figsize=(10, 8))

        node_colors_base = ['lightblue'] * len(G.nodes)
        node_sizes_base = [1000] * len(G.nodes)
        if self.nc_coder_node_id in G.nodes:
            node_colors_base[list(G.nodes).index(self.nc_coder_node_id)] = 'orange'
            node_sizes_base[list(G.nodes).index(self.nc_coder_node_id)] = 1500

        nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors_base, node_size=node_sizes_base)
        nx.draw_networkx_edges(G, pos, ax=ax, edge_color='gray', width=1.5)
        nx.draw_networkx_labels(G, pos, ax=ax, font_size=12, font_weight='bold')

        start_time = min(event[0] for event in simulation_events)
        normalized_events = sorted([(e[0] - start_time, e[1], e[2], e[3], e[4], e[5] if len(e) > 5 else None) for e in simulation_events])

        max_sim_time_covered = normalized_events[-1][0] if normalized_events else 0.1

        gif_speed_factor = 2.0

        total_animation_real_time = (max_sim_time_covered + 1.0) * gif_speed_factor

        fps_gif = 10

        total_frames = int(total_animation_real_time * fps_gif)

        arrow_visibility_duration_sim_time = 0.5

        def update(frame):
            ax.clear()

            node_colors_current = list(node_colors_base)
            node_sizes_current = list(node_sizes_base)

            nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors_current, node_size=node_sizes_current)
            nx.draw_networkx_edges(G, pos, ax=ax, edge_color='gray', width=1.5)
            nx.draw_networkx_labels(G, pos, ax=ax, font_size=12, font_weight='bold')

            current_sim_time = (frame / fps_gif) / gif_speed_factor

            active_events = []
            for event_time, msg_id, from_node, to_node_raw, event_type, optional_data in normalized_events:
                if current_sim_time >= event_time and (current_sim_time - event_time) < arrow_visibility_duration_sim_time:
                    active_events.append((msg_id, from_node, to_node_raw, event_type, optional_data))

            current_messages_info = []
            
            for anim_msg_id, from_node, to_node_raw, event_type, optional_data in active_events:
                if from_node in pos:
                    arrow_color = 'red'
                    
                    display_to_node_text = ""
                    if isinstance(optional_data, list): # Se a mensagem é um multicast (optional_data = lista de destinos finais)
                        display_to_node_text = f"[{','.join(map(str, optional_data))}]"
                    else: # Se é unicast
                        display_to_node_text = str(to_node_raw)

                    info_text = f"M{anim_msg_id}: {from_node}->{display_to_node_text}"
                    
                    offset_magnitude = (anim_msg_id % 3 - 1) * 0.05 

                    if event_type == "sending_nc_coded":
                        arrow_color = 'purple'
                        info_text = f"NC Coded M{anim_msg_id}: Coder {from_node} Broadcasting"
                        
                        if optional_data and isinstance(optional_data, list):
                            for intended_dest in optional_data:
                                if intended_dest in pos:
                                    x1_b, y1_b = pos[from_node]
                                    x2_b, y2_b = pos[intended_dest]
                                    
                                    dx = x2_b - x1_b
                                    dy = y2_b - y1_b
                                    len_vec = (dx**2 + dy**2)**0.5
                                    
                                    offset_magnitude_dest = (intended_dest % 3 - 1) * 0.05 
                                    
                                    x1_off_b = x1_b - (dy / len_vec) * offset_magnitude_dest if len_vec > 0 else x1_b
                                    y1_off_b = y1_b + (dx / len_vec) * offset_magnitude_dest if len_vec > 0 else y1_b
                                    x2_off_b = x2_b - (dy / len_vec) * offset_magnitude_dest if len_vec > 0 else x2_b
                                    y2_off_b = y2_b + (dx / len_vec) * offset_magnitude_dest if len_vec > 0 else y2_b

                                    ax.annotate(
                                        '', xy=(x2_off_b, y2_off_b), xytext=(x1_off_b, y1_off_b),
                                        arrowprops=dict(facecolor=arrow_color, edgecolor=arrow_color, shrink=0.05, width=2, headwidth=10, headlength=10),
                                        xycoords='data', textcoords='data'
                                    )
                                    current_messages_info.append(f"NC Coded M{anim_msg_id}: {from_node}->{intended_dest}")
                            continue
                                
                    elif event_type == "sending_nc_precursor":
                        arrow_color = 'green'
                        if optional_data is not None:
                            info_text = f"NC Precursor M{optional_data}: {from_node}->{display_to_node_text}"
                    elif event_type == "received_final_nc_decoded":
                        info_text = f"Decoded M{optional_data if optional_data is not None else anim_msg_id}: by {to_node_raw}"
                        try:
                            dest_idx = list(G.nodes).index(to_node_raw)
                            node_colors_current[dest_idx] = 'gold'
                        except ValueError:
                            pass
                        continue
                        
                    
                    if isinstance(to_node_raw, int) and to_node_raw in pos:
                        x1, y1 = pos[from_node]
                        x2, y2 = pos[to_node_raw]

                        dx = x2 - x1
                        dy = y2 - y1
                        len_vec = (dx**2 + dy**2)**0.5

                        x1_off = x1 - (dy / len_vec) * offset_magnitude if len_vec > 0 else x1
                        y1_off = y1 + (dx / len_vec) * offset_magnitude if len_vec > 0 else y1
                        x2_off = x2 - (dy / len_vec) * offset_magnitude if len_vec > 0 else x2
                        y2_off = y2 + (dx / len_vec) * offset_magnitude if len_vec > 0 else y2
                        
                        ax.annotate(
                            '', xy=(x2_off, y2_off), xytext=(x1_off, y1_off),
                            arrowprops=dict(facecolor=arrow_color, edgecolor=arrow_color, shrink=0.05, width=2, headwidth=10, headlength=10),
                            xycoords='data', textcoords='data'
                        )
                    current_messages_info.append(info_text)

            ax.set_title(f"Animação da Rede TSCH com NC\nTempo: {current_sim_time:.2f}s\n" +
                         "Tráfego Ativo: " + ", ".join(current_messages_info[:3]) + ("..." if len(current_messages_info) > 3 else ""),
                         fontsize=14)
            return ax,


        ani = FuncAnimation(fig, update, frames=total_frames, interval=(1000/fps_gif), blit=False, repeat=False)

        plt.close(fig)

        if save_path:
            try:
                print(f"Salvando animação como GIF... (isso pode demorar)")
                writer_gif = plt.matplotlib.animation.PillowWriter(fps=fps_gif)
                ani.save(save_path, writer=writer_gif)
            except Exception as e:
                print(f"Erro ao salvar animação GIF para '{save_path}': {e}")
                print("Verifique se a biblioteca 'Pillow' está instalada (`pip install Pillow`).")
        else:
            print("Caminho para salvar o GIF não fornecido. Animação não salva.")


def main():
    if len(sys.argv) < 2:
        sys.stdout.write("Uso: python3 tsch_udp_nc_simulation.py <caminho_para_arquivo_de_entrada>\n")
        sys.exit(1)

    input_filepath = sys.argv[1]

    log_dir = "logs" # Pasta raiz para logs
    project_root = os.path.dirname(os.path.abspath(sys.argv[0]))
    output_base_path = os.path.join(project_root, log_dir)

    os.makedirs(output_base_path, exist_ok=True)

    input_filename_without_ext = os.path.splitext(os.path.basename(input_filepath))[0]

    log_filename = f"{input_filename_without_ext}_nc_log.txt" # Log com _nc no nome
    log_filepath = os.path.join(output_base_path, log_filename)

    results_csv_filepath = os.path.join(output_base_path, "simulation_results.csv") # CSV normal

    original_stdout = sys.stdout

    results_csv_file = None

    try:
        file_exists = os.path.exists(results_csv_filepath)
        results_csv_file = open(results_csv_filepath, 'a', newline='')

        if not file_exists:
            csv.writer(results_csv_file).writerow([
                "Nome_Config_Arquivo",
                "Numero_de_Nos_Config",
                "Numero_de_Mensagens_Config",
                "Numero_de_Caminhos_Completos",
                "Tamanho_do_Slotframe",
                "Numero_de_Transmissoes_Totais",
                "Numero_de_Canais_Usados",
                "Network_Coding", # Campo para 0 ou 1
                "Mensagens_Iniciadas",
                "Mensagens_Nao_Enviadas_Sem_Rota",
                "Mensagens_Descartadas_Hop_Limit",
                "Mensagens_Descartadas_Sem_Prox_Caminho",
                "Total_Retransmissoes_Logicas"
            ])

        log_file = open(log_filepath, 'w')
        sys.stdout = log_file

        print(f"Data/Hora da Simulação NC: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n")

        network = TSCHNetwork()
        network.parse_config_file(input_filepath)
        network.create_topology()
        network.run_simulation(output_base_path, input_filename_without_ext, results_csv_file)

    except Exception as e:
        original_stdout.write(f"\nFATAL ERROR during simulation: {e}\n") # Adapta a mensagem de erro
        import traceback
        original_stdout.write(traceback.format_exc())
        sys.exit(1)
    finally:
        sys.stdout = original_stdout
        if 'log_file' in locals() and not log_file.closed:
            log_file.close()
        if results_csv_file and not results_csv_file.closed:
            results_csv_file.close()

        print(f"Registro de log NC concluído! O arquivo '{log_filename}' foi gerado.")
        print(f"Dados da simulação adicionados a 'simulation_results.csv'.")
        print(f"Verifique o diretório '{output_base_path}'.")


if __name__ == "__main__":
    main()