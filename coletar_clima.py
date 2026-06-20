import requests, pandas as pd, matplotlib
matplotlib.use("Agg")            # backend sem tela (essencial na nuvem)
import matplotlib.pyplot as plt

URL = ("https://api.open-meteo.com/v1/forecast"
       "?latitude=-16.68&longitude=-49.25"
       "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
       "&timezone=America/Sao_Paulo")

dados = requests.get(URL, timeout=30).json()["daily"]
df = pd.DataFrame(dados)

fig, ax = plt.subplots(figsize=(8, 4))
ax.plot(df["time"], df["temperature_2m_max"], marker="o", label="Máx (°C)")
ax.plot(df["time"], df["temperature_2m_min"], marker="o", label="Mín (°C)")
ax.set_title("Previsão — Goiânia")
ax.legend(); ax.grid(True); fig.autofmt_xdate()
fig.savefig("previsao_goiania.png", dpi=120, bbox_inches="tight")
print("gráfico salvo")
