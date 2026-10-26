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
