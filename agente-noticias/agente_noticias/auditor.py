import json
import re
from datetime import datetime
from urllib.parse import urlparse

from .resumir import ALCANCES, CONSEQUENCIAS, EDITORIAS, campos_invalidos
from .verificar import checar, numeros_sem_fonte, problemas_de_estilo

SISTEMA_AUDITOR = """Você é o Auditor Chefe e Fact-Checker independente de um portal de notícias de economia mundial.
Sua missão é auditar com rigor absoluto o rascunho de notícia produzido por outro agente redator.

Princípios inegociáveis:
1. Jamais confie cegamente no redator. Seja estritamente cético, investigativo e factual.
2. NUNCA gere ou use notas abstratas de confiança (ex: '95% de certeza'). A verdade não é uma pontuação estimada; ela é comprovada exclusivamente por citações textuais literais das fontes fornecidas.
3. Para cada afirmação factual do rascunho (no título, descrição, corpo, pontos e consequência), confronte-a com os textos das fontes. Cite o trecho original que a comprova ou a contradiz.
   - Traduções equivalentes do inglês para o português e paráfrases fiéis ao sentido original (ex: 'acute food shortages' -> 'escassez aguda de alimentos' ou 'insegurança alimentar aguda') devem ser marcadas como 'confirmada'.
   - Marque 'sem_suporte' ou 'contradita' apenas quando houver fato inventado, extrapolação de escopo, nexo causal não declarado na fonte ou contradição factual real.
4. Confira minuciosamente todos os números, percentuais, moedas, variações de taxa e períodos temporais ESCRITOS NO RASCUNHO.
   - Avalie em 'conferencia_numerica' EXCLUSIVAMENTE os números que aparecem escritos no rascunho do redator. Se a fonte original não divulgou algum dado (ex: valor do negócio ou percentual da fatia) e o rascunho não inventou esse número, NÃO registre nada como 'ausente'. Se o rascunho não contém números, devolva lista vazia [].
   - A data de publicação da matéria já consta nos metadados do site; NÃO exija que a data de publicação apareça escrita no corpo e NÃO marque a data de publicação como número 'ausente'.
   - Cálculos óbvios diretamente derivados de frase literal da fonte (ex: 'a quarter of the population' -> 'um quarto da população') são válidos e 'correto'.
5. Verifique contexto e ressalvas: marque 'preservado: false' apenas quando o resumo omitir condição ou ressalva que distorça materialmente o entendimento do fato principal (ex: tratar projeção regional como nacional, omitir condicionalidade essencial ou base de comparação crítica). Detalhes secundários que não cabem em 3 a 5 parágrafos não invalidam o resumo.
6. Verifique neutralidade: o texto introduz juízo de valor, adjetivos sensacionalistas ou viés opinativo não sustentado pelos fatos?
7. Verifique divergências e campos técnicos:
   - Se as fontes discordam entre si em números ou fatos, verifique se isso foi reportado no campo 'divergencias' ou atribuído no corpo.
   - O campo 'base_consequencia' só é obrigatório quando 'consequencia' for 'critica'. Para 'relevante' ou 'acompanhamento', 'base_consequencia' vazio é o padrão correto — jamais aponte isso como falha ou omissão.

Vereditos da sua auditoria:
- 'aprovado': Cada afirmação e número tem respaldo direto nas fontes. Sem contradições, sem extrapolações e com contexto central preservado.
- 'inconclusivo': Há divergências reais entre fontes não explicadas, afirmações sem suporte direto nas fontes ou omissão de ressalva essencial que distorce o fato. Requer revisão ou correção.
- 'reprovado': Há erro factual direto identificado, número incorreto/invertido, generalização falsa de escopo ou alucinação. Bloqueia a publicação.
"""

FERRAMENTA_AUDITOR = {
    "nome": "registrar_auditoria",
    "descricao": "Registra a auditoria detalhada de fidelidade factual, numérica, contextual e neutralidade.",
    "esquema": {
        "type": "object",
        "properties": {
            "veredito": {
                "type": "string",
                "enum": ["aprovado", "inconclusivo", "reprovado"],
                "description": "Veredito da avaliação semântica.",
            },
            "motivo_veredito": {
                "type": "string",
                "description": "Justificativa clara e fundamentada da decisão.",
            },
            "fidelidade_factual": {
                "type": "array",
                "description": "Auditoria de cada alegação central.",
                "items": {
                    "type": "object",
                    "properties": {
                        "alegacao": {"type": "string"},
                        "status": {"type": "string", "enum": ["confirmada", "sem_suporte", "contradita"]},
                        "citacao_fonte": {"type": "string", "description": "Trecho literal da fonte original."},
                        "fonte_nome": {"type": "string"},
                    },
                    "required": ["alegacao", "status", "citacao_fonte"],
                },
            },
            "conferencia_numerica": {
                "type": "array",
                "description": "Conferência de números, percentuais, datas e valores.",
                "items": {
                    "type": "object",
                    "properties": {
                        "indicador": {"type": "string"},
                        "status": {"type": "string", "enum": ["correto", "divergente_entre_fontes", "ausente", "incorreto"]},
                        "detalhe": {"type": "string"},
                    },
                    "required": ["indicador", "status"],
                },
            },
            "contexto_e_ressalvas": {
                "type": "object",
                "properties": {
                    "preservado": {"type": "boolean"},
                    "ressalvas_omitidas": {"type": "array", "items": {"type": "string"}},
                    "analise": {"type": "string"},
                },
                "required": ["preservado", "ressalvas_omitidas"],
            },
            "neutralidade_e_tom": {
                "type": "object",
                "properties": {
                    "neutro": {"type": "boolean"},
                    "problemas": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["neutro", "problemas"],
            },
            "divergencias_fontes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Divergências identificadas entre as fontes.",
            },
        },
        "required": [
            "veredito",
            "motivo_veredito",
            "fidelidade_factual",
            "conferencia_numerica",
            "contexto_e_ressalvas",
            "neutralidade_e_tom",
            "divergencias_fontes",
        ],
    },
}


def _garantir_lista(valor):
    if isinstance(valor, str):
        s = valor.strip()
        if s.startswith("["):
            try:
                decodificado = json.loads(s)
                if isinstance(decodificado, list):
                    return decodificado
            except ValueError:
                return []
        return [s] if len(s) > 2 else []
    return valor if isinstance(valor, list) else []


def _garantir_dict(valor, padrao):
    if isinstance(valor, str):
        s = valor.strip()
        if s.startswith("{"):
            try:
                decodificado = json.loads(s)
                if isinstance(decodificado, dict):
                    return decodificado
            except ValueError:
                pass
    return valor if isinstance(valor, dict) else dict(padrao)


def normalizar_resultado_auditoria(res):
    """Normaliza defensivamente a saída da ferramenta do LLM auditor."""
    if not isinstance(res, dict):
        return {}

    fatos = []
    for item in _garantir_lista(res.get("fidelidade_factual")):
        if isinstance(item, dict):
            fatos.append(item)
        elif isinstance(item, str) and len(item.strip()) > 3:
            fatos.append({"alegacao": item, "status": "sem_suporte", "citacao_fonte": "", "fonte_nome": ""})
    res["fidelidade_factual"] = fatos

    numeros = []
    for item in _garantir_lista(res.get("conferencia_numerica")):
        if isinstance(item, dict):
            numeros.append(item)
        elif isinstance(item, str) and len(item.strip()) > 2:
            status = "incorreto" if "incorreto" in item.lower() else ("correto" if "correto" in item.lower() else "ausente")
            numeros.append({"indicador": item, "status": status, "detalhe": item})
    res["conferencia_numerica"] = numeros

    ctx = _garantir_dict(res.get("contexto_e_ressalvas"), {"preservado": True, "ressalvas_omitidas": []})
    ctx["ressalvas_omitidas"] = _garantir_lista(ctx.get("ressalvas_omitidas"))
    res["contexto_e_ressalvas"] = ctx

    neutro = _garantir_dict(res.get("neutralidade_e_tom"), {"neutro": True, "problemas": []})
    neutro["problemas"] = _garantir_lista(neutro.get("problemas"))
    res["neutralidade_e_tom"] = neutro

    res["divergencias_fontes"] = _garantir_lista(res.get("divergencias_fontes"))

    return res


def validar_fontes(post):
    """Confere se todas as fontes possuem URLs válidas."""
    erros = []
    fontes = post.get("fontes", [])
    if not fontes:
        erros.append("lista de fontes vazia")
    for f in fontes:
        link = f.get("link", "")
        parsed = urlparse(link)
        if not parsed.scheme or parsed.scheme not in ("http", "https") or not parsed.netloc:
            erros.append(f"fonte '{f.get('nome')}' com URL incompatível: {link}")
    return erros


def validar_duplicidade(post, links_existentes=None, eventos_existentes=None):
    """Verifica se a matéria já foi publicada ou coberta recentemente."""
    links_existentes = set(links_existentes or [])
    eventos_existentes = set(eventos_existentes or [])
    problemas = []

    links_materia = set(post.get("_links", []))
    for f in post.get("fontes", []):
        if f.get("link"):
            links_materia.add(f["link"])

    repetidos = links_materia & links_existentes
    if repetidos:
        problemas.append(f"links já presentes no histórico: {', '.join(sorted(repetidos))}")

    evento = post.get("evento", "").strip()
    if evento and evento in eventos_existentes:
        problemas.append(f"evento idêntico já registrado no histórico: '{evento}'")

    return {"duplicado": len(problemas) > 0, "detalhes": problemas}


def auditar_materia(llm, modelo, post, material, links_existentes=None, eventos_existentes=None):
    """Executa a auditoria completa do Agente Revisor Independente sobre o rascunho."""
    # Problemas herdados da checagem determinística do redator (campos ausentes, enums inválidos, etc.)
    problemas_iniciais = list(post.get("problemas") or [])
    erros_campos = campos_invalidos(post)
    for err in erros_campos:
        if err not in problemas_iniciais:
            problemas_iniciais.append(err)

    erros_fontes = validar_fontes(post)
    checagem_dup = validar_duplicidade(post, links_existentes, eventos_existentes)
    problemas_verificar = checar(post, material)
    for p in problemas_verificar:
        if p not in problemas_iniciais:
            problemas_iniciais.append(p)

    # 1. Regras determinísticas de decisão
    motivos = list(problemas_iniciais)
    veredito = "aprovado"

    # Duplicidade ou fonte incompatível bloqueiam (REPROVADO)
    if checagem_dup["duplicado"]:
        veredito = "reprovado"
        motivos.extend([f"Duplicidade: {d}" for d in checagem_dup["detalhes"]])

    if erros_fontes:
        veredito = "reprovado"
        motivos.extend(erros_fontes)

    # Campos faltantes ou problemas de estilo/números sem modelo semântico levam para revisão humana (INCONCLUSIVO)
    if problemas_iniciais and veredito != "reprovado":
        veredito = "inconclusivo"

    # 2. Se houver modelo auditor configurado, executa a auditoria semântica independente
    resultado_llm = None
    if modelo and llm:
        textos_fonte = []
        for m in material:
            textos_fonte.append(f"=== FONTE: {m['fonte']} ({m['idioma']}) ===\nTítulo: {m['titulo']}\nData: {m['publicado']}\n{m['texto']}")
        fontes_bloco = "\n\n".join(textos_fonte)

        rascunho_bloco = (
            f"Título: {post.get('titulo')}\n"
            f"Descrição: {post.get('descricao')}\n"
            f"Chapéu: {post.get('chapeu')}\n"
            f"Alcance: {post.get('alcance')} | Consequência: {post.get('consequencia')}\n"
            f"Base da Consequência: {post.get('base_consequencia')}\n"
            f"Editoria: {post.get('editoria')}\n"
            f"Corpo:\n{post.get('corpo')}\n\n"
            f"Pontos principais:\n- " + "\n- ".join(post.get("pontos", [])) + "\n\n"
            f"Divergências declaradas pelo redator: {post.get('divergencias') or 'Nenhuma'}"
        )

        mensagem_auditoria = (
            f"TEXTOS BRUTOS DAS FONTES ORIGINAIS:\n{fontes_bloco}\n\n"
            f"---------------------------------------------------\n"
            f"RASCUNHO DO AGENTE REDATOR A SER AUDITADO:\n{rascunho_bloco}\n"
        )

        resultado_llm = llm.chamar_ferramenta(
            modelo,
            SISTEMA_AUDITOR,
            mensagem_auditoria,
            FERRAMENTA_AUDITOR["nome"],
            FERRAMENTA_AUDITOR["descricao"],
            FERRAMENTA_AUDITOR["esquema"],
        )
        resultado_llm = normalizar_resultado_auditoria(resultado_llm)

        # Fatos contraditos geram REPROVAÇÃO
        fatos_contraditos = [f for f in resultado_llm.get("fidelidade_factual", []) if f.get("status") == "contradita"]
        if fatos_contraditos:
            veredito = "reprovado"
            for f in fatos_contraditos:
                motivos.append(f"Fato contradito pela fonte: «{f.get('alegacao')}» (Fonte: {f.get('fonte_nome')})")

        # Números incorretos geram REPROVAÇÃO
        numeros_errados = [n for n in resultado_llm.get("conferencia_numerica", []) if n.get("status") == "incorreto"]
        if numeros_errados:
            veredito = "reprovado"
            for n in numeros_errados:
                motivos.append(f"Número incorreto ou invertido: {n.get('indicador')} - {n.get('detalhe')}")

        if veredito != "reprovado":
            # Alegações sem suporte
            fatos_sem_suporte = [f for f in resultado_llm.get("fidelidade_factual", []) if f.get("status") == "sem_suporte"]
            if fatos_sem_suporte:
                veredito = "inconclusivo"
                for f in fatos_sem_suporte:
                    motivos.append(f"Alegação sem confirmação direta na fonte: «{f.get('alegacao')}»")

            # Números divergentes ou ausentes (apenas quando há dígitos concretos no indicador citado no rascunho)
            numeros_inconclusivos = [
                n for n in resultado_llm.get("conferencia_numerica", [])
                if n.get("status") == "divergente_entre_fontes"
                or (n.get("status") == "ausente" and re.search(r"\d", str(n.get("indicador", ""))) and "data" not in str(n.get("indicador", "")).lower())
            ]
            if numeros_inconclusivos:
                veredito = "inconclusivo"
                for n in numeros_inconclusivos:
                    motivos.append(f"Número com incerteza/divergência: {n.get('indicador')} ({n.get('status')})")

            # Contexto e ressalvas omitidas
            ctx = resultado_llm.get("contexto_e_ressalvas", {})
            if not ctx.get("preservado", True):
                veredito = "inconclusivo"
                for r in ctx.get("ressalvas_omitidas", []):
                    motivos.append(f"Ressalva importante omitida: {r}")

            # Neutralidade violada
            neutro = resultado_llm.get("neutralidade_e_tom", {})
            if not neutro.get("neutro", True):
                veredito = "inconclusivo"
                for p in neutro.get("problemas", []):
                    motivos.append(f"Problema de neutralidade/tom: {p}")

            # Divergências entre fontes
            divs = resultado_llm.get("divergencias_fontes", [])
            if divs and not post.get("divergencias", "").strip():
                veredito = "inconclusivo"
                for d in divs:
                    motivos.append(f"Divergência entre fontes não tratada: {d}")

    # Remove duplicidades nos motivos mantendo a ordem
    motivos_unicos = []
    for m in motivos:
        if m not in motivos_unicos:
            motivos_unicos.append(m)

    return {
        "veredito": veredito,
        "motivo": "; ".join(motivos_unicos) if motivos_unicos else "Aprovado sem ressalvas.",
        "problemas": motivos_unicos,
        "duplicidade": checagem_dup,
        "semantico": resultado_llm,
    }
