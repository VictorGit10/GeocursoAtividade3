# Robô que faz a previsão — e depois confere se acertou

Um agente que roda sozinho toda semana, monta um **boletim de análise de
dados** e mede a própria qualidade ao longo do tempo.

Este repositório existe para responder a uma dúvida da turma:

> "Tenho interesse em agentes de IA que possam, com a ajuda de prompt ou não,
> elaborar relatórios ou boletins de análise de dados."

➡️ **Veja o resultado: [`boletim.md`](boletim.md)** (ou `boletim.html`, com visual
de página.)

---

## A virada em relação ao bot anterior

O primeiro bot da turma (`coletar_clima.py`) faz assim:

```
pega a previsão → desenha o gráfico → salva previsao_goiania.png
```

Ele funciona, mas tem um defeito que só aparece depois: **ele joga os dados
fora.** Guarda só a imagem, e sobrescreve tudo no dia seguinte. Se alguém
perguntar "a previsão de terça acertou?", não há resposta — o número de terça
não existe mais em lugar nenhum.

O robô deste repositório muda uma coisa só, e essa coisa muda tudo:

```
pega a previsão → ANOTA NUM CADERNO → depois volta e confere
```

Um agente que não guarda o que fez não consegue se avaliar. É a diferença
entre automatizar uma tarefa e automatizar um **processo**.

---

## Os três passos

| Passo | Arquivo | O que faz |
|---|---|---|
| 0 | `montar_historico.py` | Recupera as previsões que o Open-Meteo **já emitiu** nas últimas semanas, para o histórico nascer cheio. Roda uma vez. |
| 1 | `1_coletar.py` | Pega a previsão de 7 dias e **anota** cada uma em `dados/historico_previsoes.csv`, junto com a data em que foi feita. |
| 2 | `2_conferir.py` | Pega o que **de fato aconteceu** e cruza com as previsões antigas. Gera `dados/verificacao.csv` com o erro de cada uma. |
| 3 | `3_boletim.py` | Calcula as estatísticas, desenha os gráficos e monta o boletim. |
| — | `ia.py` | A camada de IA: manda os números para o modelo redigir **e audita o texto que volta**. |

### O truque que faz isso caber numa aula

Não são duas fontes de dados, é **uma só**. A mesma URL do Open-Meteo responde
as duas perguntas, dependendo do parâmetro:

```python
buscar_open_meteo(dias_passado=0,  dias_futuro=7)   # previsão: o que ele ACHA
buscar_open_meteo(dias_passado=20, dias_futuro=1)   # observado: o que ACONTECEU
```

Para datas passadas a API não devolve previsão: devolve a melhor estimativa do
que ocorreu (reanálise, alimentada por estações e satélite). Por isso a
conferência sai de graça, sem cadastrar nenhuma segunda API.

---

## A parte que responde à dúvida: onde entra a IA

> **O código calcula. A IA redige. A auditoria confere.**

Todos os números do boletim — erro médio, viés, taxa de acerto — saem de contas
em Python, dentro de `calcular()`. São determinísticas: rodando de novo, dá
igual, e qualquer um pode auditar a conta.

A IA entra só no fim, em `ia.py`. Recebe os números **já prontos** e escreve
três parágrafos: como foi a semana, o que chama atenção, e uma recomendação
prática de quanto desconfiar da previsão.

### E aqui está o pulo do gato

O prompt manda o modelo não inventar número. Só que **um prompt é um pedido,
não uma garantia.** O modelo pode desobedecer, e num boletim que sai sozinho
na segunda de manhã ninguém ficaria sabendo.

Então tem uma trava, em `ia.py`:

```python
inventados = auditar(texto, numeros_permitidos(dados))
if inventados:
    # o texto da IA é RECUSADO e entra o texto automático
```

A função varre o texto que voltou, extrai todo número e confere um por um
contra os valores que o cálculo realmente produziu. Se aparecer qualquer
número que não existe, o texto é jogado fora e o boletim sai com o texto
automático — dizendo, no rodapé, que a IA foi recusada e por quê.

Testado com casos reais de fracasso:

| Texto da IA | Veredito |
|---|---|
| "o erro médio foi de 1.44 °C" | aprovado |
| "o erro médio foi de 1,44 °C" (vírgula) | aprovado |
| "uma melhora de 18% sobre a semana passada" | **recusado** — 18 não existe |
| "somando as antecedências, o erro geral é 1.49 °C" | **recusado** — a IA calculou |
| "acertou 87.5% dos dias de chuva" | **recusado** — número plausível e falso |

**Por que isso é o ponto principal.** A tentação é mandar a planilha crua para
o modelo e pedir "me dê o erro médio". Ele responde um número, com toda a
confiança do mundo — e pode estar errado, sem nenhum aviso. Dê ao modelo o que
ele faz bem (transformar números em frase clara), não o que ele faz mal
(aritmética). E depois **confira**, com código.

Efeito colateral: **sem chave de API o boletim sai do mesmo jeito**, com o
texto montado por frases fixas. A IA é a cereja, não o bolo.

## Por que semanal, e não diário

O bot antigo rodava todo dia. Este não, e por um motivo de conteúdo: o que
ele mede é a **qualidade** da previsão, e isso quase não muda de segunda para
terça. Um boletim diário repetiria o mesmo número com ruído em volta — e
ninguém leria o quinto.

Na segunda-feira há uma semana inteira fechada, com previsões novas para
conferir, e o boletim tem duas coisas a dizer: como foi esta semana, e como
isso se compara com o acumulado. Aí a cadência faz sentido.

Cadência, aliás, é decisão de projeto — não detalhe técnico. A pergunta certa
não é "de quanto em quanto tempo dá para rodar?", é **"de quanto em quanto
tempo há algo novo para dizer?"**.

## Os dois gráficos contam a mesma história

Não são dois assuntos, são o mesmo assunto em duas escalas:

- **`erro_por_antecedencia.png`** — a regra, em média: quanto mais longe a
  previsão, maior o erro. É a barra que cresce.
- **`de_longe_e_de_perto.png`** — a mesma regra acontecendo, dia a dia. Três
  linhas: o que aconteceu, o que foi previsto na véspera (cola no observado)
  e o que foi previsto vários dias antes (se descola).

O segundo é a prova visual do primeiro. Em aula, mostre nessa ordem.

## Rodar na sua máquina

```bash
pip install -r requirements.txt

python3 1_coletar.py      # anota a previsão de hoje
python3 2_conferir.py     # confere as previsões antigas
python3 3_boletim.py      # gera boletim.md, boletim.html e os gráficos
```

Começando do zero, o passo 2 não tem nada para conferir — ainda não passou
tempo nenhum. Para o histórico nascer cheio, rode uma vez:

```bash
python3 montar_historico.py 21    # recupera as previsões dos últimos 21 dias
```

Isso não inventa nada. O Open-Meteo arquiva as previsões de cada rodada do
modelo: pedindo `temperature_2m_previous_day3` você recebe a temperatura que
**foi prevista 3 dias antes** daquele horário. São as previsões de verdade,
como foram emitidas na época.

O script busca uma antecedência por vez, com pausa entre os pedidos — sete
pedidos seguidos levam erro 429 na API gratuita. Se alguma antecedência não
vier, o que já baixou fica salvo; é só rodar de novo mais tarde.

### Para a IA escrever o texto

Pegue uma chave no [Google AI Studio](https://aistudio.google.com/apikey):

```bash
export GEMINI_API_KEY="sua-chave"
python3 3_boletim.py
```

No GitHub: **Settings → Secrets and variables → Actions → New repository
secret**, com o nome `GEMINI_API_KEY`. Nunca escreva a chave no código.

---

## Rodar sozinho toda semana

`.github/workflows/boletim.yml` executa os passos **toda segunda às 9h de
Brasília** e commita o boletim no repositório. Cada semana vira um commit — o
histórico do git passa a ser a coleção de boletins.

Dá para disparar na hora pelo botão **Actions → boletim-clima → Run workflow**
(útil em aula). Esse botão tem um campo **dias_de_historico**: preencha com
`21` na primeira vez e o robô recupera o histórico antes de gerar o boletim.
Rodando pelo Actions você também escapa do limite por IP da API — se alguma
antecedência faltar rodando na sua máquina, pelo Actions ela costuma vir.

> Agendamento (`schedule`) só funciona a partir do branch padrão. Enquanto isso
> aqui estiver num branch, use o botão.

---

## Roteiro sugerido para a aula

1. **Mostre o bot antigo.** `coletar_clima.py`, 17 linhas. Pergunte: "ele
   acertou ontem?" — ninguém consegue responder. Abra o histórico de commits:
   são 30 dias de previsão, todos perdidos, porque só a figura foi salva.
2. **Aponte o conserto.** Uma linha de CSV por previsão. Só isso.
3. **Abra `boletim.md` no gráfico de barras.** A barra cresce da esquerda
   para a direita: previsão de amanhã erra pouco, de uma semana erra bem mais.
   O robô descobriu isso medindo previsões reais contra o que aconteceu.
4. **Desça para o gráfico das três linhas.** É o mesmo fato, agora visível:
   a linha da véspera cola no observado, a dos 5 dias passeia. Primeiro a
   regra, depois a prova.
5. **Mostre a tabela de chuva.** "Previu chuva e não choveu: N dias." É o tipo
   de número que ninguém tem à mão e que sai de graça quando se guarda dado.
6. **Agora a IA — e a parte que quase ninguém mostra.** Abra `ia.py`. Primeiro
   o `PROMPT`, com a regra "não invente número". Depois `auditar()`, que
   confere se ele obedeceu. Pergunte à turma: *"e se o modelo desobedecer?"* —
   a resposta é a trava. Rode com e sem `GEMINI_API_KEY`: os números não
   mudam, só a redação.
7. **Discuta a cadência.** Por que semanal e não diário? Porque a pergunta
   certa não é "de quanto em quanto tempo dá para rodar", é "de quanto em
   quanto tempo há algo novo para dizer". Vale para qualquer automação.
8. **Feche com a generalização.** Troque Open-Meteo por: preço de commodity,
   andamento de processo, série do IBGE, sensor em campo. A estrutura
   (`anotar → conferir → redigir → auditar`) é a mesma. O clima é só o
   exemplo que dá para conferir em uma semana.

---

## Adaptar para outra cidade ou outro tema

Tudo o que muda de lugar está no topo do `comum.py`:

```python
LATITUDE = -16.68
LONGITUDE = -49.25
CIDADE = "Goiânia"
LIMIAR_CHUVA_MM = 1.0     # a partir de quanto se considera que choveu
```

---

## Arquivos

| Arquivo | O que é |
|---|---|
| `comum.py` | Chamadas à API (com repetição em caso de falha de rede) e leitura/escrita do histórico |
| `ia.py` | A camada de IA: o prompt, a chamada ao Gemini e a auditoria numérica do texto |
| `1_coletar.py` · `2_conferir.py` · `3_boletim.py` | Os três passos |
| `montar_historico.py` | Recupera previsões reais já emitidas, para encher o histórico de uma vez |
| `dados/historico_previsoes.csv` | O caderno: toda previsão já feita |
| `dados/verificacao.csv` | Previsto x observado, com o erro de cada linha |
| `dados/historico_boletins.csv` | As conclusões de cada semana, para o boletim comparar com a anterior |
| `boletim.md` · `boletim.html` | O boletim do dia |
| `graficos/` | As duas figuras do boletim |
| `coletar_clima.py` | O bot original da atividade, mantido como termo de comparação |

## As duas procedências no histórico

A coluna `origem` do CSV distingue de onde veio cada previsão — as duas são
dados reais:

- `arquivo` — recuperada por `montar_historico.py` do acervo de rodadas
  antigas do Open-Meteo.
- `ao_vivo` — coletada pelo próprio robô naquele dia, por `1_coletar.py`.

## Uma ressalva honesta

O "observado" vem da própria API (reanálise), não de uma estação meteorológica
específica de Goiânia. É bom o bastante para o exercício e para a ordem de
grandeza do erro. Para uma medição rigorosa, o passo 2 deveria buscar o dado
de uma estação do INMET — e é um bom exercício seguinte, porque só muda a
função que preenche o dicionário `observado`.

---

Dados: [Open-Meteo](https://open-meteo.com) (uso não comercial, sem chave).
