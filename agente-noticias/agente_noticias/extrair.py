from .coletar import baixar


def texto_do_artigo(url, timeout=20, limite=6000):
    try:
        import trafilatura
    except ImportError:
        return ""
    try:
        bruto = baixar(url, timeout).decode("utf-8", errors="replace")
        texto = trafilatura.extract(bruto, include_comments=False, include_tables=False, favor_precision=True) or ""
    except Exception:
        return ""
    return texto[:limite]


def material_do_grupo(grupo, extrair=True, max_artigos=5, timeout=20):
    por_fonte = {}
    for item in sorted(grupo["itens"], key=lambda i: len(i.descricao), reverse=True):
        por_fonte.setdefault(item.fonte, item)
    material = []
    for item in list(por_fonte.values())[:max_artigos]:
        texto = texto_do_artigo(item.link, timeout) if extrair else ""
        material.append({
            "fonte": item.fonte,
            "idioma": item.idioma,
            "titulo": item.titulo,
            "link": item.link,
            "publicado": item.publicado,
            "texto": texto or item.descricao,
            "texto_completo": bool(texto),
        })
    return material
