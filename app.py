import streamlit as st
import pandas as pd
import pdfplumber
import re

st.title("Riconciliazione Amex vs Mastrino")

pdf_file = st.file_uploader("Carica PDF American Express", type=["pdf"])
excel_file = st.file_uploader("Carica Excel Mastrino", type=["xlsx", "csv"])


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

    return df[['amount', 'Unnamed: 22']].rename(columns={"Unnamed: 22": "descrizione"})


def matching(amex, mastrino):
    matches = []
    used = set()

    for a in amex:
        trovato = False

        for i in range(len(mastrino)):
            if i in used:
                continue

            # match diretto
            if abs(abs(mastrino.iloc[i]['amount']) - a) < 0.01:
                matches.append((a, [mastrino.iloc[i]['amount']]))
                used.add(i)
                trovato = True
                break

            # match compensazione
            for j in range(i+1, len(mastrino)):
                if j in used:
                    continue

                somma = mastrino.iloc[i]['amount'] + mastrino.iloc[j]['amount']

                if abs(abs(somma) - a) < 0.01:
                    matches.append((a, [mastrino.iloc[i]['amount'], mastrino.iloc[j]['amount']]))
                    used.add(i)
                    used.add(j)
                    trovato = True
                    break

            if trovato:
                break

        if not trovato:
            matches.append((a, None))

    return matches


if pdf_file and excel_file:
    st.write("Elaborazione...")

    amex = estrai_importi_pdf(pdf_file)
    mastrino = carica_mastrino(excel_file)

    risultati = matching(amex, mastrino)

    match_ok = []
    scartati = []

    for r in risultati:
        if r[1]:
            match_ok.append({
                "Importo Amex": r[0],
                "Somma Mastrino": sum(r[1]),
                "Dettaglio": r[1]
            })
        else:
            scartati.append({"Importo Amex": r[0]})

    df_match = pd.DataFrame(match_ok)
    df_scartati = pd.DataFrame(scartati)

    st.subheader("Match")
    st.dataframe(df_match)

    st.subheader("Scartati")
    st.dataframe(df_scartati)

    st.download_button("Scarica Match", df_match.to_csv(index=False), "match.csv")
    st.download_button("Scarica Scartati", df_scartati.to_csv(index=False), "scartati.csv")
