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
