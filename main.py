import os
import json
import urllib.request
import urllib.error
import subprocess
import hashlib
from datetime import datetime

# ==========================================
# CONFIGURAÇÕES
# ==========================================
VIDEO_PATHS = ['D:\\Filmes', 'D:\\Filmes 3D', 'D:\\Filmes 4K', 'Y:\\Filmes']

# Substitua pela URL do seu Web App do Google Apps Script (deve ser a URL de execução, não a de edição)
WEB_APP_URL = 'https://script.google.com/macros/s/==============================================/exec'

ALLOWED_EXTENSIONS = {'mkv', 'mp4', 'mkv3d', 'avi'}

# ==========================================
# HELPERS E LÓGICA DE NEGÓCIO
# ==========================================

def formatar_tamanho(tamanho_em_bytes: int) -> str:
    """Converte bytes para um formato legível (KB, MB, GB, etc)."""
    if tamanho_em_bytes == 0:
        return "0 B"
    
    unidades = ['B', 'KB', 'MB', 'GB', 'TB']
    i = 0
    tamanho = float(tamanho_em_bytes)
    
    while tamanho >= 1024 and i < len(unidades) - 1:
        tamanho /= 1024
        i += 1
        
    return f"{tamanho:.2f} {unidades[i]}"

def gerar_assinatura_video(file_path: str) -> str:
    """Fast Hash: Lê apenas o 1º e o último MB para evitar gargalo de disco."""
    chunk_size = 1024 * 1024  # 1 MB
    tamanho = os.path.getsize(file_path)
    
    hasher = hashlib.md5()
    hasher.update(str(tamanho).encode('utf-8'))
    
    # Se o arquivo for menor que 2MB, fazemos o hash normal
    if tamanho <= (chunk_size * 2):
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    try:
        with open(file_path, 'rb') as f:
            # Lê o primeiro Megabyte
            hasher.update(f.read(chunk_size))
            # Vai para o final do arquivo, recuando 1 Megabyte
            f.seek(-chunk_size, os.SEEK_END)
            # Lê o último Megabyte
            hasher.update(f.read(chunk_size))
    except OSError:
        # Fallback de segurança caso haja falha de leitura (arquivos corrompidos, etc)
        hasher.update(file_path.encode('utf-8'))

    return hasher.hexdigest()

def procura_arquivos_video(paths: list[str]) -> list[str]:
    """Varre diretórios usando os.walk (muito rápido em sistemas de arquivos locais)."""
    found_files = []
    
    for base_path in paths:
        if not os.path.isdir(base_path):
            continue
            
        for root, _, files in os.walk(base_path):
            for file in files:
                ext = file.split('.')[-1].lower()
                if ext in ALLOWED_EXTENSIONS:
                    found_files.append(os.path.join(root, file))
                    
    return found_files

def coleta_dados_video(file_path: str) -> dict:
    stat = os.stat(file_path)

    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v",
        "-show_entries", "stream=width,height,codec_name",
        "-of", "csv=s=x:p=0",
        file_path
    ]

    melhor_height = 0
    melhor_width = 0
    resolucao_exata = "0x0"
    melhor_codec = 'desconhecido'

    try:
        resultado = subprocess.run(cmd, capture_output=True, text=True)

        if resultado.returncode != 0:
            print(f"[Aviso] FFprobe falhou: {os.path.basename(file_path)} — {resultado.stderr.strip()}")
        else:
            maior_area = 0
            for linha in resultado.stdout.splitlines():
                partes = linha.split('x')
                # Espera: ['hevc', '3840', '2160'] ou ['hevc', '3840', '2160', '']
                numericos = [p for p in partes if p.strip().isdigit()]
                codec = partes[0].strip() if partes else 'desconhecido'

                if len(numericos) != 2:
                    continue
                w, h = int(numericos[0]), int(numericos[1])
                if (area := w * h) > maior_area:
                    maior_area = area
                    melhor_width = w
                    melhor_height = h
                    resolucao_exata = f"{w}x{h}"
                    melhor_codec = codec

    except Exception as e:
        print(f"[Erro] Falha ao chamar FFprobe: {e}")

    # Classifica pela maior dimensão — imune ao letterboxing
    melhor_dim = max(melhor_width, melhor_height)

    match melhor_dim:
        case _ if melhor_dim >= 3840: resolucao_label = '4K'
        case _ if melhor_dim >= 2560: resolucao_label = 'QHD'
        case _ if melhor_dim >= 1920: resolucao_label = 'FHD'
        case _ if melhor_dim >= 1280: resolucao_label = 'HD'
        case _ if melhor_dim > 0:     resolucao_label = 'SD'
        case _:                       resolucao_label = 'ERRO'

    return {
        'nome': os.path.basename(file_path),
        'data': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
        'tamanho_bytes': stat.st_size,
        'tamanho_humano': formatar_tamanho(stat.st_size),
        'resolucao_exata': resolucao_exata,
        'resolucao_label': resolucao_label,
        'hash': gerar_assinatura_video(file_path),
        'path': file_path,
        'codec': melhor_codec
    }

def buscar_filmes_na_planilha(url: str) -> list[str]:
    """Recupera hashes existentes. O urllib lida automaticamente com os redirects (HTTP 302) do Google."""
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data if isinstance(data, list) else []
    except urllib.error.URLError as e:
        print(f"Erro ao buscar planilha: {e}")
        return []

def inserir_dados_na_planilha(url: str, dados: list[dict]) -> None:
    """Envia novos registros via POST para o webhook."""
    rows = [
        [
            d['nome'], 
            d['tamanho_humano'],   # Coluna visual
            d['resolucao_label'],  # Coluna visual
            d['resolucao_exata'],  # Coluna nova de proporção
            d['codec'],            # Coluna nova para codec
            d['tamanho_bytes'],    # Coluna nova para ordenação precisa
            d['data'], 
            d['hash'], 
            d['path']
        ] 
        for d in dados
    ]
    
    payload = json.dumps({"values": rows}).encode('utf-8')
    headers = {"Content-Type": "application/json"}
    
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            pass
    except urllib.error.URLError as e:
        print(f"Erro ao inserir na planilha: {e}")


# ==========================================
# EXECUÇÃO PRINCIPAL
# ==========================================
if __name__ == "__main__":
    print("Iniciando varredura...")
    arquivos = procura_arquivos_video(VIDEO_PATHS)
    
    print(f"Processando metadados e gerando hashes de {len(arquivos)} arquivos...")
    dados_coletados = [coleta_dados_video(path) for path in arquivos]
    
    print("Consultando planilha para evitar duplicidade...")
    hashes_existentes = buscar_filmes_na_planilha(WEB_APP_URL)
    hashes_set = set(hashes_existentes) # Conversão para set(O(1)) deixa a busca mais rápida
    
    novos_dados = [item for item in dados_coletados if item['hash'] not in hashes_set]
    
    if novos_dados:
        print(f"Enviando {len(novos_dados)} novos vídeos para a planilha...")
        inserir_dados_na_planilha(WEB_APP_URL, novos_dados)
        print("Processamento concluído com sucesso.")
    else:
        print("Processamento concluído. Nenhum vídeo novo encontrado.")
