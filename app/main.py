# app/main.py
import streamlit as st
from pathlib import Path
import pandas as pd
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
from src.parser import parse_files_to_dataframe
from src.metrics import (
    compute_all_metrics,
    make_cpf_cnpj_lists,
    protocols_multi_by_type,
)
from src.viz import plot_pie_cpf_cnpj, plot_bar_multi_protocols

# Page config
st.set_page_config(
    page_title="Analise Pré Disparos - RTLA",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load CSS (wrap inside <style> so it's interpreted as CSS, not printed)
css_path = Path(__file__).parents[1] / "styles" / "styles.css"
if css_path.exists():
    css = css_path.read_text()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# HEADER
col1, col2 = st.columns([0.12, 0.88])
with col1:
    st.markdown("")
    logo_path = Path(__file__).parents[1] / "assets" / "logo_rtla_placeholder.png"
    st.image(str(logo_path), width=150)
with col2:
    st.markdown(
        "<h1 style='margin:0'>Analise Pré Disparos</h1>", unsafe_allow_html=True
    )
    st.markdown(
        "Dashboard para análise de títulos cancelamento — extração de devedores, protocolos e indicadores."
    )

st.markdown("---")

# Upload area
uploaded_files = st.file_uploader(
    "Upload de XMLs (arraste múltiplos arquivos)",
    type=["xml"],
    accept_multiple_files=True,
)

# Sidebar: quick info & downloads
st.sidebar.header("Ações Rápidas")
st.sidebar.write("Faça upload dos XMLs e aguarde a análise automática.")

if uploaded_files:
    # parse
    with st.spinner("Parseando arquivos..."):
        df, parse_errors = parse_files_to_dataframe(uploaded_files)

    if parse_errors:
        st.warning("Alguns arquivos apresentaram erros no parse. Veja abaixo:")
        for e in parse_errors:
            st.write("- " + e)

    if df.empty:
        st.info("Nenhum registro extraído — verifique a estrutura dos XMLs.")
    else:
        # compute metrics
        metrics = compute_all_metrics(df)

        # top cards
        st.markdown("### Indicadores rápidos")
        c1, c2, c3, c4 = st.columns(4)
        c5, c6, c7, c8 = st.columns(4)

        c1.markdown(
            f"<div class='card'><div class='card-title'>Total Títulos</div><div class='card-value'>{metrics['total_titulos']}</div></div>",
            unsafe_allow_html=True,
        )
        c2.markdown(
            f"<div class='card'><div class='card-title'>Títulos com Telefone</div><div class='card-value'>{metrics['titles_with_phone']}</div></div>",
            unsafe_allow_html=True,
        )
        c3.markdown(
            f"<div class='card'><div class='card-title'>Títulos com CPF</div><div class='card-value'>{metrics['titles_with_cpf']}</div></div>",
            unsafe_allow_html=True,
        )
        c4.markdown(
            f"<div class='card'><div class='card-title'>Títulos com CNPJ</div><div class='card-value'>{metrics['titles_with_cnpj']}</div></div>",
            unsafe_allow_html=True,
        )

        c5.markdown(
            f"<div class='card'><div class='card-title'>CPFs Únicos</div><div class='card-value'>{metrics['qtd_cpfs_unicos']}</div></div>",
            unsafe_allow_html=True,
        )
        c6.markdown(
            f"<div class='card'><div class='card-title'>CNPJs Únicos</div><div class='card-value'>{metrics['qtd_cnpjs_unicos']}</div></div>",
            unsafe_allow_html=True,
        )
        c7.markdown(
            f"<div class='card'><div class='card-title'>CPFs multi protocolo</div><div class='card-value'>{metrics['cpf_multi_count']}</div></div>",
            unsafe_allow_html=True,
        )
        c8.markdown(
            f"<div class='card'><div class='card-title'>CNPJs multi protocolo</div><div class='card-value'>{metrics['cnpj_multi_count']}</div></div>",
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # Tabs: tables + charts
        tab1, tab2, tab3 = st.tabs(
            ["Analítico Geral", "CPFs >1 protocolo", "CNPJs >1 protocolo"]
        )

        with tab1:
            st.subheader("Tabela Analítica (cada linha = 1 devedor extraído)")
            # filters
            files = sorted(df["source_file"].unique().tolist())
            selected_files = st.multiselect("Arquivos", files, default=files)
            tipo_opts = sorted(df["devedor_tipo"].fillna("UNKNOWN").unique().tolist())
            selected_tipos = st.multiselect(
                "Tipo de Devedor", tipo_opts, default=tipo_opts
            )
            text_search = st.text_input("Buscar por nome ou documento")

            mask = df["source_file"].isin(selected_files)
            if selected_tipos:
                mask &= df["devedor_tipo"].fillna("UNKNOWN").isin(selected_tipos)
            if text_search:
                ts = text_search.lower()
                mask &= df.apply(
                    lambda r: ts in str(r.get("devedor_nome") or "").lower()
                    or ts in str(r.get("devedor_documento_raw") or "").lower()
                    or ts in str(r.get("devedor_documento") or ""),
                    axis=1,
                )

            df_filtered = df[mask].copy()
            st.dataframe(df_filtered.reset_index(drop=True), height=480)

            # downloads
            st.download_button(
                "Baixar CSV (filtrado)",
                data=df_filtered.to_csv(index=False).encode("utf-8"),
                file_name="analitico_filtrado.csv",
                mime="text/csv",
            )

            # charts
            st.subheader("Gráficos")
            col_a, col_b = st.columns(2)
            with col_a:
                fig1 = plot_pie_cpf_cnpj(
                    metrics["qtd_cpfs_unicos"], metrics["qtd_cnpjs_unicos"]
                )
                st.plotly_chart(fig1, use_container_width=True)
            with col_b:
                fig2 = plot_bar_multi_protocols(
                    metrics["cpf_multi_count"], metrics["cnpj_multi_count"]
                )
                st.plotly_chart(fig2, use_container_width=True)

        with tab2:
            st.subheader("CPFs com mais de 1 protocolo único")
            st.dataframe(metrics["df_cpf_multi"], height=480)
            st.download_button(
                "Baixar: CPFs com >1 protocolo (CSV)",
                data=metrics["df_cpf_multi"].to_csv(index=False).encode("utf-8"),
                file_name="cpfs_multi_protocolos.csv",
                mime="text/csv",
            )

        with tab3:
            st.subheader("CNPJs com mais de 1 protocolo único")
            st.dataframe(metrics["df_cnpj_multi"], height=480)
            st.download_button(
                "Baixar: CNPJs com >1 protocolo (CSV)",
                data=metrics["df_cnpj_multi"].to_csv(index=False).encode("utf-8"),
                file_name="cnpjs_multi_protocolos.csv",
                mime="text/csv",
            )

        st.markdown("---")
        st.info(
            "Exportações disponíveis no final de cada aba — baixe CSV/Excel conforme necessário."
        )

else:
    st.info("Faça upload de arquivos XML para iniciar a análise.")
