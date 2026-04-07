"""
Scraper – 3TORRESLEILOES
Baixa automaticamente os arquivos (edital, matrícula, despacho, etc.)
de todos os lotes de um determinado leilão.
Autor: você :)
"""

import os
import re
import time
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

# ------------------------- CONFIGURAÇÃO -------------------------

BASE_URL         = 'https://www.3torresleiloes.com.br'
# ex.: https://www.3torresleiloes.com.br/leilao/2482/lotes
URL_LEILAO       =  'https://www.3torresleiloes.com.br/leilao/2482/lotes'
NUM_PAGINAS      = 3            # quantas páginas da lista percorrer (1 se não houver paginação)
PASTA_DOWNLOADS = os.path.join(os.getcwd(), 'editais')

HEADERS = {
    'User-Agent' : ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/124.0 Safari/537.36'),
    'Referer'    : BASE_URL
}

PALAVRAS_CHAVE   = {
    'EDITAL'          : 'Edital',
    'DESPACHO'        : 'Despacho',
    'PENHORA'         : 'Auto_Penhora',
    'MATRÍCULA'       : 'Matricula',
    'MATRICULA'       : 'Matricula',
    'AVALIAÇÃO'       : 'Avaliacao',
    'LAUDO'           : 'Laudo'
}

# ------------------------- FUNÇÕES ------------------------------

def slugificar(texto: str) -> str:
    """Remove caracteres proibidos para nomes de arquivo."""
    return re.sub(r'[\\/*?:"<>|]', '', texto.strip()).replace(' ', '_')


def baixar_arquivo(url: str, nome_base: str) -> None:
    caminho = os.path.join(PASTA_DOWNLOADS, nome_base)

    # pula download se já existir
    if os.path.exists(caminho):
        print(f'    [✓] Já existe: {nome_base}')
        return

    try:
        print(f'    ↓ {url}')
        with requests.get(url, headers=HEADERS, stream=True, timeout=40) as r:
            r.raise_for_status()
            with open(caminho, 'wb') as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
        print(f'    [OK] Salvo em {nome_base}')
    except Exception as err:
        print(f'    [ERRO] {url} – {err}')


def extrair_lotes_de_pagina(html: str) -> list[str]:
    """
    Recebe o HTML de uma página da lista de lotes
    e devolve a url absoluta do primeiro link de
    cada cartão (para evitar duplicatas).
    """
    soup = BeautifulSoup(html, 'html.parser')
    urls_lotes = []

    for div_lote in soup.select('.lista-lotes .lote'):
        a = div_lote.find('a', href=re.compile(r'/item/\d+/detalhes'))
        if not a:
            continue
        url_abs = urljoin(BASE_URL, a['href'])
        if url_abs not in urls_lotes:            # remove duplicados
            urls_lotes.append(url_abs)

    return urls_lotes


def obter_links_lotes() -> list[str]:
    """
    Percorre as páginas da lista de lotes (page=1,2…)
    e devolve todas as urls dos lotes.
    """
    todos = []
    for pagina in range(1, NUM_PAGINAS + 1):
        # garante que só exista UM parâmetro page=x na url
        url_parts = list(urlparse(URL_LEILAO))
        qs = parse_qs(url_parts[4])
        qs['page'] = [str(pagina)]
        url_parts[4] = '&'.join(f'{k}={v[0]}' for k, v in qs.items())
        url_pagina = urljoin(BASE_URL, urlparse('')._replace(**dict(zip(
            ['scheme', 'netloc', 'path', 'params', 'query', 'fragment'],
            url_parts))).geturl())

        print(f'\n[+] Lendo página da lista: {url_pagina}')
        try:
            resp = requests.get(url_pagina, headers=HEADERS, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            print(f'   [ERRO] Não foi possível acessar {url_pagina}: {e}')
            break

        urls = extrair_lotes_de_pagina(resp.text)
        print(f'   → {len(urls)} links encontrados')
        if not urls:                      # provavelmente não há mais páginas
            break
        todos.extend(urls)

    return todos


def processar_lote(url_lote: str, idx: int) -> None:
    print(f'\n--- Lote {idx:03d} ---')
    print(f'URL: {url_lote}')

    try:
        r = requests.get(url_lote, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f'  [ERRO] Falha ao abrir página do lote: {e}')
        return

    soup = BeautifulSoup(r.text, 'html.parser')

    # Nome amigável (título H1 costuma ter “LOTE 00X”)
    titulo = soup.find('h1')
    nome_lote = slugificar(titulo.text if titulo else f'Lote_{idx:03d}')

    # Seleciona links dentro do bloco “Documentos”
    links_docs = soup.select('.arquivos-lote a[href]')

    if not links_docs:
        print('  Nenhum documento encontrado.')
        return

    for link in links_docs:
        texto_link = link.get_text(strip=True).upper()
        url_doc   = urljoin(BASE_URL, link['href'])

        # Descobre que tipo de arquivo é (edital, despacho …)
        nome_doc = None
        for palavra, rotulo in PALAVRAS_CHAVE.items():
            if palavra in texto_link:
                nome_doc = rotulo
                break

        if not nome_doc:
            # fallback: usa o próprio texto do botão
            nome_doc = slugificar(texto_link.title())

        # tenta manter a extensão de origem
        ext = os.path.splitext(url_doc.split('?')[0])[1] or '.pdf'
        nome_final = f'{nome_lote}_{nome_doc}{ext}'
        baixar_arquivo(url_doc, nome_final)


def main() -> None:
    print('=== 3 TORRES – DOWNLOAD DE DOCUMENTOS ===')

    if not os.path.isdir(PASTA_DOWNLOADS):
        os.makedirs(PASTA_DOWNLOADS)

    lotes = obter_links_lotes()
    if not lotes:
        print('Nenhum lote encontrado. Verifique a URL.')
        return

    print(f'\nTotal de lotes a processar: {len(lotes)}')

    for idx, url in enumerate(lotes, 1):
        processar_lote(url, idx)
        time.sleep(1.5)          # pequena pausa anti-flood

    print('\nConcluído! Arquivos em:', os.path.abspath(PASTA_DOWNLOADS))


if __name__ == '__main__':
    main()