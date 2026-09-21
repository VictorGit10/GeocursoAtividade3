"""
MONTAR O HISTÓRICO — previsões reais que já foram emitidas no passado.

O problema: a conferência precisa que o tempo passe. Começando do zero, o robô
levaria uma semana para ter o que comparar.

A solução: o Open-Meteo guarda as previsões antigas — não o que aconteceu, mas
o que o modelo *dizia que ia acontecer*, em cada rodada. É a API de rodadas
anteriores (previous runs). Pedindo `temperature_2m_previous_day3` você recebe
a temperatura que foi prevista 3 dias antes daquele horário.

Com isso o histórico nasce cheio e REAL. Nada aqui é simulado.

    python3 montar_historico.py          # últimos 30 dias
    python3 montar_historico.py 60       # últimos 60 dias

Detalhe: essa API só entrega variáveis HORÁRIAS. Então o script soma/agrega as
24 horas de cada dia para chegar em máxima, mínima e chuva acumulada — que é
o que o resto do projeto usa.
"""

import sys
import time
from collections import defaultdict
from datetime import date, timedelta

import comum

URL = "https://previous-runs-api.open-meteo.com/v1/forecast"

# Antecedências que o arquivo cobre. day0 é a rodada do próprio dia, que já é
# quase observação — não serve para medir acerto.
ANTECEDENCIAS = [1, 2, 3, 4, 5, 6, 7]

DIAS_PADRAO = 30

# A API de uso livre limita quantos pedidos cabem por minuto. Sete pedidos
# seguidos levam 429 ("Too Many Requests"); espaçados, todos passam. Ser
# educado com uma API gratuita também é parte do trabalho.
PAUSA_ENTRE_PEDIDOS = 20


def buscar_uma_antecedencia(antecedencia, dias):
    """Traz o que foi previsto com N dias de antecedência, ao longo do período.

    Um pedido por antecedência, com 2 variáveis cada, em vez de um pedido
    gigante com 16. A API de uso livre cobra por volume, e o pedido grande é
    recusado por cota — este passa.
    """
    return comum.pedir_json(
        URL,
        {
            "latitude": comum.LATITUDE,
            "longitude": comum.LONGITUDE,
            "timezone": comum.FUSO,
            "past_days": dias,
            "forecast_days": 1,
            "hourly": (f"temperature_2m_previous_day{antecedencia},"
                       f"precipitation_previous_day{antecedencia}"),
        },
    )


def agregar_por_dia(horarios, sufixo):
    """Transforma a série horária de uma antecedência em números diários.

    As horas vêm no fuso pedido, então o dia local é só o começo do texto
    ("2026-09-14T15:00" -> "2026-09-14").
    """
    temps = defaultdict(list)
    chuvas = defaultdict(list)

    campo_temp = f"temperature_2m{sufixo}"
    campo_chuva = f"precipitation{sufixo}"

    if campo_temp not in horarios:
        return {}

    for i, instante in enumerate(horarios["time"]):
        dia = instante[:10]

        t = horarios[campo_temp][i]
        if t is not None:
            temps[dia].append(t)

        c = horarios.get(campo_chuva, [None] * len(horarios["time"]))[i]
        if c is not None:
            chuvas[dia].append(c)

    diario = {}
    for dia, valores in temps.items():
        # Um dia incompleto (o arquivo começa no meio dele) daria uma máxima
        # falsa. Exige as 24 horas.
        if len(valores) < 24:
            continue
        diario[dia] = {
            "tmax": round(max(valores), 1),
            "tmin": round(min(valores), 1),
            "chuva": round(sum(chuvas.get(dia, [])), 1),
        }
    return diario


def main():
    dias = DIAS_PADRAO
    if len(sys.argv) > 1:
        dias = int(sys.argv[1])

    print(f"Buscando as previsões emitidas nos últimos {dias} dias...")

    historico = comum.ler_historico()
    ja_existe = {(l["data_previsao"], l["data_alvo"]) for l in historico}
    hoje = date.today()
    criadas = 0
    sem_dados = []

    # Dias já encerrados que a janela pedida cobre.
    alvos_da_janela = {
        (hoje - timedelta(days=n)).isoformat() for n in range(1, dias + 1)
    }

    primeiro_pedido = True
    for antecedencia in ANTECEDENCIAS:
        rotulo = f"  antecedência de {antecedencia} " \
                 f"{'dia' if antecedencia == 1 else 'dias'}..."

        # Se o caderno já tem toda a janela nesta antecedência, não gasta
        # pedido. É o que torna barato rodar de novo para preencher o que
        # faltou da vez anterior.
        ja_cobertos = {
            l["data_alvo"] for l in historico
            if int(l["antecedencia_dias"]) == antecedencia
        }
        if alvos_da_janela.issubset(ja_cobertos):
            print(f"{rotulo} já no caderno")
            continue

        # Pausa só antes de um pedido de verdade.
        if not primeiro_pedido:
            time.sleep(PAUSA_ENTRE_PEDIDOS)
        primeiro_pedido = False

        print(rotulo, end=" ", flush=True)
        try:
            horarios = buscar_uma_antecedencia(antecedencia, dias)["hourly"]
        except Exception as erro:
            # Cota estourada numa antecedência não invalida as outras.
            print(f"indisponível ({erro})")
            sem_dados.append(antecedencia)
            continue

        diario = agregar_por_dia(horarios, f"_previous_day{antecedencia}")
        if not diario:
            print("sem dados")
            sem_dados.append(antecedencia)
            continue

        novas_aqui = 0

        for dia, valores in sorted(diario.items()):
            data_alvo = date.fromisoformat(dia)
            # Só dias já encerrados: um dia em curso ainda pode mudar.
            if data_alvo >= hoje:
                continue

            data_previsao = data_alvo - timedelta(days=antecedencia)
            if (data_previsao.isoformat(), dia) in ja_existe:
                continue

            historico.append(
                {
                    "data_previsao": data_previsao.isoformat(),
                    "data_alvo": dia,
                    "antecedencia_dias": str(antecedencia),
                    "tmax_prevista": str(valores["tmax"]),
                    "tmin_prevista": str(valores["tmin"]),
                    "chuva_prevista_mm": str(valores["chuva"]),
                    "origem": "arquivo",
                }
            )
            criadas += 1
            novas_aqui += 1

        # Salva a cada etapa: um 429 no meio do caminho não joga fora
        # o que já foi baixado.
        historico = comum.gravar_historico(historico)
        ja_existe = {(l["data_previsao"], l["data_alvo"]) for l in historico}
        print(f"{novas_aqui} dias")

    finais = comum.gravar_historico(historico)

    print()
    print(f"{criadas} previsões reais recuperadas do arquivo do Open-Meteo.")
    if sem_dados:
        print(f"Antecedências que não vieram: {sem_dados}.")
        print("Se foi cota da API, rode de novo mais tarde — o que já veio fica "
              "salvo e não é baixado outra vez.")
    print(f"Caderno agora tem {len(finais)} linhas.")
    print("Agora rode: python3 2_conferir.py && python3 3_boletim.py")


if __name__ == "__main__":
    main()
