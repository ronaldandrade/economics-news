import json
from datetime import datetime, timezone
from pathlib import Path

from .agrupar import agrupar, ranquear
from .auditor import auditar_materia
from .coletar import coletar
from .estado import Estado
from .extrair import material_do_grupo
from .publicar import PublicadorArquivo, criar_publicador
from .resumir import reescrever_pos_auditoria, resumir


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
    meta_posts = cfg.get("max_posts", 5)
    modelo_auditor = cfg.get("modelos", {}).get("auditar")
    permitir_avulsas = cfg.get("permitir_avulsas", False)
    limite_pool = max(meta_posts * 2, 10) if modelo_auditor else meta_posts
    candidatos_pool, descartados = ranquear(
        grupos,
        cfg.get("min_fontes", 2),
        limite_pool,
        estado.links(),
        permitir_avulsas=permitir_avulsas,
    )
    escolhidos = list(candidatos_pool[:meta_posts])
    suplentes = list(candidatos_pool[meta_posts:])
    relatorio["grupos"] = [
        {"evento": g["evento"], "fontes": g["fontes"], "relevancia": g["relevancia"],
         "alcance": g["alcance_economico"], "canal": g["canal_economico"]}
        for g in grupos
    ]
    relatorio["descartados"] = descartados
    for g in escolhidos:
        avulso_tag = " (mais relevante não repetida)" if len(g["veiculos"]) < cfg.get("min_fontes", 2) else ""
        log(f"   ✓ {len(g['fontes'])} fonte(s) · {g['evento']}{avulso_tag}")
    if suplentes:
        log(f"   ({len(suplentes)} pauta(s) suplente(s) na reserva caso alguma seja reprovada)")
    if not escolhidos:
        log("   nenhum acontecimento elegível para publicação")

    log("== resumindo e auditando com revisor independente")
    posts, falhas = [], []
    tentativas_auditoria = cfg.get("tentativas_auditoria", 1) if modelo_auditor else 0
    indice = 0
    while indice < len(escolhidos):
        g = escolhidos[indice]
        indice += 1
        try:
            material = material_do_grupo(g, cfg.get("extrair_texto", True), cfg.get("max_artigos_por_evento", 5))
            post = resumir(llm, cfg["modelos"]["resumir"], g, material)
        except Exception as e:
            # um resumo que falha não joga fora os outros da rodada, que já foram pagos
            falhas.append({"evento": g["evento"], "erro": f"{type(e).__name__}: {e}"})
            log(f"   ! {g['evento']}: {falhas[-1]['erro']}")
            if suplentes and sum(1 for p in posts if p["status"] == "pronto") < meta_posts:
                prox = suplentes.pop(0)
                log(f"   + acionando pauta suplente da fila: {prox['evento']}")
                escolhidos.append(prox)
            continue
        post["_links"] = [m.link for m in g["itens"]]

        for rodada_aud in range(tentativas_auditoria + 1):
            try:
                auditoria = auditar_materia(
                    llm, modelo_auditor, post, material,
                    links_existentes=estado.links(),
                    eventos_existentes=estado.eventos(),
                )
            except Exception as e:
                auditoria = {
                    "veredito": "inconclusivo",
                    "motivo": f"Falha na auditoria: {type(e).__name__}: {e}",
                    "problemas": [f"Erro técnico no auditor: {e}"],
                    "semantico": None,
                }
                break

            if auditoria["veredito"] == "aprovado" or rodada_aud >= tentativas_auditoria:
                break
            if auditoria.get("duplicidade", {}).get("duplicado"):
                break

            log(f"   ↻ auto-correção ({rodada_aud + 1}/{tentativas_auditoria}): '{post['titulo']}' -> corrigindo {len(auditoria['problemas'])} apontamento(s) do auditor")
            try:
                post = reescrever_pos_auditoria(llm, cfg["modelos"]["resumir"], g, material, post, auditoria["problemas"])
                post["_links"] = [m.link for m in g["itens"]]
            except Exception as e:
                log(f"   ! falha ao reescrever {g['evento']}: {e}")
                break

        post["auditoria"] = auditoria
        post["veredito"] = auditoria["veredito"]
        post["problemas"] = auditoria["problemas"]
        if auditoria["veredito"] == "aprovado":
            post["status"] = "pronto"
            marca = "✓ APROVADO (merge automático)"
        elif auditoria["veredito"] == "inconclusivo":
            post["status"] = "revisar"
            marca = "⚠ INCONCLUSIVO (revisão humana: " + "; ".join(post["problemas"][:2]) + ")"
        else:
            post["status"] = "reprovado"
            marca = "✗ REPROVADO (bloqueado: " + "; ".join(post["problemas"][:2]) + ")"
        posts.append(post)
        log(f"   {post['titulo']} [{marca}]")

        aprovados_ate_agora = sum(1 for p in posts if p["status"] == "pronto")
        restantes_na_fila = len(escolhidos) - indice
        if post["status"] != "pronto" and suplentes and (aprovados_ate_agora + restantes_na_fila) < meta_posts:
            prox = suplentes.pop(0)
            avulso_tag = " (mais relevante não repetida)" if len(prox["veiculos"]) < cfg.get("min_fontes", 2) else ""
            log(f"   + acionando pauta suplente da fila: {prox['evento']}{avulso_tag}")
            escolhidos.append(prox)

    log("== publicando" + (" (modo seco: só grava em saida/seco)" if seco else ""))
    publicados = []
    destino_seco = destino_local(cfg["publicacao"], "saida/seco", raiz)
    destino_revisar = destino_local(cfg["publicacao"], "saida/revisar", raiz)
    destino_reprovado = destino_local(cfg["publicacao"], "saida/reprovados", raiz)
    prontos = [p for p in posts if p["status"] == "pronto"]
    if prontos:
        # o acontecimento mais repetido entre os veículos vira a manchete do site
        prontos[0]["destaque"] = True
    publicador = None
    if prontos and not seco:
        publicador = criar_publicador(cfg["publicacao"], raiz)
        publicador.preparar(data)
    try:
        for post in posts:
            if post["status"] == "revisar":
                local = destino_revisar.publicar(post, data)
                if post.get("auditoria"):
                    caminho_auditoria = Path(local).with_name(f"{Path(local).stem}.auditoria.json")
                    caminho_auditoria.write_text(json.dumps(post["auditoria"], ensure_ascii=False, indent=2), encoding="utf-8")
            elif post["status"] == "reprovado":
                local = destino_reprovado.publicar(post, data)
                if post.get("auditoria"):
                    caminho_bloqueio = Path(local).with_name(f"{Path(local).stem}.bloqueio.json")
                    caminho_bloqueio.write_text(json.dumps(post["auditoria"], ensure_ascii=False, indent=2), encoding="utf-8")
            elif seco:
                local = destino_seco.publicar(post, data)
            else:
                local = publicador.publicar(post, data)
                estado.registrar(post["evento"], post["_links"], local)
            publicados.append({"titulo": post["titulo"], "status": post["status"], "veredito": post.get("veredito", post["status"]), "destino": local, "problemas": post["problemas"]})
            log(f"   → {local}")
        resultado_git = publicador.finalizar(data) if publicador else None
    except BaseException:
        if publicador:
            publicador.cancelar()
        raise
    if resultado_git:
        log(f"   git: {resultado_git}")

    if not seco:
        estado.salvar()
    relatorio["posts"] = publicados
    relatorio["falhas"] = falhas
    relatorio["git"] = resultado_git
    relatorio["uso"] = llm.relatorio()
    log(f"== custo estimado: US$ {relatorio['uso']['custo_estimado_usd']:.4f}")
    pasta_logs = raiz / "logs"
    pasta_logs.mkdir(parents=True, exist_ok=True)
    (pasta_logs / f"{agora.astimezone().strftime('%Y-%m-%d_%H%M')}.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return relatorio
