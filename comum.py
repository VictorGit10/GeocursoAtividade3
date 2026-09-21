"""
Funções que os três passos do robô compartilham.

A ideia central do projeto: UMA única API (Open-Meteo) serve para as duas
pontas do problema.
  - dias no futuro  -> é PREVISÃO  (o que o modelo acha que vai acontecer)
  - dias no passado -> é OBSERVADO (a melhor estimativa do que de fato aconteceu)

É isso que torna possível o robô conferir a si mesmo.
"""

import csv
import os
import time

import requests

# Goiânia. Troque aqui para rodar o robô em outra cidade.
LATITUDE = -16.68
LONGITUDE = -49.25
FUSO = "America/Sao_Paulo"
CIDADE = "Goiânia"

# Acima de quanto milímetro num dia a gente considera que "choveu".
LIMIAR_CHUVA_MM = 1.0

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQ_HISTORICO = os.path.join(PASTA, "dados", "historico_previsoes.csv")
ARQ_VERIFICACAO = os.path.join(PASTA, "dados", "verificacao.csv")

COLUNAS_HISTORICO = [
    "data_previsao",        # quando o robô fez a previsão
    "data_alvo",            # para que dia ela valia
    "antecedencia_dias",    # data_alvo - data_previsao
    "tmax_prevista",
    "tmin_prevista",
    "chuva_prevista_mm",
    "origem",               # "real" ou "exemplo" (dados simulados p/ demonstração)
]


def buscar_open_meteo(dias_passado=0, dias_futuro=7, tentativas=4):
    """Chama a API e devolve o bloco 'daily' como dicionário.

    dias_passado=0 e dias_futuro=7  -> só previsão
    dias_passado=15 e dias_futuro=1 -> traz o observado das últimas 2 semanas

    Um robô que roda sozinho de madrugada não tem ninguém para clicar em
    "tentar de novo". Então ele mesmo tenta: 4 vezes, esperando cada vez mais
    (2s, 4s, 8s). Uma falha de rede passageira deixa de virar um dia sem dados.
    """
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": FUSO,
        "past_days": dias_passado,
        "forecast_days": dias_futuro,
    }

    for tentativa in range(1, tentativas + 1):
        try:
            resposta = requests.get(
                "https://api.open-meteo.com/v1/forecast", params=params, timeout=60
            )
            resposta.raise_for_status()
            break
        except requests.RequestException as erro:
            if tentativa == tentativas:
                raise
            espera = 2 ** tentativa
            print(f"  rede falhou ({erro.__class__.__name__}); "
                  f"tentando de novo em {espera}s "
                  f"[{tentativa}/{tentativas - 1}]")
            time.sleep(espera)

    dados = resposta.json()

    # A API responde HTTP 200 mesmo quando recusa o pedido (cota, parâmetro
    # errado). Sem esta checagem o robô quebraria mais adiante, com um erro
    # confuso e longe da causa real.
    if dados.get("error"):
        raise RuntimeError(f"Open-Meteo recusou o pedido: {dados.get('reason')}")

    return dados["daily"]


def ler_historico():
    """Lê o caderno de anotações do robô. Devolve lista de dicionários."""
    if not os.path.exists(ARQ_HISTORICO):
        return []
    with open(ARQ_HISTORICO, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def gravar_historico(linhas):
    """Regrava o caderno inteiro, ordenado, sem duplicatas."""
    os.makedirs(os.path.dirname(ARQ_HISTORICO), exist_ok=True)

    # Uma previsão é identificada pelo par (quando previu, para que dia).
    # Se o robô rodar duas vezes no mesmo dia, a segunda substitui a primeira
    # em vez de criar linha repetida.
    unicas = {}
    for linha in linhas:
        unicas[(linha["data_previsao"], linha["data_alvo"])] = linha

    ordenadas = sorted(unicas.values(), key=lambda l: (l["data_previsao"], l["data_alvo"]))

    with open(ARQ_HISTORICO, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS_HISTORICO)
        escritor.writeheader()
        escritor.writerows(ordenadas)

    return ordenadas


def numero(valor):
    """Converte texto do CSV em float, tolerando vazio."""
    if valor is None or valor == "":
        return None
    return float(valor)
