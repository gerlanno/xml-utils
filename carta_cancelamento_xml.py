# app_streamlit_xml_analise_especifico.py
import streamlit as st
import pandas as pd
import io
import re
from lxml import etree

st.set_page_config(
    page_title="Análise XML - Cancelamento (estrutura específica)", layout="wide"
)

st.title("Análise de XMLs — Títulos de Cancelamento (parser específico)")

uploaded_files = st.file_uploader(
    "Upload de XMLs (multi) — estrutura: <carta_cancelamento><titulos><titulo>...",
    type=["xml"],
    accept_multiple_files=True,
)

# Regexes / helpers
ONLY_DIGITS = re.compile(r"\d+")
CPF_CLEAN = re.compile(r"\D")
PHONE_CLEAN = re.compile(r"[^0-9+]")


def clean_digits(s):
    if s is None:
        return None
    s = str(s).strip()
    if s == "":
        return None
    # Remove common mask characters but keep digits
    digits = re.sub(r"\D", "", s)
    return digits if digits != "" else None


def detect_doc_type(raw):
    """
    Return "CPF", "CNPJ" or "UNKNOWN" based on cleaned digits length.
    Handles masked strings (returns UNKNOWN).
    """
    if not raw:
        return "UNKNOWN"
    # If raw contains '*' or words like 'MASCAR' then unknown
    if (
        "*" in raw
        or "MASCAR" in raw.upper()
        or "MASCARADO" in raw.upper()
        or "MASCARA" in raw.upper()
    ):
        return "UNKNOWN"
    digits = clean_digits(raw)
    if digits is None:
        return "UNKNOWN"
    if len(digits) == 11:
        return "CPF"
    if len(digits) == 14:
        return "CNPJ"
    return "UNKNOWN"


def first_text(elem):
    if elem is None:
        return None
    txt = (elem.text or "").strip()
    return txt if txt != "" else None


def find_child_text(parent, tag_names):
    """
    parent: lxml element
    tag_names: iterable of local names to search (case-insensitive)
    returns first matching child's text or None
    """
    if parent is None:
        return None
    tag_names_lower = {n.lower() for n in tag_names}
    for child in parent.iter():
        name = etree.QName(child).localname.lower()
        if name in tag_names_lower:
            t = first_text(child)
            if t:
                return t
    return None


def parse_single_xml(file_like):
    """
    Parse a single XML with the expected structure and return list of records:
    one record per devedor (so titles with multiple devedores produce multiple rows).
    Fields:
      - source_file, protocolo, numerotitulo, credor, valorprotestado, dataprotesto, devedor_nome,
        devedor_documento_raw, devedor_documento_clean, devedor_tipo, telefone_raw, telefone_clean
    """
    try:
        tree = etree.parse(file_like)
        root = tree.getroot()
    except Exception as e:
        return [], f"Erro ao parsear XML: {e}"

    records = []

    # Navigate to titulos -> titulo
    # Accept either root being <carta_cancelamento> or direct <titulos>
    titulos_nodes = []
    # find all 'titulo' nodes anywhere
    for elem in root.iter():
        if etree.QName(elem).localname.lower() == "titulo":
            titulos_nodes.append(elem)

    # If none found, maybe <titulos> directly contains single <titulo> children
    if not titulos_nodes:
        titulos_parent = None
        for elem in root.iter():
            if etree.QName(elem).localname.lower() == "titulos":
                titulos_parent = elem
                break
        if titulos_parent is not None:
            for child in titulos_parent:
                if etree.QName(child).localname.lower() == "titulo":
                    titulos_nodes.append(child)

    # If still none, fallback to root
    if not titulos_nodes:
        titulos_nodes = [root]

    for t in titulos_nodes:
        protocolo = find_child_text(t, ("protocolo",))
        numerotitulo = find_child_text(t, ("numerotitulo", "numero", "numero_titulo"))
        credor = find_child_text(t, ("credor", "reclamante", "exequente"))
        valorprotestado = find_child_text(t, ("valorprotestado", "valor"))
        dataprotesto = find_child_text(t, ("dataprotesto", "data_protesto", "data"))

        # find devedores -> multiple devedor
        devedores_parent = None
        for child in t:
            if etree.QName(child).localname.lower() == "devedores":
                devedores_parent = child
                break

        devedor_nodes = []
        if devedores_parent is not None:
            for d in devedores_parent:
                if etree.QName(d).localname.lower() == "devedor":
                    devedor_nodes.append(d)

        # If none, try to find any 'devedor' anywhere under t
        if not devedor_nodes:
            for elem in t.iter():
                if etree.QName(elem).localname.lower() == "devedor":
                    devedor_nodes.append(elem)

        # If still none, create an implicit devedor from title
        if not devedor_nodes:
            devedor_nodes = [t]

        for d in devedor_nodes:
            nome = find_child_text(
                d, ("nome", "nome_devedor", "nome_parte", "razao_social")
            )
            documento_raw = find_child_text(
                d, ("documento", "cpf", "cnpj", "doc", "documento_devedor")
            )
            telefone_raw = None
            # telefones structure: <telefones><telefone>...</telefone></telefones>
            for child in d.iter():
                if etree.QName(child).localname.lower() == "telefone":
                    telefone_raw = first_text(child)
                    if telefone_raw:
                        break
            # clean & detect
            documento_clean = clean_digits(documento_raw)
            telefone_clean = None
            if telefone_raw:
                telefone_clean = re.sub(r"\D", "", telefone_raw) or None

            devedor_tipo = detect_doc_type(documento_raw)

            records.append(
                {
                    "source_file": getattr(file_like, "name", "uploaded"),
                    "protocolo": protocolo,
                    "numerotitulo": numerotitulo,
                    "credor": credor,
                    "valorprotestado": valorprotestado,
                    "dataprotesto": dataprotesto,
                    "devedor_nome": nome,
                    "devedor_documento_raw": documento_raw,
                    "devedor_documento": documento_clean,
                    "devedor_tipo": devedor_tipo,
                    "telefone_raw": telefone_raw,
                    "telefone": telefone_clean,
                }
            )

    return records, None


# Main
if uploaded_files:
    all_records = []
    errors = []
    total_titulos_declared = None

    for f in uploaded_files:
        # try to read declared TotalTitulos from file (if present)
        try:
            # parse quickly to find TotalTitulos
            root_try = etree.parse(f).getroot()
            for elem in root_try.iter():
                if etree.QName(elem).localname.lower() == "totaltitulos":
                    txt = (elem.text or "").strip()
                    if txt:
                        total_titulos_declared = int(re.sub(r"\D", "", txt))
                    break
            # reset file pointer for full parse (if file object supports seek)
            try:
                f.seek(0)
            except Exception:
                pass
        except Exception:
            # ignore read-only peek errors
            try:
                f.seek(0)
            except Exception:
                pass

        recs, err = parse_single_xml(f)
        if err:
            errors.append(f"{f.name}: {err}")
        else:
            for r in recs:
                r["source_file"] = f.name
            all_records.extend(recs)

    if errors:
        st.warning("Alguns arquivos apresentaram erro ao parsear:")
        for e in errors:
            st.write("- " + e)

    if not all_records:
        st.info("Nenhum registro de devedor extraído. Verifique a estrutura dos XMLs.")
    else:
        df = pd.DataFrame(all_records)

        # Determine title_key (unique title identifier) - prefer numerotitulo then protocolo then index
        def title_key(row):
            if (
                pd.notna(row.get("numerotitulo"))
                and str(row.get("numerotitulo")).strip() != ""
            ):
                return str(row.get("numerotitulo"))
            if (
                pd.notna(row.get("protocolo"))
                and str(row.get("protocolo")).strip() != ""
            ):
                return "P:" + str(row.get("protocolo"))
            return f"ROWIDX:{row.name}"

        df["title_key"] = df.apply(title_key, axis=1)

        # Has telefone per row
        df["has_telefone_row"] = df["telefone"].notna() & (
            df["telefone"].astype(str).str.strip() != ""
        )

        # --- INCLUIR AQUI: cálculo de protocolos únicos por devedor (colocar após df e após definir title_key) ---
        # Agrupa protocolos únicos por documento (ignora documentos nulos)
        prot_by_devedor = (
            df.dropna(subset=["devedor_documento"])
            .groupby("devedor_documento")["protocolo"]
            .apply(lambda s: sorted({str(x).strip() for x in s.dropna().astype(str) if str(x).strip() != ""}))
        )

        # Conta protocolos únicos
        prot_counts = prot_by_devedor.apply(len)

        # Recupera o(s) tipo(s) associados a cada documento (pode ser "CPF","CNPJ","UNKNOWN", ou combinação)
        type_by_doc = (
            df.dropna(subset=["devedor_documento"])
            .groupby("devedor_documento")["devedor_tipo"]
            .apply(lambda s: ",".join(sorted(set([str(x) for x in s.dropna() if str(x).strip() != ""])) ) )
        )

        # Filtra devedores com mais de 1 protocolo
        multi_mask = prot_counts > 1
        multi_docs = prot_counts[multi_mask]

        # Separar CPF e CNPJ (considera documento como CPF se o campo devedor_tipo contiver "CPF")
        cpf_multi = multi_docs[type_by_doc.loc[multi_docs.index].str.contains("CPF", na=False)]
        cnpj_multi = multi_docs[type_by_doc.loc[multi_docs.index].str.contains("CNPJ", na=False)]

        # DataFrames para exibir/exportar
        def make_df_from_series(series):
            if series.empty:
                return pd.DataFrame(columns=["devedor_documento", "qtd_protocolos_unicos", "protocolos_unicos"])
            return pd.DataFrame({
                "devedor_documento": series.index,
                "qtd_protocolos_unicos": series.values,
                "protocolos_unicos": prot_by_devedor.loc[series.index].apply(lambda lst: ", ".join(lst))
            }).reset_index(drop=True)

        df_cpf_multi = make_df_from_series(cpf_multi)
        df_cnpj_multi = make_df_from_series(cnpj_multi)

        # Métricas laterais separadas
        st.sidebar.metric("CPFs com >1 protocolo único", int(df_cpf_multi.shape[0]))
        st.sidebar.metric("CNPJs com >1 protocolo único", int(df_cnpj_multi.shape[0]))

        # Seção na página principal
        st.subheader("Devedores (CPF) com mais de 1 protocolo único")
        st.write("Documentos classificados como CPF que aparecem em mais de um protocolo (protocolos únicos listados).")
        st.dataframe(df_cpf_multi, height=250)
        st.download_button("Baixar: CPFs com >1 protocolo (CSV)", data=df_cpf_multi.to_csv(index=False).encode("utf-8"), file_name="cpfs_multi_protocolos.csv", mime="text/csv")

        st.subheader("Devedores (CNPJ) com mais de 1 protocolo único")
        st.write("Documentos classificados como CNPJ que aparecem em mais de um protocolo (protocolos únicos listados).")
        st.dataframe(df_cnpj_multi, height=250)
        st.download_button("Baixar: CNPJs com >1 protocolo (CSV)", data=df_cnpj_multi.to_csv(index=False).encode("utf-8"), file_name="cnpjs_multi_protocolos.csv", mime="text/csv")
        # --- FIM DO TRECHO ---
        
        
        
        
        # Aggregations per title
        grouped = df.groupby("title_key")

        total_titulos = df["protocolo"].nunique()
        # If file declared TotalTitulos and there's only one uploaded file, consider showing it for comparison
        if total_titulos_declared is not None and len(uploaded_files) == 1:
            st.info(f"TotalTitulos declarado no XML: {total_titulos_declared}")

        titles_with_phone = int(grouped["has_telefone_row"].any().sum())

        has_cpf_by_title = grouped["devedor_tipo"].apply(
            lambda s: any(x == "CPF" for x in s)
        )
        has_cnpj_by_title = grouped["devedor_tipo"].apply(
            lambda s: any(x == "CNPJ" for x in s)
        )

        titles_with_cpf = int(has_cpf_by_title.sum())
        titles_with_cnpj = int(has_cnpj_by_title.sum())
        titles_with_both = int(((has_cpf_by_title) & (has_cnpj_by_title)).sum())

        # CPFs únicos (usar devedor_documento tal como armazenado; ignora nulos)
        unique_cpfs = df.loc[df["devedor_tipo"] == "CPF", "devedor_documento"].dropna().unique()
        qtd_cpfs_unicos = unique_cpfs.shape[0]

        # CNPJs únicos
        unique_cnpjs = df.loc[df["devedor_tipo"] == "CNPJ", "devedor_documento"].dropna().unique()
        qtd_cnpjs_unicos = unique_cnpjs.shape[0]
        
        # Total de devedores únicos (mantém a definição anterior, se quiser)
        unique_devedores = pd.Series(df["devedor_documento"].dropna().unique()).shape[0]

        # Sidebar metrics
        st.sidebar.header("Totalizadores")
        st.sidebar.metric("Total títulos (únicos extraídos)", total_titulos)
        st.sidebar.metric("Títulos com pelo menos 1 telefone", titles_with_phone)
        st.sidebar.metric("Títulos com devedor CPF (PF)", titles_with_cpf)
        st.sidebar.metric("Títulos com devedor CNPJ (PJ)", titles_with_cnpj)
        st.sidebar.metric("Títulos com ambos (CPF e CNPJ)", titles_with_both)
        
        # Exibir nas métricas da sidebar (ou onde você exibe métricas)
        st.sidebar.metric("Devedores únicos (CPFs)", qtd_cpfs_unicos)
        st.sidebar.metric("Devedores únicos (CNPJs)", qtd_cnpjs_unicos)
        st.sidebar.metric("Devedores únicos (total)", int(unique_devedores))

        # Main metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total títulos", total_titulos)
        c2.metric("Títulos com telefone", titles_with_phone)
        c3.metric("Títulos com CPF (PF)", titles_with_cpf)
        c4.metric("Títulos com CNPJ (PJ)", titles_with_cnpj)
        st.write(f"Títulos com ambos CPF e CNPJ: **{titles_with_both}**")

        st.markdown("---")
        st.subheader("Tabela analítica (cada linha = 1 devedor extraído)")
        st.write(
            "Filtre por arquivo, tipo, nome ou documento. Baixe CSV/Excel se precisar."
        )

        # Filters
        with st.expander("Filtros"):
            cols = st.columns(3)
            unique_files = sorted(df["source_file"].unique())
            selected_files = cols[0].multiselect(
                "Arquivos", unique_files, default=unique_files
            )
            tipo_options = sorted(df["devedor_tipo"].fillna("UNKNOWN").unique())
            selected_types = cols[1].multiselect(
                "Tipo de devedor", tipo_options, default=tipo_options
            )
            text_search = cols[2].text_input("Buscar por nome ou documento")

        mask = df["source_file"].isin(selected_files)
        if selected_types:
            mask &= df["devedor_tipo"].fillna("UNKNOWN").isin(selected_types)
        if text_search:
            ts = text_search.lower()
            mask &= df.apply(
                lambda r: ts in str(r.get("devedor_nome") or "").lower()
                or ts in str(r.get("devedor_documento_raw") or "").lower()
                or ts in str(r.get("devedor_documento") or ""),
                axis=1,
            )

        df_filtered = df[mask].copy()

        display_cols = [
            "source_file",
            "title_key",
            "numerotitulo",
            "protocolo",
            "credor",
            "valorprotestado",
            "dataprotesto",
            "devedor_nome",
            "devedor_documento_raw",
            "devedor_documento",
            "devedor_tipo",
            "telefone_raw",
            "telefone",
        ]
        display_cols = [c for c in display_cols if c in df_filtered.columns]
        st.dataframe(df_filtered[display_cols].reset_index(drop=True), height=420)

        # Aggregated per-title summary
        st.subheader("Resumo por título (agregado)")
        agg = (
            grouped.agg(
                numerotitulo=("numerotitulo", "first"),
                protocolo=("protocolo", "first"),
                credor=("credor", "first"),
                dataprotesto=("dataprotesto", "first"),
                valorprotestado=("valorprotestado", "first"),
                devedores_docs=(
                    "devedor_documento",
                    lambda s: (
                        ", ".join(sorted(set([x for x in s.dropna()])))
                        if s.dropna().any()
                        else ""
                    ),
                ),
                tipos_devedores=(
                    "devedor_tipo",
                    lambda s: (
                        ", ".join(sorted(set([x for x in s.dropna()])))
                        if s.dropna().any()
                        else ""
                    ),
                ),
                tem_telefone=("has_telefone_row", "any"),
                arquivos=("source_file", lambda s: ", ".join(sorted(set(s)))),
            )
            .reset_index()
            .rename(columns={"title_key": "titulo_chave"})
        )
        st.dataframe(agg, height=350)

        # Export options
        csv_bytes = df_filtered.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Baixar tabela filtrada (CSV)",
            data=csv_bytes,
            file_name="titulos_devedores_filtrados.csv",
            mime="text/csv",
        )

        to_excel = io.BytesIO()
        with pd.ExcelWriter(to_excel, engine="openpyxl") as writer:
            df_filtered.to_excel(writer, sheet_name="raw", index=False)
            agg.to_excel(writer, sheet_name="por_titulo", index=False)
        to_excel.seek(0)
        st.download_button(
            "Baixar relatório (Excel)",
            data=to_excel,
            file_name="relatorio_titulos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        st.success("Análise concluída.")
else:
    st.info(
        "Faça upload de um ou mais arquivos XML com a estrutura exemplo para iniciar a análise."
    )
