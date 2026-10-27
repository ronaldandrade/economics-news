import json
from datetime import datetime, timezone
from pathlib import Path

from .agrupar import agrupar, ranquear
from .coletar import coletar
from .estado import Estado
from .extrair import material_do_grupo
from .publicar import PublicadorArquivo, criar_publicador
from .resumir import resumir


def destino_local(cfg_publicacao, pasta, raiz):
    """Grava na pasta do agente, no mesmo formato da publicação (JSON do site ou MDX), sem git."""
    if cfg_publicacao.get("tipo") == "site_json":
        return criar_publicador({"tipo": "site_json", "pasta": pasta}, raiz)
    return PublicadorArquivo({"pasta": pasta}, raiz)


def executar(cfg, fontes, llm, raiz, seco=False, log=print, agora=None):
    agora = agora or datetime.now(timezone.utc)
    data = agora.astimezone().strftime("%Y-%m-%d")
    raiz = Path(raiz)
    estado = Estado(raiz / cfg.get("arquivo_estado", "dados/estado.json"), cfg.get("dias_memoria", 5))
    relatorio = {"inicio": agora.isoformat(), "seco": seco}

    log(f"== coletando {len(fontes)} fontes (últimas {cfg.get('janela_horas', 24)} h)")
    itens, info = coletar(fontes, cfg.get("janela_horas", 24), cfg.get("max_itens_por_fonte", 30), agora=agora, log=log)
    relatorio["coleta"] = {"itens": len(itens), **info}
    log(f"   {len(itens)} manchetes de {sum(1 for v in info['por_fonte'].values() if v)} fontes")

    log("== agrupando acontecimentos repetidos entre sites")
    grupos = agrupar(llm, cfg["modelos"]["agrupar"], itens, estado.eventos())
    escolhidos, descartados = ranquear(grupos, cfg.get("min_fontes", 2), cfg.get("max_posts", 3), estado.links())
    relatorio["grupos"] = [
        {"evento": g["evento"], "fontes": g["fontes"], "relevancia": g["relevancia"],
         "alcance": g["alcance_economico"], "canal": g["canal_economico"]}
        for g in grupos
    ]
    relatorio["descartados"] = descartados
    for g in escolhidos:
        log(f"   ✓ {len(g['fontes'])} fontes · {g['evento']}")
    if not escolhidos:
        log("   nenhum acontecimento atingiu o mínimo de fontes")

    log("== resumindo")
    posts = []
    for g in escolhidos:
        material = material_do_grupo(g, cfg.get("extrair_texto", True), cfg.get("max_artigos_por_evento", 5))
        post = resumir(llm, cfg["modelos"]["resumir"], g, material)
        post["_links"] = [m.link for m in g["itens"]]
        posts.append(post)
        marca = "pronto" if post["status"] == "pronto" else "REVISAR: " + "; ".join(post["problemas"])
        log(f"   {post['titulo']} [{marca}]")

    log("== publicando" + (" (modo seco: só grava em saida/seco)" if seco else ""))
    publicados = []
    destino_seco = destino_local(cfg["publicacao"], "saida/seco", raiz)
    destino_revisar = destino_local(cfg["publicacao"], "saida/revisar", raiz)
    prontos = [p for p in posts if p["status"] == "pronto"]
    if prontos:
        # o acontecimento mais repetido entre os veículos vira a manchete do site
        prontos[0]["destaque"] = True
    publicador = None
    if prontos and not seco:
        publicador = criar_publicador(cfg["publicacao"], raiz)
        publicador.preparar(data)
    for post in posts:
        if seco:
            local = destino_seco.publicar(post, data)
        elif post["status"] != "pronto":
            local = destino_revisar.publicar(post, data)
        else:
            local = publicador.publicar(post, data)
            estado.registrar(post["evento"], post["_links"], local)
        publicados.append({"titulo": post["titulo"], "status": post["status"], "destino": local, "problemas": post["problemas"]})
        log(f"   → {local}")
    resultado_git = publicador.finalizar(data) if publicador else None
    if resultado_git:
        log(f"   git: {resultado_git}")

    if not seco:
        estado.salvar()
    relatorio["posts"] = publicados
    relatorio["git"] = resultado_git
    relatorio["uso"] = llm.relatorio()
    log(f"== custo estimado: US$ {relatorio['uso']['custo_estimado_usd']:.4f}")
    pasta_logs = raiz / "logs"
    pasta_logs.mkdir(parents=True, exist_ok=True)
    (pasta_logs / f"{agora.astimezone().strftime('%Y-%m-%d_%H%M')}.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return relatorio
