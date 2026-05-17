# Movies2GSheets

Utilitário Python que varre pastas locais de vídeos, coleta metadados de cada arquivo e os sincroniza com uma planilha Google Sheets via Google Apps Script — evitando duplicatas a cada execução.

---

## Como funciona

```
Pastas locais (D:\Filmes, Y:\Filmes…)
        │
        ▼
  Varredura recursiva
  (os.walk + extensões permitidas)
        │
        ▼
  Coleta de metadados por arquivo
  (tamanho, data, resolução, codec, hash)
        │
        ▼
  Consulta à planilha (GET)
  ← lista de hashes já cadastrados
        │
        ▼
  Filtra apenas arquivos novos
        │
        ▼
  Envia novos registros (POST)
  → Google Sheets via Apps Script
```

A planilha funciona como banco de dados leve: o script nunca recadastra um arquivo que já está lá.

---

## Pré-requisitos

- Python 3.10 ou superior (usa `match` e `os.walk` com type hints)
- `ffprobe` instalado e disponível no PATH (parte do pacote [FFmpeg](https://ffmpeg.org/download.html))
- Uma planilha Google Sheets com um Web App publicado via Google Apps Script (veja a seção abaixo)

---

## Configuração

Edite as constantes no topo do script:

```python
# Caminhos das pastas a varrer
VIDEO_PATHS = ['D:\\Filmes', 'D:\\Filmes 3D', 'D:\\Filmes 4K', 'Y:\\Filmes']

# URL do Web App publicado no Google Apps Script
WEB_APP_URL = 'https://script.google.com/macros/s/<SEU_ID>/exec'

# Extensões de vídeo reconhecidas
ALLOWED_EXTENSIONS = {'mkv', 'mp4', 'mkv3d', 'avi'}
```

---

## Google Apps Script

O script `appscript.ghs` se comunica com a planilha através de um Web App publicado no Google Apps Script. O endpoint precisa suportar dois métodos:

| Método | Comportamento esperado |
|--------|----------------------|
| `GET`  | Retorna um array JSON com todos os hashes já cadastrados na planilha |
| `POST` | Recebe `{ "values": [[...], [...]] }` e insere as linhas na planilha |

### 1. Criar o projeto Apps Script a partir da planilha
  - Abra a planilha no Google Sheets.
  - No menu, acesse: **Extensões → Apps Script**.
  - Um novo projeto será criado automaticamente e vinculado a esta planilha.
  - Dê um nome ao projeto.
  - Copie o conteúdo de `appscript.ghs` para lá e implante um app web.

### 2. Fazer o deploy como Web App
  - No novo editor: `Deploy` → `New deployment`.
  - Em `Select type` escolha **Web app**.
  - Em `Description` coloque um rótulo (ex.: "v1 - lançamento inicial").
  - Em `Execute as` selecione **Me** (o script executa com suas credenciais) ou escolha conforme a necessidade.
  - Em `Who has access` selecione **Anyone** (O hash é grande).
  - Clique em `Deploy` e siga as instruções para conceder permissões; copie a URL do Web App.

### Atualizar o script e criar novas versões
  - O Web App deployado usa uma versão do código (snapshot). Alterações no editor NÃO afetam automaticamente uma implantação existente até que você publique uma nova versão e atualize o deployment.

#### Passos para criar nova versão e redeploy:
  - No editor Apps Script, vá em `File` → `Manage versions...` (ou `Versions` no novo editor) e clique em `Save New Version` colocando uma descrição curta (ex.: "Correção X").
  - Depois vá em `Deploy` → `Manage deployments` → selecione a implantação do tipo **Web app** → `Edit`.
  - Na edição da implantação escolha a versão recém-criada (ou selecione a opção para usar a última versão, se disponível) e salve/atualize.
  - Clique em `Redeploy` (ou `Update`) — o URL do Web App se mantém, mas passa a servir o novo código.
  - Observação rápida: sempre anote a descrição da versão para rastreabilidade e use números/labels claros (ex.: `v2 - correção de X`).

### Colunas gravadas na planilha

| # | Campo | Descrição |
|---|-------|-----------|
| 1 | Nome | Nome do arquivo |
| 2 | Tamanho | Tamanho legível (ex: `12.34 GB`) |
| 3 | Resolução | Label de qualidade (`SD`, `HD`, `FHD`, `QHD`, `4K`) |
| 4 | Resolução exata | Dimensões reais em pixels (ex: `3840x2160`) |
| 5 | Codec | Codec do stream de vídeo (ex: `hevc`, `h264`) |
| 6 | Tamanho (bytes) | Valor numérico bruto para ordenação precisa |
| 7 | Data | Data de modificação do arquivo (`YYYY-MM-DD HH:MM:SS`) |
| 8 | Hash | Assinatura MD5 do arquivo (chave de deduplicação) |
| 9 | Caminho | Caminho completo no sistema de arquivos |

---

## Funcionamento interno

### Deduplicação por hash

Cada arquivo recebe uma assinatura MD5 calculada a partir do tamanho e dos conteúdos do arquivo. Antes do envio, o script busca todos os hashes já cadastrados na planilha e filtra apenas os arquivos ausentes.

### Fast Hash

Para evitar leitura completa de arquivos grandes (que podem ter dezenas de GB), o hash é calculado lendo apenas:

- o **primeiro 1 MB** do arquivo
- o **último 1 MB** do arquivo
- o **tamanho total** em bytes (incluso no hash)

Arquivos menores que 2 MB passam por hash completo. Arquivos corrompidos ou inacessíveis usam o caminho como fallback.

### Classificação de resolução

A resolução é classificada pela **maior dimensão** do vídeo (largura ou altura), o que torna a lógica imune ao letterboxing (barras pretas que reduzem a altura real):

| Maior dimensão | Label |
|---------------|-------|
| ≥ 3840 px | `4K` |
| ≥ 2560 px | `QHD` |
| ≥ 1920 px | `FHD` |
| ≥ 1280 px | `HD` |
| > 0 px | `SD` |

Os tiers são definidos na constante `RESOLUTION_TIERS` — adicionar suporte a `8K`, por exemplo, é só incluir `(7680, '8K')` no início da lista.

---

## Uso

```bash
python main.py
```

Saída esperada:

```
Iniciando varredura...
Processando metadados e gerando hashes de 312 arquivos...
Consultando planilha para evitar duplicidade...
Enviando 5 novos vídeos para a planilha...
Processamento concluído com sucesso.
```

---

## Extensões suportadas

`mkv` · `mp4` · `mkv3d` · `avi`

Para adicionar novas extensões, edite `ALLOWED_EXTENSIONS` no topo do script.
