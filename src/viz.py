# src/viz.py
import plotly.express as px
import pandas as pd


def plot_pie_cpf_cnpj(qtd_cpfs, qtd_cnpjs):
    df = pd.DataFrame(
        {"tipo": ["CPF", "CNPJ"], "quantidade": [int(qtd_cpfs), int(qtd_cnpjs)]}
    )
    fig = px.pie(
        df,
        names="tipo",
        values="quantidade",
        title="Proporção de CPFs vs CNPJs únicos",
        hole=0.4,
    )
    fig.update_traces(textinfo="percent+label")
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10))
    return fig


def plot_bar_multi_protocols(qtd_cpf_multi, qtd_cnpj_multi):
    df = pd.DataFrame(
        {
            "tipo": ["CPF (>1 protocolo)", "CNPJ (>1 protocolo)"],
            "quantidade": [int(qtd_cpf_multi), int(qtd_cnpj_multi)],
        }
    )
    fig = px.bar(
        df, x="tipo", y="quantidade", title="Devedores com >1 protocolo (por tipo)"
    )
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=20))
    return fig
