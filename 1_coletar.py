"""
PASSO 1 — Coletar e ANOTAR.

O bot antigo (coletar_clima.py) pegava a previsão, desenhava o gráfico e
sobrescrevia o PNG. No dia seguinte, a previsão de ontem tinha desaparecido.
Sem memória não existe conferência: não há como saber se ele acertou.

Este passo faz a única coisa que faltava: escreve num caderno (um CSV) toda
previsão que o robô já fez, com a data em que ela foi feita.
"""

from datetime import date, datetime

import comum


def main():
    hoje = date.today().isoformat()

    # Só o futuro: 7 dias de previsão a partir de hoje.
    diario = comum.buscar_open_meteo(dias_passado=0, dias_futuro=7)

    historico = comum.ler_historico()
    antes = len(historico)

    for i, data_alvo in enumerate(diario["time"]):
        antecedencia = (
            datetime.fromisoformat(data_alvo).date() - date.fromisoformat(hoje)
        ).days

        # Antecedência 0 é a previsão para hoje mesmo — já é quase observação,
        # não serve para medir acerto. O que interessa é de 1 a 7 dias à frente.
        if antecedencia < 1:
            continue

        historico.append(
            {
                "data_previsao": hoje,
                "data_alvo": data_alvo,
                "antecedencia_dias": str(antecedencia),
                "tmax_prevista": str(diario["temperature_2m_max"][i]),
                "tmin_prevista": str(diario["temperature_2m_min"][i]),
                "chuva_prevista_mm": str(diario["precipitation_sum"][i]),
                "origem": "ao_vivo",
            }
        )

    finais = comum.gravar_historico(historico)

    print(f"Previsão de {hoje} anotada no caderno.")
    print(f"  linhas antes: {antes}  ->  agora: {len(finais)}")
    print(f"  arquivo: {comum.ARQ_HISTORICO}")


if __name__ == "__main__":
    main()
