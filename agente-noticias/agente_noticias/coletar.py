import calendar
import gzip
import html
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser

AGENTE_HTTP = "Mozilla/5.0 (X11; Linux x86_64) agente-noticias/1.0 (+leitor RSS pessoal)"
TAGS = re.compile(r"<[^>]+>")
PARAMETROS_RASTREIO = re.compile(r"^(utm_|cmpid|ocid|ns_|at_|src$|ref$|fbclid|gclid)", re.I)


@dataclass
class Item:
    id: int
    fonte: str
    idioma: str
    titulo: str
    descricao: str
    link: str
    publicado: str
    veiculo: str = ""
    imagem: str = ""

    def para_dict(self):
        return asdict(self)


def limpar_texto(texto):
    return re.sub(r"\s+", " ", html.unescape(TAGS.sub(" ", texto or ""))).strip()


def normalizar_link(link):
    partes = urllib.parse.urlsplit(link.strip())
    consulta = [(k, v) for k, v in urllib.parse.parse_qsl(partes.query) if not PARAMETROS_RASTREIO.match(k)]
    return urllib.parse.urlunsplit((partes.scheme.lower(), partes.netloc.lower(), partes.path.rstrip("/"), urllib.parse.urlencode(consulta), ""))


def limpar_link(link):
    partes = urllib.parse.urlsplit(link.strip())
    consulta = [(k, v) for k, v in urllib.parse.parse_qsl(partes.query) if not PARAMETROS_RASTREIO.match(k)]
    return urllib.parse.urlunsplit((partes.scheme, partes.netloc, partes.path, urllib.parse.urlencode(consulta), ""))


def baixar(url, timeout=20):
    if url.startswith("file://") or Path(url).exists():
        return Path(url.replace("file://", "")).read_bytes()
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE_HTTP, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
        conteudo = resposta.read()
    # alguns sites (g1) mandam gzip mesmo sem o pedido aceitar; o urllib não descompacta sozinho
    if conteudo[:2] == b"\x1f\x8b":
        conteudo = gzip.decompress(conteudo)
    return conteudo


def data_da_entrada(entrada):
    for chave in ("published_parsed", "updated_parsed"):
        valor = entrada.get(chave)
        if valor:
            return datetime.fromtimestamp(calendar.timegm(valor), tz=timezone.utc)
    return None


def imagem_da_entrada(entrada):
    """Maior imagem que o feed oferece (media:content, media:thumbnail ou enclosure)."""
    candidatas = []
    for m in entrada.get("media_content") or []:
        if m.get("url") and (m.get("medium") == "image" or (m.get("type") or "image").startswith("image")):
            candidatas.append((int(m.get("width") or 0), m["url"]))
    for m in entrada.get("media_thumbnail") or []:
        if m.get("url"):
            candidatas.append((int(m.get("width") or 0), m["url"]))
    for l in entrada.get("links") or []:
        if l.get("rel") == "enclosure" and (l.get("type") or "").startswith("image") and l.get("href"):
            candidatas.append((0, l["href"]))
    if not candidatas:
        return ""
    return max(candidatas, key=lambda c: c[0])[1]


def ler_fonte(fonte, timeout=20):
    conteudo = baixar(fonte["url"], timeout)
    feed = feedparser.parse(conteudo)
    if feed.bozo and not feed.entries:
        raise ValueError(f"feed inválido: {feed.bozo_exception}")
    return feed.entries


def coletar(fontes, janela_horas=24, max_por_fonte=30, agora=None, timeout=20, log=print):
    agora = agora or datetime.now(timezone.utc)
    limite = agora - timedelta(hours=janela_horas)
    itens, vistos, por_fonte, erros = [], set(), {}, {}
    for fonte in fontes:
        try:
            entradas = ler_fonte(fonte, timeout)
        except Exception as e:
            erros[fonte["nome"]] = f"{type(e).__name__}: {e}"
            log(f"  ! {fonte['nome']}: {erros[fonte['nome']]}")
            continue
        aceitos = 0
        for entrada in entradas:
            if aceitos >= max_por_fonte:
                break
            link = entrada.get("link") or ""
            titulo = limpar_texto(entrada.get("title"))
            if not link or not titulo:
                continue
            chave = normalizar_link(link)
            if chave in vistos:
                continue
            publicado = data_da_entrada(entrada)
            if publicado is not None and (publicado < limite or publicado > agora + timedelta(hours=2)):
                continue
            vistos.add(chave)
            descricao = limpar_texto(entrada.get("summary") or entrada.get("description"))[:400]
            itens.append(Item(
                id=len(itens),
                fonte=fonte["nome"],
                idioma=fonte.get("idioma", "?"),
                titulo=titulo,
                descricao=descricao,
                link=limpar_link(link),
                publicado=publicado.isoformat() if publicado else "",
                veiculo=fonte.get("grupo", fonte["nome"]),
                imagem=imagem_da_entrada(entrada),
            ))
            aceitos += 1
        por_fonte[fonte["nome"]] = aceitos
    return itens, {"por_fonte": por_fonte, "erros": erros}


def verificar_fontes(fontes, timeout=20):
    resultado = []
    for fonte in fontes:
        try:
            entradas = ler_fonte(fonte, timeout)
            datas = [d for d in (data_da_entrada(e) for e in entradas) if d]
            mais_recente = max(datas).isoformat() if datas else "sem datas"
            resultado.append((fonte["nome"], True, f"{len(entradas)} itens, mais recente: {mais_recente}"))
        except Exception as e:
            resultado.append((fonte["nome"], False, f"{type(e).__name__}: {e}"))
    return resultado
