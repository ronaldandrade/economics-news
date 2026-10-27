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
    corpo = " ".join([
        post.get("titulo", ""), post.get("descricao", ""), post.get("corpo", ""), " ".join(post.get("pontos", [])),
        post.get("divergencias", ""), post.get("chapeu", ""), post.get("base_consequencia", ""),
    ])
    problemas = []
    faltando = numeros_sem_fonte(corpo, textos)
    if faltando:
        problemas.append("números que não aparecem em nenhuma fonte: " + ", ".join(faltando))
    problemas += problemas_de_estilo(corpo)
    if len(post.get("titulo", "")) > 100:
        problemas.append(f"título com {len(post['titulo'])} caracteres (máximo 100)")
    if not 60 <= len(post.get("descricao", "")) <= 260:
        problemas.append(f"descrição com {len(post.get('descricao', ''))} caracteres (entre 60 e 260)")
    if "chapeu" in post and len(post["chapeu"]) > 40:
        problemas.append(f"chapéu com {len(post['chapeu'])} caracteres (máximo 40)")
    if post.get("consequencia") == "critica" and not post.get("base_consequencia", "").strip():
        problemas.append("consequência crítica sem base_consequencia: diga a evidência com os números das fontes ou use relevante")
    return problemas
