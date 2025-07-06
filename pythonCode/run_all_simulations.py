import os
import subprocess
import sys
import time
import shutil

def clean_logs_folder(logs_path):
    if os.path.exists(logs_path):
        for item in os.listdir(logs_path):
            item_path = os.path.join(logs_path, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            except Exception as e:
                print(f"  Erro ao remover {item}: {e}")
    else:
        print(f"A pasta de logs '{logs_path}' não existe. Criando...")
        os.makedirs(logs_path)
    


def run_all_simulations():
    configs_dir_name = "simulations_configs"
    log_dir_name = "logs" 

    project_root = os.path.dirname(os.path.abspath(sys.argv[0]))
    
    configs_path = os.path.join(project_root, configs_dir_name)
    logs_path = os.path.join(project_root, log_dir_name) 

    clean_logs_folder(logs_path)

    if not os.path.isdir(configs_path):
        print(f"Erro: A pasta '{configs_path}' não foi encontrada.")
        print("Por favor, crie a pasta 'simulations_configs' na raiz do projeto e coloque seus arquivos .txt nela.")
        sys.exit(1)

    config_files = [f for f in os.listdir(configs_path) if f.endswith('.txt')]
    config_files.sort() 

    if not config_files:
        print(f"Nenhum arquivo .txt encontrado na pasta '{configs_path}'.")
        print("Certifique-se de que seus arquivos de configuração estejam lá.")
        sys.exit(0)

    simulation_scripts = {
        "TSCH WITH UDP": 'tsch_udp_simulation.py',
        "TSCH WITH UDP AND NETWORK CODING": 'tsch_udp_nc_simulation.py'
    }

    results = {
        "TSCH WITH UDP": [],
        "TSCH WITH UDP AND NETWORK CODING": []
    }

    print(f"Iniciando a execução de {len(config_files)} simulações para cada modo de operação.\n")
    print("=" * 70)

    for mode, script_name in simulation_scripts.items():
        script_path = os.path.join(project_root, script_name)
        
        if not os.path.exists(script_path):
            print(f"\nAVISO: Script '{script_name}' não encontrado em '{project_root}'. Pulando este modo de simulação.")
            continue

        print(f"\n{mode}")
        
        for i, config_file in enumerate(config_files):
            full_config_filepath = os.path.join(configs_path, config_file)
            
            file_base_name = os.path.splitext(config_file)[0]
            
            try:
                # Execute o subprocesso e capture a saída
                subprocess.run(
                    ['python3', script_path, full_config_filepath],
                    check=True, 
                    text=True,
                    capture_output=True # Captura stdout e stderr
                )
                print(f"Simulation {i+1} ({file_base_name}): SUCCESS")
                results[mode].append(True)
            except subprocess.CalledProcessError:
                print(f"Simulation {i+1} ({file_base_name}): FAILURE")
                results[mode].append(False)
            except FileNotFoundError:
                print(f"!!! ERRO: O executável 'python3' ou o script '{script_name}' não foi encontrado.")
                print("Certifique-se de que o Python está no seu PATH e o script está no diretório correto.")
                sys.exit(1)
            except Exception as e:
                print(f"!!! Ocorreu um erro inesperado ao rodar a simulação '{config_file}' no modo {mode}: {e} !!!")
                results[mode].append(False) # Considera falha qualquer outro erro

    print("\nTODAS AS SIMULAÇÕES FORAM PROCESSADAS.")
    print("=" * 70)

    total_success = 0
    for mode, outcomes in results.items():
        success_count = sum(outcomes)
        print(f"TOTAL OF SUCCESS {mode}: {success_count}")
        total_success += success_count
    
    print(f"TOTAL OF SUCCESS: {total_success}")
    print("=" * 70)
    print(f"\nVerifique a pasta '{log_dir_name}/' para os arquivos de saída de cada simulação (logs detalhados, imagens e GIFs).")


if __name__ == "__main__":
    run_all_simulations()