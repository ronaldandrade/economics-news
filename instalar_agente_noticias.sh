#!/usr/bin/env bash
set -euo pipefail
DESTINO="${1:-$HOME/agente-noticias}"
[[ -e "$DESTINO" ]] && { echo "ERRO: $DESTINO já existe"; exit 1; }
mkdir -p "$DESTINO"
cd "$DESTINO"
mkdir -p "."
cat > "./.gitignore" <<'FIM_DO_ARQUIVO_AGENTE'
.venv/
__pycache__/
.pytest_cache/
config.json
saida/
dados/
logs/
.env
FIM_DO_ARQUIVO_AGENTE
mkdir -p "."
cat > "./README.md" <<'FIM_DO_ARQUIVO_AGENTE'
# agente-noticias

Agente que lê vários sites de notícias, encontra os acontecimentos de economia mundial que **aparecem em mais de um site**, escreve um resumo em português juntando o que cada fonte diz e publica no seu site.

```
fontes.json ──► 1. coletar ──► 2. agrupar ──► 3. resumir ──► 4. verificar ──► 5. publicar
 (RSS)          manchetes      mesmo fato     texto novo     números e      MDX no repo (PR)
                das últimas    em ≥ 2 sites   com fontes     estilo         ou API do site
                24 h           (pt e en)      atribuídas         │
                                                                 └─ falhou 2× ─► saida/revisar/
```

## Como funciona cada etapa

| Etapa | Arquivo | Quem decide | O que faz |
|---|---|---|---|
| Coletar | `coletar.py` | código | Lê os feeds RSS de `fontes.json`, fica com as manchetes da janela (`janela_horas`), remove duplicatas e parâmetros de rastreio (`utm_*`) dos links. Um feed fora do ar não derruba os outros. |
| Agrupar | `agrupar.py` | IA + código | O modelo recebe todas as manchetes numeradas e junta as que tratam do **mesmo fato**, inclusive entre português e inglês, descartando o que não é economia mundial. O código então confere: descarta números de itens inventados, impede item em dois grupos e **exige `min_fontes` sites diferentes**. Os grupos são ordenados por número de sites, depois relevância, depois recência. |
| Não repetir | `estado.py` | IA + código | `dados/estado.json` guarda o que foi publicado nos últimos `dias_memoria` dias. Um grupo é descartado se metade dos links já foi publicada ou se o modelo marca que é o mesmo acontecimento sem fato novo. |
| Resumir | `extrair.py`, `resumir.py` | IA | Baixa o texto de cada artigo (com `trafilatura`; se der paywall, usa o resumo do feed) e pede um resumo original, com números atribuídos às fontes e um campo de divergências. |
| Verificar | `verificar.py` | código | **Todo número do resumo precisa aparecer em alguma fonte** (aceita 4.5 = 4,5 e 1,200 = 1.200). Também barra travessão, "vale ressaltar", "papel fundamental" e outros padrões da skill `humanizar`. Se falhar, o modelo recebe a lista de problemas e tenta de novo; se falhar outra vez, o post vai para `saida/revisar/` e **não é publicado**. |
| Publicar | `publicar.py` | código | Grava o `.mdx` (frontmatter + resumo + "Em resumo" + divergências + lista de fontes com links) ou envia para a API do site. |

A IA nunca decide sozinha o que é verdade: as regras que importam (mínimo de fontes, números com fonte, não repetir) são verificadas em código.

## Instalação

```bash
cd ~
# copie a pasta agente-noticias para ~/agente-noticias
cd ~/agente-noticias
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp config.exemplo.json config.json
mkdir -p ~/.config/agente-noticias
install -m 600 /dev/null ~/.config/agente-noticias/env
echo 'ANTHROPIC_API_KEY=sk-ant-...' > ~/.config/agente-noticias/env
```

Teste os feeds (as URLs de `fontes.json` não puderam ser testadas daqui; remova as que falharem):

```bash
.venv/bin/python -m agente_noticias verificar-feeds
```

Primeira execução, sem publicar nada:

```bash
set -a; . ~/.config/agente-noticias/env; set +a
.venv/bin/python -m agente_noticias executar --seco
```

Leia os arquivos em `saida/seco/`. Rode umas 3 ou 4 vezes em dias diferentes antes de ligar a publicação.

## Configuração (`config.json`)

| Campo | Padrão | Efeito |
|---|---|---|
| `janela_horas` | 24 | idade máxima das manchetes |
| `min_fontes` | 2 | quantos sites diferentes precisam noticiar o fato |
| `max_posts` | 3 | posts por execução |
| `extrair_texto` | true | baixa o artigo inteiro para o resumo (mais qualidade, mais tokens) |
| `dias_memoria` | 5 | por quantos dias um evento publicado bloqueia repetição |
| `modelos.agrupar` / `modelos.resumir` | `claude-haiku-5-5` | troque `resumir` por `claude-sonnet-5-5` para textos melhores, a ~10× o custo |

### Publicar no blog (Next.js + MDX, como o `portfolio-math`)

```json
"publicacao": {
  "tipo": "arquivo",
  "repositorio": "~/projetos/portfolio-math",
  "pasta": "src/content/posts",
  "git": "pr",
  "separador_slug": "_",
  "frontmatter_extra": {"author": "Ronald Andrade", "difficulty": "beginner"},
  "aviso_ia": true
}
```

`git` aceita:
- `"pr"`: cria a branch `noticias/AAAA-MM-DD`, commita, faz push e abre um PR com `gh`. A Vercel gera o preview e **você faz o merge**. Recomendado.
- `"commit"`: commita e faz push direto na branch atual. Se for a `main`, publica sem revisão.
- `"nenhum"`: só grava os arquivos.

O repositório precisa estar sem alterações pendentes, e o `gh` precisa estar logado (`gh auth login`). O MDX gerado passa no validador do blog (`validar_post.mjs`).

### Publicar em outro site (API)

```json
"publicacao": {
  "tipo": "http",
  "url": "https://seusite.com.br/api/noticias",
  "variavel_token": "NOTICIAS_TOKEN"
}
```

Envia um `POST` JSON com `titulo`, `descricao`, `conteudo_markdown`, `pontos`, `tags`, `fontes`, `data` e `categoria`, e o cabeçalho `Authorization: Bearer <token>`. O token vai no mesmo arquivo `env`.

### Fontes (`fontes.json`)

Cada fonte tem `nome`, `idioma` (`pt` ou `en`) e `url` do feed RSS. Quanto mais fontes de países diferentes, melhor o critério "repetido entre sites" separa o que é importante do que é pauta de um veículo só. Feeds de seção (economia) rendem mais que feeds gerais.

## Agendar (2× por dia)

```bash
mkdir -p ~/.config/systemd/user
cp systemd/agente-noticias.* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now agente-noticias.timer
systemctl --user list-timers agente-noticias.timer
journalctl --user -u agente-noticias -n 50
```

Para rodar com o notebook desligado, deixe o timer no desktop.

## Custo

Com Haiku 5.5 e 11 fontes, cada execução usa cerca de 20 a 40 mil tokens: menos de US$ 0,02. Cada execução grava em `logs/` um relatório com as manchetes por fonte, os grupos formados, os descartados (e por quê), os posts e o custo estimado. Os preços em `precos_por_milhao` são estimativas; o valor real fica no Console da Anthropic.

## Testes

```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q tests
```

Os testes rodam sem internet e sem chave de API: usam feeds de exemplo em `tests/fixtures/` (com uma fonte quebrada de propósito) e um cliente de IA falso. Cobrem coleta, agrupamento, a checagem de números, a nova tentativa, o envio para revisão, a publicação por PR num repositório Git local e o bloqueio de repetição na segunda execução.

## Limitações

- **Agrupamento por IA pode errar.** Dois fatos parecidos (duas decisões de juros no mesmo dia) podem cair juntos. O relatório em `logs/` mostra cada grupo e suas fontes.
- **A checagem de números não pega atribuição errada.** Se a fonte A diz 4,5% e o resumo atribui o número à fonte B, passa. Por isso o modo `pr` é o padrão.
- **Paywall.** Sites fechados entregam só o resumo do feed; o texto do post fica mais raso para esse acontecimento.
- **Direitos autorais.** O agente escreve um texto próprio e linka as fontes, com no máximo uma citação curta. Não altere o prompt para reproduzir os artigos.
- **Feeds mudam.** Rode `verificar-feeds` quando uma fonte parar de aparecer nos relatórios.
FIM_DO_ARQUIVO_AGENTE
mkdir -p "./agente_noticias"
cat > "./agente_noticias/__init__.py" <<'FIM_DO_ARQUIVO_AGENTE'
__version__ = "1.0.0"
FIM_DO_ARQUIVO_AGENTE
mkdir -p "./agente_noticias"
cat > "./agente_noticias/__main__.py" <<'FIM_DO_ARQUIVO_AGENTE'
import argparse
import json
import os
import sys
from pathlib import Path

from .coletar import verificar_fontes
from .llm import ClienteLLM
from .pipeline import executar

RAIZ = Path(os.environ.get("AGENTE_NOTICIAS_RAIZ", Path(__file__).resolve().parent.parent))


def carregar(caminho):
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"arquivo não encontrado: {caminho}")
    except ValueError as e:
        sys.exit(f"JSON inválido em {caminho}: {e}")


def main():
    p = argparse.ArgumentParser(prog="agente_noticias", description="Agente que resume as notícias de economia mundial repetidas entre vários sites.")
    sub = p.add_subparsers(dest="comando", required=True)
    e = sub.add_parser("executar", help="coleta, agrupa, resume e publica")
    e.add_argument("--seco", action="store_true", help="não publica nem grava estado; salva os posts em saida/seco")
    e.add_argument("--config", default=str(RAIZ / "config.json"))
    e.add_argument("--fontes", default=str(RAIZ / "fontes.json"))
    v = sub.add_parser("verificar-feeds", help="testa se cada feed responde")
    v.add_argument("--fontes", default=str(RAIZ / "fontes.json"))
    args = p.parse_args()

    if args.comando == "verificar-feeds":
        falhas = 0
        for nome, ok, detalhe in verificar_fontes(carregar(args.fontes)["fontes"]):
            print(f"  {'✓' if ok else '✗'} {nome:<28} {detalhe}")
            falhas += not ok
        sys.exit(1 if falhas else 0)

    cfg = carregar(args.config)
    fontes = carregar(args.fontes)["fontes"]
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("defina ANTHROPIC_API_KEY (chave da API da Anthropic)")
    llm = ClienteLLM(max_tokens=cfg.get("max_tokens", 4096), precos=cfg.get("precos_por_milhao"))
    relatorio = executar(cfg, fontes, llm, RAIZ, seco=args.seco)
    sys.exit(0 if all(p["status"] == "pronto" for p in relatorio["posts"]) else 3)


if __name__ == "__main__":
    main()
FIM_DO_ARQUIVO_AGENTE
mkdir -p "./agente_noticias"
cat > "./agente_noticias/agrupar.py" <<'FIM_DO_ARQUIVO_AGENTE'

CATEGORIAS = [
    "politica_monetaria", "inflacao", "atividade_e_emprego", "comercio_e_tarifas", "cambio",
    "commodities_e_energia", "mercados", "divida_e_fiscal", "empresas_globais", "organismos_e_acordos", "crise",
]

SISTEMA = """Você é editor de economia internacional. Recebe uma lista numerada de manchetes de vários sites de notícias, em português e em inglês.

Sua tarefa é agrupar as manchetes que tratam do MESMO acontecimento específico: o mesmo fato, na mesma data aproximada, ainda que em idiomas diferentes e com títulos diferentes. Dois textos sobre o mesmo tema geral (por exemplo, "inflação") mas sobre fatos diferentes ficam em grupos diferentes.

Considere apenas economia mundial: bancos centrais e juros, inflação, PIB e emprego, comércio internacional e tarifas, câmbio, petróleo e outras commodities, mercados financeiros globais, dívida pública e política fiscal de grandes economias, crises, organismos e acordos (FMI, Banco Mundial, OMC, G20, OPEP) e grandes empresas quando o fato afeta a economia de vários países.

Ignore: economia local sem efeito internacional, finanças pessoais, dicas de investimento, promoções, colunas de opinião, conteúdo patrocinado, esportes e celebridades.

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
                    },
                    "required": ["evento", "itens", "categoria", "relevancia", "repete_publicado"],
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
        datas = [m.publicado for m in membros if m.publicado]
        grupos.append({
            "evento": str(g.get("evento", "")).strip(),
            "categoria": g.get("categoria", ""),
            "relevancia": int(g.get("relevancia", 1)),
            "repete_publicado": bool(g.get("repete_publicado", False)),
            "itens": membros,
            "fontes": fontes,
            "mais_recente": max(datas) if datas else "",
        })
    return grupos


def ranquear(grupos, min_fontes, max_posts, links_publicados):
    candidatos, descartados = [], []
    for g in grupos:
        links = {m.link for m in g["itens"]}
        sobreposicao = len(links & links_publicados) / len(links)
        if g["repete_publicado"] or sobreposicao >= 0.5:
            descartados.append((g["evento"], "já publicado"))
        elif len(g["fontes"]) < min_fontes:
            descartados.append((g["evento"], f"{len(g['fontes'])} fonte(s), mínimo {min_fontes}"))
        else:
            candidatos.append(g)
    candidatos.sort(key=lambda g: (len(g["fontes"]), g["relevancia"], g["mais_recente"]), reverse=True)
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
FIM_DO_ARQUIVO_AGENTE
mkdir -p "./agente_noticias"
cat > "./agente_noticias/coletar.py" <<'FIM_DO_ARQUIVO_AGENTE'
import calendar
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
        return resposta.read()


def data_da_entrada(entrada):
    for chave in ("published_parsed", "updated_parsed"):
        valor = entrada.get(chave)
        if valor:
            return datetime.fromtimestamp(calendar.timegm(valor), tz=timezone.utc)
    return None


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
FIM_DO_ARQUIVO_AGENTE
mkdir -p "./agente_noticias"
cat > "./agente_noticias/estado.py" <<'FIM_DO_ARQUIVO_AGENTE'
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


class Estado:
    def __init__(self, caminho, dias_memoria=5):
        self.caminho = Path(caminho)
        self.dias_memoria = dias_memoria
        try:
            self.dados = json.loads(self.caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.dados = {"publicados": []}
        self._expirar()

    def _expirar(self):
        limite = (datetime.now(timezone.utc) - timedelta(days=self.dias_memoria)).isoformat()
        self.dados["publicados"] = [p for p in self.dados["publicados"] if p.get("em", "") >= limite]

    def eventos(self):
        return [p["evento"] for p in self.dados["publicados"]]

    def links(self):
        return {l for p in self.dados["publicados"] for l in p.get("links", [])}

    def registrar(self, evento, links, destino):
        self.dados["publicados"].append({
            "em": datetime.now(timezone.utc).isoformat(),
            "evento": evento,
            "links": sorted(links),
            "destino": destino,
        })

    def salvar(self):
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.caminho.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.dados, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.caminho)
FIM_DO_ARQUIVO_AGENTE
mkdir -p "./agente_noticias"
cat > "./agente_noticias/extrair.py" <<'FIM_DO_ARQUIVO_AGENTE'
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
FIM_DO_ARQUIVO_AGENTE
mkdir -p "./agente_noticias"
cat > "./agente_noticias/llm.py" <<'FIM_DO_ARQUIVO_AGENTE'
from collections import defaultdict


class ClienteLLM:
    def __init__(self, cliente=None, max_tokens=4096, precos=None):
        if cliente is None:
            import anthropic

            cliente = anthropic.Anthropic(max_retries=6)
        self.cliente = cliente
        self.max_tokens = max_tokens
        self.precos = precos or {}
        self.uso = defaultdict(lambda: {"chamadas": 0, "entrada": 0, "saida": 0})

    def chamar_ferramenta(self, modelo, sistema, mensagem, nome, descricao, esquema):
        resposta = self.cliente.messages.create(
            model=modelo,
            max_tokens=self.max_tokens,
            system=sistema,
            tools=[{"name": nome, "description": descricao, "input_schema": esquema}],
            tool_choice={"type": "tool", "name": nome},
            messages=[{"role": "user", "content": mensagem}],
        )
        registro = self.uso[modelo]
        registro["chamadas"] += 1
        uso = getattr(resposta, "usage", None)
        if uso is not None:
            registro["entrada"] += getattr(uso, "input_tokens", 0) or 0
            registro["saida"] += getattr(uso, "output_tokens", 0) or 0
        for bloco in resposta.content:
            if getattr(bloco, "type", None) == "tool_use" and getattr(bloco, "name", None) == nome:
                return bloco.input
        raise RuntimeError(f"o modelo {modelo} não devolveu a ferramenta {nome}")

    def custo_estimado(self):
        total = 0.0
        for modelo, u in self.uso.items():
            preco = self.precos.get(modelo)
            if preco:
                total += u["entrada"] / 1e6 * preco[0] + u["saida"] / 1e6 * preco[1]
        return round(total, 4)

    def relatorio(self):
        return {"por_modelo": dict(self.uso), "custo_estimado_usd": self.custo_estimado()}
FIM_DO_ARQUIVO_AGENTE
mkdir -p "./agente_noticias"
cat > "./agente_noticias/pipeline.py" <<'FIM_DO_ARQUIVO_AGENTE'
import json
from datetime import datetime, timezone
from pathlib import Path

from .agrupar import agrupar, ranquear
from .coletar import coletar
from .estado import Estado
from .extrair import material_do_grupo
from .publicar import PublicadorArquivo, criar_publicador
from .resumir import resumir


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
    relatorio["grupos"] = [{"evento": g["evento"], "fontes": g["fontes"], "relevancia": g["relevancia"]} for g in grupos]
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
    destino_seco = PublicadorArquivo({"pasta": "saida/seco"}, raiz)
    destino_revisar = PublicadorArquivo({"pasta": "saida/revisar"}, raiz)
    prontos = [p for p in posts if p["status"] == "pronto"]
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
FIM_DO_ARQUIVO_AGENTE
mkdir -p "./agente_noticias"
cat > "./agente_noticias/publicar.py" <<'FIM_DO_ARQUIVO_AGENTE'
import json
import os
import re
import subprocess
import unicodedata
import urllib.request
from pathlib import Path


def gerar_slug(texto, separador="-", limite=60):
    base = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    palavras = [p for p in re.split(r"[^a-z0-9]+", base) if p]
    slug = ""
    for palavra in palavras:
        candidato = f"{slug}{separador}{palavra}" if slug else palavra
        if len(candidato) > limite:
            break
        slug = candidato
    return slug or (palavras[0][:limite] if palavras else "post")


def tempo_de_leitura(texto, palavras_por_minuto=150):
    return max(1, round(len(re.findall(r"\w+", texto)) / palavras_por_minuto))


def yaml_valor(valor):
    return json.dumps(valor, ensure_ascii=False)


def renderizar_mdx(post, data, extra=None, aviso_ia=True):
    frontmatter = {
        "title": post["titulo"],
        "date": data,
        "description": post["descricao"],
        "tags": post["tags"],
        "readingTime": f"{tempo_de_leitura(post['corpo'])} min",
    }
    frontmatter.update(extra or {})
    linhas = ["---"] + [f"{chave}: {yaml_valor(valor)}" for chave, valor in frontmatter.items()] + ["---", ""]
    linhas.append(post["corpo"].strip())
    linhas += ["", "## Em resumo", ""] + [f"- {p.strip()}" for p in post["pontos"]]
    if post.get("divergencias", "").strip():
        linhas += ["", "## Onde as fontes divergem", "", post["divergencias"].strip()]
    linhas += ["", "## Fontes", ""] + [f"- {f['nome']}: [{escapar_markdown(f['titulo'])}]({f['link']})" for f in post["fontes"]]
    if aviso_ia:
        linhas += ["", "*Resumo produzido com auxílio de IA a partir das fontes acima.*"]
    return "\n".join(linhas) + "\n"


def escapar_markdown(texto):
    return re.sub(r"([\[\]{}<>])", r"\\\1", texto)


def git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} falhou: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout.strip()


class PublicadorArquivo:
    def __init__(self, cfg, raiz_agente):
        self.repo = Path(os.path.expanduser(cfg["repositorio"])) if cfg.get("repositorio") else None
        base = self.repo or Path(raiz_agente)
        self.pasta = base / cfg.get("pasta", "saida/posts")
        self.git_modo = cfg.get("git", "nenhum") if self.repo else "nenhum"
        self.separador = cfg.get("separador_slug", "-")
        self.extra = cfg.get("frontmatter_extra", {})
        self.aviso_ia = cfg.get("aviso_ia", True)
        self.prefixo_branch = cfg.get("prefixo_branch", "noticias")
        self.branch_base = cfg.get("branch_base", "main")
        self.remoto = cfg.get("remoto", "origin")
        self.escritos = []

    def preparar(self, data):
        if self.git_modo == "pr":
            if git(self.repo, "status", "--porcelain", "--untracked-files=no"):
                raise RuntimeError(f"o repositório {self.repo} tem alterações não commitadas; resolva antes de publicar")
            git(self.repo, "fetch", self.remoto, self.branch_base)
            branch = f"{self.prefixo_branch}/{data}"
            existentes = git(self.repo, "branch", "--list", branch)
            if existentes:
                git(self.repo, "switch", branch)
            else:
                git(self.repo, "switch", "-c", branch, f"{self.remoto}/{self.branch_base}")
            self.branch = branch

    def publicar(self, post, data):
        self.pasta.mkdir(parents=True, exist_ok=True)
        slug = gerar_slug(post["titulo"], self.separador)
        caminho = self.pasta / f"{slug}.mdx"
        n = 2
        while caminho.exists():
            caminho = self.pasta / f"{slug}{self.separador}{n}.mdx"
            n += 1
        caminho.write_text(renderizar_mdx(post, data, self.extra, self.aviso_ia), encoding="utf-8")
        self.escritos.append((caminho, post["titulo"]))
        return str(caminho)

    def finalizar(self, data):
        if self.git_modo == "nenhum" or not self.escritos:
            return None
        for caminho, _ in self.escritos:
            git(self.repo, "add", str(caminho.relative_to(self.repo)))
        corpo = "\n".join(f"- {titulo}" for _, titulo in self.escritos)
        mensagem = f"docs(noticias): adiciona resumos de economia de {data}\n\nResumos gerados pelo agente de notícias:\n{corpo}\n"
        git(self.repo, "commit", "-m", mensagem)
        if self.git_modo == "commit":
            git(self.repo, "push", self.remoto, "HEAD")
            return {"modo": "commit", "commit": git(self.repo, "rev-parse", "--short", "HEAD")}
        git(self.repo, "push", "-u", self.remoto, self.branch)
        existente = subprocess.run(["gh", "pr", "view", self.branch, "--json", "url", "-q", ".url"], cwd=self.repo, capture_output=True, text=True)
        if existente.returncode == 0:
            return {"modo": "pr", "url": existente.stdout.strip()}
        criado = subprocess.run(
            ["gh", "pr", "create", "--base", self.branch_base, "--head", self.branch,
             "--title", f"Notícias de economia: {data}",
             "--body", f"Resumos gerados pelo agente de notícias.\n\n{corpo}\n\nConfira o preview antes do merge."],
            cwd=self.repo, capture_output=True, text=True,
        )
        if criado.returncode != 0:
            raise RuntimeError(f"gh pr create falhou: {criado.stderr.strip()}")
        return {"modo": "pr", "url": criado.stdout.strip()}


class PublicadorHTTP:
    def __init__(self, cfg, raiz_agente=None):
        self.url = cfg["url"]
        self.token = os.environ.get(cfg.get("variavel_token", "NOTICIAS_TOKEN"), "")
        self.timeout = cfg.get("timeout", 30)

    def preparar(self, data):
        if not self.token:
            raise RuntimeError("token da API do site não definido (variável de ambiente indicada em variavel_token)")

    def publicar(self, post, data):
        corpo = {
            "titulo": post["titulo"], "descricao": post["descricao"], "conteudo_markdown": renderizar_mdx(post, data, aviso_ia=True).split("---", 2)[2].strip(),
            "pontos": post["pontos"], "tags": post["tags"], "fontes": post["fontes"], "data": data, "categoria": post.get("categoria"),
        }
        pedido = urllib.request.Request(
            self.url, data=json.dumps(corpo, ensure_ascii=False).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.token}"},
        )
        with urllib.request.urlopen(pedido, timeout=self.timeout) as resposta:
            return f"HTTP {resposta.status}"

    def finalizar(self, data):
        return None


def criar_publicador(cfg, raiz_agente):
    tipo = cfg.get("tipo", "arquivo")
    if tipo == "arquivo":
        return PublicadorArquivo(cfg, raiz_agente)
    if tipo == "http":
        return PublicadorHTTP(cfg, raiz_agente)
    raise ValueError(f"tipo de publicação desconhecido: {tipo}")
FIM_DO_ARQUIVO_AGENTE
mkdir -p "./agente_noticias"
cat > "./agente_noticias/resumir.py" <<'FIM_DO_ARQUIVO_AGENTE'
from .verificar import checar

SISTEMA = """Você é jornalista de economia e escreve em português do Brasil para um público curioso, mas não especialista.

Você recebe o mesmo acontecimento contado por vários sites. Escreva um resumo original que junte o que as fontes dizem.

Fatos:
- Use apenas informações presentes nos textos fornecidos. Não acrescente contexto, números, datas ou nomes de memória.
- Copie números exatamente como estão nas fontes; pode trocar ponto decimal por vírgula e traduzir a unidade.
- Quando um número ou uma declaração vier de uma fonte só, atribua: "segundo a BBC", "de acordo com a CNBC".
- Quando as fontes discordarem, diga isso no campo "divergencias".
- Não especule sobre consequências que as fontes não mencionam.

Direitos autorais:
- Escreva com suas palavras. Não copie frases das fontes.
- No máximo uma citação direta curta (até 15 palavras), entre aspas e atribuída.

Estilo:
- Frases diretas. Comece pelo fato principal, sem introdução.
- Proibido: travessão, "não é só X, é Y", "vale ressaltar", "é importante destacar", "papel fundamental", "crucial", "cenário", "panorama", frase final de efeito ("resta saber", "o futuro é promissor"), negrito, emoji.
- "corpo" em Markdown simples, de 3 a 5 parágrafos, sem títulos."""

FERRAMENTA = {
    "nome": "registrar_resumo",
    "descricao": "Registra o resumo do acontecimento.",
    "esquema": {
        "type": "object",
        "properties": {
            "titulo": {"type": "string", "description": "Título informativo, até 90 caracteres."},
            "descricao": {"type": "string", "description": "Uma ou duas frases para listagem e SEO, 80 a 220 caracteres."},
            "corpo": {"type": "string"},
            "pontos": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 5},
            "divergencias": {"type": "string", "description": "Onde as fontes discordam. Vazio se concordam."},
            "tags": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 5},
        },
        "required": ["titulo", "descricao", "corpo", "pontos", "divergencias", "tags"],
    },
}


def montar_mensagem(grupo, material):
    blocos = [f"Acontecimento: {grupo['evento']}\n"]
    for m in material:
        aviso = "" if m["texto_completo"] else " (só o resumo do feed)"
        blocos.append(f"### {m['fonte']} ({m['idioma']}){aviso}\nTítulo: {m['titulo']}\nPublicado: {m['publicado']}\n\n{m['texto']}\n")
    return "\n".join(blocos)


def resumir(llm, modelo, grupo, material, tentativas=2):
    mensagem = montar_mensagem(grupo, material)
    problemas = []
    post = {}
    for tentativa in range(tentativas):
        if problemas:
            mensagem_atual = mensagem + "\n\nSua versão anterior tinha estes problemas. Reescreva corrigindo todos:\n- " + "\n- ".join(problemas)
        else:
            mensagem_atual = mensagem
        post = llm.chamar_ferramenta(modelo, SISTEMA, mensagem_atual, FERRAMENTA["nome"], FERRAMENTA["descricao"], FERRAMENTA["esquema"])
        problemas = checar(post, material)
        if not problemas:
            break
    post["problemas"] = problemas
    post["status"] = "pronto" if not problemas else "revisar"
    post["fontes"] = [{"nome": m["fonte"], "titulo": m["titulo"], "link": m["link"]} for m in material]
    post["evento"] = grupo["evento"]
    post["categoria"] = grupo["categoria"]
    return post
FIM_DO_ARQUIVO_AGENTE
mkdir -p "./agente_noticias"
cat > "./agente_noticias/verificar.py" <<'FIM_DO_ARQUIVO_AGENTE'
import re
from datetime import datetime

NUMERO = re.compile(r"(?<![\w.,])\d{1,3}(?:[.,\s]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?")

PADROES_DE_IA = [
    (re.compile(r"—|–(?!\d)|(?<!\d)–"), "travessão"),
    (re.compile(r"\bnão (?:é|são|foi) (?:só|apenas|somente|simplesmente)\b", re.I), "contraste 'não é só X, é Y'"),
    (re.compile(r"\bnão se trata (?:só |apenas )?de\b", re.I), "contraste 'não se trata de'"),
    (re.compile(r"\b(?:vale|cabe) (?:ressaltar|destacar|lembrar|notar|mencionar)\b", re.I), "preparação 'vale ressaltar'"),
    (re.compile(r"\bé importante (?:destacar|notar|ressaltar|lembrar)\b", re.I), "preparação 'é importante destacar'"),
    (re.compile(r"\bpapel (?:fundamental|crucial|essencial|central)\b", re.I), "importância inflada 'papel fundamental'"),
    (re.compile(r"\b(?:crucial|cruciais|divisor de águas|cenário|panorama|potencializ\w+|mergulh\w+)\b", re.I), "palavra de IA"),
    (re.compile(r"\b(?:atua|atuam) como\b|\bse configura como\b", re.I), "fugindo do 'é'"),
    (re.compile(r"\b(?:o futuro (?:é|parece) promissor|resta saber|só o tempo dirá)\b", re.I), "frase final de efeito"),
    (re.compile(r"[\U0001F300-\U0001FAFF]"), "emoji"),
]


def variantes(numero):
    bruto = numero.replace(" ", "")
    saida = {bruto}
    sem_milhar_ponto = re.sub(r"\.(?=\d{3}(?:\D|$))", "", bruto)
    sem_milhar_virgula = re.sub(r",(?=\d{3}(?:\D|$))", "", bruto)
    for v in (sem_milhar_ponto, sem_milhar_virgula):
        saida.add(v)
        saida.add(v.replace(",", "."))
        saida.add(v.replace(".", ","))
    mais = set()
    for v in saida:
        if re.search(r"[.,]\d*0$", v):
            mais.add(re.sub(r"[.,]?0+$", "", v))
    return {v for v in saida | mais if v}


def normalizar_fontes(textos):
    juntos = " ".join(textos)
    juntos = re.sub(r"(?<=\d)\s(?=\d{3}\b)", "", juntos)
    tokens = set()
    for m in NUMERO.finditer(juntos):
        tokens |= variantes(m.group(0))
    return tokens


def numeros_sem_fonte(texto, textos_fonte, ano_atual=None):
    ano_atual = ano_atual or datetime.now().year
    disponiveis = normalizar_fontes(textos_fonte)
    faltando = []
    for m in NUMERO.finditer(texto):
        numero = m.group(0).strip()
        if not re.search(r"[.,]", numero) and int(re.sub(r"\D", "", numero) or 0) < 10:
            continue
        if numero.isdigit() and abs(int(numero) - ano_atual) <= 1:
            continue
        if not (variantes(numero) & disponiveis):
            faltando.append(numero)
    return sorted(set(faltando))


def problemas_de_estilo(texto):
    achados = []
    for regex, nome in PADROES_DE_IA:
        m = regex.search(texto)
        if m:
            achados.append(f"{nome}: «{m.group(0)}»")
    return achados


def checar(post, material):
    textos = [m["titulo"] + " " + m["texto"] for m in material]
    corpo = " ".join([post.get("titulo", ""), post.get("descricao", ""), post.get("corpo", ""), " ".join(post.get("pontos", [])), post.get("divergencias", "")])
    problemas = []
    faltando = numeros_sem_fonte(corpo, textos)
    if faltando:
        problemas.append("números que não aparecem em nenhuma fonte: " + ", ".join(faltando))
    problemas += problemas_de_estilo(corpo)
    if len(post.get("titulo", "")) > 100:
        problemas.append(f"título com {len(post['titulo'])} caracteres (máximo 100)")
    if not 60 <= len(post.get("descricao", "")) <= 260:
        problemas.append(f"descrição com {len(post.get('descricao', ''))} caracteres (entre 60 e 260)")
    return problemas
FIM_DO_ARQUIVO_AGENTE
mkdir -p "."
cat > "./config.exemplo.json" <<'FIM_DO_ARQUIVO_AGENTE'
{
  "janela_horas": 24,
  "max_itens_por_fonte": 30,
  "min_fontes": 2,
  "max_posts": 3,
  "max_artigos_por_evento": 5,
  "extrair_texto": true,
  "dias_memoria": 5,
  "modelos": {
    "agrupar": "claude-haiku-5-5",
    "resumir": "claude-haiku-5-5"
  },
  "precos_por_milhao": {
    "claude-haiku-5-5": [0.10, 0.50],
    "claude-sonnet-5-5": [2.00, 10.00]
  },
  "publicacao": {
    "tipo": "arquivo",
    "pasta": "saida/posts",
    "repositorio": null,
    "git": "nenhum",
    "separador_slug": "-",
    "frontmatter_extra": {
      "author": "Ronald Andrade"
    },
    "aviso_ia": true
  }
}
FIM_DO_ARQUIVO_AGENTE
mkdir -p "."
cat > "./fontes.json" <<'FIM_DO_ARQUIVO_AGENTE'
{
  "fontes": [
    {"nome": "BBC Business", "idioma": "en", "url": "https://feeds.bbci.co.uk/news/business/rss.xml"},
    {"nome": "The Guardian Economics", "idioma": "en", "url": "https://www.theguardian.com/business/economics/rss"},
    {"nome": "CNBC Economy", "idioma": "en", "url": "https://www.cnbc.com/id/20910258/device/rss/rss.html"},
    {"nome": "NYT Economy", "idioma": "en", "url": "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml"},
    {"nome": "DW Business", "idioma": "en", "url": "https://rss.dw.com/rdf/rss-en-bus"},
    {"nome": "MarketWatch", "idioma": "en", "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories"},
    {"nome": "Al Jazeera", "idioma": "en", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"nome": "g1 Economia", "idioma": "pt", "url": "https://g1.globo.com/rss/g1/economia/"},
    {"nome": "InfoMoney", "idioma": "pt", "url": "https://www.infomoney.com.br/feed/"},
    {"nome": "BBC News Brasil", "idioma": "pt", "url": "https://feeds.bbci.co.uk/portuguese/rss.xml"},
    {"nome": "CNN Brasil Economia", "idioma": "pt", "url": "https://www.cnnbrasil.com.br/economia/feed/"}
  ]
}
FIM_DO_ARQUIVO_AGENTE
mkdir -p "."
cat > "./requirements.txt" <<'FIM_DO_ARQUIVO_AGENTE'
anthropic>=0.40
feedparser>=6.0
trafilatura>=1.6
FIM_DO_ARQUIVO_AGENTE
mkdir -p "./systemd"
cat > "./systemd/agente-noticias.service" <<'FIM_DO_ARQUIVO_AGENTE'
[Unit]
Description=Agente de notícias de economia mundial
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=%h/agente-noticias
EnvironmentFile=%h/.config/agente-noticias/env
ExecStart=%h/agente-noticias/.venv/bin/python -m agente_noticias executar
FIM_DO_ARQUIVO_AGENTE
mkdir -p "./systemd"
cat > "./systemd/agente-noticias.timer" <<'FIM_DO_ARQUIVO_AGENTE'
[Unit]
Description=Roda o agente de notícias às 7h e às 19h

[Timer]
OnCalendar=*-*-* 07,19:00:00
RandomizedDelaySec=10min
Persistent=true

[Install]
WantedBy=timers.target
FIM_DO_ARQUIVO_AGENTE
mkdir -p "./tests/fixtures"
cat > "./tests/fixtures/fonte_a.xml" <<'FIM_DO_ARQUIVO_AGENTE'
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Fonte A (teste)</title>
<item><title>Exampleland central bank raises rates to 4.5%</title><link>https://fonte-a.test/juros?utm_source=rss</link><pubDate>Mon, 26 Oct 2026 09:00:00 GMT</pubDate><description><![CDATA[<p>The central bank of Exampleland raised its key rate by 0.25 points to 4.5%, citing inflation of 3.8% in September.</p>]]></description></item>
<item><title>Exampleland central bank raises rates to 4.5%</title><link>https://fonte-a.test/juros?utm_medium=x</link><pubDate>Mon, 26 Oct 2026 09:05:00 GMT</pubDate><description>duplicado</description></item>
<item><title>Local bakery wins award</title><link>https://fonte-a.test/padaria</link><pubDate>Mon, 26 Oct 2026 08:00:00 GMT</pubDate><description>A bakery won a prize.</description></item>
<item><title>Old story from last week</title><link>https://fonte-a.test/antiga</link><pubDate>Mon, 19 Oct 2026 08:00:00 GMT</pubDate><description>Old.</description></item>
</channel></rss>
FIM_DO_ARQUIVO_AGENTE
mkdir -p "./tests/fixtures"
cat > "./tests/fixtures/fonte_b.xml" <<'FIM_DO_ARQUIVO_AGENTE'
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Fonte B (teste)</title>
<item><title>Banco central da Exemplândia sobe juros para 4,5% ao ano</title><link>https://fonte-b.test/economia/juros-exemplandia</link><pubDate>Mon, 26 Oct 2026 10:00:00 GMT</pubDate><description>Alta de 0,25 ponto percentual; inflação de 3,8% em setembro pressionou a decisão. Mercado esperava manutenção.</description></item>
<item><title>Petróleo fecha em queda de 2%</title><link>https://fonte-b.test/economia/petroleo</link><pubDate>Mon, 26 Oct 2026 11:00:00 GMT</pubDate><description>Barril do Brent recuou para US$ 71,20.</description></item>
</channel></rss>
FIM_DO_ARQUIVO_AGENTE
mkdir -p "./tests/fixtures"
cat > "./tests/fixtures/fonte_c.xml" <<'FIM_DO_ARQUIVO_AGENTE'
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Fonte C (teste)</title>
<item><title>Exampleland surprises markets with rate hike</title><link>https://fonte-c.test/markets/exampleland-hike</link><pubDate>Mon, 26 Oct 2026 09:30:00 GMT</pubDate><description>Analysts had expected rates to stay at 4.25%. The currency gained 1.1% against the dollar.</description></item>
</channel></rss>
FIM_DO_ARQUIVO_AGENTE
mkdir -p "./tests/fixtures"
cat > "./tests/fixtures/quebrado.xml" <<'FIM_DO_ARQUIVO_AGENTE'
<html><body>isto não é um feed
FIM_DO_ARQUIVO_AGENTE
mkdir -p "./tests"
cat > "./tests/test_agente.py" <<'FIM_DO_ARQUIVO_AGENTE'
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
from agente_noticias.publicar import gerar_slug, renderizar_mdx
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
    assert descartados == [("petróleo", "1 fonte(s), mínimo 2")]


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


def test_pipeline_publica_em_repo_via_pr_e_nao_repete(tmp_path):
    remoto = tmp_path / "remoto.git"
    repo = tmp_path / "blog"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remoto)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
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

    cfg = cfg_base(repositorio=str(repo), pasta="src/content/posts", git="pr", separador_slug="_",
                   frontmatter_extra={"author": "Ronald Andrade", "difficulty": "beginner"})
    llm, _ = cliente([RESUMO_BOM])
    rel = executar(cfg, FONTES, llm, tmp_path / "agente", log=lambda *_: None, agora=AGORA)
    assert rel["git"] == {"modo": "pr", "url": "https://github.com/x/y/pull/1"}
    branches = subprocess.run(["git", "-C", str(remoto), "branch"], capture_output=True, text=True).stdout
    assert "noticias/" in branches
    post = next((repo / "src/content/posts").glob("*.mdx"))
    assert re.fullmatch(r"[a-z0-9_]+\.mdx", post.name)
    texto = post.read_text()
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
FIM_DO_ARQUIVO_AGENTE
echo "agente-noticias criado em $DESTINO. Próximo passo: README.md, seção Instalação."
