import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import BytesIO

st.title("Riconciliazione Amex vs Mastrino - Versione 3")

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

                if val > 1000000:
                    continue

                importi.append(round(val,2))
    return importi


# ---------------- MASTRINO ----------------
def carica_mastrino(file):
    if file.name.endswith(".csv"):
        df = pd.read_csv(file, sep=';')
    else:
        df = pd.read_excel(file)

    df = df.iloc[1:].copy()

    def parse(x):
        try:
            return float(str(x).replace('.', '').replace(',', '.'))
        except:
            return 0

    df['dare'] = df['Unnamed: 11'].apply(parse)
    df['avere'] = df['Unnamed: 10'].apply(parse)
    df['amount'] = df['avere'] - df['dare']

    return df[['amount','Unnamed: 22']].rename(columns={"Unnamed:22":"descrizione"})


# ---------------- SIMILARITA DESCRIZIONE ----------------
def similar(a, b):
    if pd.isna(a) or pd.isna(b):
        return False
    a = str(a).lower()
    b = str(b).lower()
    return any(word in b for word in a.split()[:3])


# ---------------- MATCHING V3 ----------------
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

    pd.DataFrame(r, columns=["Amex","Mastrino","Tipo","Descrizione"]).to_excel(writer, sheet_name="Riconciliati", index=False)
    pd.DataFrame(v, columns=["Amex","Mastrino","Tipo","Descrizione"]).to_excel(writer, sheet_name="Da_verificare", index=False)
    pd.DataFrame(s, columns=["Amex"]).to_excel(writer, sheet_name="Scartati", index=False)

    writer.close()
    output.seek(0)
    return output


# ---------------- MAIN ----------------
if pdf_file and excel_file:

    st.write("Elaborazione intelligente...")

    amex = estrai_pdf(pdf_file)
    mastrino = carica_mastrino(excel_file)

    r, v, s = matching_v3(amex, mastrino)

    file_excel = crea_excel(r, v, s)

    st.success("Elaborazione completata")

    st.download_button(
        "Scarica Excel completo",
        file_excel,
        "riconciliazione_v3.xlsx"
    )
