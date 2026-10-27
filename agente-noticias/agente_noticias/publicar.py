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
    extensao = "mdx"

    def __init__(self, cfg, raiz_agente):
        self.repo = None
        if cfg.get("repositorio"):
            repo = Path(os.path.expanduser(cfg["repositorio"]))
            # caminho relativo é contado a partir da pasta do agente ("..": o repositório do site)
            self.repo = repo if repo.is_absolute() else (Path(raiz_agente) / repo).resolve()
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
            self.branch_original = git(self.repo, "rev-parse", "--abbrev-ref", "HEAD")
            base = f"{self.remoto}/{self.branch_base}"
            # Uma branch por PR: se a do dia já foi mergeada, a segunda rodada usa noticias/AAAA-MM-DD-2
            n = 1
            while True:
                branch = f"{self.prefixo_branch}/{data}" if n == 1 else f"{self.prefixo_branch}/{data}-{n}"
                local = bool(git(self.repo, "branch", "--list", branch))
                remota = bool(git(self.repo, "ls-remote", "--heads", self.remoto, branch))
                if not local and not remota:
                    git(self.repo, "switch", "-c", branch, base)
                    break
                if remota:
                    git(self.repo, "fetch", self.remoto, branch)
                ponta = branch if local else f"{self.remoto}/{branch}"
                mergeada = subprocess.run(["git", "-C", str(self.repo), "merge-base", "--is-ancestor", ponta, base]).returncode == 0
                if not mergeada and self._pr_aberto(branch) is not None:
                    # ainda em revisão: acrescenta as notícias novas ao mesmo PR
                    git(self.repo, "switch", branch) if local else git(self.repo, "switch", "-c", branch, ponta)
                    break
                n += 1
            self.branch = branch

    def _pr_aberto(self, branch):
        r = subprocess.run(["gh", "pr", "list", "--head", branch, "--state", "open", "--json", "url", "-q", ".[0].url"],
                           cwd=self.repo, capture_output=True, text=True)
        url = r.stdout.strip()
        return url if r.returncode == 0 and url else None

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

    def _voltar_branch(self):
        if getattr(self, "branch_original", None) and self.branch_original != "HEAD":
            git(self.repo, "switch", self.branch_original)

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
        # devolve o repositório à branch em que estava, para não deixar o usuário na branch do agente
        self._voltar_branch()
        existente = self._pr_aberto(self.branch)
        if existente:
            return {"modo": "pr", "url": existente}
        criado = subprocess.run(
            ["gh", "pr", "create", "--base", self.branch_base, "--head", self.branch,
             "--title", f"Notícias de economia: {data}",
             "--body", f"Resumos gerados pelo agente de notícias.\n\n{corpo}\n\nConfira o preview antes do merge."],
            cwd=self.repo, capture_output=True, text=True,
        )
        if criado.returncode != 0:
            raise RuntimeError(f"gh pr create falhou: {criado.stderr.strip()}")
        return {"modo": "pr", "url": criado.stdout.strip()}


def juntar_nomes(nomes):
    return nomes[0] if len(nomes) == 1 else ", ".join(nomes[:-1]) + " e " + nomes[-1]


def noticia_para_site(post, data, slug):
    """Converte o post do agente no formato de content/noticias/*.json do site Next.js."""
    paragrafos = [p.strip() for p in re.split(r"\n\s*\n", post["corpo"]) if p.strip()]
    if post.get("divergencias", "").strip():
        paragrafos.append("Onde as fontes divergem: " + post["divergencias"].strip())
    paises = post.get("paises") or []
    alcance = post.get("alcance", "nacional")
    fontes = post["fontes"]
    nomes = [f["nome"] for f in fontes]
    noticia = {
        "slug": slug,
        "date": data,
        "featured": bool(post.get("destaque")),
        "impactScope": alcance,
        "consequence": post.get("consequencia", "acompanhamento"),
        "category": post["editoria"],
        "kicker": post.get("chapeu", "").upper(),
        "title": post["titulo"],
        "subtitle": post["descricao"],
        "author": "MERIDIAN, com base em " + juntar_nomes(nomes),
        "location": post.get("local", ""),
        "readTime": f"{tempo_de_leitura(post['corpo'])} min de leitura",
        "affectedCountries": paises,
        "image": post.get("imagem", ""),
        "imageCaption": f"Foto: {post['credito_imagem']}." if post.get("credito_imagem") else "",
        "source": " / ".join(nomes),
        "sourceUrl": fontes[0]["link"],
        "sources": [{"name": f["nome"], "title": f["titulo"], "url": f["link"]} for f in fontes],
        "keyPoints": post["pontos"],
        "body": paragrafos,
        "generatedByAI": True,
    }
    if post.get("base_consequencia", "").strip():
        noticia["consequenceBasis"] = post["base_consequencia"].strip()
    if alcance == "internacional":
        noticia["corridorTag"] = " • ".join(p.upper() for p in paises[:3])
    return noticia


class PublicadorSiteJSON(PublicadorArquivo):
    """Grava cada post como content/noticias/AAAA-MM-DD_slug.json no repositório do site."""

    extensao = "json"

    def __init__(self, cfg, raiz_agente):
        super().__init__({"pasta": "content/noticias", **cfg, "separador_slug": "-"}, raiz_agente)

    def _slugs_existentes(self):
        slugs = set()
        for arquivo in self.pasta.glob("*.json"):
            try:
                slugs.add(json.loads(arquivo.read_text(encoding="utf-8")).get("slug"))
            except (OSError, ValueError):
                continue
        return slugs

    def publicar(self, post, data):
        self.pasta.mkdir(parents=True, exist_ok=True)
        base = gerar_slug(post["titulo"], "-")
        existentes = self._slugs_existentes()
        slug, n = base, 2
        while slug in existentes:
            slug, n = f"{base}-{n}", n + 1
        caminho = self.pasta / f"{data}_{slug}.json"
        noticia = noticia_para_site(post, data, slug)
        caminho.write_text(json.dumps(noticia, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.escritos.append((caminho, post["titulo"]))
        return str(caminho)


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
    if tipo == "site_json":
        return PublicadorSiteJSON(cfg, raiz_agente)
    if tipo == "http":
        return PublicadorHTTP(cfg, raiz_agente)
    raise ValueError(f"tipo de publicação desconhecido: {tipo}")
