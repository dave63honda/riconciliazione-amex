import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import BytesIO

st.title("Riconciliazione Amex vs Mastrino")

pdf_file = st.file_uploader("Carica PDF American Express", type=["pdf"])
excel_file = st.file_uploader("Carica Excel Mastrino", type=["xlsx", "csv"])


# ---------------- PDF ----------------
def estrai_importi_pdf(file):
    importi = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""

            matches = re.findall(r'\d{1,3}(?:\.\d{3})*,\d{2}', text)

            for m in matches:
                val = float(m.replace('.', '').replace(',', '.'))

                # ignora saldi enormi
                if val > 1000000:
                    continue

                importi.append(round(val, 2))

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

    # QUESTE SONO LE COLONNE GIUSTE DEL TUO FILE ORIGINALE
    df['dare'] = df['Unnamed: 11'].apply(parse)
    df['avere'] = df['Unnamed: 10'].apply(parse)

    df['amount'] = df['avere'] - df['dare']

    return df[['amount']]


# ---------------- MATCHING SEMPLICE ----------------
def matching(amex, mastrino):

    mastrino_list = mastrino['amount'].tolist()

    match = []
    scartati = []

    used = [False] * len(mastrino_list)

    for a in amex:
        trovato = False

        # MATCH DIRETTO
        for i, m in enumerate(mastrino_list):
            if not used[i] and abs(abs(m) - a) < 0.01:
                match.append({
                    "Importo Amex": a,
                    "Importo Mastrino": m,
                    "Tipo": "Diretto"
                })
                used[i] = True
                trovato = True
                break

        if trovato:
            continue

        # MATCH A COPPIE
        for i in range(len(mastrino_list)):
            if used[i]:
                continue

            for j in range(i+1, len(mastrino_list)):
                if used[j]:
                    continue

                somma = mastrino_list[i] + mastrino_list[j]

                if abs(abs(somma) - a) < 0.01:
                    match.append({
                        "Importo Amex": a,
                        "Importo Mastrino": somma,
                        "Tipo": "Compensazione"
                    })
                    used[i] = True
                    used[j] = True
                    trovato = True
                    break

            if trovato:
                break

        if not trovato:
            scartati.append({
                "Importo Amex": a
            })

    return match, scartati


# ---------------- EXCEL ----------------
def crea_excel(match, scartati):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')

    pd.DataFrame(match).to_excel(writer, sheet_name="Match", index=False)
    pd.DataFrame(scartati).to_excel(writer, sheet_name="Scartati", index=False)

    writer.close()
    output.seek(0)
    return output


# ---------------- MAIN ----------------
if pdf_file and excel_file:

    st.write("Elaborazione...")

    amex = estrai_importi_pdf(pdf_file)
    mastrino = carica_mastrino(excel_file)

    match, scartati = matching(amex, mastrino)

    file_excel = crea_excel(match, scartati)

    st.success("Elaborazione completata")

    st.download_button(
        "Scarica risultato",
        file_excel,
        "riconciliazione.xlsx"
    )
