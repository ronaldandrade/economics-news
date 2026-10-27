from .verificar import checar

# Mesmas editorias de src/lib/tipos.ts do site
# Mesmos valores de ESCOPOS e CONSEQUENCIAS em src/lib/tipos.ts
ALCANCES = ["global", "internacional", "nacional"]
CONSEQUENCIAS = ["acompanhamento", "relevante", "critica"]
EDITORIAS = ["Macroeconomia", "Geopolítica & Fronteiras", "Energia & Recursos", "Comércio & Logística", "Tecnologia & Soberania"]

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
- "corpo" em Markdown simples, de 3 a 5 parágrafos, sem títulos.

Classificação para o site:
Alcance e consequência são dois campos independentes. Classifique pelo efeito que as fontes descrevem, não pelos países citados nem pela sede das empresas: uma multinacional ou uma lista de países não torna o fato global.
- "alcance": "global" se as fontes mostram efeito sobre mercados, preços ou cadeias em vários continentes; "internacional" se mostram efeito direto sobre a economia de dois ou mais países ou de um bloco (vizinhos ou não); "nacional" se o efeito descrito fica concentrado num país. Na dúvida, escolha o mais restrito.
- "consequencia": "acompanhamento" para proposta, anúncio, plano ou efeito ainda incerto; "relevante" quando as fontes medem um efeito concreto sobre preços, fluxos ou regras de um mercado; "critica" só para choque amplo já em curso, com números nas fontes que mostram disrupção séria. Na dúvida, escolha a menor.
- "base_consequencia": a evidência, em uma frase com os números das fontes. Obrigatória para "critica"; para as outras, pode ficar vazia.
- "chapeu": 2 a 4 palavras que nomeiam o assunto (ex.: "CHOQUE ENERGÉTICO", "BARREIRA COMERCIAL").
- "local": cidade ou país de onde o fato foi noticiado, como aparece nas fontes.
- "paises": países ou blocos afetados citados nas fontes, em português."""

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
            "alcance": {"type": "string", "enum": ALCANCES},
            "consequencia": {"type": "string", "enum": CONSEQUENCIAS},
            "base_consequencia": {"type": "string", "description": "Evidência com números das fontes; obrigatória se a consequência for critica."},
            "editoria": {"type": "string", "enum": EDITORIAS},
            "chapeu": {"type": "string", "description": "Até 40 caracteres, em maiúsculas."},
            "local": {"type": "string"},
            "paises": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 6},
        },
        "required": ["titulo", "descricao", "corpo", "pontos", "divergencias", "tags", "alcance", "consequencia", "base_consequencia", "editoria", "chapeu", "local", "paises"],
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
    # Imagem da primeira fonte que tiver uma; o crédito vai para essa fonte
    com_imagem = next((m for m in material if m.get("imagem")), None)
    post["imagem"] = com_imagem["imagem"] if com_imagem else ""
    post["credito_imagem"] = com_imagem["fonte"] if com_imagem else ""
    post["evento"] = grupo["evento"]
    post["categoria"] = grupo["categoria"]
    return post
