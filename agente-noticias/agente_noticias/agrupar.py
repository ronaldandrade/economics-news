
CATEGORIAS = [
    "politica_monetaria", "inflacao", "atividade_e_emprego", "comercio_e_tarifas", "cambio",
    "commodities_e_energia", "mercados", "divida_e_fiscal", "empresas_globais", "organismos_e_acordos", "crise",
]

ALCANCES = ["global", "internacional", "nacional", "nao_economico"]
# Só estes viram post; o resto é descartado em código, mesmo que o modelo esqueça a regra
ALCANCES_PUBLICAVEIS = {"global", "internacional"}

SISTEMA = """Você é editor de economia internacional. Recebe uma lista numerada de manchetes de vários sites de notícias, em português e em inglês.

Sua tarefa é agrupar as manchetes que tratam do MESMO acontecimento específico: o mesmo fato, na mesma data aproximada, ainda que em idiomas diferentes e com títulos diferentes. Dois textos sobre o mesmo tema geral (por exemplo, "inflação") mas sobre fatos diferentes ficam em grupos diferentes.

Considere apenas economia mundial: bancos centrais e juros, inflação, PIB e emprego, comércio internacional e tarifas, câmbio, petróleo e outras commodities, mercados financeiros globais, dívida pública e política fiscal de grandes economias, crises, organismos e acordos (FMI, Banco Mundial, OMC, G20, OPEP) e grandes empresas quando o fato afeta a economia de vários países.

O critério é o fato em si ser econômico e ter efeito fora do país de origem. Um assunto que só tem consequência econômica indireta não entra.

Não inclua, mesmo que vários sites noticiem:
- Política e eleições: resultado de eleição, posse, crise de governo, escândalo. Entra só a reação econômica concreta com números (ex.: "bolsa cai 5% e moeda despenca após eleição"), num grupo próprio sobre o mercado, e só se afetar investidores ou economias de fora.
- Celebridades, esportes e cultura, inclusive quando há patrocinador ou empresa envolvida (ex.: atleta perde contrato de patrocínio).
- Medida econômica de um país só, sem efeito descrito sobre outros: subsídio interno, programa social, imposto doméstico, orçamento sem impacto externo, salário mínimo nacional.
- Resultado de uma empresa que não mexe com mercados de vários países; finanças pessoais, dicas de investimento, promoções, colunas de opinião e conteúdo patrocinado.

Para cada grupo, classifique "alcance_economico":
- "global": afeta mercados, preços ou cadeias de vários continentes.
- "internacional": afeta diretamente a economia de outros países, de vizinhos ou de um bloco (comércio, câmbio, investimento, energia que cruza a fronteira).
- "nacional": efeito econômico só dentro de um país.
- "nao_economico": política, esportes, celebridades, cultura ou outro assunto que não é economia.
Na dúvida entre duas opções, escolha a mais restrita. Em "canal_economico", diga em uma frase por onde o fato atinge outros países (ex.: "preço do gás importado pela Europa"); para "nacional" e "nao_economico", escreva "nenhum".

Regras:
- Use apenas os números de itens da lista. Nunca invente itens.
- Cada item entra em no máximo um grupo.
- Um grupo de um item só é permitido quando o fato é de grande relevância.
- "evento" é uma frase factual curta em português sobre o que aconteceu, sem opinião.
- Marque "repete_publicado" como true quando o grupo for o mesmo acontecimento de algum evento já publicado (lista fornecida), sem fato novo relevante."""

FERRAMENTA = {
    "nome": "registrar_grupos",
    "descricao": "Registra os grupos de manchetes sobre o mesmo acontecimento de economia mundial.",
    "esquema": {
        "type": "object",
        "properties": {
            "grupos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "evento": {"type": "string"},
                        "itens": {"type": "array", "items": {"type": "integer"}},
                        "categoria": {"type": "string", "enum": CATEGORIAS},
                        "relevancia": {"type": "integer", "minimum": 1, "maximum": 5},
                        "repete_publicado": {"type": "boolean"},
                        "alcance_economico": {"type": "string", "enum": ALCANCES},
                        "canal_economico": {"type": "string"},
                    },
                    "required": ["evento", "itens", "categoria", "relevancia", "repete_publicado", "alcance_economico", "canal_economico"],
                },
            }
        },
        "required": ["grupos"],
    },
}


def montar_mensagem(itens, eventos_publicados):
    linhas = []
    for item in itens:
        descricao = f" | {item.descricao[:180]}" if item.descricao else ""
        linhas.append(f"[{item.id}] ({item.fonte}, {item.idioma}) {item.titulo}{descricao}")
    publicados = "\n".join(f"- {e}" for e in eventos_publicados) or "(nenhum)"
    return f"Eventos já publicados nos últimos dias:\n{publicados}\n\nManchetes:\n" + "\n".join(linhas)


def validar_grupos(brutos, itens):
    por_id = {i.id: i for i in itens}
    usados, grupos = set(), []
    for g in brutos:
        ids = []
        for i in g.get("itens", []):
            if isinstance(i, int) and i in por_id and i not in usados:
                ids.append(i)
                usados.add(i)
        if not ids:
            continue
        membros = [por_id[i] for i in ids]
        fontes = sorted({m.fonte for m in membros})
        # BBC Business e BBC News Brasil são o mesmo veículo: contam como uma fonte só
        veiculos = sorted({m.veiculo or m.fonte for m in membros})
        datas = [m.publicado for m in membros if m.publicado]
        grupos.append({
            "evento": str(g.get("evento", "")).strip(),
            "categoria": g.get("categoria", ""),
            "relevancia": int(g.get("relevancia", 1)),
            "repete_publicado": bool(g.get("repete_publicado", False)),
            # sem classificação, o grupo não passa no filtro de alcance
            "alcance_economico": g.get("alcance_economico", "nao_informado"),
            "canal_economico": str(g.get("canal_economico", "")).strip(),
            "itens": membros,
            "fontes": fontes,
            "veiculos": veiculos,
            "mais_recente": max(datas) if datas else "",
        })
    return grupos


def ranquear(grupos, min_fontes, max_posts, links_publicados):
    candidatos, descartados = [], []
    for g in grupos:
        links = {m.link for m in g["itens"]}
        sobreposicao = len(links & links_publicados) / len(links)
        if g["alcance_economico"] not in ALCANCES_PUBLICAVEIS:
            descartados.append((g["evento"], f"alcance {g['alcance_economico']}"))
        elif g["repete_publicado"] or sobreposicao >= 0.5:
            descartados.append((g["evento"], "já publicado"))
        elif len(g["veiculos"]) < min_fontes:
            descartados.append((g["evento"], f"{len(g['veiculos'])} veículo(s), mínimo {min_fontes}"))
        else:
            candidatos.append(g)
    candidatos.sort(key=lambda g: (len(g["veiculos"]), g["relevancia"], g["mais_recente"]), reverse=True)
    return candidatos[:max_posts], descartados


def agrupar(llm, modelo, itens, eventos_publicados, max_itens=400):
    if not itens:
        return []
    recentes = sorted(itens, key=lambda i: i.publicado or "", reverse=True)[:max_itens]
    recentes.sort(key=lambda i: i.id)
    resposta = llm.chamar_ferramenta(
        modelo, SISTEMA, montar_mensagem(recentes, eventos_publicados),
        FERRAMENTA["nome"], FERRAMENTA["descricao"], FERRAMENTA["esquema"],
    )
    return validar_grupos(resposta.get("grupos", []), recentes)
