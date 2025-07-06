import os
import subprocess
import sys
import time
import shutil

def clean_logs_folder(logs_path):
    if os.path.exists(logs_path):
        print(f"Limpando a pasta de logs: '{logs_path}'...")
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
    
    print("Pasta de logs limpa/criada.")


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
        "NORMAL": 'tsch_udp_simulation.py',
        "NETWORK_CODING": 'tsch_udp_nc_simulation.py'
    }

    print(f"Iniciando a execução de {len(config_files)} simulações para cada modo de operação ({', '.join(simulation_scripts.keys())}).")
    print("=" * 70)

    for mode, script_name in simulation_scripts.items():
        script_path = os.path.join(project_root, script_name)
        
        if not os.path.exists(script_path):
            print(f"\nAVISO: Script '{script_name}' não encontrado em '{project_root}'. Pulando este modo de simulação.")
            continue

        print(f"\n--- INICIANDO SIMULAÇÕES NO MODO: {mode} ({script_name}) ---")
        print("-" * 50)

        for i, config_file in enumerate(config_files):
            full_config_filepath = os.path.join(configs_path, config_file)
            
            print(f"\n--- RODANDO {mode} SIMULAÇÃO {i+1}/{len(config_files)}: '{config_file}' ---")
            start_time = time.time()

            try:
                result = subprocess.run(
                    ['python3', script_path, full_config_filepath],
                    check=True, 
                    text=True,
                    capture_output=True
                )
                print(f"--- SIMULAÇÃO '{config_file}' no modo {mode} CONCLUÍDA COM SUCESSO! ---")
            except subprocess.CalledProcessError as e:
                print(f"!!! ERRO NA SIMULAÇÃO '{config_file}' no modo {mode} !!!")
                print(f"Código de saída: {e.returncode}")
                print(f"--- STDOUT do subprocesso:\n{e.stdout}")
                print(f"--- STDERR do subprocesso:\n{e.stderr}")
                print("Continuando para a próxima simulação...")
            except FileNotFoundError:
                print(f"!!! ERRO: O executável 'python3' ou o script '{script_name}' não foi encontrado.")
                print("Certifique-se de que o Python está no seu PATH e o script está no diretório correto.")
                sys.exit(1)
            except Exception as e:
                print(f"!!! Ocorreu um erro inesperado ao rodar a simulação '{config_file}' no modo {mode}: {e} !!!")
                print("Continuando para a próxima simulação...")

            end_time = time.time()
            print(f"Tempo total para '{config_file}' no modo {mode}: {end_time - start_time:.2f} segundos.")
            print("-" * 50)
            
    print("\nTODAS AS SIMULAÇÕES FORAM PROCESSADAS.")
    print(f"Verifique a pasta '{log_dir_name}/' para os arquivos de saída de cada simulação.")
    print("Cada simulação terá seu próprio arquivo de log e resultados visuais.")


if __name__ == "__main__":
    run_all_simulations()