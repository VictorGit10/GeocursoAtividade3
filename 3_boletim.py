"""
PASSO 3 — Boletim: números viram gráfico e texto.

Aqui está a divisão de trabalho que é o ponto central deste projeto:

    O CÓDIGO calcula.      A IA redige.

Todos os números (erro médio, viés, taxa de acerto) saem de contas em Python,
determinísticas e auditáveis. A IA recebe esses números já prontos e só escreve
o parágrafo de análise em português. Ela nunca é encarregada de calcular nada.

Por que isso importa: se você mandar a planilha crua para o modelo e pedir "qual
foi o erro médio?", ele vai responder um número com toda a confiança do mundo —
e ele pode estar errado, sem aviso. Um boletim que sai toda madrugada, sem
ninguém conferindo, não pode depender disso.

Sem GEMINI_API_KEY o boletim sai igual, só com o texto escrito por um modelo de
frases fixas. Nada quebra.
"""

import csv
import json
import os
import statistics
from collections import Counter
from datetime import date

import matplotlib
matplotlib.use("Agg")  # backend sem tela: essencial para rodar na nuvem
import matplotlib.pyplot as plt
import requests

import comum

PASTA = comum.PASTA
ARQ_BOLETIM_MD = os.path.join(PASTA, "boletim.md")
ARQ_BOLETIM_HTML = os.path.join(PASTA, "boletim.html")
GRAF_ERRO = os.path.join(PASTA, "graficos", "erro_por_antecedencia.png")
GRAF_LINHA = os.path.join(PASTA, "graficos", "previsto_vs_observado.png")

# Paleta validada (checagem de daltonismo e de contraste no fundo claro).
AZUL = "#2a78d6"
LARANJA = "#eb6834"
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


# --------------------------------------------------------------------------
# 1. Ler a conferência e calcular as estatísticas
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


def calcular(linhas):
    """Todas as contas do boletim ficam nesta função. Nada de IA aqui."""
    erros_tmax = [l["erro_tmax"] for l in linhas]
    erros_tmin = [l["erro_tmin"] for l in linhas]

    # Erro médio absoluto: o tamanho do erro, ignorando o sinal.
    # "Em média, o robô erra a máxima em X graus."
    mae_tmax = statistics.fmean(abs(e) for e in erros_tmax)

    # Viés: a média COM sinal. Se der positivo, o robô puxa para cima
    # sistematicamente. É um erro que se pode corrigir; o MAE não.
    vies_tmax = statistics.fmean(erros_tmax)

    por_antecedencia = {}
    for antecedencia in sorted({l["antecedencia_dias"] for l in linhas}):
        grupo = [l for l in linhas if l["antecedencia_dias"] == antecedencia]
        por_antecedencia[antecedencia] = {
            "n": len(grupo),
            "mae_tmax": round(statistics.fmean(abs(l["erro_tmax"]) for l in grupo), 2),
            "mae_tmin": round(statistics.fmean(abs(l["erro_tmin"]) for l in grupo), 2),
            "vies_tmax": round(statistics.fmean(l["erro_tmax"] for l in grupo), 2),
        }

    chuva = Counter(l["veredito_chuva"] for l in linhas)
    acertos_chuva = chuva["acerto"] + chuva["acerto_seco"]

    pior = max(linhas, key=lambda l: abs(l["erro_tmax"]))

    return {
        "cidade": comum.CIDADE,
        "gerado_em": date.today().isoformat(),
        "n_previsoes": len(linhas),
        "periodo_inicio": min(l["data_alvo"] for l in linhas),
        "periodo_fim": max(l["data_alvo"] for l in linhas),
        "mae_tmax": round(mae_tmax, 2),
        "mae_tmin": round(statistics.fmean(abs(e) for e in erros_tmin), 2),
        "vies_tmax": round(vies_tmax, 2),
        "por_antecedencia": por_antecedencia,
        "chuva": dict(chuva),
        "acerto_chuva_pct": round(100 * acertos_chuva / len(linhas), 1),
        "pior_erro": {
            "data": pior["data_alvo"],
            "antecedencia": pior["antecedencia_dias"],
            "previsto": pior["tmax_prevista"],
            "observado": pior["tmax_observada"],
            "erro": pior["erro_tmax"],
        },
        # Se qualquer linha vier do semeador, o boletim inteiro é demonstração.
        "modo_exemplo": any(l.get("origem") == "exemplo" for l in linhas),
    }


# --------------------------------------------------------------------------
# 2. Gráficos
# --------------------------------------------------------------------------

def _limpar_eixo(ax):
    """Grade e molduras discretas: os dados em primeiro plano, não a decoração."""
    ax.set_facecolor(FUNDO)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(GRADE)
    ax.tick_params(colors=TINTA_FRACA, labelsize=9, length=0)
    ax.grid(axis="y", color=GRADE, linewidth=0.8)
    ax.set_axisbelow(True)


def grafico_erro_por_antecedencia(m):
    """O gráfico principal: o erro cresce conforme a previsão se afasta.

    Uma série só, uma cor só — o comprimento da barra já diz a magnitude,
    então colorir por ela de novo seria redundante. Valor escrito em cada
    barra: ninguém precisa mirar no eixo.
    """
    antecedencias = sorted(m["por_antecedencia"])
    valores = [m["por_antecedencia"][a]["mae_tmax"] for a in antecedencias]

    fig, ax = plt.subplots(figsize=(7.6, 4.2), facecolor=FUNDO)
    barras = ax.bar([str(a) for a in antecedencias], valores,
                    color=AZUL, width=0.62)
    _limpar_eixo(ax)

    for barra, valor in zip(barras, valores):
        ax.annotate(f"{valor:.1f}",
                    (barra.get_x() + barra.get_width() / 2, valor),
                    textcoords="offset points", xytext=(0, 5),
                    ha="center", fontsize=10, color=TINTA)

    ax.set_title(f"Erro médio da temperatura máxima — {m['cidade']}",
                 fontsize=13, color=TINTA, pad=14, loc="left")
    ax.set_xlabel("Dias de antecedência da previsão", fontsize=10, color=TINTA_FRACA)
    ax.set_ylabel("Erro médio (°C)", fontsize=10, color=TINTA_FRACA)
    ax.set_ylim(0, max(valores) * 1.22)

    fig.tight_layout()
    fig.savefig(GRAF_ERRO, dpi=140, facecolor=FUNDO)
    plt.close(fig)


def grafico_previsto_vs_observado(linhas, m):
    """Linha do tempo: o que o robô disse 3 dias antes x o que aconteceu.

    Duas séries distintas, então duas cores categóricas + legenda + rótulo
    direto na última ponta (identidade nunca depende só da cor).
    """
    # Uma antecedência só, senão viram várias linhas embaralhadas.
    disponiveis = sorted({l["antecedencia_dias"] for l in linhas})
    escolhida = 3 if 3 in disponiveis else disponiveis[len(disponiveis) // 2]

    grupo = sorted((l for l in linhas if l["antecedencia_dias"] == escolhida),
                   key=lambda l: l["data_alvo"])
    if len(grupo) < 2:
        return None

    dias = [l["data_alvo"][5:] for l in grupo]  # mês-dia, para caber no eixo
    previsto = [l["tmax_prevista"] for l in grupo]
    observado = [l["tmax_observada"] for l in grupo]

    fig, ax = plt.subplots(figsize=(8.4, 4.2), facecolor=FUNDO)
    ax.plot(dias, observado, color=AZUL, linewidth=2,
            marker="o", markersize=5, label="Observado")
    ax.plot(dias, previsto, color=LARANJA, linewidth=2,
            marker="o", markersize=5, label=f"Previsto ({escolhida} dias antes)")
    _limpar_eixo(ax)

    ax.annotate("Observado", (len(dias) - 1, observado[-1]),
                textcoords="offset points", xytext=(8, 0),
                color=AZUL, fontsize=9, va="center")
    ax.annotate("Previsto", (len(dias) - 1, previsto[-1]),
                textcoords="offset points", xytext=(8, 0),
                color=LARANJA, fontsize=9, va="center")

    ax.set_title(f"Previsto x observado — máxima em {m['cidade']}",
                 fontsize=13, color=TINTA, pad=14, loc="left")
    ax.set_ylabel("Temperatura máxima (°C)", fontsize=10, color=TINTA_FRACA)
    # Legenda fora da área de dados: dentro dela, a linha laranja mergulha
    # justamente onde o quadro ficaria.
    ax.legend(frameon=False, fontsize=9, labelcolor=TINTA_FRACA,
              loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2)
    fig.autofmt_xdate(rotation=45)
    # Espaço à direita para os rótulos diretos não serem cortados.
    fig.subplots_adjust(right=0.86)
    fig.savefig(GRAF_LINHA, dpi=140, facecolor=FUNDO, bbox_inches="tight")
    plt.close(fig)
    return escolhida


# --------------------------------------------------------------------------
# 3. A camada de IA: escrever o texto (e só o texto)
# --------------------------------------------------------------------------

PROMPT = """Você é um analista que redige um boletim diário curto sobre a
qualidade das previsões do tempo de {cidade}.

Abaixo estão os números JÁ CALCULADOS. Sua tarefa é escrever a análise em
português do Brasil.

REGRAS:
- Não calcule nada. Não invente nenhum número. Use somente os valores do JSON.
- Se citar um número, copie-o exatamente como está.
- Dois parágrafos curtos, no máximo 130 palavras no total.
- Parágrafo 1: o robô tem acertado? Comente o erro médio e como ele muda com a
  antecedência.
- Parágrafo 2: o que chama atenção (viés, chuva, o pior erro) e o que isso
  significa na prática para alguém que usa a previsão.
- Tom direto e claro, sem jargão e sem elogios ao próprio texto.
- Responda só com os dois parágrafos, sem título e sem marcadores.

NÚMEROS:
{numeros}
"""


def texto_de_reserva(m):
    """Boletim sem IA: frases montadas por código. Roda sempre, de graça."""
    antecedencias = sorted(m["por_antecedencia"])
    primeira = m["por_antecedencia"][antecedencias[0]]["mae_tmax"]
    ultima = m["por_antecedencia"][antecedencias[-1]]["mae_tmax"]
    lado = "acima" if m["vies_tmax"] > 0 else "abaixo"

    p1 = (
        f"Nas {m['n_previsoes']} previsões conferidas entre {m['periodo_inicio']} "
        f"e {m['periodo_fim']}, o erro médio da temperatura máxima foi de "
        f"{m['mae_tmax']} °C. A qualidade cai com a distância: com "
        f"{antecedencias[0]} dia de antecedência o erro médio é {primeira} °C, "
        f"e com {antecedencias[-1]} dias sobe para {ultima} °C."
    )
    p2 = (
        f"O viés de {m['vies_tmax']:+} °C indica que a previsão tende a ficar "
        f"{lado} do que se observa. Para chuva, o acerto entre \"vai chover\" e "
        f"\"não vai\" foi de {m['acerto_chuva_pct']}%. O maior desacerto do "
        f"período foi em {m['pior_erro']['data']}: previa "
        f"{m['pior_erro']['previsto']} °C e foram "
        f"{m['pior_erro']['observado']} °C."
    )
    return f"{p1}\n\n{p2}"


def texto_da_ia(m):
    """Chama o Gemini. Devolve (texto, autor). Nunca levanta exceção."""
    chave = os.environ.get("GEMINI_API_KEY")
    if not chave:
        return texto_de_reserva(m), "texto automático (sem GEMINI_API_KEY)"

    prompt = PROMPT.format(
        cidade=m["cidade"],
        numeros=json.dumps(m, ensure_ascii=False, indent=2),
    )
    modelo = "gemini-2.5-flash"

    try:
        resposta = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{modelo}:generateContent",
            headers={"x-goog-api-key": chave},  # chave no cabeçalho, não na URL
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                # temperatura baixa: boletim é para ser sóbrio e estável
                "generationConfig": {"temperature": 0.3},
            },
            timeout=90,
        )
        resposta.raise_for_status()
        partes = resposta.json()["candidates"][0]["content"]["parts"]
        texto = "".join(p.get("text", "") for p in partes).strip()
        if not texto:
            raise ValueError("resposta vazia")
        return texto, f"análise escrita por {modelo}"
    except Exception as erro:
        # Um boletim sem parágrafo bonito ainda serve. Um boletim que não sai,
        # não serve para nada — então a falha da IA nunca derruba o robô.
        print(f"  IA indisponível ({erro.__class__.__name__}: {erro}).")
        print("  Seguindo com o texto automático.")
        return texto_de_reserva(m), "texto automático (a IA falhou hoje)"


# --------------------------------------------------------------------------
# 4. Montar os arquivos do boletim
# --------------------------------------------------------------------------

AVISO_EXEMPLO = (
    "Este boletim inclui previsões **simuladas** (`origem=exemplo`), criadas por "
    "`semear_exemplo.py` para demonstrar o formato antes de o histórico real "
    "encher. Os números de erro abaixo são ilustrativos, não uma medição."
)


def montar_markdown(m, analise, autor, antecedencia_linha):
    linhas = [
        f"# Boletim de acerto da previsão — {m['cidade']}",
        "",
        f"**Gerado em {m['gerado_em']}** · {m['n_previsoes']} previsões conferidas "
        f"({m['periodo_inicio']} a {m['periodo_fim']})",
        "",
    ]
    if m["modo_exemplo"]:
        linhas += [f"> ⚠️ **MODO EXEMPLO** — {AVISO_EXEMPLO}", ""]

    linhas += [
        "## Análise",
        "",
        analise,
        "",
        f"<sub>{autor}. Todos os números foram calculados em Python; "
        "a IA apenas redigiu o texto.</sub>",
        "",
        "## Os números",
        "",
        "| Medida | Valor |",
        "|---|---|",
        f"| Erro médio da máxima | {m['mae_tmax']} °C |",
        f"| Erro médio da mínima | {m['mae_tmin']} °C |",
        f"| Viés da máxima | {m['vies_tmax']:+} °C |",
        f"| Acerto chove / não chove | {m['acerto_chuva_pct']}% |",
        "",
        "### Erro por antecedência",
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

    linhas += [
        "",
        f"![Erro médio por antecedência](graficos/{os.path.basename(GRAF_ERRO)})",
        "",
        "### Chuva: acertou o sim ou não?",
        "",
        f"Considera-se que choveu a partir de {comum.LIMIAR_CHUVA_MM} mm no dia.",
        "",
        "| Situação | Dias |",
        "|---|---|",
    ]
    for chave, rotulo in ROTULOS_CHUVA.items():
        linhas.append(f"| {rotulo} | {m['chuva'].get(chave, 0)} |")

    linhas += [
        "",
        "### Maior desacerto do período",
        "",
        f"Em **{m['pior_erro']['data']}**, com {m['pior_erro']['antecedencia']} dias "
        f"de antecedência: previsto {m['pior_erro']['previsto']} °C, "
        f"observado {m['pior_erro']['observado']} °C "
        f"({m['pior_erro']['erro']:+} °C).",
        "",
    ]
    if antecedencia_linha:
        linhas += [
            f"![Previsto x observado](graficos/{os.path.basename(GRAF_LINHA)})",
            "",
        ]
    linhas += [
        "---",
        "",
        "<sub>Dados: Open-Meteo. O “observado” é a melhor estimativa da API para "
        "datas passadas (reanálise), não a leitura de uma estação específica. "
        "Gerado automaticamente por "
        "[GeocursoAtividade3](https://github.com/VictorGit10/GeocursoAtividade3).</sub>",
        "",
    ]
    return "\n".join(linhas)


def montar_html(m, analise, autor, antecedencia_linha):
    paragrafos = "".join(
        f"<p>{p.strip()}</p>" for p in analise.split("\n\n") if p.strip()
    )
    aviso = ""
    if m["modo_exemplo"]:
        aviso = (
            '<div class="aviso"><strong>MODO EXEMPLO</strong> — este boletim '
            "inclui previsões simuladas, criadas para demonstrar o formato "
            "antes de o histórico real encher. Os números de erro são "
            "ilustrativos, não uma medição.</div>"
        )

    filas = "".join(
        f"<tr><td>{a} {'dia' if a == 1 else 'dias'}</td>"
        f"<td>{m['por_antecedencia'][a]['n']}</td>"
        f"<td>{m['por_antecedencia'][a]['mae_tmax']} °C</td>"
        f"<td>{m['por_antecedencia'][a]['mae_tmin']} °C</td>"
        f"<td>{m['por_antecedencia'][a]['vies_tmax']:+} °C</td></tr>"
        for a in sorted(m["por_antecedencia"])
    )
    filas_chuva = "".join(
        f"<tr><td>{rotulo}</td><td>{m['chuva'].get(chave, 0)}</td></tr>"
        for chave, rotulo in ROTULOS_CHUVA.items()
    )
    grafico_linha = (
        f'<img src="graficos/{os.path.basename(GRAF_LINHA)}" '
        f'alt="Linha do tempo comparando a máxima prevista com a observada">'
        if antecedencia_linha else ""
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Boletim de acerto da previsão — {m['cidade']}</title>
<style>
  :root {{
    --fundo: {FUNDO}; --cartao: #ffffff; --tinta: {TINTA};
    --tinta-fraca: {TINTA_FRACA}; --linha: {GRADE}; --azul: {AZUL};
    --laranja: {LARANJA};
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --fundo: #141413; --cartao: #1a1a19; --tinta: #ffffff;
      --tinta-fraca: #c3c2b7; --linha: #35342f; --azul: #3987e5;
      --laranja: #d95926;
    }}
  }}
  :root[data-theme="dark"] {{
    --fundo: #141413; --cartao: #1a1a19; --tinta: #ffffff;
    --tinta-fraca: #c3c2b7; --linha: #35342f; --azul: #3987e5;
    --laranja: #d95926;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 32px 16px; background: var(--fundo);
    color: var(--tinta); font: 16px/1.65 -apple-system, BlinkMacSystemFont,
    "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  main {{ max-width: 760px; margin: 0 auto; }}
  h1 {{ font-size: 1.6rem; line-height: 1.25; margin: 0 0 6px; }}
  h2 {{ font-size: 1.15rem; margin: 40px 0 12px; }}
  h3 {{ font-size: 1rem; margin: 28px 0 10px; color: var(--tinta-fraca);
        text-transform: uppercase; letter-spacing: .06em; }}
  .meta {{ color: var(--tinta-fraca); font-size: .9rem; margin-bottom: 28px; }}
  .aviso {{
    border-left: 3px solid var(--laranja); background: var(--cartao);
    padding: 14px 16px; border-radius: 6px; font-size: .92rem; margin: 0 0 28px;
  }}
  .kpis {{
    display: grid; gap: 12px; margin: 0 0 8px;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  }}
  .kpi {{
    background: var(--cartao); border: 1px solid var(--linha);
    border-radius: 10px; padding: 14px 16px;
  }}
  .kpi span {{ display: block; color: var(--tinta-fraca); font-size: .78rem;
               text-transform: uppercase; letter-spacing: .05em; }}
  .kpi strong {{ font-size: 1.7rem; font-weight: 600; }}
  table {{ width: 100%; border-collapse: collapse; margin: 8px 0 4px;
           font-size: .93rem; }}
  th, td {{ text-align: left; padding: 9px 10px;
            border-bottom: 1px solid var(--linha); }}
  th {{ color: var(--tinta-fraca); font-weight: 600; font-size: .8rem;
        text-transform: uppercase; letter-spacing: .05em; }}
  td:not(:first-child) {{ font-variant-numeric: tabular-nums; }}
  img {{ width: 100%; height: auto; border-radius: 10px; margin: 16px 0;
         border: 1px solid var(--linha); background: #fff; }}
  .credito {{ color: var(--tinta-fraca); font-size: .82rem; }}
  footer {{ margin-top: 40px; padding-top: 18px;
            border-top: 1px solid var(--linha); }}
</style>
</head>
<body>
<main>
  <h1>Boletim de acerto da previsão — {m['cidade']}</h1>
  <p class="meta">Gerado em {m['gerado_em']} · {m['n_previsoes']} previsões
     conferidas ({m['periodo_inicio']} a {m['periodo_fim']})</p>
  {aviso}

  <div class="kpis">
    <div class="kpi"><span>Erro médio máx.</span><strong>{m['mae_tmax']} °C</strong></div>
    <div class="kpi"><span>Erro médio mín.</span><strong>{m['mae_tmin']} °C</strong></div>
    <div class="kpi"><span>Viés da máxima</span><strong>{m['vies_tmax']:+} °C</strong></div>
    <div class="kpi"><span>Acerto de chuva</span><strong>{m['acerto_chuva_pct']}%</strong></div>
  </div>

  <h2>Análise</h2>
  {paragrafos}
  <p class="credito">{autor}. Todos os números foram calculados em Python;
     a IA apenas redigiu o texto.</p>

  <h3>Erro por antecedência</h3>
  <table>
    <thead><tr><th>Antecedência</th><th>Previsões</th><th>Erro médio máx.</th>
    <th>Erro médio mín.</th><th>Viés máx.</th></tr></thead>
    <tbody>{filas}</tbody>
  </table>
  <img src="graficos/{os.path.basename(GRAF_ERRO)}"
       alt="Gráfico de barras: o erro médio da temperatura máxima cresce conforme
            aumentam os dias de antecedência da previsão">

  <h3>Chuva: acertou o sim ou não?</h3>
  <table>
    <thead><tr><th>Situação</th><th>Dias</th></tr></thead>
    <tbody>{filas_chuva}</tbody>
  </table>

  <h3>Maior desacerto do período</h3>
  <p>Em <strong>{m['pior_erro']['data']}</strong>, com
     {m['pior_erro']['antecedencia']} dias de antecedência: previsto
     {m['pior_erro']['previsto']} °C, observado
     {m['pior_erro']['observado']} °C ({m['pior_erro']['erro']:+} °C).</p>
  {grafico_linha}

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
        print("Nada conferido ainda. Rode 1_coletar.py e 2_conferir.py.")
        print("Para ver o boletim completo hoje: python3 semear_exemplo.py")
        return

    m = calcular(linhas)

    os.makedirs(os.path.dirname(GRAF_ERRO), exist_ok=True)
    grafico_erro_por_antecedencia(m)
    antecedencia_linha = grafico_previsto_vs_observado(linhas, m)

    analise, autor = texto_da_ia(m)

    with open(ARQ_BOLETIM_MD, "w", encoding="utf-8") as f:
        f.write(montar_markdown(m, analise, autor, antecedencia_linha))
    with open(ARQ_BOLETIM_HTML, "w", encoding="utf-8") as f:
        f.write(montar_html(m, analise, autor, antecedencia_linha))

    print(f"Boletim gerado ({autor}).")
    if m["modo_exemplo"]:
        print("  ATENÇÃO: inclui previsões de exemplo (simuladas).")
    print(f"  {ARQ_BOLETIM_MD}")
    print(f"  {ARQ_BOLETIM_HTML}")


if __name__ == "__main__":
    main()
