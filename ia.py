"""
A CAMADA DE IA — e a trava que a vigia.

A regra do projeto é "o código calcula, a IA redige". Só que uma regra escrita
no prompt é um pedido, não uma garantia: o modelo pode desobedecer e ninguém
fica sabendo. Num boletim que sai sozinho, isso é justamente o perigo.

Então aqui tem duas partes:

  1. redigir()  — manda os números prontos e pede o texto.
  2. auditar()  — confere, número por número, se o texto só usa valores que
                  realmente existem no cálculo. Se aparecer um número
                  inventado, o texto é RECUSADO e entra o texto automático.

É a ideia central de integrar IA com responsabilidade: não basta pedir bem,
tem que dar para verificar. A trava é código, é determinística, e roda sempre.
"""

import os
import re

import requests

MODELO = "gemini-2.5-flash"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent"


PROMPT = """Você redige o boletim semanal sobre a qualidade das previsões do
tempo de {cidade}. Quem lê não é meteorologista: é alguém que usa a previsão
para decidir alguma coisa.

Os números abaixo JÁ ESTÃO CALCULADOS.

REGRAS (a primeira é verificada automaticamente depois):
- Não calcule nada e não invente nenhum número. Todo número que você escrever
  precisa aparecer exatamente como está nos dados. Se não achar o número que
  precisa, escreva sem número.
- Não use número nenhum que não esteja nos dados — nem arredondado.
- Português do Brasil, tom direto, sem jargão, sem elogiar o próprio texto.
- No máximo 180 palavras no total.

ESCREVA TRÊS PARÁGRAFOS, sem título e sem marcadores:

1. Como foi a semana que fechou. Compare com o acumulado: a semana foi melhor
   ou pior que o normal? Se houver dados da semana anterior, diga o que mudou.

2. O que chama atenção: o viés (o modelo puxa para cima ou para baixo?), o
   acerto de chuva, o maior desacerto.

3. Uma recomendação prática: com base no erro por antecedência, diga de quanto
   alguém deve desconfiar ao usar a previsão com poucos dias e com muitos dias
   de antecedência. Seja concreto.

DADOS:
{numeros}
"""


# ---------------------------------------------------------------------------
# A trava: quais números o texto pode usar
# ---------------------------------------------------------------------------

def _formas(valor):
    """As grafias aceitáveis de um mesmo número.

    1.44 pode ser citado como "1.44" ou "1,44"; 20.0 como "20". Tudo isso é o
    mesmo número — só não pode ser um número que não existe.
    """
    formas = set()
    texto = str(valor)
    formas.add(texto)

    if isinstance(valor, float):
        if valor == int(valor):
            formas.add(str(int(valor)))      # 20.0 -> "20"
        formas.add(f"{valor:.1f}")
        formas.add(f"{valor:.2f}")
    return formas


def numeros_permitidos(dados):
    """Varre a estrutura toda e junta todo número que o cálculo produziu."""
    permitidos = set()

    def visitar(no):
        if isinstance(no, dict):
            for chave, valor in no.items():
                # A própria chave pode carregar número (ex.: antecedência "3").
                if isinstance(chave, (int, float)):
                    permitidos.update(_formas(chave))
                elif isinstance(chave, str) and chave.isdigit():
                    permitidos.add(chave)
                visitar(valor)
        elif isinstance(no, (list, tuple)):
            for item in no:
                visitar(item)
        elif isinstance(no, bool):
            pass
        elif isinstance(no, (int, float)):
            permitidos.update(_formas(abs(no) if no < 0 else no))
        elif isinstance(no, str):
            # Datas entram inteiras; seus pedaços são tratados na extração.
            permitidos.add(no)

    visitar(dados)
    return permitidos


# Datas (2026-09-14) saem antes da conferência: são texto, não conta.
RE_DATA = re.compile(r"\d{4}-\d{2}-\d{2}")
# Um número: opcional sinal, dígitos, opcional decimal com ponto ou vírgula.
RE_NUMERO = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


def auditar(texto, permitidos):
    """Devolve a lista de números do texto que o cálculo nunca produziu."""
    limpo = RE_DATA.sub(" ", texto)

    inventados = []
    for achado in RE_NUMERO.findall(limpo):
        # "1,44" e "1.44" são o mesmo número.
        normalizado = achado.replace(",", ".").lstrip("+-")

        # Tira zeros decimais inúteis: "20.0" e "20" conferem igual.
        candidatos = {normalizado}
        if "." in normalizado:
            candidatos.add(normalizado.rstrip("0").rstrip("."))
            try:
                valor = float(normalizado)
                candidatos.update(_formas(valor))
            except ValueError:
                pass
        else:
            candidatos.add(f"{normalizado}.0")

        if not (candidatos & permitidos):
            inventados.append(achado)

    return inventados


# ---------------------------------------------------------------------------
# A chamada
# ---------------------------------------------------------------------------

def redigir(dados, cidade, texto_reserva):
    """Devolve (texto, autor). Nunca levanta exceção e nunca deixa passar
    número inventado."""
    import json

    chave = os.environ.get("GEMINI_API_KEY")
    if not chave:
        return texto_reserva, "texto automático (sem GEMINI_API_KEY)"

    prompt = PROMPT.format(
        cidade=cidade, numeros=json.dumps(dados, ensure_ascii=False, indent=2)
    )

    try:
        resposta = requests.post(
            URL,
            headers={"x-goog-api-key": chave},  # chave no cabeçalho, não na URL
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                # Temperatura baixa: boletim é para ser sóbrio e estável.
                "generationConfig": {"temperature": 0.3},
            },
            timeout=90,
        )
        resposta.raise_for_status()
        partes = resposta.json()["candidates"][0]["content"]["parts"]
        texto = "".join(p.get("text", "") for p in partes).strip()
        if not texto:
            raise ValueError("resposta vazia")
    except Exception as erro:
        # Um boletim sem parágrafo bonito ainda serve. Um boletim que não sai
        # não serve para nada — a falha da IA nunca derruba o robô.
        print(f"  IA indisponível ({erro.__class__.__name__}: {erro}).")
        print("  Seguindo com o texto automático.")
        return texto_reserva, "texto automático (a IA falhou)"

    inventados = auditar(texto, numeros_permitidos(dados))
    if inventados:
        print(f"  TEXTO RECUSADO pela auditoria: a IA citou {inventados}, "
              "que não saiu de nenhum cálculo.")
        print("  Seguindo com o texto automático.")
        return texto_reserva, ("texto automático — o texto da IA foi recusado "
                               f"por citar número inexistente: {inventados[0]}")

    return texto, f"análise escrita por {MODELO}, aprovada na auditoria numérica"
