import time
import threading
import random
from collections import deque
from enum import Enum
from dataclasses import dataclass, field
import dataclasses
from typing import Dict, List, Set, Optional
import re 
import sys
import os 
import csv 

# --- Adicionando bibliotecas para visualização e animação ---
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
# -----------------------------------------------------------

# Lista global para armazenar os eventos da simulação para a animação
# Cada evento será uma tupla: (timestamp, msg_id, from_node, to_node, event_type)
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
    destination: int
    data: str
    timestamp: float
    hop_count: int = 0
    path: List[int] = field(default_factory=list) 


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
        self.current_slot = (self.current_slot + 1) % self.slotframe_length


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
        
    def set_network(self, network):
        self.network = network
        
    def add_neighbor(self, neighbor_id: int):
        self.neighbors.add(neighbor_id)
        
    def send_message(self, destination: int, data: str, direct: bool = False):
        with self.lock:
            self.message_counter += 1
            message = Message(
                id=self.message_counter,
                source=self.node_id,
                destination=destination,
                data=data,
                timestamp=time.time(),
                path=[self.node_id] 
            )
            
            print(f"\n--- Node {self.node_id} - Sending Message ---")
            print(f"  Message ID: {message.id}")
            print(f"  Source: {self.node_id}")
            print(f"  Destination: {destination}")
            print(f"  Data: '{message.data}'")
            print(f"  Initial Path: {message.path}") 
            
            is_direct_possible = destination in self.neighbors 

            if is_direct_possible:
                print(f"  Direct send to neighbor {destination}.")
                with simulation_events_lock:
                    simulation_events.append((time.time(), message.id, self.node_id, destination, "sending_direct"))
                self.network.deliver_message(message, destination)
                current_slot = self.schedule.get_current_slot()
                if current_slot: 
                    self.transmitted_messages_by_channel[current_slot.channel] = \
                        self.transmitted_messages_by_channel.get(current_slot.channel, 0) + 1
            else:
                next_hop = self.get_next_hop(destination) 
                if next_hop:
                    print(f"  Forwarding via next hop: {next_hop}.")
                    with simulation_events_lock:
                        simulation_events.append((time.time(), message.id, self.node_id, next_hop, "sending_forward"))
                    self.network.deliver_message(message, next_hop)
                    current_slot = self.schedule.get_current_slot()
                    if current_slot: 
                        self.transmitted_messages_by_channel[current_slot.channel] = \
                            self.transmitted_messages_by_channel.get(current_slot.channel, 0) + 1
                else:
                    print(f"  ERROR: No route to destination {destination} from node {self.node_id}.")
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
    
    def receive_message(self, message: Message):
        with self.lock:
            print(f"\n--- Node {self.node_id} - Receiving Message ---")
            print(f"  Message ID: {message.id}")
            print(f"  Source: {message.source}")
            print(f"  Destination: {message.destination}")
            
            if message.destination == self.node_id:
                message.path.append(self.node_id) 
                self.received_messages.append(message)
                with simulation_events_lock:
                    last_hop_node = message.path[-2] if len(message.path) >= 2 else message.source
                    simulation_events.append((time.time(), message.id, last_hop_node, self.node_id, "received_final"))
                print(f"  SUCCESS: Node {self.node_id} received final message: '{message.data}'")
                print(f"  Final Path: {message.path}") 
            else:
                print(f"  Node {self.node_id} (intermediate) is forwarding message {message.id}.")
                message.hop_count += 1
                message.path.append(self.node_id) 
                if message.hop_count < 5: 
                    next_hop = self.get_next_hop(message.destination) 
                    if next_hop and next_hop != message.source:
                        with simulation_events_lock:
                            simulation_events.append((time.time(), message.id, self.node_id, next_hop, "forwarding"))
                        print(f"  Forwarding to next_hop: {next_hop}. Hop count: {message.hop_count}")
                        print(f"  Current Path: {message.path}") 
                        self.network.deliver_message(message, next_hop)
                    else:
                        print(f"  WARNING: Cannot forward message {message.id}. No suitable next_hop or message returning to source.")
                else:
                    print(f"  WARNING: Message {message.id} dropped due to hop limit ({message.hop_count}).")
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
        self.network_coding_enabled = 0 
        
    def add_node(self, node: TSCHNode):
        self.nodes[node.node_id] = node
        node.set_network(self)
        
    def parse_config_file(self, filename: str):
        """
        Lê e parseia o arquivo de configuração simplificado para topologia e comandos de simulação.
        """
        try:
            with open(filename, 'r') as f:
                lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                
                self.num_nodes_config = int(lines[0])
                current_line_idx = 1
                self.topology_data = {}
                for i in range(self.num_nodes_config):
                    parts = [int(p) for p in lines[current_line_idx + i].split()]
                    node_id = parts[0]
                    neighbors = parts[1:]
                    self.topology_data[node_id] = neighbors
                current_line_idx += self.num_nodes_config

                self.num_messages_config = int(lines[current_line_idx])
                current_line_idx += 1
                self.simulation_commands = []
                for i in range(self.num_messages_config):
                    line = lines[current_line_idx + i]
                    match = re.match(r'(\d+)\s+(\d+)\s+\[(.*?)\]', line)
                    if match:
                        source = int(match.group(1))
                        destination = int(match.group(2))
                        data = match.group(3)
                        self.simulation_commands.append({"type": "send", "source": source, "destination": destination, "data": data})
                    else:
                        print(f"WARNING: Could not parse simulation command line: '{line}'")
                        
                self.simulation_commands.append({"type": "wait", "time": 2.0})

        except FileNotFoundError:
            print(f"ERROR: Configuration file '{filename}' not found.")
            print("Please ensure the file exists and the path is correct.")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: Error parsing configuration file '{filename}': {e}")
            sys.exit(1)

    def create_topology(self):
        """
        Cria a topologia com base nos dados lidos do arquivo de configuração.
        """
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
                
    def deliver_message(self, message: Message, destination: int):
        if destination in self.nodes:
            threading.Thread(
                target=self._delayed_delivery,
                args=(message, destination),
                daemon=True
            ).start()
            
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
                        direct=False 
                    )
                else:
                    print(f"WARNING: Source node {command['source']} not found for sending message.")
            elif command["type"] == "wait":
                print(f"\n--- Waiting for {command['time']} seconds ---")
                time.sleep(command["time"])
        
        print("\n" + "=" * 60)
        print("        SIMULAÇÃO CONCLUÍDA")
        print("        Resumo de Mensagens Recebidas:")
        print("=" * 60)
        
        total_paths_found = 0 
        for node_id, node in self.nodes.items():
            print(f"\nNó {node_id}:")
            if node.received_messages:
                total_paths_found += len(node.received_messages) 
                print(f"  Total de mensagens recebidas: {len(node.received_messages)}")
                for i, msg in enumerate(node.received_messages):
                    path_str = " -> ".join(map(str, msg.path))
                    print(f"    - Mensagem {i+1} (ID: {msg.id}, Origem: {msg.source}, Destino Final: {msg.destination}, Hops: {msg.hop_count}, Caminho: {path_str}): '{msg.data}'")
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
                self.network_coding_enabled 
            ]
            results_csv_writer.writerow(row_data)
            print(f"Dados da simulação adicionados ao CSV: {row_data}") 
        
        topology_image_path_final = os.path.join(output_base_path, f"{output_file_base_name}_topology_final.png")
        self.plot_network_topology(save_path=topology_image_path_final)
        print(f"Imagem da topologia final salva como '{output_file_base_name}_topology_final.png'.")

        gif_output_path = os.path.join(output_base_path, f"{output_file_base_name}_traffic.gif")
        print("Gerando animação da rede. Isso pode levar um tempo...")
        self.animate_network_traffic(save_path=gif_output_path)
        print(f"Animação concluída! O arquivo '{output_file_base_name}_traffic.gif' foi gerado.")

    def plot_network_topology(self, save_path: Optional[str] = None):
        """
        Desenha a topologia da rede usando NetworkX e Matplotlib.
        Se save_path for fornecido, salva a imagem em vez de exibi-la.
        """
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
        """
        Gera uma animação do tráfego de mensagens na rede com setas e salva em um arquivo GIF.
        """
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
        normalized_events = sorted([(e[0] - start_time, e[1], e[2], e[3], e[4]) for e in simulation_events])

        # A duração total do tempo simulado que a animação representa
        max_sim_time_covered = normalized_events[-1][0] if normalized_events else 0.1
        
        # Fator pelo qual a duração real do GIF será esticada em relação ao tempo da simulação
        # Por exemplo, 2.0 significa que 1 segundo de simulação será representado em 2 segundos de GIF
        gif_speed_factor = 2.0 # Aumente este valor para deixar o GIF mais lento (e mais longo)
                               # 1.0 = duração real da simulação no GIF
                               # 0.5 = GIF mais rápido que a simulação

        # O tempo total de animação real (duração do GIF)
        total_animation_real_time = (max_sim_time_covered + 1.0) * gif_speed_factor
        
        # FPS do GIF gerado. Mantendo um FPS razoável para fluidez visual.
        fps_gif = 10 # Por exemplo, 10 frames por segundo para o GIF

        # Número total de frames necessários
        total_frames = int(total_animation_real_time * fps_gif)
        
        # Duração que a seta permanece visível em segundos do TEMPO SIMULADO
        arrow_visibility_duration_sim_time = 0.5 

        def update(frame):
            ax.clear()

            nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors_base, node_size=node_sizes_base)
            nx.draw_networkx_edges(G, pos, ax=ax, edge_color='gray', width=1.5)
            nx.draw_networkx_labels(G, pos, ax=ax, font_size=12, font_weight='bold')

            # Calcula o tempo SIMULADO atual que este frame representa
            # Divide 'frame' pelo 'fps_gif' para obter o tempo de animação,
            # depois divide pelo 'gif_speed_factor' para mapear de volta ao tempo de simulação
            current_sim_time = (frame / fps_gif) / gif_speed_factor 
            
            active_events = []
            for event_time, msg_id, from_node, to_node, event_type in normalized_events:
                # Verifica se o evento está ativo para ser desenhado
                # A condição usa o tempo SIMULADO
                if current_sim_time >= event_time and (current_sim_time - event_time) < arrow_visibility_duration_sim_time:
                    active_events.append((msg_id, from_node, to_node, event_type))

            current_messages_info = []
            for msg_id, from_node, to_node, event_type in active_events:
                if from_node in pos and to_node in pos:
                    if not G.has_edge(from_node, to_node):
                        print(f"AVISO: Tentando desenhar seta em aresta não existente {from_node}->{to_node} (Mensagem ID: {msg_id})")
                        continue 
                        
                    x1, y1 = pos[from_node]
                    x2, y2 = pos[to_node]
                    
                    offset_factor = 0.05
                    dx = x2 - x1
                    dy = y2 - y1
                    len_vec = (dx**2 + dy**2)**0.5
                    
                    x1_off = x1 - (dy / len_vec) * (msg_id % 3 - 1) * offset_factor if len_vec > 0 else x1
                    y1_off = y1 + (dx / len_vec) * (msg_id % 3 - 1) * offset_factor if len_vec > 0 else y1
                    x2_off = x2 - (dy / len_vec) * (msg_id % 3 - 1) * offset_factor if len_vec > 0 else x2
                    y2_off = y2 + (dx / len_vec) * (msg_id % 3 - 1) * offset_factor if len_vec > 0 else y2

                    ax.annotate(
                        '', xy=(x2_off, y2_off), xytext=(x1_off, y1_off),
                        arrowprops=dict(facecolor='red', edgecolor='red', shrink=0.05, width=2, headwidth=10, headlength=10),
                        xycoords='data', textcoords='data'
                    )
                    current_messages_info.append(f"M{msg_id}: {from_node}->{to_node}")
            
            title_text = f"Animação da Rede TSCH\nTempo: {current_sim_time:.2f}s" 
            if current_messages_info:
                title_text += "\nTráfego Ativo: " + ", ".join(current_messages_info[:3])
                if len(current_messages_info) > 3:
                    title_text += "..."
            ax.set_title(title_text, fontsize=14)
            return ax,

        # 'interval' na FuncAnimation determina o atraso entre os frames *no GIF*, em milissegundos
        # Para que o GIF rode a 'fps_gif', o intervalo é 1000 / fps_gif
        ani = FuncAnimation(fig, update, frames=total_frames, interval=(1000/fps_gif), blit=False, repeat=False)
        
        plt.close(fig) 

        if save_path:
            try:
                print(f"Salvando animação como GIF... (isso pode demorar)")
                writer_gif = plt.matplotlib.animation.PillowWriter(fps=fps_gif) # Salva com o fps_gif
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
                "Numero_de_Nos_Config",
                "Numero_de_Mensagens_Config",
                "Numero_de_Caminhos_Completos",
                "Tamanho_do_Slotframe",
                "Numero_de_Transmissoes_Totais",
                "Numero_de_Canais_Usados",
                "Network_Coding" 
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