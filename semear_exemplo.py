"""
SEMEADOR DE EXEMPLO — só para a aula.

O problema: a conferência precisa que o tempo passe. No primeiro dia o robô
ainda não tem previsão antiga nenhuma para comparar, e o boletim sai vazio.
Ruim para explicar em aula.

A solução honesta: este script inventa um histórico de previsões PLAUSÍVEL,
partindo do que de fato aconteceu (dado real da API) e somando um erro
artificial que cresce com a antecedência — que é como erro de previsão se
comporta na vida real.

As linhas criadas levam a marca `origem=exemplo`, e o boletim exibe um aviso
bem visível quando as usa. Assim ninguém confunde demonstração com medição.

    python3 semear_exemplo.py            # cria o histórico de exemplo
    python3 semear_exemplo.py --limpar   # apaga só as linhas de exemplo

O histórico REAL começa no primeiro `1_coletar.py` e vai convivendo com este.
Em cerca de uma semana já há medição de verdade e o exemplo pode ser apagado.
"""

import random
import sys
from datetime import date, timedelta

import comum

DIAS_PARA_TRAS = 20

# Erro típico de temperatura (em °C) por dia de antecedência. Previsão de
# amanhã erra pouco; previsão de 6 dias erra bem mais. É esta curva que o
# gráfico do boletim vai mostrar.
ERRO_TIPICO_POR_ANTECEDENCIA = {1: 0.9, 2: 1.3, 3: 1.8, 4: 2.4, 5: 3.0, 6: 3.6}

# Modelos de previsão costumam ter um viés: erram sistematicamente para um
# lado. Aqui, meio grau para cima.
VIES_C = 0.5


def limpar():
    historico = [l for l in comum.ler_historico() if l.get("origem") != "exemplo"]
    comum.gravar_historico(historico)
    print(f"Linhas de exemplo removidas. Sobraram {len(historico)} linhas reais.")


def main():
    if "--limpar" in sys.argv:
        limpar()
        return

    # Semente fixa: rodar duas vezes dá o mesmo resultado. Em aula, o número
    # que você mostrou no ensaio é o mesmo que aparece na projeção.
    sorteio = random.Random(42)

    diario = comum.buscar_open_meteo(dias_passado=DIAS_PARA_TRAS, dias_futuro=1)
    hoje = date.today()

    historico = comum.ler_historico()
    ja_existe = {(l["data_previsao"], l["data_alvo"]) for l in historico}
    criadas = 0

    for i, dia in enumerate(diario["time"]):
        data_alvo = date.fromisoformat(dia)
        if data_alvo >= hoje:
            continue  # ainda não aconteceu: não há o que "ter previsto"

        tmax_real = diario["temperature_2m_max"][i]
        tmin_real = diario["temperature_2m_min"][i]
        chuva_real = diario["precipitation_sum"][i]

        for antecedencia, erro_tipico in ERRO_TIPICO_POR_ANTECEDENCIA.items():
            data_previsao = data_alvo - timedelta(days=antecedencia)

            # Não reescreve previsão real nem duplica exemplo já criado.
            chave = (data_previsao.isoformat(), dia)
            if chave in ja_existe:
                continue

            tmax_prev = tmax_real + VIES_C + sorteio.gauss(0, erro_tipico)
            tmin_prev = tmin_real + VIES_C + sorteio.gauss(0, erro_tipico)

            # Chuva: quanto maior a antecedência, maior a chance de o robô
            # trocar "vai chover" por "não vai" (e vice-versa).
            chance_de_errar = 0.06 * antecedencia
            choveu = chuva_real >= comum.LIMIAR_CHUVA_MM
            if sorteio.random() < chance_de_errar:
                # Erra o sim/não: se choveu, prevê seco; se secou, prevê chuva.
                chuva_prev = 0.0 if choveu else round(sorteio.uniform(1.5, 9.0), 1)
            else:
                # Acerta o sim/não, mas erra a quantidade.
                fator = sorteio.uniform(0.5, 1.7)
                chuva_prev = round(chuva_real * fator, 1) if choveu else 0.0

            historico.append(
                {
                    "data_previsao": data_previsao.isoformat(),
                    "data_alvo": dia,
                    "antecedencia_dias": str(antecedencia),
                    "tmax_prevista": str(round(tmax_prev, 1)),
                    "tmin_prevista": str(round(tmin_prev, 1)),
                    "chuva_prevista_mm": str(chuva_prev),
                    "origem": "exemplo",
                }
            )
            criadas += 1

    finais = comum.gravar_historico(historico)
    print(f"{criadas} previsões de EXEMPLO criadas (marcadas origem=exemplo).")
    print(f"Caderno agora tem {len(finais)} linhas.")
    print("Atenção: são dados simulados, para demonstrar o formato do boletim.")


if __name__ == "__main__":
    main()
