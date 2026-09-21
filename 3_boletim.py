"""
PASSO 3 — Boletim semanal: números viram gráfico e texto.

Divisão de trabalho, que é o ponto central do projeto:

    O CÓDIGO calcula.      A IA redige.      A AUDITORIA confere.

Todos os números saem de contas em Python, determinísticas e auditáveis. A IA
recebe os números prontos e só escreve o texto. E, antes de publicar, o
`ia.py` confere número por número se o texto inventou algum — se inventou, o
texto é recusado.

Por que semanal e não diário: o que este boletim mede é a QUALIDADE da
previsão, e isso quase não muda de um dia para o outro. Um boletim diário
repetiria o mesmo número com ruído. Semanalmente há uma semana inteira nova
para comparar com o acumulado — aí o boletim tem o que dizer.
"""

import csv
import os
import statistics
from collections import Counter
from datetime import date, timedelta

import matplotlib
matplotlib.use("Agg")  # backend sem tela: essencial para rodar na nuvem
import matplotlib.pyplot as plt

import comum
import ia

PASTA = comum.PASTA
ARQ_BOLETIM_MD = os.path.join(PASTA, "boletim.md")
ARQ_BOLETIM_HTML = os.path.join(PASTA, "boletim.html")
ARQ_SERIE = os.path.join(PASTA, "dados", "historico_boletins.csv")
GRAF_ERRO = os.path.join(PASTA, "graficos", "erro_por_antecedencia.png")
GRAF_LINHA = os.path.join(PASTA, "graficos", "de_longe_e_de_perto.png")

DIAS_DA_SEMANA = 7
DIAS_NO_GRAFICO = 21

# Paleta validada (checagem de daltonismo e de contraste no fundo claro).
AZUL = "#2a78d6"
LARANJA = "#eb6834"
VERDE = "#1baf7a"
TINTA = "#0b0b0b"
TINTA_FRACA = "#52514e"
GRADE = "#dcdcd8"
FUNDO = "#fcfcfb"

ROTULOS_CHUVA = {
    "acerto": "Previu chuva e choveu",
    "falso_alarme": "Previu chuva e não choveu",
    "chuva_perdida": "Não previu e choveu",
    "acerto_seco": "Previu seco e ficou seco",
}

COLUNAS_SERIE = ["gerado_em", "periodo_inicio", "periodo_fim", "n_previsoes",
                 "mae_tmax", "mae_tmin", "vies_tmax", "acerto_chuva_pct"]


# --------------------------------------------------------------------------
# 1. Ler a conferência e calcular. Nenhuma IA daqui até o fim da seção.
# --------------------------------------------------------------------------

def ler_verificacao():
    if not os.path.exists(comum.ARQ_VERIFICACAO):
        return []
    with open(comum.ARQ_VERIFICACAO, newline="", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    for l in linhas:
        for campo in ("erro_tmax", "erro_tmin", "tmax_prevista", "tmax_observada",
                      "chuva_prevista_mm", "chuva_observada_mm"):
            l[campo] = comum.numero(l[campo])
        l["antecedencia_dias"] = int(l["antecedencia_dias"])
    return linhas


def calcular_bloco(linhas):
    """As estatísticas de um conjunto de previsões conferidas."""
    if not linhas:
        return None

    erros_tmax = [l["erro_tmax"] for l in linhas]
    chuva = Counter(l["veredito_chuva"] for l in linhas)
    acertos = chuva["acerto"] + chuva["acerto_seco"]

    return {
        "n_previsoes": len(linhas),
        "periodo_inicio": min(l["data_alvo"] for l in linhas),
        "periodo_fim": max(l["data_alvo"] for l in linhas),
        # Erro médio absoluto: o tamanho do erro, ignorando o sinal.
        "mae_tmax": round(statistics.fmean(abs(e) for e in erros_tmax), 2),
        "mae_tmin": round(statistics.fmean(abs(l["erro_tmin"]) for l in linhas), 2),
        # Viés: a média COM sinal. Positivo = o modelo puxa para o quente.
        # É um erro sistemático, que dá para corrigir; o MAE não.
        "vies_tmax": round(statistics.fmean(erros_tmax), 2),
        "acerto_chuva_pct": round(100 * acertos / len(linhas), 1),
        "chuva": dict(chuva),
    }


def calcular(linhas):
    hoje = date.today()
    corte = (hoje - timedelta(days=DIAS_DA_SEMANA)).isoformat()
    da_semana = [l for l in linhas if l["data_alvo"] >= corte]

    por_antecedencia = {}
    for antecedencia in sorted({l["antecedencia_dias"] for l in linhas}):
        grupo = [l for l in linhas if l["antecedencia_dias"] == antecedencia]
        por_antecedencia[antecedencia] = {
            "n": len(grupo),
            "mae_tmax": round(statistics.fmean(abs(l["erro_tmax"]) for l in grupo), 2),
            "mae_tmin": round(statistics.fmean(abs(l["erro_tmin"]) for l in grupo), 2),
            "vies_tmax": round(statistics.fmean(l["erro_tmax"] for l in grupo), 2),
        }

    pior = max(linhas, key=lambda l: abs(l["erro_tmax"]))

    return {
        "cidade": comum.CIDADE,
        "gerado_em": hoje.isoformat(),
        "semana": calcular_bloco(da_semana),
        "acumulado": calcular_bloco(linhas),
        "por_antecedencia": por_antecedencia,
        "pior_erro": {
            "data": pior["data_alvo"],
            "antecedencia": pior["antecedencia_dias"],
            "previsto": pior["tmax_prevista"],
            "observado": pior["tmax_observada"],
            "erro": pior["erro_tmax"],
        },
        # De onde veio cada previsão. As duas são dados reais do Open-Meteo:
        # "arquivo" = recuperada das rodadas antigas do modelo
        # "ao_vivo" = coletada pelo próprio robô naquele dia
        "origens": dict(Counter(l.get("origem", "arquivo") for l in linhas)),
    }


def ler_boletim_anterior(hoje):
    """O boletim da semana passada, para o texto poder dizer o que mudou.

    O robô guarda as próprias conclusões, não só as próprias previsões: é a
    mesma ideia do passo 1, um nível acima.
    """
    if not os.path.exists(ARQ_SERIE):
        return None
    with open(ARQ_SERIE, newline="", encoding="utf-8") as f:
        anteriores = [l for l in csv.DictReader(f) if l["gerado_em"] != hoje]
    if not anteriores:
        return None
    ultimo = sorted(anteriores, key=lambda l: l["gerado_em"])[-1]
    return {
        "gerado_em": ultimo["gerado_em"],
        "mae_tmax": comum.numero(ultimo["mae_tmax"]),
        "vies_tmax": comum.numero(ultimo["vies_tmax"]),
        "acerto_chuva_pct": comum.numero(ultimo["acerto_chuva_pct"]),
    }


def gravar_na_serie(m):
    semana = m["semana"]
    linha = {
        "gerado_em": m["gerado_em"],
        "periodo_inicio": semana["periodo_inicio"],
        "periodo_fim": semana["periodo_fim"],
        "n_previsoes": semana["n_previsoes"],
        "mae_tmax": semana["mae_tmax"],
        "mae_tmin": semana["mae_tmin"],
        "vies_tmax": semana["vies_tmax"],
        "acerto_chuva_pct": semana["acerto_chuva_pct"],
    }

    existentes = []
    if os.path.exists(ARQ_SERIE):
        with open(ARQ_SERIE, newline="", encoding="utf-8") as f:
            existentes = [l for l in csv.DictReader(f)
                          if l["gerado_em"] != m["gerado_em"]]

    os.makedirs(os.path.dirname(ARQ_SERIE), exist_ok=True)
    with open(ARQ_SERIE, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS_SERIE)
        escritor.writeheader()
        escritor.writerows(sorted(existentes + [linha],
                                  key=lambda l: l["gerado_em"]))


# --------------------------------------------------------------------------
# 2. Gráficos — os dois contam a MESMA história
# --------------------------------------------------------------------------

def _limpar_eixo(ax):
    """Grade e molduras discretas: os dados em primeiro plano."""
    ax.set_facecolor(FUNDO)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(GRADE)
    ax.tick_params(colors=TINTA_FRACA, labelsize=9, length=0)
    ax.grid(axis="y", color=GRADE, linewidth=0.8)
    ax.set_axisbelow(True)


def grafico_erro_por_antecedencia(m):
    """Gráfico 1 — a regra: quanto mais longe, pior.

    Uma série só, uma cor só: o comprimento da barra já diz a magnitude,
    colorir por ela de novo seria redundante.
    """
    antecedencias = sorted(m["por_antecedencia"])
    valores = [m["por_antecedencia"][a]["mae_tmax"] for a in antecedencias]

    fig, ax = plt.subplots(figsize=(7.6, 4.2), facecolor=FUNDO)
    barras = ax.bar([str(a) for a in antecedencias], valores, color=AZUL, width=0.62)
    _limpar_eixo(ax)

    for barra, valor in zip(barras, valores):
        ax.annotate(f"{valor:.2f}",
                    (barra.get_x() + barra.get_width() / 2, valor),
                    textcoords="offset points", xytext=(0, 5),
                    ha="center", fontsize=10, color=TINTA)

    ax.set_title(f"A regra: quanto mais longe, pior — {m['cidade']}",
                 fontsize=13, color=TINTA, pad=14, loc="left")
    ax.set_xlabel("Dias de antecedência da previsão", fontsize=10, color=TINTA_FRACA)
    ax.set_ylabel("Erro médio da máxima (°C)", fontsize=10, color=TINTA_FRACA)
    ax.set_ylim(0, max(valores) * 1.22)

    fig.tight_layout()
    fig.savefig(GRAF_ERRO, dpi=140, facecolor=FUNDO)
    plt.close(fig)
    return antecedencias


def grafico_de_longe_e_de_perto(linhas, m, antecedencias):
    """Gráfico 2 — a MESMA história do gráfico 1, dia a dia.

    O gráfico 1 diz "com 5 dias o erro é maior" como média. Este mostra isso
    acontecendo: a linha da previsão de véspera cola no observado; a da
    previsão mais distante se descola. É o mesmo fato, visto de perto.
    """
    perto = antecedencias[0]
    longe = antecedencias[-1]
    if perto == longe:
        return None

    corte = (date.today() - timedelta(days=DIAS_NO_GRAFICO)).isoformat()

    def serie(antecedencia):
        return {l["data_alvo"]: l for l in linhas
                if l["antecedencia_dias"] == antecedencia and l["data_alvo"] >= corte}

    de_perto, de_longe = serie(perto), serie(longe)
    # Só dias em que as duas previsões existem: senão as linhas comparariam
    # períodos diferentes e a diferença entre elas não significaria nada.
    dias = sorted(set(de_perto) & set(de_longe))
    if len(dias) < 3:
        return None

    observado = [de_perto[d]["tmax_observada"] for d in dias]
    prev_perto = [de_perto[d]["tmax_prevista"] for d in dias]
    prev_longe = [de_longe[d]["tmax_prevista"] for d in dias]
    rotulos = [d[5:] for d in dias]  # mês-dia, para caber no eixo

    fig, ax = plt.subplots(figsize=(8.6, 4.4), facecolor=FUNDO)
    ax.plot(rotulos, observado, color=AZUL, linewidth=2.4, marker="o",
            markersize=5, label="O que aconteceu", zorder=3)
    ax.plot(rotulos, prev_perto, color=VERDE, linewidth=2, marker="o",
            markersize=4.5, label=f"Previsto {perto} dia antes", zorder=2)
    ax.plot(rotulos, prev_longe, color=LARANJA, linewidth=2, marker="o",
            markersize=4.5, label=f"Previsto {longe} dias antes", zorder=1)
    _limpar_eixo(ax)

    # Rótulo direto na ponta: a identidade da linha nunca depende só da cor.
    # Quando as três linhas terminam quase no mesmo valor, os rótulos se
    # sobrepõem — então eles são afastados na vertical até caberem.
    pontas = sorted(
        ((observado[-1], AZUL, "Aconteceu"),
         (prev_perto[-1], VERDE, f"{perto} dia antes"),
         (prev_longe[-1], LARANJA, f"{longe} dias antes")),
        key=lambda ponta: ponta[0], reverse=True,
    )

    fig.canvas.draw()  # precisa do desenho para converter dados em pixels
    separacao_minima = 13  # pontos
    ultimo_y = None
    for valor, cor, nome in pontas:
        _, y_tela = ax.transData.transform((len(dias) - 1, valor))
        if ultimo_y is not None and ultimo_y - y_tela < separacao_minima:
            y_tela = ultimo_y - separacao_minima
        ultimo_y = y_tela

        _, y_dado = ax.transData.inverted().transform((0, y_tela))
        ax.annotate(nome, (len(dias) - 1, valor),
                    xytext=(len(dias) - 1 + 0.25, y_dado), textcoords="data",
                    color=cor, fontsize=8.5, va="center")

    ax.set_title("A mesma história, dia a dia: de perto acerta, de longe erra",
                 fontsize=13, color=TINTA, pad=14, loc="left")
    ax.set_ylabel("Temperatura máxima (°C)", fontsize=10, color=TINTA_FRACA)
    ax.legend(frameon=False, fontsize=9, labelcolor=TINTA_FRACA,
              loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=3)
    fig.autofmt_xdate(rotation=45)
    fig.savefig(GRAF_LINHA, dpi=140, facecolor=FUNDO, bbox_inches="tight")
    plt.close(fig)
    return {"perto": perto, "longe": longe, "dias": len(dias)}


# --------------------------------------------------------------------------
# 3. Texto de reserva (sem IA) e montagem dos arquivos
# --------------------------------------------------------------------------

def texto_de_reserva(m, anterior):
    """Boletim sem IA: frases montadas por código. Roda sempre, de graça."""
    semana, acumulado = m["semana"], m["acumulado"]
    antecedencias = sorted(m["por_antecedencia"])
    perto = m["por_antecedencia"][antecedencias[0]]["mae_tmax"]
    longe = m["por_antecedencia"][antecedencias[-1]]["mae_tmax"]

    if semana["mae_tmax"] < acumulado["mae_tmax"]:
        comparacao = "melhor que o acumulado"
    elif semana["mae_tmax"] > acumulado["mae_tmax"]:
        comparacao = "pior que o acumulado"
    else:
        comparacao = "igual ao acumulado"

    p1 = (f"Na semana de {semana['periodo_inicio']} a {semana['periodo_fim']}, "
          f"o erro médio da temperatura máxima foi de {semana['mae_tmax']} °C "
          f"em {semana['n_previsoes']} previsões conferidas — {comparacao}, que "
          f"está em {acumulado['mae_tmax']} °C.")
    if anterior:
        p1 += (f" No boletim anterior, de {anterior['gerado_em']}, a semana "
               f"havia fechado em {anterior['mae_tmax']} °C.")

    lado = "acima" if semana["vies_tmax"] > 0 else "abaixo"
    p2 = (f"O viés de {semana['vies_tmax']:+} °C indica que a previsão tende a "
          f"ficar {lado} do que se observa. O acerto entre \"vai chover\" e "
          f"\"não vai\" foi de {semana['acerto_chuva_pct']}%. O maior "
          f"desacerto do histórico foi em {m['pior_erro']['data']}: previa "
          f"{m['pior_erro']['previsto']} °C e foram "
          f"{m['pior_erro']['observado']} °C.")

    p3 = (f"Na prática: com {antecedencias[0]} dia de antecedência, conte com "
          f"cerca de {perto} °C de margem; com {antecedencias[-1]} dias, a "
          f"margem sobe para perto de {longe} °C. Para decisões que não podem "
          f"errar, prefira confirmar na véspera.")

    return f"{p1}\n\n{p2}\n\n{p3}"


def descricao_origens(m):
    """De onde vieram as previsões. As duas fontes são dados reais."""
    arquivo = m["origens"].get("arquivo", 0)
    ao_vivo = m["origens"].get("ao_vivo", 0)
    partes = []
    if arquivo:
        partes.append(f"{arquivo} recuperadas do arquivo de rodadas antigas "
                      "do Open-Meteo")
    if ao_vivo:
        partes.append(f"{ao_vivo} coletadas pelo próprio robô, dia a dia")
    corpo = " e ".join(partes) if partes else "origem não identificada"
    return (f"Previsões conferidas: {corpo}. São previsões reais, emitidas "
            "antes da data que descrevem — nada aqui é simulado.")


def montar_markdown(m, analise, autor, comparacao):
    semana, acumulado = m["semana"], m["acumulado"]
    linhas = [
        f"# Boletim semanal de acerto da previsão — {m['cidade']}",
        "",
        f"**{m['gerado_em']}** · semana de {semana['periodo_inicio']} a "
        f"{semana['periodo_fim']} · {acumulado['n_previsoes']} previsões no "
        "histórico",
        "",
        f"> {descricao_origens(m)}",
        "",
        "## Análise",
        "",
        analise,
        "",
        f"<sub>{autor}. Os números são calculados em Python; a IA só redige, "
        "e o texto passa por uma auditoria que recusa qualquer número que não "
        "saia do cálculo.</sub>",
        "",
        "## A semana, comparada",
        "",
        "| Medida | Esta semana | Acumulado |",
        "|---|---|---|",
        f"| Previsões conferidas | {semana['n_previsoes']} | "
        f"{acumulado['n_previsoes']} |",
        f"| Erro médio da máxima | {semana['mae_tmax']} °C | "
        f"{acumulado['mae_tmax']} °C |",
        f"| Erro médio da mínima | {semana['mae_tmin']} °C | "
        f"{acumulado['mae_tmin']} °C |",
        f"| Viés da máxima | {semana['vies_tmax']:+} °C | "
        f"{acumulado['vies_tmax']:+} °C |",
        f"| Acerto chove / não chove | {semana['acerto_chuva_pct']}% | "
        f"{acumulado['acerto_chuva_pct']}% |",
        "",
        "## Quanto a previsão erra, por antecedência",
        "",
        "Sobre todo o histórico. É a regra central do boletim: a previsão de "
        "véspera é boa, a de uma semana é um palpite informado.",
        "",
        "| Antecedência | Previsões | Erro médio máx. | Erro médio mín. | Viés máx. |",
        "|---|---|---|---|---|",
    ]
    for a in sorted(m["por_antecedencia"]):
        d = m["por_antecedencia"][a]
        linhas.append(
            f"| {a} {'dia' if a == 1 else 'dias'} | {d['n']} | {d['mae_tmax']} °C "
            f"| {d['mae_tmin']} °C | {d['vies_tmax']:+} °C |"
        )

    linhas += ["", f"![Erro por antecedência](graficos/{os.path.basename(GRAF_ERRO)})", ""]

    if comparacao:
        linhas += [
            f"E a mesma regra vista dia a dia: a previsão feita "
            f"{comparacao['perto']} dia antes acompanha o que aconteceu; a de "
            f"{comparacao['longe']} dias se descola.",
            "",
            f"![De longe e de perto](graficos/{os.path.basename(GRAF_LINHA)})",
            "",
        ]

    linhas += [
        "## Chuva: acertou o sim ou não?",
        "",
        f"Na semana. Considera-se que choveu a partir de "
        f"{comum.LIMIAR_CHUVA_MM} mm no dia.",
        "",
        "| Situação | Dias |",
        "|---|---|",
    ]
    for chave, rotulo in ROTULOS_CHUVA.items():
        linhas.append(f"| {rotulo} | {semana['chuva'].get(chave, 0)} |")

    linhas += [
        "",
        "## Maior desacerto do histórico",
        "",
        f"Em **{m['pior_erro']['data']}**, com {m['pior_erro']['antecedencia']} "
        f"dias de antecedência: previsto {m['pior_erro']['previsto']} °C, "
        f"observado {m['pior_erro']['observado']} °C "
        f"({m['pior_erro']['erro']:+} °C).",
        "",
        "---",
        "",
        "<sub>Dados: Open-Meteo. O “observado” é a melhor estimativa da API "
        "para datas passadas (reanálise), não a leitura de uma estação "
        "específica. Gerado automaticamente por "
        "[GeocursoAtividade3](https://github.com/VictorGit10/GeocursoAtividade3).</sub>",
        "",
    ]
    return "\n".join(linhas)


def montar_html(m, analise, autor, comparacao):
    semana, acumulado = m["semana"], m["acumulado"]
    paragrafos = "".join(
        f"<p>{p.strip()}</p>" for p in analise.split("\n\n") if p.strip()
    )

    def seta(valor_semana, valor_acumulado, menor_e_melhor=True):
        """Marca se a semana ficou melhor ou pior que o acumulado."""
        if valor_semana == valor_acumulado:
            return '<span class="igual">igual ao normal</span>'
        melhor = (valor_semana < valor_acumulado) == menor_e_melhor
        classe = "bom" if melhor else "ruim"
        palavra = "melhor que o normal" if melhor else "pior que o normal"
        return f'<span class="{classe}">{palavra}</span>'

    filas = "".join(
        f"<tr><td>{a} {'dia' if a == 1 else 'dias'}</td>"
        f"<td>{m['por_antecedencia'][a]['n']}</td>"
        f"<td>{m['por_antecedencia'][a]['mae_tmax']} °C</td>"
        f"<td>{m['por_antecedencia'][a]['mae_tmin']} °C</td>"
        f"<td>{m['por_antecedencia'][a]['vies_tmax']:+} °C</td></tr>"
        for a in sorted(m["por_antecedencia"])
    )
    filas_chuva = "".join(
        f"<tr><td>{rotulo}</td><td>{semana['chuva'].get(chave, 0)}</td></tr>"
        for chave, rotulo in ROTULOS_CHUVA.items()
    )

    bloco_linha = ""
    if comparacao:
        bloco_linha = f"""
  <p>E a mesma regra vista dia a dia: a previsão feita
     {comparacao['perto']} dia antes acompanha o que aconteceu; a de
     {comparacao['longe']} dias se descola.</p>
  <img src="graficos/{os.path.basename(GRAF_LINHA)}"
       alt="Três linhas ao longo de {comparacao['dias']} dias: o que aconteceu,
            o previsto {comparacao['perto']} dia antes, que acompanha de perto,
            e o previsto {comparacao['longe']} dias antes, que se descola">
"""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Boletim semanal — {m['cidade']}</title>
<style>
  :root {{
    --fundo: {FUNDO}; --cartao: #ffffff; --tinta: {TINTA};
    --tinta-fraca: {TINTA_FRACA}; --linha: {GRADE}; --azul: {AZUL};
    --laranja: {LARANJA}; --verde: {VERDE};
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --fundo: #141413; --cartao: #1a1a19; --tinta: #ffffff;
      --tinta-fraca: #c3c2b7; --linha: #35342f; --azul: #3987e5;
      --laranja: #d95926; --verde: #199e70;
    }}
  }}
  :root[data-theme="dark"] {{
    --fundo: #141413; --cartao: #1a1a19; --tinta: #ffffff;
    --tinta-fraca: #c3c2b7; --linha: #35342f; --azul: #3987e5;
    --laranja: #d95926; --verde: #199e70;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 32px 16px; background: var(--fundo);
    color: var(--tinta); font: 16px/1.65 -apple-system, BlinkMacSystemFont,
    "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  main {{ max-width: 780px; margin: 0 auto; }}
  h1 {{ font-size: 1.6rem; line-height: 1.25; margin: 0 0 6px; }}
  h2 {{ font-size: 1.15rem; margin: 42px 0 10px; }}
  .meta {{ color: var(--tinta-fraca); font-size: .9rem; margin-bottom: 22px; }}
  .aviso {{
    border-left: 3px solid var(--azul); background: var(--cartao);
    padding: 13px 16px; border-radius: 6px; font-size: .9rem; margin: 0 0 28px;
    color: var(--tinta-fraca);
  }}
  .sub {{ color: var(--tinta-fraca); font-size: .92rem; margin: 0 0 14px; }}
  .kpis {{
    display: grid; gap: 12px; margin: 0 0 8px;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  }}
  .kpi {{
    background: var(--cartao); border: 1px solid var(--linha);
    border-radius: 10px; padding: 14px 16px;
  }}
  .kpi span {{ display: block; color: var(--tinta-fraca); font-size: .76rem;
               text-transform: uppercase; letter-spacing: .05em; }}
  .kpi strong {{ font-size: 1.6rem; font-weight: 600; display: block;
                 margin: 2px 0 4px; }}
  .kpi .bom, .kpi .ruim, .kpi .igual {{ font-size: .78rem;
    text-transform: none; letter-spacing: 0; }}
  .bom {{ color: #0f7a52; }} .ruim {{ color: #b24a22; }}
  .igual {{ color: var(--tinta-fraca); }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) .bom {{ color: #4cc79a; }}
    :root:not([data-theme="light"]) .ruim {{ color: #e8875c; }}
  }}
  table {{ width: 100%; border-collapse: collapse; margin: 8px 0 4px;
           font-size: .93rem; }}
  th, td {{ text-align: left; padding: 9px 10px;
            border-bottom: 1px solid var(--linha); }}
  th {{ color: var(--tinta-fraca); font-weight: 600; font-size: .78rem;
        text-transform: uppercase; letter-spacing: .05em; }}
  td:not(:first-child) {{ font-variant-numeric: tabular-nums; }}
  img {{ width: 100%; height: auto; border-radius: 10px; margin: 14px 0;
         border: 1px solid var(--linha); background: #fff; }}
  .credito {{ color: var(--tinta-fraca); font-size: .82rem; }}
  footer {{ margin-top: 44px; padding-top: 18px;
            border-top: 1px solid var(--linha); }}
</style>
</head>
<body>
<main>
  <h1>Boletim semanal de acerto da previsão — {m['cidade']}</h1>
  <p class="meta">{m['gerado_em']} · semana de {semana['periodo_inicio']} a
     {semana['periodo_fim']} · {acumulado['n_previsoes']} previsões no histórico</p>
  <div class="aviso">{descricao_origens(m)}</div>

  <div class="kpis">
    <div class="kpi"><span>Erro médio da máxima</span>
      <strong>{semana['mae_tmax']} °C</strong>
      {seta(semana['mae_tmax'], acumulado['mae_tmax'])}</div>
    <div class="kpi"><span>Erro médio da mínima</span>
      <strong>{semana['mae_tmin']} °C</strong>
      {seta(semana['mae_tmin'], acumulado['mae_tmin'])}</div>
    <div class="kpi"><span>Viés da máxima</span>
      <strong>{semana['vies_tmax']:+} °C</strong>
      {seta(abs(semana['vies_tmax']), abs(acumulado['vies_tmax']))}</div>
    <div class="kpi"><span>Acerto de chuva</span>
      <strong>{semana['acerto_chuva_pct']}%</strong>
      {seta(semana['acerto_chuva_pct'], acumulado['acerto_chuva_pct'], False)}</div>
  </div>

  <h2>Análise</h2>
  {paragrafos}
  <p class="credito">{autor}. Os números são calculados em Python; a IA só
     redige, e o texto passa por uma auditoria que recusa qualquer número que
     não saia do cálculo.</p>

  <h2>Quanto a previsão erra, por antecedência</h2>
  <p class="sub">Sobre todo o histórico. É a regra central do boletim: a
     previsão de véspera é boa, a de uma semana é um palpite informado.</p>
  <table>
    <thead><tr><th>Antecedência</th><th>Previsões</th><th>Erro médio máx.</th>
    <th>Erro médio mín.</th><th>Viés máx.</th></tr></thead>
    <tbody>{filas}</tbody>
  </table>
  <img src="graficos/{os.path.basename(GRAF_ERRO)}"
       alt="Gráfico de barras: o erro médio da temperatura máxima cresce
            conforme aumentam os dias de antecedência da previsão">
  {bloco_linha}

  <h2>Chuva: acertou o sim ou não?</h2>
  <p class="sub">Na semana. Considera-se que choveu a partir de
     {comum.LIMIAR_CHUVA_MM} mm no dia.</p>
  <table>
    <thead><tr><th>Situação</th><th>Dias</th></tr></thead>
    <tbody>{filas_chuva}</tbody>
  </table>

  <h2>Maior desacerto do histórico</h2>
  <p>Em <strong>{m['pior_erro']['data']}</strong>, com
     {m['pior_erro']['antecedencia']} dias de antecedência: previsto
     {m['pior_erro']['previsto']} °C, observado
     {m['pior_erro']['observado']} °C ({m['pior_erro']['erro']:+} °C).</p>

  <footer class="credito">
    Dados: Open-Meteo. O “observado” é a melhor estimativa da API para datas
    passadas (reanálise), não a leitura de uma estação específica.
    Gerado automaticamente por
    <a href="https://github.com/VictorGit10/GeocursoAtividade3">GeocursoAtividade3</a>.
  </footer>
</main>
</body>
</html>
"""


def main():
    linhas = ler_verificacao()
    if not linhas:
        print("Nada conferido ainda. Rode:")
        print("    python3 montar_historico.py 21 && python3 2_conferir.py")
        return

    m = calcular(linhas)
    if not m["semana"]:
        print("Nenhuma previsão vencida na última semana. Rode montar_historico.py.")
        return

    anterior = ler_boletim_anterior(m["gerado_em"])
    if anterior:
        m["semana_anterior"] = anterior

    os.makedirs(os.path.dirname(GRAF_ERRO), exist_ok=True)
    antecedencias = grafico_erro_por_antecedencia(m)
    comparacao = grafico_de_longe_e_de_perto(linhas, m, antecedencias)

    # A IA recebe só os números já calculados — e o texto dela é auditado
    # antes de entrar no boletim.
    analise, autor = ia.redigir(m, m["cidade"], texto_de_reserva(m, anterior))

    with open(ARQ_BOLETIM_MD, "w", encoding="utf-8") as f:
        f.write(montar_markdown(m, analise, autor, comparacao))
    with open(ARQ_BOLETIM_HTML, "w", encoding="utf-8") as f:
        f.write(montar_html(m, analise, autor, comparacao))

    gravar_na_serie(m)

    print(f"Boletim semanal gerado ({autor}).")
    print(f"  {ARQ_BOLETIM_MD}")
    print(f"  {ARQ_BOLETIM_HTML}")


if __name__ == "__main__":
    main()
