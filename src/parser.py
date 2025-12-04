# src/parser.py
from lxml import etree
import re
import pandas as pd

CPF_RE = re.compile(r"\d{11}")
CNPJ_RE = re.compile(r"\d{14}")


def clean_digits(s):
    if s is None:
        return None
    s = str(s).strip()
    if s == "":
        return None
    digits = re.sub(r"\D", "", s)
    return digits if digits else None


def detect_doc_type(raw):
    if not raw:
        return "UNKNOWN"
    if "*" in raw or "MASCAR" in raw.upper():
        return "UNKNOWN"
    digits = clean_digits(raw)
    if not digits:
        return "UNKNOWN"
    if len(digits) == 11:
        return "CPF"
    if len(digits) == 14:
        return "CNPJ"
    return "UNKNOWN"


def first_text(elem):
    if elem is None:
        return None
    t = (elem.text or "").strip()
    return t if t else None


def find_child_text(parent, tag_names):
    if parent is None:
        return None
    names = {n.lower() for n in tag_names}
    for child in parent.iter():
        if etree.QName(child).localname.lower() in names:
            t = first_text(child)
            if t:
                return t
    return None


def parse_single_tree(tree, source_name="uploaded"):
    root = tree.getroot()
    records = []
    # find all titulo nodes
    titulo_nodes = [
        e for e in root.iter() if etree.QName(e).localname.lower() == "titulo"
    ]
    if not titulo_nodes:
        # fallback: maybe root is titulo
        titulo_nodes = [root]

    for t in titulo_nodes:
        protocolo = find_child_text(t, ("protocolo",))
        numerotitulo = find_child_text(t, ("numerotitulo", "numero", "numero_titulo"))
        credor = find_child_text(t, ("credor",))
        valorprotestado = find_child_text(t, ("valorprotestado", "valor"))
        dataprotesto = find_child_text(t, ("dataprotesto", "data_protesto", "data"))

        # devedores
        devedor_nodes = []
        for elem in t.iter():
            if etree.QName(elem).localname.lower() == "devedor":
                devedor_nodes.append(elem)
        if not devedor_nodes:
            # if none, maybe single implicit devedor under titulos
            for elem in t.iter():
                if etree.QName(elem).localname.lower() == "devedores":
                    for ch in elem:
                        if etree.QName(ch).localname.lower() == "devedor":
                            devedor_nodes.append(ch)

        if not devedor_nodes:
            devedor_nodes = [t]

        for d in devedor_nodes:
            nome = find_child_text(d, ("nome", "nome_devedor", "razao_social"))
            documento_raw = find_child_text(d, ("documento", "cpf", "cnpj", "doc"))
            telefone_raw = None
            for child in d.iter():
                if etree.QName(child).localname.lower() == "telefone":
                    telefone_raw = first_text(child)
                    if telefone_raw:
                        break

            documento_clean = clean_digits(documento_raw) or (
                documento_raw.strip() if documento_raw else None
            )
            telefone_clean = clean_digits(telefone_raw)

            devedor_tipo = detect_doc_type(documento_raw)

            records.append(
                {
                    "source_file": source_name,
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
    return records


def parse_files_to_dataframe(file_objs):
    """
    file_objs: list of uploaded file-like objects
    returns: pd.DataFrame (all records) and list of parse_errors
    """
    all_records = []
    errors = []
    for f in file_objs:
        try:
            # parse using lxml
            tree = etree.parse(f)
            recs = parse_single_tree(tree, source_name=getattr(f, "name", "uploaded"))
            all_records.extend(recs)
            try:
                f.seek(0)
            except Exception:
                pass
        except Exception as e:
            errors.append(f"{getattr(f,'name','file')}: {e}")
            try:
                f.seek(0)
            except Exception:
                pass

    df = pd.DataFrame(all_records)
    # ensure columns exist
    if df.empty:
        return df, errors

    # title_key
    def title_key(row):
        if (
            pd.notna(row.get("numerotitulo"))
            and str(row.get("numerotitulo")).strip() != ""
        ):
            return str(row.get("numerotitulo"))
        if pd.notna(row.get("protocolo")) and str(row.get("protocolo")).strip() != "":
            return "P:" + str(row.get("protocolo"))
        return f"ROWIDX:{row.name}"

    df["title_key"] = df.apply(title_key, axis=1)
    return df, errors
