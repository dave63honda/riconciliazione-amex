import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import BytesIO

st.title("Riconciliazione Amex vs Mastrino - PRO")

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
                
                # ignora saldi
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

# ---------------- MATCHING ----------------
def matching_avanzato(amex, mastrino):
    used = set()
    risultati = []

    for a in amex:
        trovato = False

        for i in range(len(mastrino)):
            if i in used:
                continue

            # match diretto
            if abs(abs(mastrino.iloc[i]['amount']) - a) < 0.01:
                risultati.append((a,[mastrino.iloc[i]['amount']],"Diretto"))
                used.add(i)
                trovato = True
                break

            # match compensazione
            for j in range(i+1,len(mastrino)):
                if j in used:
                    continue

                somma = mastrino.iloc[i]['amount'] + mastrino.iloc[j]['amount']

                if abs(abs(somma) - a) < 0.01:
                    risultati.append((a,[mastrino.iloc[i]['amount'],mastrino.iloc[j]['amount']],"Compensazione"))
                    used.add(i); used.add(j)
                    trovato = True
                    break

            if trovato:
                break

        if not trovato:
            risultati.append((a,None,"Scartato"))

    return risultati

# ---------------- OUTPUT EXCEL ----------------
def crea_excel(match, scartati):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')

    df_match = pd.DataFrame(match)
    df_scartati = pd.DataFrame(scartati)

    df_match.to_excel(writer, sheet_name="Match", index=False)
    df_scartati.to_excel(writer, sheet_name="Scartati", index=False)

    writer.close()
    output.seek(0)
    return output

# ---------------- MAIN ----------------
if pdf_file and excel_file:

    st.write("Elaborazione avanzata...")

    amex = estrai_pdf(pdf_file)
    mastrino = carica_mastrino(excel_file)

    risultati = matching_avanzato(amex, mastrino)

    match = []
    scartati = []

    for r in risultati:
        if r[1]:
            match.append({
                "Importo Amex": r[0],
                "Somma Mastrino": sum(r[1]),
                "Tipo": r[2],
                "Dettaglio": " + ".join([str(x) for x in r[1]])
            })
        else:
            scartati.append({"Importo Amex": r[0]})

    file_excel = crea_excel(match, scartati)

    st.success("Elaborazione completata")

    st.download_button(
        label="Scarica Excel",
        data=file_excel,
        file_name="riconciliazione.xlsx"
    )
