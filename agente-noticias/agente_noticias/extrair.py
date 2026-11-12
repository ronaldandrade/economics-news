import html
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from .coletar import MAX_PARALELO, baixar

try:
    import trafilatura
except ImportError as e:
    # Sem o trafilatura os posts sairiam só com o resumo do feed, sem aviso.
    raise ImportError(f"trafilatura não carregou ({e}); rode pip install -r requirements.txt") from e

OG_IMAGE = re.compile(r"""<meta[^>]+(?:property|name)=["'](?:og:image|twitter:image)["'][^>]*>""", re.I)
CONTEUDO = re.compile(r"""content=["']([^"']+)["']""", re.I)
CHARSET = re.compile(rb"""<meta[^>]+charset\s*=\s*["']?\s*([\w-]+)""", re.I)


def decodificar(conteudo):
    """Bytes da página em texto. A maioria é UTF-8; quando não é (sites antigos em ISO-8859-1),
    vale o charset declarado no <meta> e, sem ele, windows-1252. Antes tudo era lido como UTF-8
    e os acentos dessas páginas viravam "�" no texto enviado ao modelo."""
    try:
        return conteudo.decode("utf-8")
    except UnicodeDecodeError:
        pass
    declarado = CHARSET.search(conteudo[:4096])
    for codificacao in ([declarado.group(1).decode("ascii")] if declarado else []) + ["cp1252"]:
        try:
            return conteudo.decode(codificacao)
        except (UnicodeDecodeError, LookupError):
            continue
    return conteudo.decode("utf-8", errors="replace")


def imagem_da_pagina(pagina, url):
    for tag in OG_IMAGE.findall(pagina):
        m = CONTEUDO.search(tag)
        if m:
            return urllib.parse.urljoin(url, html.unescape(m.group(1)))
    return ""


def ler_artigo(url, timeout=20, limite=6000):
    """Texto principal e imagem de destaque (og:image) da página; vazios se der erro ou paywall."""
    try:
        pagina = decodificar(baixar(url, timeout))
    except Exception:
        return "", ""
    try:
        texto = trafilatura.extract(pagina, include_comments=False, include_tables=False, favor_precision=True) or ""
    except Exception:
        texto = ""
    return texto[:limite], imagem_da_pagina(pagina, url)


def texto_do_artigo(url, timeout=20, limite=6000):
    return ler_artigo(url, timeout, limite)[0]


def material_do_grupo(grupo, extrair=True, max_artigos=5, timeout=20):
    por_fonte = {}
    for item in sorted(grupo["itens"], key=lambda i: len(i.descricao), reverse=True):
        por_fonte.setdefault(item.fonte, item)
    itens = list(por_fonte.values())[:max_artigos]
    if extrair and itens:
        # as páginas são de sites diferentes: baixar em paralelo não pesa em nenhum deles
        with ThreadPoolExecutor(max_workers=min(MAX_PARALELO, len(itens))) as pool:
            lidos = list(pool.map(lambda i: ler_artigo(i.link, timeout), itens))
    else:
        lidos = [("", "")] * len(itens)
    material = []
    for item, (texto, imagem_pagina) in zip(itens, lidos):
        material.append({
            "fonte": item.fonte,
            "idioma": item.idioma,
            "titulo": item.titulo,
            "link": item.link,
            "publicado": item.publicado,
            "texto": texto or item.descricao,
            "texto_completo": bool(texto),
            # og:image costuma vir em 1200 px; a do feed é o plano B
            "imagem": imagem_pagina or item.imagem,
        })
    return material
