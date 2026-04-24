import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import BytesIO

st.title("Riconciliazione Amex vs Mastrino - V3 stabile")

pdf_file = st.file_uploader("Carica PDF Amex", type=["pdf"])
excel_file = st.file_uploader("Carica Excel Mastrino", type=["xlsx","csv"])


# ---------------- PDF ----------------
def estrai_pdf(file):
    importi = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            matches = re.findall(r'\d{1,3}(?:\.\d{3})*,\d{2}', text)

            for m in matches:
                val = float(m.replace('.', '').replace(',', '.'))

                # filtro saldi enormi
                if val > 1000000:
                    continue

                importi.append(round(val,2))
    return importi


# ---------------- MASTRINO ROBUSTO ----------------
def carica_mastrino(file):

    if file.name.endswith(".csv"):
        df = pd.read_csv(file, sep=';', dtype=str)
    else:
        df = pd.read_excel(file, dtype=str)

    # pulizia base
    df = df.fillna("")

    def parse(x):
        try:
            return float(str(x).replace('.', '').replace(',', '.'))
        except:
            return 0

    # trova colonne numeriche automaticamente
    numeric_cols = []
    for col in df.columns:
        sample = df[col].astype(str).str.contains(r'\d+,\d+').sum()
        if sample > 10:
            numeric_cols.append(col)

    if len(numeric_cols) < 2:
        st.error("Non riesco a identificare le colonne Dare/Avere")
        return None

    # assumiamo ultime 2 colonne numeriche come dare/avere
    dare_col = numeric_cols[-2]
    avere_col = numeric_cols[-1]

    df['dare'] = df[dare_col].apply(parse)
    df['avere'] = df[avere_col].apply(parse)

    df['amount'] = df['avere'] - df['dare']

    # descrizione = colonna testuale più lunga
    text_cols = [col for col in df.columns if df[col].astype(str).str.len().mean() > 10]
    descr_col = text_cols[0] if text_cols else df.columns[0]

    df['descrizione'] = df[descr_col]

    return df[['amount','descrizione']]


# ---------------- SIMILARITA ----------------
def similar(a, b):
    a = str(a).lower()
    b = str(b).lower()
    return any(word in b for word in a.split()[:3])


# ---------------- MATCHING ----------------
def matching_v3(amex, mastrino):

    used = set()
    riconciliati = []
    da_verificare = []
    scartati = []

    for a in amex:
        trovato = False

        for i in range(len(mastrino)):
            if i in used:
                continue

            amt_i = mastrino.iloc[i]['amount']
            desc_i = mastrino.iloc[i]['descrizione']

            # MATCH DIRETTO
            if abs(abs(amt_i) - a) < 0.01:
                riconciliati.append((a, amt_i, "Diretto", desc_i))
                used.add(i)
                trovato = True
                break

            # MATCH COMPENSAZIONE
            for j in range(i+1, len(mastrino)):
                if j in used:
                    continue

                amt_j = mastrino.iloc[j]['amount']
                desc_j = mastrino.iloc[j]['descrizione']

                somma = amt_i + amt_j

                if abs(abs(somma) - a) < 0.01:

                    if similar(desc_i, desc_j):
                        riconciliati.append((a, somma, "Compensazione", desc_i))
                    else:
                        da_verificare.append((a, somma, "Compensazione dubbia", desc_i))

                    used.add(i)
                    used.add(j)
                    trovato = True
                    break

            if trovato:
                break

        if not trovato:
            scartati.append((a,))

    return riconciliati, da_verificare, scartati


# ---------------- EXCEL ----------------
def crea_excel(r, v, s):

    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')

    pd.DataFrame(r, columns=["Amex","Mastrino","Tipo","Descrizione"])\
        .to_excel(writer, sheet_name="Riconciliati", index=False)

    pd.DataFrame(v, columns=["Amex","Mastrino","Tipo","Descrizione"])\
        .to_excel(writer, sheet_name="Da_verificare", index=False)

    pd.DataFrame(s, columns=["Amex"])\
        .to_excel(writer, sheet_name="Scartati", index=False)

    writer.close()
    output.seek(0)
    return output


# ---------------- MAIN ----------------
if pdf_file and excel_file:

    st.write("Elaborazione...")

    amex = estrai_pdf(pdf_file)
    mastrino = carica_mastrino(excel_file)

    if mastrino is not None:

        r, v, s = matching_v3(amex, mastrino)

        file_excel = crea_excel(r, v, s)

        st.success("Elaborazione completata")

        st.download_button(
            "Scarica Excel",
            file_excel,
            "riconciliazione_v3.xlsx"
        )
