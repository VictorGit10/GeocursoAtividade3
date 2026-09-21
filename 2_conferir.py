"""
PASSO 2 — Conferir: o robô nota a própria prova.

Pega o que de fato aconteceu nos últimos dias e cruza com o que o robô havia
previsto para aqueles mesmos dias. O resultado é uma tabela de erros.

Como o "observado" é obtido: a MESMA API do passo 1, só que pedindo dias do
passado (past_days). Para datas passadas o Open-Meteo não devolve previsão, e
sim a melhor estimativa do que ocorreu (reanálise alimentada por estações e
satélite). É essa dupla função do mesmo endereço que faz o projeto caber numa
aula.
"""

import csv
import os
from datetime import date

import comum

# A API aceita no máximo 92 dias de passado numa chamada.
LIMITE_DA_API = 92
# Piso, para o caso de o caderno ter só datas futuras.
JANELA_MINIMA = 10


def janela_necessaria(historico, hoje):
    """Quantos dias de observação buscar.

    Uma janela fixa era um erro silencioso: se o caderno guardasse 60 dias de
    previsões e o conferidor só olhasse 20 dias para trás, os outros 40
    ficariam parados no CSV, sem nunca virar medição — e ninguém veria falha
    nenhuma, porque o boletim saía normal, só que menor.

    Então a janela sai do próprio caderno: recua até a previsão mais antiga
    que ainda espera conferência.
    """
    passadas = [date.fromisoformat(l["data_alvo"]) for l in historico
                if date.fromisoformat(l["data_alvo"]) < hoje]
    if not passadas:
        return JANELA_MINIMA
    return min(max((hoje - min(passadas)).days, JANELA_MINIMA), LIMITE_DA_API)


def main():
    historico = comum.ler_historico()
    if not historico:
        print("Caderno vazio. Rode 1_coletar.py primeiro.")
        return

    hoje = date.today()

    # O que realmente aconteceu, cobrindo todo o caderno.
    dias = janela_necessaria(historico, hoje)
    print(f"Buscando o observado dos últimos {dias} dias...")
    diario = comum.buscar_open_meteo(dias_passado=dias, dias_futuro=1)
    observado = {}
    for i, dia in enumerate(diario["time"]):
        # Só dias já encerrados entram como observação. O dia de hoje ainda
        # está acontecendo: sua máxima pode subir depois que o robô rodar.
        if date.fromisoformat(dia) >= hoje:
            continue
        observado[dia] = {
            "tmax": diario["temperature_2m_max"][i],
            "tmin": diario["temperature_2m_min"][i],
            "chuva": diario["precipitation_sum"][i],
        }

    linhas = []
    for previsao in historico:
        real = observado.get(previsao["data_alvo"])
        if real is None:
            continue  # data ainda no futuro, ou fora da janela consultada

        tmax_p = comum.numero(previsao["tmax_prevista"])
        tmin_p = comum.numero(previsao["tmin_prevista"])
        chuva_p = comum.numero(previsao["chuva_prevista_mm"])

        previu_chuva = chuva_p >= comum.LIMIAR_CHUVA_MM
        choveu = real["chuva"] >= comum.LIMIAR_CHUVA_MM

        if previu_chuva and choveu:
            veredito_chuva = "acerto"        # previu chuva, choveu
        elif previu_chuva and not choveu:
            veredito_chuva = "falso_alarme"  # previu chuva, não choveu
        elif not previu_chuva and choveu:
            veredito_chuva = "chuva_perdida" # não previu, choveu
        else:
            veredito_chuva = "acerto_seco"   # não previu, não choveu

        linhas.append(
            {
                "data_alvo": previsao["data_alvo"],
                "data_previsao": previsao["data_previsao"],
                "antecedencia_dias": previsao["antecedencia_dias"],
                "tmax_prevista": tmax_p,
                "tmax_observada": real["tmax"],
                # Erro com sinal: positivo = o robô previu mais quente do que foi.
                "erro_tmax": round(tmax_p - real["tmax"], 2),
                "tmin_prevista": tmin_p,
                "tmin_observada": real["tmin"],
                "erro_tmin": round(tmin_p - real["tmin"], 2),
                "chuva_prevista_mm": chuva_p,
                "chuva_observada_mm": real["chuva"],
                "erro_chuva_mm": round(chuva_p - real["chuva"], 2),
                "veredito_chuva": veredito_chuva,
                "origem": previsao.get("origem", "real"),
            }
        )

    linhas.sort(key=lambda l: (l["data_alvo"], int(l["antecedencia_dias"])))

    os.makedirs(os.path.dirname(comum.ARQ_VERIFICACAO), exist_ok=True)
    with open(comum.ARQ_VERIFICACAO, "w", newline="", encoding="utf-8") as f:
        if linhas:
            escritor = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
            escritor.writeheader()
            escritor.writerows(linhas)

    print(f"{len(linhas)} previsões conferidas.")
    if not linhas:
        print("Nenhuma previsão antiga tem data já vencida.")
        print("Para trazer o histórico real de uma vez:")
        print("    python3 montar_historico.py")
    print(f"  arquivo: {comum.ARQ_VERIFICACAO}")


if __name__ == "__main__":
    main()
