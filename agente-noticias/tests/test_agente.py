import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from agente_noticias.agrupar import ranquear, validar_grupos
from agente_noticias.coletar import coletar, normalizar_link
from agente_noticias.llm import ClienteLLM
from agente_noticias.pipeline import executar
from agente_noticias.extrair import imagem_da_pagina
from agente_noticias.publicar import gerar_slug, noticia_para_site, renderizar_mdx
from agente_noticias.verificar import checar, numeros_sem_fonte, problemas_de_estilo

FIXTURES = Path(__file__).parent / "fixtures"
AGORA = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
FONTES = [
    {"nome": "Fonte A", "idioma": "en", "url": str(FIXTURES / "fonte_a.xml")},
    {"nome": "Fonte B", "idioma": "pt", "url": str(FIXTURES / "fonte_b.xml")},
    {"nome": "Fonte C", "idioma": "en", "url": str(FIXTURES / "fonte_c.xml")},
    {"nome": "Quebrada", "idioma": "pt", "url": str(FIXTURES / "quebrado.xml")},
]

RESUMO_BOM = {
    "titulo": "Banco central da Exemplândia sobe juros para 4,5% e surpreende o mercado",
    "descricao": "A alta de 0,25 ponto foi justificada pela inflação de 3,8% em setembro; analistas esperavam manutenção em 4,25%.",
    "corpo": "O banco central da Exemplândia elevou a taxa básica em 0,25 ponto, para 4,5% ao ano.\n\nA decisão foi atribuída à inflação de 3,8% em setembro. Segundo a Fonte C, analistas esperavam que a taxa ficasse em 4,25%.\n\nA moeda local subiu 1,1% frente ao dólar, de acordo com a Fonte C.",
    "pontos": ["Juros sobem para 4,5%", "Inflação de 3,8% em setembro", "Mercado esperava 4,25%"],
    "divergencias": "",
    "tags": ["juros", "bancos centrais"],
    "alcance": "regional",
    "editoria": "Macroeconomia",
    "chapeu": "POLÍTICA MONETÁRIA",
    "gravidade": "Aperto Monetário",
    "local": "Exemplândia",
    "paises": ["Exemplândia", "Vizinhândia"],
}
RESUMO_RUIM = dict(RESUMO_BOM, corpo=RESUMO_BOM["corpo"] + "\n\nVale ressaltar que o PIB cresceu 2,7% — um marco.")


class ClienteFalso:
    def __init__(self, resumos):
        self.resumos = list(resumos)
        self.chamadas = []

    def create(self, **kw):
        self.chamadas.append(kw)
        nome = kw["tool_choice"]["name"]
        if nome == "registrar_grupos":
            texto = kw["messages"][0]["content"]
            ids_juros = [int(i) for i in re.findall(r"\[(\d+)\][^\n]*(?:Exampleland|Exemplândia)", texto)]
            ids_petroleo = [int(i) for i in re.findall(r"\[(\d+)\][^\n]*Petróleo", texto)]
            entrada = {"grupos": [
                {"evento": "Banco central da Exemplândia sobe juros para 4,5%", "itens": ids_juros + [999], "categoria": "politica_monetaria", "relevancia": 4, "repete_publicado": "Exemplândia sobe juros" in texto.split("Manchetes:")[0]},
                {"evento": "Petróleo cai 2%", "itens": ids_petroleo + ids_juros[:1], "categoria": "commodities_e_energia", "relevancia": 3, "repete_publicado": False},
            ]}
        else:
            entrada = self.resumos.pop(0)
        return SimpleNamespace(
            content=[SimpleNamespace(type="tool_use", name=nome, input=entrada)],
            usage=SimpleNamespace(input_tokens=2000, output_tokens=500),
        )


def cliente(resumos):
    falso = ClienteFalso(resumos)
    return ClienteLLM(cliente=SimpleNamespace(messages=falso), precos={"claude-haiku-5-5": [0.10, 0.50]}), falso


def cfg_base(**publicacao):
    return {
        "janela_horas": 24, "max_itens_por_fonte": 30, "min_fontes": 2, "max_posts": 3,
        "extrair_texto": False, "modelos": {"agrupar": "claude-haiku-5-5", "resumir": "claude-haiku-5-5"},
        "publicacao": {"tipo": "arquivo", "pasta": "saida/posts", "git": "nenhum", **publicacao},
    }


def test_coleta_filtra_janela_duplicatas_e_feed_quebrado():
    itens, info = coletar(FONTES, 24, agora=AGORA, log=lambda *_: None)
    titulos = [i.titulo for i in itens]
    assert titulos.count("Exampleland central bank raises rates to 4.5%") == 1
    assert "Old story from last week" not in titulos
    assert info["por_fonte"] == {"Fonte A": 2, "Fonte B": 2, "Fonte C": 1}
    assert "Quebrada" in info["erros"]
    assert "<p>" not in itens[0].descricao
    assert itens[0].link == "https://fonte-a.test/juros"


def test_normalizar_link_remove_rastreio():
    assert normalizar_link("https://X.com/a/?utm_source=rss&id=3") == "https://x.com/a?id=3"


def test_grupos_descartam_ids_inventados_e_exigem_duas_fontes():
    itens, _ = coletar(FONTES, 24, agora=AGORA, log=lambda *_: None)
    brutos = [
        {"evento": "juros", "itens": [0, 2, 3, 999, 0], "categoria": "x", "relevancia": 4, "repete_publicado": False},
        {"evento": "petróleo", "itens": [3], "categoria": "x", "relevancia": 3, "repete_publicado": False},
    ]
    grupos = validar_grupos(brutos, itens)
    assert [len(g["itens"]) for g in grupos] == [3]
    escolhidos, descartados = ranquear(validar_grupos([dict(brutos[0], itens=[0, 2]), dict(brutos[1], itens=[3])], itens), 2, 3, set())
    assert [g["evento"] for g in escolhidos] == ["juros"]
    assert descartados == [("petróleo", "1 veículo(s), mínimo 2")]


def test_numeros_conferidos_contra_fontes():
    fontes = ["rate to 4.5% with inflation of 3.8%", "1,200 jobs and 2026 outlook"]
    assert numeros_sem_fonte("Juros de 4,5% e inflação de 3,8%; 1.200 vagas em 2026.", fontes, 2026) == []
    assert numeros_sem_fonte("O PIB cresceu 2,7% e 15 bancos subiram.", fontes, 2026) == ["15", "2,7"]


def test_estilo_detecta_padroes_de_ia():
    achados = problemas_de_estilo("A decisão — inesperada — desempenha um papel fundamental. Vale ressaltar.")
    assert any("travessão" in a for a in achados)
    assert any("papel fundamental" in a for a in achados)
    assert problemas_de_estilo("Os juros subiram 0,25 ponto, entre 30–40 analistas.") == []


def test_pipeline_seco_tenta_de_novo_e_nao_publica(tmp_path):
    llm, falso = cliente([RESUMO_RUIM, RESUMO_BOM])
    rel = executar(cfg_base(), FONTES, llm, tmp_path, seco=True, log=lambda *_: None, agora=AGORA)
    assert [p["status"] for p in rel["posts"]] == ["pronto"]
    resumos = [c for c in falso.chamadas if c["tool_choice"]["name"] == "registrar_resumo"]
    assert len(resumos) == 2 and "números que não aparecem" in resumos[1]["messages"][0]["content"]
    assert list((tmp_path / "saida/seco").glob("*.mdx"))
    assert not (tmp_path / "dados/estado.json").exists()
    assert rel["uso"]["custo_estimado_usd"] > 0


def test_pipeline_manda_para_revisar_quando_nao_corrige(tmp_path):
    llm, _ = cliente([RESUMO_RUIM, RESUMO_RUIM])
    rel = executar(cfg_base(), FONTES, llm, tmp_path, log=lambda *_: None, agora=AGORA)
    assert rel["posts"][0]["status"] == "revisar"
    assert "/saida/revisar/" in rel["posts"][0]["destino"]
    assert not list((tmp_path / "saida/posts").glob("*.mdx"))


def preparar_repo_com_remoto(tmp_path, remoto, repo):
    # git init -b só existe a partir do git 2.28; symbolic-ref funciona em versões antigas
    for caminho, extra in ((remoto, ["--bare"]), (repo, [])):
        subprocess.run(["git", "init", "-q", *extra, str(caminho)], check=True)
        subprocess.run(["git", "-C", str(caminho), "symbolic-ref", "HEAD", "refs/heads/main"], check=True)
    for k, v in (("user.email", "t@t"), ("user.name", "t")):
        subprocess.run(["git", "-C", str(repo), "config", k, v], check=True)
    (repo / "README.md").write_text("blog\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "chore: first commit"], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(remoto)], check=True)
    subprocess.run(["git", "-C", str(repo), "push", "-q", "origin", "main"], check=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text('#!/bin/bash\nif [ "$1 $2" = "pr view" ]; then exit 1; fi\necho https://github.com/x/y/pull/1\n')
    (bin_dir / "gh").chmod(0o755)
    os.environ["PATH"] = f"{bin_dir}:{os.environ['PATH']}"


def test_pipeline_publica_em_repo_via_pr_e_nao_repete(tmp_path):
    remoto = tmp_path / "remoto.git"
    repo = tmp_path / "blog"
    preparar_repo_com_remoto(tmp_path, remoto, repo)

    cfg = cfg_base(repositorio=str(repo), pasta="src/content/posts", git="pr", separador_slug="_",
                   frontmatter_extra={"author": "Ronald Andrade", "difficulty": "beginner"})
    llm, _ = cliente([RESUMO_BOM])
    rel = executar(cfg, FONTES, llm, tmp_path / "agente", log=lambda *_: None, agora=AGORA)
    assert rel["git"] == {"modo": "pr", "url": "https://github.com/x/y/pull/1"}
    branches = subprocess.run(["git", "-C", str(remoto), "branch"], capture_output=True, text=True).stdout
    assert "noticias/" in branches
    # depois do PR o repositório volta para a main; o post está na branch do agente
    branch = "noticias/" + rel["inicio"][:10]
    nome = subprocess.run(["git", "-C", str(remoto), "show", "--name-only", "--format=", branch], capture_output=True, text=True).stdout.strip()
    assert re.fullmatch(r"src/content/posts/[a-z0-9_]+\.mdx", nome)
    texto = subprocess.run(["git", "-C", str(remoto), "show", f"{branch}:{nome}"], capture_output=True, text=True).stdout
    assert texto.startswith("---\ntitle: ") and '"author": ' not in texto and 'author: "Ronald Andrade"' in texto
    assert "## Fontes" in texto and "https://fonte-b.test/economia/juros-exemplandia" in texto

    llm2, falso2 = cliente([RESUMO_BOM])
    rel2 = executar(cfg, FONTES, llm2, tmp_path / "agente", log=lambda *_: None, agora=AGORA)
    assert rel2["posts"] == []
    assert any(motivo == "já publicado" for _, motivo in rel2["descartados"])


def test_mdx_valida_no_padrao_do_blog(tmp_path):
    post = dict(RESUMO_BOM, fontes=[{"nome": "Fonte A", "titulo": "Rates [up] <now>", "link": "https://a.test/x"}])
    texto = renderizar_mdx(post, "2026-10-26", {"author": "Ronald Andrade"})
    assert 'date: "2026-10-26"' in texto
    assert "Rates \\[up\\] \\<now\\>" in texto
    assert "\n# " not in texto
    assert gerar_slug("Banco Central sobe juros: 4,5%!", "_") == "banco_central_sobe_juros_4_5"
    assert gerar_slug("Banco central da Exemplândia sobe juros para 4,5% e surpreende o mercado", "_") == "banco_central_da_exemplandia_sobe_juros_para_4_5_e"


def test_extrai_texto_do_artigo_com_trafilatura(tmp_path):
    from agente_noticias.extrair import texto_do_artigo
    pagina = tmp_path / "artigo.html"
    paragrafo = "The central bank of Exampleland raised its key interest rate to 4.5 percent on Monday. " * 6
    pagina.write_text(f"<html><head><title>x</title></head><body><nav>Menu Home Sports</nav><article><h1>Rates up</h1><p>{paragrafo}</p><p>{paragrafo}</p></article><footer>Cookies</footer></body></html>")
    texto = texto_do_artigo(str(pagina))
    assert "4.5 percent" in texto and "Cookies" not in texto


def test_coleta_guarda_a_maior_imagem_do_feed():
    itens, _ = coletar(FONTES, 24, agora=AGORA, log=lambda *_: None)
    juros_b = next(i for i in itens if i.fonte == "Fonte B" and "juros" in i.link)
    assert juros_b.imagem == "https://fonte-b.test/img/grande.jpg"
    assert next(i for i in itens if i.fonte == "Fonte A").imagem == ""


def test_mesmo_veiculo_conta_como_uma_fonte():
    fontes = [dict(FONTES[0], grupo="Rede X"), dict(FONTES[1], grupo="Rede X"), FONTES[2]]
    itens, _ = coletar(fontes, 24, agora=AGORA, log=lambda *_: None)
    juros_a_b = [i.id for i in itens if "juros" in i.link]
    grupos = validar_grupos([{"evento": "juros", "itens": juros_a_b, "categoria": "x", "relevancia": 4, "repete_publicado": False}], itens)
    assert grupos[0]["fontes"] == ["Fonte A", "Fonte B"] and grupos[0]["veiculos"] == ["Rede X"]
    escolhidos, descartados = ranquear(grupos, 2, 3, set())
    assert escolhidos == [] and descartados == [("juros", "1 veículo(s), mínimo 2")]


def test_imagem_og_da_pagina():
    pagina = '<head><meta property="og:image" content="/fotos/a.jpg?w=1200&amp;h=630"></head>'
    assert imagem_da_pagina(pagina, "https://site.test/noticia/1") == "https://site.test/fotos/a.jpg?w=1200&h=630"
    assert imagem_da_pagina("<head></head>", "https://site.test/") == ""


def test_noticia_no_formato_do_site():
    post = dict(RESUMO_BOM, destaque=True, imagem="https://fonte-b.test/img/grande.jpg", credito_imagem="Fonte B",
                divergencias="A Fonte C fala em 4,25%.",
                fontes=[{"nome": "Fonte B", "titulo": "Juros", "link": "https://b.test/1"}, {"nome": "Fonte C", "titulo": "Hike", "link": "https://c.test/2"}])
    n = noticia_para_site(post, "2026-10-26", "banco-central-sobe-juros")
    assert n["featured"] is True and n["impactScope"] == "regional" and n["impactLabel"] == "Impacto nos Países Vizinhos"
    assert n["inRadar"] is True and n["corridorTag"] == "EXEMPLÂNDIA • VIZINHÂNDIA"
    assert n["category"] == "Macroeconomia" and n["kicker"] == "POLÍTICA MONETÁRIA"
    assert len(n["body"]) == 4 and n["body"][-1].startswith("Onde as fontes divergem")
    assert n["author"] == "MERIDIAN, com base em Fonte B e Fonte C"
    assert n["source"] == "Fonte B / Fonte C" and n["sourceUrl"] == "https://b.test/1" and len(n["sources"]) == 2
    assert n["image"].endswith("grande.jpg") and n["imageCaption"] == "Foto: Fonte B."
    assert n["keyPoints"] == RESUMO_BOM["pontos"] and n["generatedByAI"] is True


def test_pipeline_publica_json_no_site_via_pr(tmp_path):
    remoto, repo = tmp_path / "remoto.git", tmp_path / "site"
    preparar_repo_com_remoto(tmp_path, remoto, repo)
    existente = repo / "content/noticias/2026-10-20_banco-central-da-exemplandia-sobe-juros-para-4-5-e.json"
    existente.parent.mkdir(parents=True)
    existente.write_text(json.dumps({"slug": "banco-central-da-exemplandia-sobe-juros-para-4-5-e"}))
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "docs: noticia antiga"], check=True)
    subprocess.run(["git", "-C", str(repo), "push", "-q", "origin", "main"], check=True)

    cfg = cfg_base()
    cfg["publicacao"] = {"tipo": "site_json", "repositorio": str(repo), "git": "pr"}
    llm, _ = cliente([RESUMO_BOM])
    rel = executar(cfg, FONTES, llm, tmp_path / "agente", log=lambda *_: None, agora=AGORA)
    assert rel["git"] == {"modo": "pr", "url": "https://github.com/x/y/pull/1"}
    novos = subprocess.run(["git", "-C", str(remoto), "show", "--name-only", "--format=", "refs/heads/noticias/" + rel["inicio"][:10]],
                           capture_output=True, text=True).stdout.split()
    assert len(novos) == 1 and novos[0].startswith("content/noticias/") and novos[0].endswith(".json")
    # o slug já existia: ganha sufixo para não quebrar o build do site
    assert novos[0].endswith("_banco-central-da-exemplandia-sobe-juros-para-4-5-e-2.json")
    # o repositório volta para a branch em que estava
    assert subprocess.run(["git", "-C", str(repo), "branch", "--show-current"], capture_output=True, text=True).stdout.strip() == "main"
    conteudo = subprocess.run(["git", "-C", str(remoto), "show", f"refs/heads/noticias/{rel['inicio'][:10]}:{novos[0]}"],
                              capture_output=True, text=True).stdout
    noticia = json.loads(conteudo)
    assert re.fullmatch(r"[a-z0-9-]+", noticia["slug"]) and noticia["featured"] is True
    assert noticia["image"] == "https://fonte-b.test/img/grande.jpg"
    assert {f["url"] for f in noticia["sources"]} >= {"https://fonte-b.test/economia/juros-exemplandia"}


def test_modo_seco_grava_json_quando_publica_no_site(tmp_path):
    cfg = cfg_base()
    cfg["publicacao"] = {"tipo": "site_json", "repositorio": str(tmp_path / "nao-usado"), "git": "pr"}
    llm, _ = cliente([RESUMO_BOM])
    executar(cfg, FONTES, llm, tmp_path, seco=True, log=lambda *_: None, agora=AGORA)
    arquivos = list((tmp_path / "saida/seco").glob("*.json"))
    assert len(arquivos) == 1 and json.loads(arquivos[0].read_text())["category"] == "Macroeconomia"


def test_baixar_descompacta_gzip(tmp_path, monkeypatch):
    import gzip
    import io
    from agente_noticias import coletar as modulo

    class Resposta(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(modulo.urllib.request, "urlopen", lambda *a, **k: Resposta(gzip.compress(b"<rss/>")))
    assert modulo.baixar("https://feed.test/rss") == b"<rss/>"
