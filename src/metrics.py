# src/metrics.py
import pandas as pd


def compute_all_metrics(df):
    """
    Recebe dataframe do parser e retorna dict com métricas e tabelas prontas.
    """
    # safety: ensure columns exist
    required = [
        "title_key",
        "protocolo",
        "devedor_documento",
        "devedor_tipo",
        "telefone",
    ]
    for c in required:
        if c not in df.columns:
            df[c] = None

    grouped = df.groupby("title_key")

    total_titulos = df["title_key"].nunique()
    titles_with_phone = int(
        grouped["telefone"]
        .apply(
            lambda s: s.dropna()
            .astype(str)
            .str.strip()
            .replace("", pd.NA)
            .notna()
            .any()
        )
        .sum()
    )
    has_cpf_by_title = grouped["devedor_tipo"].apply(lambda s: s.eq("CPF").any())
    has_cnpj_by_title = grouped["devedor_tipo"].apply(lambda s: s.eq("CNPJ").any())

    titles_with_cpf = int(has_cpf_by_title.sum())
    titles_with_cnpj = int(has_cnpj_by_title.sum())
    titles_with_both = int(((has_cpf_by_title) & (has_cnpj_by_title)).sum())

    # unique cpfs / cnpjs
    unique_cpfs = (
        df.loc[df["devedor_tipo"] == "CPF", "devedor_documento"].dropna().unique()
    )
    unique_cnpjs = (
        df.loc[df["devedor_tipo"] == "CNPJ", "devedor_documento"].dropna().unique()
    )
    qtd_cpfs_unicos = unique_cpfs.shape[0]
    qtd_cnpjs_unicos = unique_cnpjs.shape[0]
    unique_devedores_total = pd.Series(df["devedor_documento"].dropna().unique()).shape[
        0
    ]

    # multi-protocolos por tipo
    df_cpf_multi, cpf_multi_count = protocols_multi_by_type(df, tipo="CPF")
    df_cnpj_multi, cnpj_multi_count = protocols_multi_by_type(df, tipo="CNPJ")

    return {
        "total_titulos": int(total_titulos),
        "titles_with_phone": int(titles_with_phone),
        "titles_with_cpf": int(titles_with_cpf),
        "titles_with_cnpj": int(titles_with_cnpj),
        "titles_with_both": int(titles_with_both),
        "qtd_cpfs_unicos": int(qtd_cpfs_unicos),
        "qtd_cnpjs_unicos": int(qtd_cnpjs_unicos),
        "unique_devedores_total": int(unique_devedores_total),
        "df_cpf_multi": df_cpf_multi,
        "df_cnpj_multi": df_cnpj_multi,
        "cpf_multi_count": int(cpf_multi_count),
        "cnpj_multi_count": int(cnpj_multi_count),
    }


def protocols_multi_by_type(df, tipo="CPF"):
    """
    Retorna (df_multi, count) onde df_multi é dataframe com documentos do tipo
    especificado que possuem mais de 1 protocolo único.
    """
    # dropna docs
    df_docs = df.dropna(subset=["devedor_documento"]).copy()
    # group protocols per document
    prot_by_doc = df_docs.groupby("devedor_documento")["protocolo"].apply(
        lambda s: sorted(
            {str(x).strip() for x in s.dropna().astype(str) if str(x).strip() != ""}
        )
    )
    prot_counts = prot_by_doc.apply(len)
    # types by doc
    type_by_doc = df_docs.groupby("devedor_documento")["devedor_tipo"].apply(
        lambda s: ",".join(sorted(set([str(x) for x in s.dropna() if str(x).strip()])))
    )
    multi = prot_counts[prot_counts > 1]
    # filter by tipo
    mask = type_by_doc.loc[multi.index].str.contains(tipo, na=False)
    selected = multi[mask]
    if selected.empty:
        df_multi = pd.DataFrame(
            columns=["devedor_documento", "qtd_protocolos_unicos", "protocolos_unicos"]
        )
        return df_multi, 0
    df_multi = (
        pd.DataFrame(
            {
                "devedor_documento": selected.index,
                "qtd_protocolos_unicos": selected.values,
                "protocolos_unicos": prot_by_doc.loc[selected.index].apply(
                    lambda lst: ", ".join(lst)
                ),
            }
        )
        .reset_index(drop=True)       
    )
    return df_multi, df_multi.shape[0]


def make_cpf_cnpj_lists(df):
    cpfs = sorted(
        df.loc[df["devedor_tipo"] == "CPF", "devedor_documento"]
        .dropna()
        .unique()
        .tolist()
    )
    cnpjs = sorted(
        df.loc[df["devedor_tipo"] == "CNPJ", "devedor_documento"]
        .dropna()
        .unique()
        .tolist()
    )
    return cpfs, cnpjs
