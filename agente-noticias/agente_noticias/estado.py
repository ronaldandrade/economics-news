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
