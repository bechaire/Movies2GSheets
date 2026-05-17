# Movies2GSheets

Script em python para enviar ao Google Sheets uma relação atualizada dos filmes backupeados

# AtualizaListaFilmes

Este projeto contém um script Python para escanear pastas de filmes locais, coletar metadados relevantes e atualizar uma planilha do Google Sheets via um Web App do Google Apps Script.

## Objetivo

O script procura arquivos de vídeo em diretórios configurados, extrai informações sobre resolução, codec, tamanho e data de modificação, e gera uma assinatura rápida para cada arquivo. Em seguida, ele consulta uma planilha existente para evitar duplicações e envia apenas os filmes novos.

## Como funciona

- `VIDEO_PATHS`: lista de diretórios locais onde os vídeos são pesquisados.
- `ALLOWED_EXTENSIONS`: tipos de arquivo de vídeo considerados válidos (`mkv`, `mp4`, `mkv3d`, `avi`).
- `WEB_APP_URL`: URL do Web App do Google Apps Script que recebe os dados.
- `procura_arquivos_video()`: varre os diretórios definidos e coleta caminhos de arquivos suportados.
- `coleta_dados_video()`: usa `ffprobe` para extrair resolução e codec e coleta metadados do arquivo.
- `gerar_assinatura_video()`: cria um hash rápido usando o primeiro e último megabyte do arquivo, além do tamanho total, para identificar vídeos.
- `buscar_filmes_na_planilha()`: baixa os hashes existentes da planilha para comparação.
- `inserir_dados_na_planilha()`: envia os novos registros via POST para o Web App.

## Requisitos

- Python 3.x
- `ffprobe` disponível no PATH (parte do FFmpeg)

## Configuração

1. Altere `VIDEO_PATHS` para os diretórios onde seus filmes estão armazenados.
2. Ajuste `WEB_APP_URL` para a URL de execução do seu Web App do Google Apps Script.
3. Verifique se os arquivos de vídeo usam extensões suportadas.

## Uso

Execute o script diretamente com Python:

```bash
python AtualizaListaFilmes.py
```

O script exibirá o progresso no console e informará se encontrou novos vídeos para enviar.

## Pontos principais

- Evita duplicidade usando hashes armazenados na planilha.
- Classifica automaticamente a resolução como `4K`, `QHD`, `FHD`, `HD` ou `SD`.
- Usa `ffprobe` para extrair informações de vídeo de forma eficiente.
- Envia apenas novos registros, fazendo o processo mais rápido e seguro.

## Observações

- O script trabalha melhor em ambientes Windows, mas pode ser adaptado para outros sistemas desde que `ffprobe` esteja disponível e os caminhos sejam ajustados.
- Se `ffprobe` falhar para algum arquivo, o script continuará processando os demais.
