# Boletim de acerto da previsão — Goiânia

**Gerado em 2026-09-21** · 100 previsões conferidas (2026-09-01 a 2026-09-20)

> Previsões conferidas: 100 recuperadas do arquivo de rodadas antigas do Open-Meteo. São previsões reais, emitidas antes da data que descrevem — nada aqui é simulado.

## Análise

Nas 100 previsões conferidas entre 2026-09-01 e 2026-09-20, o erro médio da temperatura máxima foi de 1.44 °C. A qualidade cai com a distância: com 1 dia de antecedência o erro médio é 1.19 °C, e com 5 dias sobe para 1.79 °C.

O viés de +0.73 °C indica que a previsão tende a ficar acima do que se observa. Para chuva, o acerto entre "vai chover" e "não vai" foi de 92.0%. O maior desacerto do período foi em 2026-09-02: previa 34.0 °C e foram 29.5 °C.

<sub>texto automático (sem GEMINI_API_KEY). Todos os números foram calculados em Python; a IA apenas redigiu o texto.</sub>

## Os números

| Medida | Valor |
|---|---|
| Erro médio da máxima | 1.44 °C |
| Erro médio da mínima | 0.89 °C |
| Viés da máxima | +0.73 °C |
| Acerto chove / não chove | 92.0% |

### Erro por antecedência

| Antecedência | Previsões | Erro médio máx. | Erro médio mín. | Viés máx. |
|---|---|---|---|---|
| 1 dia | 20 | 1.19 °C | 0.51 °C | +0.66 °C |
| 2 dias | 20 | 1.26 °C | 0.81 °C | +0.92 °C |
| 3 dias | 20 | 1.35 °C | 0.72 °C | +0.82 °C |
| 4 dias | 20 | 1.61 °C | 0.97 °C | +0.54 °C |
| 5 dias | 20 | 1.79 °C | 1.47 °C | +0.72 °C |

![Erro médio por antecedência](graficos/erro_por_antecedencia.png)

### Chuva: acertou o sim ou não?

Considera-se que choveu a partir de 1.0 mm no dia.

| Situação | Dias |
|---|---|
| Previu chuva e choveu | 31 |
| Previu chuva e não choveu | 4 |
| Não previu e choveu | 4 |
| Previu seco e ficou seco | 61 |

### Maior desacerto do período

Em **2026-09-02**, com 5 dias de antecedência: previsto 34.0 °C, observado 29.5 °C (+4.5 °C).

![Previsto x observado](graficos/previsto_vs_observado.png)

---

<sub>Dados: Open-Meteo. O “observado” é a melhor estimativa da API para datas passadas (reanálise), não a leitura de uma estação específica. Gerado automaticamente por [GeocursoAtividade3](https://github.com/VictorGit10/GeocursoAtividade3).</sub>
