import time
import threading
import random
from collections import deque
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Union
import re
import sys
import os
import csv
import functools

import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

simulation_events = []
simulation_events_lock = threading.Lock()


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
    nc_precursor_original_final_dest: Optional[Union[int, List[int]]] = None
    global_id: Optional[int] = None 


class TSCHSlot:
    def __init__(self, slot_id: int, channel: int, tx_node: int, rx_node: int):
        self.slot_id = slot_id
        self.channel = channel
        self.tx_node = tx_node
        self.rx_node = rx_node


class TSCHSchedule:
    def __init__(self, slotframe_length: int = 2):
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
        self.nc_buffer: Dict[int, Message] = {}


    def set_network(self, network):
        self.network = network

    def add_neighbor(self, neighbor_id: int):
        self.neighbors.add(neighbor_id)

    def send_message(self, destination: Union[int, List[int]], data: str, global_id: int):
        with self.lock:
            self.message_counter += 1

            message = Message(
                id=self.message_counter, 
                source=self.node_id,
                destination=destination, 
                data=data,
                timestamp=time.time(),
                path=[self.node_id], 
                hop_count=0, 
                global_id=global_id
            )

            self.network.total_messages_initiated += 1

            print(f"\n--- Node {self.node_id} - Sending Message ---")
            print(f"  Message ID (local): {message.id}")
            print(f"  Global Message ID: {message.global_id}")
            print(f"  Source: {self.node_id}")
            print(f"  Original Final Destination(s): {message.destination}") 
            print(f"  Data: '{message.data}'")
            print(f"  Current Path (after source added): {message.path}")
            print(f"  Current Hop Count: {message.hop_count}")


            next_physical_hop = None
            if isinstance(destination, list):
                for dest_id in destination:
                    if dest_id in self.neighbors:
                        next_physical_hop = dest_id
                        break
                if not next_physical_hop:
                    for dest_id in destination:
                        calculated_next_hop = self.get_next_hop(dest_id)
                        if calculated_next_hop:
                            next_physical_hop = calculated_next_hop
                            break 
            elif isinstance(destination, int):
                next_physical_hop = self.get_next_hop(destination)


            if next_physical_hop:
                print(f"  Transmitting to next physical hop: {next_physical_hop}.")
                with simulation_events_lock:
                    simulation_events.append((time.time(), message.global_id, self.node_id, next_physical_hop, "sending_regular"))

                self.network.deliver_message(message, next_physical_hop)

                current_slot = self.schedule.get_current_slot()
                if current_slot:
                    self.transmitted_messages_by_channel[current_slot.channel] = \
                        self.transmitted_messages_by_channel.get(current_slot.channel, 0) + 1
            else:
                print(f"  ERROR: No route to any destination {message.destination} from node {self.node_id}.")
                self.network.messages_not_sent_no_route += 1
            print("-----------------------------------\n")

    def _send_retransmitted_message(self, message_to_retransmit: Message, next_physical_hop: int):
        with simulation_events_lock:
            simulation_events.append((time.time(), message_to_retransmit.global_id, self.node_id, next_physical_hop, "forwarding"))
        
        self.network.deliver_message(message_to_retransmit, next_physical_hop)

        current_slot = self.schedule.get_current_slot()
        if current_slot:
            self.transmitted_messages_by_channel[current_slot.channel] = \
                self.transmitted_messages_by_channel.get(current_slot.channel, 0) + 1

    def get_next_hop(self, destination: int) -> Optional[int]:
        if destination in self.neighbors:
            return destination

        for neighbor in self.neighbors:
            if self.network and neighbor in self.network.nodes:
                neighbor_node = self.network.nodes[neighbor]
                if destination in neighbor_node.neighbors:
                    return neighbor

        return list(self.neighbors)[0] if self.neighbors else None


    def receive_message(self, message: Message):
        with self.lock:
            print(f"\n--- Node {self.node_id} - Receiving Message ---")
            print(f"  Message ID (local source): {message.id}")
            print(f"  Global Message ID: {message.global_id}")
            print(f"  Source: {message.source}")
            print(f"  Original Final Destination(s): {message.destination}")
            print(f"  Data: '{message.data}'")
            print(f"  Current Path (before processing): {message.path}")
            print(f"  Current Hop Count (before processing): {message.hop_count}")

            if self.node_id not in message.path: 
                message.path.append(self.node_id)
                message.hop_count += 1 

            is_final_destination_for_this_node = False
            if isinstance(message.destination, list):
                if self.node_id in message.destination:
                    is_final_destination_for_this_node = True
            elif self.node_id == message.destination: 
                is_final_destination_for_this_node = True

            if is_final_destination_for_this_node:
                self.received_messages.append(message) 
                with simulation_events_lock:
                    last_hop_node = message.path[-2] if len(message.path) >= 2 else message.source
                    simulation_events.append((time.time(), message.global_id, last_hop_node, self.node_id, "received_final"))
                print(f"  SUCCESS: Node {self.node_id} received final message: '{message.data}'")
                print(f"  Final Path: {message.path}")
                print(f"  Final Hop Count: {message.hop_count}")
            
            needs_forwarding = False
            forwarding_targets = [] 

            if isinstance(message.destination, list):
                for original_final_dest_id in message.destination:
                    if original_final_dest_id != self.node_id and original_final_dest_id not in message.path:
                        needs_forwarding = True
                        forwarding_targets.append(original_final_dest_id)
            elif not is_final_destination_for_this_node: 
                needs_forwarding = True
                forwarding_targets.append(message.destination) 

            if needs_forwarding and message.hop_count < 5: 
                print(f"  Node {self.node_id} (intermediate) is forwarding message {message.id} (Global ID: {message.global_id}).")
                
                for target_final_dest in forwarding_targets:
                    next_hop_for_this_target = self.get_next_hop(target_final_dest)

                    is_valid_forward = False
                    if next_hop_for_this_target:
                        if len(message.path) < 2: 
                            is_valid_forward = True
                        elif next_hop_for_this_target != message.path[-2]: 
                            is_valid_forward = True
                        if next_hop_for_this_target in message.path:
                             is_valid_forward = False 
                             print(f"  WARNING: Skipping forward to {next_hop_for_this_target} as it's already in the path {message.path}. Avoiding cycle.")

                    if is_valid_forward:
                        self.network.total_forwarded_messages += 1
                        
                        cloned_message_for_transmission = Message(
                            id=message.id, 
                            source=message.source,
                            destination=message.destination, 
                            data=message.data,
                            timestamp=time.time(), 
                            hop_count=message.hop_count, 
                            path=list(message.path), 
                            global_id=message.global_id
                        )

                        print(f"    - Initiating retransmission from {self.node_id} to {next_hop_for_this_target} for Global ID: {cloned_message_for_transmission.global_id} towards final dest {target_final_dest}. Current Path: {cloned_message_for_transmission.path}")
                        
                        self._send_retransmitted_message(cloned_message_for_transmission, next_hop_for_this_target)
                        
                    else:
                        print(f"  WARNING: Cannot forward message {message.id} (Global ID: {message.global_id}) towards {target_final_dest}. No suitable next_hop found or message returning to previous node/cycle detected.")
                        self.network.messages_dropped_no_forward_path += 1
            elif needs_forwarding and message.hop_count >= 5:
                 print(f"  WARNING: Message {message.id} (Global ID: {message.global_id}) dropped due to hop limit ({message.hop_count}).")
                 self.network.messages_dropped_hop_limit += 1
            
            elif not is_final_destination_for_this_node and not needs_forwarding:
                print(f"  Node {self.node_id} received message {message.id} (Global ID: {message.global_id}) but is not a final destination and no further forwarding path found/needed.")
            
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
        self.num_nodes_config = 0
        self.num_messages_config = 0
        self.available_channels = list(range(10))
        self.network_coding_enabled: Optional[int] = 0
        self.nc_coder_node_id: Optional[int] = None
        self.nc_senders_nodes_list: List[int] = []
        self.total_nc_coded_messages_sent = 0
        self.messages_dropped_not_intended_nc_dest = 0 

        self.total_messages_initiated = 0
        self.total_forwarded_messages = 0
        self.messages_not_sent_no_route = 0
        self.messages_dropped_hop_limit = 0
        self.messages_dropped_no_forward_path = 0

        self.original_message_data_map: Dict[int, Dict] = {} 

    def add_node(self, node: TSCHNode):
        self.nodes[node.node_id] = node
        node.set_network(self)

    def parse_config_file(self, filename: str):
        try:
            with open(filename, 'r') as f:
                lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]

                if len(lines) < 3: 
                    print(f"ERROR: Configuration file '{filename}' has insufficient lines. Expected at least 3 (2 skipped + node config).")
                    sys.exit(1)

                lines = lines[2:]

                self.num_nodes_config = int(lines[0])
                current_line_idx = 1
                self.topology_data = {}
                for i in range(self.num_nodes_config):
                    parts = [int(p) for p in lines[current_line_idx + i].split()]
                    node_id = parts[0]
                    neighbors = parts[1:]
                    self.topology_data[node_id] = neighbors
                current_line_idx += self.num_nodes_config

                num_command_lines = int(lines[current_line_idx]) 
                current_line_idx += 1

                self.simulation_commands = []
                self.original_message_data_map = {} 

                global_message_id_counter = 0

                message_line_pattern = re.compile(r'(\d+)\s+((?:\d+\s+)*)\[(.*?)\]')

                for i in range(num_command_lines):
                    line = lines[current_line_idx + i]

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

    def deliver_message(self, message: Message, target_node_id: int): 
        if target_node_id in self.nodes:
            threading.Thread(
                target=self._delayed_delivery,
                args=(message, target_node_id), 
                daemon=True
            ).start()
        else:
            print(f"WARNING: Attempted to deliver message {message.id} (Global ID: {message.global_id}) to non-existent node {target_node_id}. Dropping.")


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
        print("        INICIANDO SIMULAÇÃO TSCH + UDP")
        print(f"        Topologia da Rede: Carregada de '{output_file_base_name}.txt'")
        print(f"        Canais Disponíveis: {len(self.available_channels)}")
        print("        TODAS AS MENSAGENS ENVIADAS SIMULTANEAMENTE NO INÍCIO!")
        print("=" * 60)

        self.start_tsch_timer()

        time.sleep(0.5)

        for command in self.simulation_commands:
            if command["type"] == "send":
                source_node = self.nodes.get(command["source"])
                if source_node:
                    source_node.send_message(
                        command["destination"], 
                        command["data"],
                        global_id=command["global_id"] 
                    )
                else:
                    print(f"WARNING: Source node {command['source']} not found for sending message (Global ID: {command['global_id']}).")
            elif command["type"] == "wait":
                print(f"\n--- Waiting for {command['time']} seconds ---")
                time.sleep(command["time"])

        print("\n" + "=" * 60)
        print("        SIMULAÇÃO CONCLUÍDA")
        print("        Resumo de Mensagens Recebidas:")
        print("=" * 60)

        total_paths_found = 0
        received_global_ids_at_final_destinations = set() 

        for node_id, node in self.nodes.items():
            print(f"\nNó {node_id}:")
            if node.received_messages:
                num_received_by_this_node = 0
                for msg in node.received_messages:
                    if node_id == msg.destination:
                        num_received_by_this_node += 1
                        received_global_ids_at_final_destinations.add(msg.global_id) 

                print(f"  Total de mensagens recebidas (como destino final): {num_received_by_this_node}")
                for i, msg in enumerate(node.received_messages):
                    path_str = " -> ".join(map(str, msg.path))
                    display_dest = ""
                    display_dest = str(msg.destination)

                    print(f"    - Mensagem {i+1} (ID local: {msg.id}, Global ID: {msg.global_id}, Origem: {msg.source}, Destino Final: {display_dest}, Hops: {msg.hop_count}, Caminho: {path_str}): '{msg.data}'")
            else:
                print("  Nenhuma mensagem recebida.")

        total_paths_found = len(received_global_ids_at_final_destinations)

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
        print(f"Mensagens entregues com sucesso (únicas por Global ID): {total_paths_found}")
        print(f"Mensagens não enviadas (sem rota inicial): {self.messages_not_sent_no_route}")
        print(f"Mensagens descartadas por limite de hops: {self.messages_dropped_hop_limit}")
        print(f"Mensagens descartadas (sem caminho para frente): {self.messages_dropped_no_forward_path}")
        print(f"Total de mensagens reencaminhadas (hops intermediários): {self.total_forwarded_messages}")
        print(f"Mensagens descartadas (não é destino NC pretendido): {self.messages_dropped_not_intended_nc_dest}")
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
                self.network_coding_enabled,
                self.total_messages_initiated,
                self.messages_not_sent_no_route,
                self.messages_dropped_hop_limit,
                self.messages_dropped_no_forward_path,
                self.total_forwarded_messages
            ]
            results_csv_writer.writerow(row_data)
            print(f"Dados da simulação adicionados ao CSV: {row_data}")

        topology_image_path_final = os.path.join(output_base_path, f"{output_file_base_name}_topology_final.png")
        self.plot_network_topology(save_path=topology_image_path_final)
        print(f"Imagem da topologia final salva como '{output_file_base_name}_topology_final.png'.")

        gif_output_path = os.path.join(output_base_path, f"{output_file_base_name}_traffic.gif")
        print("Gerando animação da rede. Isso pode levar um tempo...")
        self.animate_network_traffic(save_path=gif_output_path)
        print(f"Animação concluída! O arquivo '{gif_output_path}' foi gerado.")

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

        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes)
        nx.draw_networkx_edges(G, pos, edge_color='gray', width=1.5)
        nx.draw_networkx_labels(G, pos, font_size=12, font_weight='bold')

        plt.title("Topologia da Rede TSCH Carregada", fontsize=16)
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
                    display_to_node_text = str(to_node_raw)

                    info_text = f"M{anim_msg_id}: {from_node}->{display_to_node_text}"

                    offset_magnitude = (anim_msg_id % 3 - 1) * 0.05

                    if event_type == "received_final":
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
                    else:
                        print(f"WARNING: Animation skipped for event type {event_type} with invalid to_node_raw: {to_node_raw}")


            ax.set_title(f"Animação da Rede TSCH\nTempo: {current_sim_time:.2f}s\n" +
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
        sys.stdout.write("Uso: python3 tsch_udp_simulation.py <caminho_para_arquivo_de_entrada>\n")
        sys.exit(1)

    input_filepath = sys.argv[1]

    log_dir = "logs"
    project_root = os.path.dirname(os.path.abspath(sys.argv[0]))
    output_base_path = os.path.join(project_root, log_dir)

    os.makedirs(output_base_path, exist_ok=True)

    input_filename_without_ext = os.path.splitext(os.path.basename(input_filepath))[0]

    log_filename = f"{input_filename_without_ext}_log.txt"
    log_filepath = os.path.join(output_base_path, log_filename)

    results_csv_filepath = os.path.join(output_base_path, "simulation_results.csv")

    original_stdout = sys.stdout

    results_csv_file = None

    try:
        file_exists = os.path.exists(results_csv_filepath)
        results_csv_file = open(results_csv_filepath, 'a', newline='')

        if not file_exists:
            csv.writer(results_csv_file).writerow([
                "Nome_Config_Arquivo",
                "N_Nos_Config",
                "N_Msg_Config",
                "N_Caminhos_Completos",
                "Tamanho_do_Slotframe",
                "N_Transmissoes_Totais",
                "N_Canais_Usados",
                "Network_Coding",
                "Msg_Iniciadas",
                "Msg_Nao_Enviadas_Sem_Rota",
                "Msg_Descartadas_Hop_Limit",
                "Msg_Descartadas_Sem_Prox_Caminho",
                "Total_Retransmissoes_Logicas"
            ])

        log_file = open(log_filepath, 'w')
        sys.stdout = log_file

        print(f"Data/Hora da Simulação: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n")

        network = TSCHNetwork()
        network.parse_config_file(input_filepath)
        network.create_topology()
        network.run_simulation(output_base_path, input_filename_without_ext, results_csv_file)

    except Exception as e:
        original_stdout.write(f"\nFATAL ERROR during simulation: {e}\n")
        import traceback
        original_stdout.write(traceback.format_exc())
        sys.exit(1)
    finally:
        sys.stdout = original_stdout
        if 'log_file' in locals() and not log_file.closed:
            log_file.close()
        if results_csv_file and not results_csv_file.closed:
            results_csv_file.close()

        print(f"Registro de log concluído! O arquivo '{log_filename}' foi gerado.")
        print(f"Dados da simulação adicionados a 'simulation_results.csv'.")
        print(f"Verifique o diretório '{output_base_path}'.")


if __name__ == "__main__":
    main()