from collections import defaultdict


class ClienteLLM:
    def __init__(self, cliente=None, max_tokens=16000, precos=None):
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
        # Resposta cortada vem com a ferramenta pela metade ou vazia; seguir adiante daria "nenhum grupo"
        # ou um post sem campos, sem nenhum aviso. O raciocínio do modelo também consome max_tokens.
        motivo = getattr(resposta, "stop_reason", None)
        if motivo == "max_tokens":
            raise RuntimeError(f"resposta do modelo {modelo} cortada em {self.max_tokens} tokens; aumente \"max_tokens\" no config.json")
        if motivo == "refusal":
            raise RuntimeError(f"o modelo {modelo} recusou o pedido da ferramenta {nome}")
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
