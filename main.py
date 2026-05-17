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
WEB_APP_URL = 'https://script.google.com/macros/s/==============================================/exec'

ALLOWED_EXTENSIONS = {'mkv', 'mp4', 'mk3d', 'avi'}

CHUNK_SIZE = 1024 * 1024  # 1 MB

# Pares (dimensão mínima, label) em ordem decrescente — adicionar tiers aqui é suficiente
RESOLUTION_TIERS = [
    (3840, '4K'),
    (2560, 'QHD'),
    (1920, 'FHD'),
    (1280, 'HD'),
    (1,    'SD'),
]

FFPROBE_DEFAULT = 'desconhecido'

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


def classificar_resolucao(maior_dim: int) -> str:
    """Retorna o label de resolução com base na maior dimensão do vídeo."""
    for threshold, label in RESOLUTION_TIERS:
        if maior_dim >= threshold:
            return label
    return 'ERRO'


def gerar_assinatura_video(file_path: str) -> str:
    """Fast Hash: lê apenas o 1º e o último MB para evitar gargalo de disco."""
    tamanho = os.path.getsize(file_path)
    hasher = hashlib.md5()
    hasher.update(str(tamanho).encode('utf-8'))

    # Arquivo pequeno: hash completo
    if tamanho <= CHUNK_SIZE * 2:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    try:
        with open(file_path, 'rb') as f:
            hasher.update(f.read(CHUNK_SIZE))          # Primeiro MB
            f.seek(-CHUNK_SIZE, os.SEEK_END)
            hasher.update(f.read(CHUNK_SIZE))          # Último MB
    except OSError:
        # Fallback para arquivos corrompidos ou inacessíveis
        hasher.update(file_path.encode('utf-8'))

    return hasher.hexdigest()


def procura_arquivos_video(paths: list[str]) -> list[str]:
    """Varre os diretórios recursivamente e retorna arquivos com extensão permitida."""
    found_files = []

    for base_path in paths:
        if not os.path.isdir(base_path):
            continue

        for root, _, files in os.walk(base_path):
            for file in files:
                _, ext = os.path.splitext(file)
                if ext.lstrip('.').lower() in ALLOWED_EXTENSIONS:
                    found_files.append(os.path.join(root, file))

    return found_files


def coleta_dados_video(file_path: str) -> dict:
    """Coleta metadados do arquivo: tamanho, data, resolução, codec e hash."""
    stat = os.stat(file_path)

    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v",
        "-show_entries", "stream=width,height,codec_name",
        "-of", "csv=s=x:p=0",
        file_path
    ]

    melhor_width, melhor_height = 0, 0
    resolucao_exata = "0x0"
    melhor_codec = FFPROBE_DEFAULT

    try:
        resultado = subprocess.run(cmd, capture_output=True, text=True)

        if resultado.returncode != 0:
            print(f"[Aviso] FFprobe falhou: {os.path.basename(file_path)} — {resultado.stderr.strip()}")
        else:
            maior_area = 0
            for linha in resultado.stdout.splitlines():
                partes = linha.split('x')
                numericos = [p for p in partes if p.strip().isdigit()]
                codec = partes[0].strip() if partes else FFPROBE_DEFAULT

                if len(numericos) != 2:
                    continue

                w, h = int(numericos[0]), int(numericos[1])
                if (area := w * h) > maior_area:
                    maior_area = area
                    melhor_width, melhor_height = w, h
                    resolucao_exata = f"{w}x{h}"
                    melhor_codec = codec

    except Exception as e:
        print(f"[Erro] Falha ao chamar FFprobe: {e}")

    # Classifica pela maior dimensão — imune ao letterboxing
    resolucao_label = classificar_resolucao(max(melhor_width, melhor_height))

    return {
        'nome':            os.path.basename(file_path),
        'data':            datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
        'tamanho_bytes':   stat.st_size,
        'tamanho_humano':  formatar_tamanho(stat.st_size),
        'resolucao_exata': resolucao_exata,
        'resolucao_label': resolucao_label,
        'hash':            gerar_assinatura_video(file_path),
        'path':            file_path,
        'codec':           melhor_codec,
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
            d['tamanho_humano'],    # Coluna visual
            d['resolucao_label'],   # Coluna visual
            d['resolucao_exata'],   # Proporção exata
            d['codec'],
            d['tamanho_bytes'],     # Para ordenação precisa
            d['data'],
            d['hash'],
            d['path'],
        ]
        for d in dados
    ]

    payload = json.dumps({"values": rows}).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
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
    hashes_set = set(hashes_existentes)  # set → busca O(1)

    novos_dados = [item for item in dados_coletados if item['hash'] not in hashes_set]

    if novos_dados:
        print(f"Enviando {len(novos_dados)} novos vídeos para a planilha...")
        inserir_dados_na_planilha(WEB_APP_URL, novos_dados)
        print("Processamento concluído com sucesso.")
    else:
        print("Processamento concluído. Nenhum vídeo novo encontrado.")
