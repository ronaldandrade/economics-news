from types import SimpleNamespace
import pytest
from agente_noticias.auditor import auditar_materia, validar_duplicidade, validar_fontes

POST_BASE = {
    "titulo": "Banco central sobe juros para 4,5%",
    "descricao": "A taxa subiu 0,25 ponto percentual conforme esperado pela maioria do mercado.",
    "corpo": "O comitê de política monetária decidiu por unanimidade elevar a taxa de juros para 4,5% ao ano.\n\nA decisão visa conter a alta da inflação que atingiu 3,8% nos últimos doze meses.\n\nO mercado de câmbio reagiu com estabilidade.",
    "pontos": ["Juros sobem para 4,5%", "Inflação atinge 3,8%", "Decisão por unanimidade"],
    "divergencias": "",
    "tags": ["juros", "inflacao"],
    "alcance": "nacional",
    "consequencia": "relevante",
    "base_consequencia": "",
    "editoria": "Macroeconomia",
    "chapeu": "JUROS",
    "local": "Brasília",
    "paises": ["Brasil"],
    "fontes": [{"nome": "Fonte A", "titulo": "BC sobe juros", "link": "https://a.test/1"}],
    "problemas": [],
}

MATERIAL_BASE = [
    {
        "fonte": "Fonte A",
        "idioma": "pt",
        "titulo": "BC sobe juros para 4,5%",
        "publicado": "2026-11-11",
        "texto": "O banco central elevou a taxa básica em 0,25 ponto, para 4,5% com inflação a 3,8%. Decisão foi por unanimidade.",
    }
]


class LLMAuditorMock:
    def __init__(self, retorno):
        self.retorno = retorno

    def chamar_ferramenta(self, modelo, sistema, mensagem, nome, descricao, esquema):
        return self.retorno


def test_auditor_aprova_quando_fatos_e_numeros_comprovados():
    retorno_llm = {
        "veredito": "aprovado",
        "motivo_veredito": "Tudo comprovado",
        "fidelidade_factual": [
            {"alegacao": "BC elevou juros para 4,5%", "status": "confirmada", "citacao_fonte": "elevou a taxa para 4,5%", "fonte_nome": "Fonte A"}
        ],
        "conferencia_numerica": [
            {"indicador": "4,5%", "status": "correto", "detalhe": "Presente na fonte"}
        ],
        "contexto_e_ressalvas": {"preservado": True, "ressalvas_omitidas": [], "analise": "OK"},
        "neutralidade_e_tom": {"neutro": True, "problemas": []},
        "divergencias_fontes": [],
    }
    llm = LLMAuditorMock(retorno_llm)
    res = auditar_materia(llm, "claude-haiku-5-5", POST_BASE, MATERIAL_BASE)
    assert res["veredito"] == "aprovado"
    assert len(res["problemas"]) == 0


def test_auditor_inconclusivo_quando_ha_divergencias_ou_incerteza():
    retorno_llm = {
        "veredito": "inconclusivo",
        "motivo_veredito": "Divergência sobre o impacto inflacionário",
        "fidelidade_factual": [
            {"alegacao": "Impacto na inflação", "status": "sem_suporte", "citacao_fonte": "", "fonte_nome": ""}
        ],
        "conferencia_numerica": [
            {"indicador": "3,8%", "status": "divergente_entre_fontes", "detalhe": "Outra fonte cita 4,1%"}
        ],
        "contexto_e_ressalvas": {"preservado": False, "ressalvas_omitidas": ["Decisão sujeita a revisão extraordinária"], "analise": ""},
        "neutralidade_e_tom": {"neutro": True, "problemas": []},
        "divergencias_fontes": ["Projeções inflacionárias divergem entre 3,8% e 4,1%"],
    }
    llm = LLMAuditorMock(retorno_llm)
    res = auditar_materia(llm, "claude-haiku-5-5", POST_BASE, MATERIAL_BASE)
    assert res["veredito"] == "inconclusivo"
    assert any("sem confirmação direta" in p for p in res["problemas"])
    assert any("divergência" in p for p in res["problemas"])


def test_auditor_reprova_quando_fato_contradito_ou_numero_incorreto():
    retorno_llm = {
        "veredito": "reprovado",
        "motivo_veredito": "Erro factual comprovado",
        "fidelidade_factual": [
            {"alegacao": "Juros subiram para 4,5%", "status": "contradita", "citacao_fonte": "taxa foi mantida em 4,25%", "fonte_nome": "Fonte A"}
        ],
        "conferencia_numerica": [
            {"indicador": "4,5%", "status": "incorreto", "detalhe": "Fonte declara 4,25%"}
        ],
        "contexto_e_ressalvas": {"preservado": True, "ressalvas_omitidas": []},
        "neutralidade_e_tom": {"neutro": True, "problemas": []},
        "divergencias_fontes": [],
    }
    llm = LLMAuditorMock(retorno_llm)
    res = auditar_materia(llm, "claude-haiku-5-5", POST_BASE, MATERIAL_BASE)
    assert res["veredito"] == "reprovado"
    assert any("contradito" in p for p in res["problemas"])
    assert any("Número incorreto" in p for p in res["problemas"])


def test_auditor_reprova_duplicidade_e_fonte_invalida():
    post_dup = dict(POST_BASE, _links=["https://antigo.test/post1"])
    res = auditar_materia(None, None, post_dup, MATERIAL_BASE, links_existentes=["https://antigo.test/post1"])
    assert res["veredito"] == "reprovado"
    assert any("Duplicidade" in p for p in res["problemas"])

    post_link_ruim = dict(POST_BASE, fontes=[{"nome": "X", "link": "not_a_url"}])
    res_link = auditar_materia(None, None, post_link_ruim, MATERIAL_BASE)
    assert res_link["veredito"] == "reprovado"
    assert any("URL incompatível" in p for p in res_link["problemas"])


def test_ranquear_completa_ate_5_com_mais_relevantes_nao_repetidas():
    from agente_noticias.agrupar import ranquear
    from types import SimpleNamespace

    def item(link):
        return SimpleNamespace(link=link)

    grupos = [
        {"evento": "G1", "veiculos": ["A", "B"], "relevancia": 4, "mais_recente": "2026-11-11T10:00", "alcance_economico": "global", "repete_publicado": False, "itens": [item("http://1")]},
        {"evento": "G2", "veiculos": ["A", "B", "C"], "relevancia": 3, "mais_recente": "2026-11-11T09:00", "alcance_economico": "global", "repete_publicado": False, "itens": [item("http://2")]},
        {"evento": "Avulso Baixa Relevancia", "veiculos": ["A"], "relevancia": 1, "mais_recente": "2026-11-11T08:00", "alcance_economico": "global", "repete_publicado": False, "itens": [item("http://3")]},
        {"evento": "Avulso Alta Relevancia 1", "veiculos": ["B"], "relevancia": 5, "mais_recente": "2026-11-11T12:00", "alcance_economico": "global", "repete_publicado": False, "itens": [item("http://4")]},
        {"evento": "Avulso Alta Relevancia 2", "veiculos": ["C"], "relevancia": 5, "mais_recente": "2026-11-11T11:00", "alcance_economico": "global", "repete_publicado": False, "itens": [item("http://5")]},
        {"evento": "Avulso Media Relevancia", "veiculos": ["D"], "relevancia": 4, "mais_recente": "2026-11-11T07:00", "alcance_economico": "global", "repete_publicado": False, "itens": [item("http://6")]},
    ]

    # Com permitir_avulsas=False, só os 2 repetidos são escolhidos
    escolhidos_padrao, desc_padrao = ranquear(grupos, min_fontes=2, max_posts=5, links_publicados=set(), permitir_avulsas=False)
    assert len(escolhidos_padrao) == 2
    assert [g["evento"] for g in escolhidos_padrao] == ["G2", "G1"]

    # Com permitir_avulsas=True, completa até 5 com as mais relevantes não repetidas
    escolhidos, desc = ranquear(grupos, min_fontes=2, max_posts=5, links_publicados=set(), permitir_avulsas=True)
    assert len(escolhidos) == 5
    # Os 2 repetidos vêm primeiro
    assert escolhidos[0]["evento"] == "G2"
    assert escolhidos[1]["evento"] == "G1"
    # E os 3 avulsos mais relevantes completam a cota
    assert escolhidos[2]["evento"] == "Avulso Alta Relevancia 1"
    assert escolhidos[3]["evento"] == "Avulso Alta Relevancia 2"
    assert escolhidos[4]["evento"] == "Avulso Media Relevancia"
    # O avulso de baixa relevância foi descartado
    assert any("Avulso Baixa Relevancia" in d[0] for d in desc)


def test_loop_autocorrecao_e_fila_de_suplentes(tmp_path):
    from agente_noticias.pipeline import executar
    from tests.test_agente import AGORA, FONTES, RESUMO_BOM

    auditoria_reprovada = {
        "veredito": "reprovado",
        "motivo_veredito": "Adjetivo sem suporte na fonte",
        "fidelidade_factual": [{"alegacao": "Demanda fraca", "status": "contradita", "citacao_fonte": "taxa de 4,5%", "fonte_nome": "Fonte A"}],
        "conferencia_numerica": [],
        "contexto_e_ressalvas": {"preservado": True, "ressalvas_omitidas": []},
        "neutralidade_e_tom": {"neutro": True, "problemas": []},
        "divergencias_fontes": [],
    }
    auditoria_aprovada = {
        "veredito": "aprovado",
        "motivo_veredito": "Corrigido e comprovado nas fontes",
        "fidelidade_factual": [{"alegacao": "Juros a 4,5%", "status": "confirmada", "citacao_fonte": "4.5%", "fonte_nome": "Fonte A"}],
        "conferencia_numerica": [{"indicador": "4,5%", "status": "correto", "detalhe": "OK"}],
        "contexto_e_ressalvas": {"preservado": True, "ressalvas_omitidas": []},
        "neutralidade_e_tom": {"neutro": True, "problemas": []},
        "divergencias_fontes": [],
    }

    resumo_petroleo = dict(
        RESUMO_BOM,
        titulo="Petróleo fecha em queda de 2% no mercado global",
        descricao="O barril do Brent recuou para US$ 71,20 com ajustes na oferta internacional de energia.",
        corpo="O preço do petróleo fechou em queda de 2% nesta sessão.\n\nO barril do tipo Brent recuou para US$ 71,20 no mercado internacional.\n\nOperadores acompanham os desdobramentos sobre a oferta global.",
        pontos=["Petróleo cai 2%", "Brent recua para US$ 71,20", "Mercado acompanha oferta"],
    )

    class LLMFluxoCompleto:
        def __init__(self):
            self.resumos = [
                # Pauta 1: rascunho inicial + reescrita que ainda falha
                dict(RESUMO_BOM, titulo="Pauta 1 Rascunho Inicial"),
                dict(RESUMO_BOM, titulo="Pauta 1 Reescrita"),
                # Pauta 2 (suplente acionada): rascunho inicial reprovado + reescrita corrigida e aprovada!
                dict(resumo_petroleo, titulo="Pauta 2 Suplente Inicial"),
                dict(resumo_petroleo, titulo="Pauta 2 Suplente Corrigida"),
            ]
            self.auditorias = [
                auditoria_reprovada,  # Pauta 1 tentativa 1 -> reprovada
                auditoria_reprovada,  # Pauta 1 após reescrita -> continua reprovada (aciona suplente!)
                auditoria_reprovada,  # Pauta 2 tentativa 1 -> reprovada
                auditoria_aprovada,   # Pauta 2 após auto-correção -> APROVADA!
            ]

        def chamar_ferramenta(self, modelo, sistema, mensagem, nome, descricao, esquema):
            if nome == "registrar_grupos":
                return {
                    "grupos": [
                        {"evento": "Juros na Exemplândia", "itens": [0, 2, 4], "categoria": "politica_monetaria", "relevancia": 5, "repete_publicado": False, "alcance_economico": "internacional", "canal_economico": "juros"},
                        {"evento": "Petróleo global", "itens": [3], "categoria": "commodities_e_energia", "relevancia": 4, "repete_publicado": False, "alcance_economico": "global", "canal_economico": "energia"},
                    ]
                }
            if nome == "registrar_resumo":
                return self.resumos.pop(0)
            if nome == "registrar_auditoria":
                return self.auditorias.pop(0)
            raise ValueError(nome)

        def relatorio(self):
            return {"por_modelo": {}, "custo_estimado_usd": 0.01}

    cfg = {
        "janela_horas": 24,
        "max_itens_por_fonte": 30,
        "min_fontes": 2,
        "max_posts": 1,
        "permitir_avulsas": True,
        "tentativas_auditoria": 1,
        "extrair_texto": False,
        "modelos": {"agrupar": "m", "resumir": "m", "auditar": "m"},
        "publicacao": {"tipo": "arquivo", "pasta": "saida/posts", "git": "nenhum"},
    }
    rel = executar(cfg, FONTES, LLMFluxoCompleto(), tmp_path, seco=True, log=lambda *_: None, agora=AGORA)
    # Pauta 1 foi reprovada mesmo após reescrita -> Pauta 2 (suplente) entrou, foi corrigida pelo loop e aprovada!
    assert len(rel["posts"]) == 2
    assert rel["posts"][0]["veredito"] == "reprovado"
    assert rel["posts"][1]["veredito"] == "aprovado"
    assert rel["posts"][1]["titulo"] == "Pauta 2 Suplente Corrigida"


