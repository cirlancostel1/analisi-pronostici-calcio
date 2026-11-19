import os
import requests
import pandas as pd
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Analisi Partite e Pronostici", page_icon="⚽", layout="wide")

def verifica_password():
    password_corretta = st.secrets.get("APP_PASSWORD", os.getenv("APP_PASSWORD", "1234"))
    if st.session_state.get("autenticato", False):
        return True

    st.title("🔒 Accesso Riservato")
    pwd = st.text_input("Inserisci la password per accedere all'app", type="password")
    if st.button("Entra"):
        if pwd == password_corretta:
            st.session_state["autenticato"] = True
            st.rerun()
        else:
            st.error("Password non corretta.")
    return False

if not verifica_password():
    st.stop()

api_key = st.secrets.get("API_FOOTBALL_KEY", os.getenv("API_FOOTBALL_KEY"))
headers = {"x-apisports-key": api_key}

st.title("⚽ Analisi Partite e Pronostici")

@st.cache_data(ttl=600)
def carica_partite(data_str):
    url = "https://" + f"v3.football.api-sports.io/fixtures?date={data_str}"
    r = requests.get(url, headers=headers).json()
    return r.get("response", [])

@st.cache_data(ttl=3600)
def carica_pronostico(id_partita):
    url = "https://" + f"v3.football.api-sports.io/predictions?fixture={id_partita}"
    r = requests.get(url, headers=headers).json()
    return r.get("response", [])

@st.cache_data(ttl=3600)
def carica_classifica(id_lega, stagione):
    url = "https://" + f"v3.football.api-sports.io/standings?league={id_lega}&season={stagione}"
    r = requests.get(url, headers=headers).json()
    return r.get("response", [])

data_scelta = st.sidebar.date_input("Seleziona la data", datetime.now())
partite = carica_partite(data_scelta.strftime("%Y-%m-%d"))

if not partite:
    st.warning("Nessuna partita trovata per questa data.")
else:
    paesi = sorted(list(set(p["league"]["country"] for p in partite)))
    paese_scelto = st.sidebar.selectbox("Filtra per Paese", ["Tutti"] + paesi)

    if paese_scelto != "Tutti":
        partite = [p for p in partite if p["league"]["country"] == paese_scelto]

    campionati = sorted(list(set(p["league"]["name"] for p in partite)))
    campionato_scelto = st.sidebar.selectbox("Filtra per Campionato", ["Tutti"] + campionati)

    if campionato_scelto != "Tutti":
        partite = [p for p in partite if p["league"]["name"] == campionato_scelto]

    ricerca_squadra = st.sidebar.text_input("🔍 Cerca Squadra", placeholder="Es. Inter, Milan, Boca...")
    if ricerca_squadra:
        termine = ricerca_squadra.strip().lower()
        partite = [
            p for p in partite
            if termine in p["teams"]["home"]["name"].lower() or termine in p["teams"]["away"]["name"].lower()
        ]

    if campionato_scelto != "Tutti" and partite:
        id_lega = partite[0]["league"]["id"]
        stagione = partite[0]["league"]["season"]
        if st.checkbox(f"🏆 Mostra Classifica ({campionato_scelto})"):
            dati_classifica = carica_classifica(id_lega, stagione)
            if dati_classifica:
                gruppi = dati_classifica[0]["league"]["standings"]
                for g in gruppi:
                    righe = []
                    for sq in g:
                        righe.append({
                            "Pos": sq["rank"],
                            "Squadra": sq["team"]["name"],
                            "PT": sq["points"],
                            "G": sq["all"]["played"],
                            "V": sq["all"]["win"],
                            "N": sq["all"]["draw"],
                            "P": sq["all"]["lose"],
                            "DR": sq["goalsDiff"],
                            "Forma": sq.get("form", "")
                        })
                    df = pd.DataFrame(righe)
                    st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Classifica non disponibile per questa competizione (es. coppe o amichevoli).")

    st.write(f"Trovate **{len(partite)}** partite.")

    partite_da_mostrare = partite if (campionato_scelto != "Tutti" or ricerca_squadra) else partite[:20]

    for p in partite_da_mostrare:
        id_p = p["fixture"]["id"]
        ora = p["fixture"]["date"][11:16]
        stato = p["fixture"]["status"]["short"]
        minuto = p["fixture"]["status"]["elapsed"]
        
        lega = p["league"]["name"]
        casa = p["teams"]["home"]["name"]
        logo_casa = p["teams"]["home"]["logo"]
        trasferta = p["teams"]["away"]["name"]
        logo_trasferta = p["teams"]["away"]["logo"]
        
        gol_casa = p["goals"]["home"]
        gol_trasferta = p["goals"]["away"]

        if stato in ["1H", "HT", "2H", "ET", "P", "LIVE"]:
            etichetta_stato = f"🔴 LIVE {minuto}' ({gol_casa}-{gol_trasferta})"
        elif stato in ["FT", "AET", "PEN"]:
            etichetta_stato = f"🏁 Finale ({gol_casa}-{gol_trasferta})"
        else:
            etichetta_stato = f"🕒 {ora}"

        with st.expander(f"{etichetta_stato} | {lega} | {casa} vs {trasferta}"):
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                if logo_casa:
                    st.image(logo_casa, width=50)
                st.subheader(casa)
            with col_b:
                st.markdown(f"<h2 style='text-align: center;'>{gol_casa if gol_casa is not None else '-'} : {gol_trasferta if gol_trasferta is not None else '-'}</h2>", unsafe_allow_html=True)
            with col_c:
                if logo_trasferta:
                    st.image(logo_trasferta, width=50)
                st.subheader(trasferta)

            st.divider()

            if st.button("Analizza Pronostico", key=f"btn_{id_p}"):
                dati = carica_pronostico(id_p)
                if dati:
                    info = dati[0]
                    pred = info["predictions"]
                    teams_stats = info.get("teams", {})
                    comp = info.get("comparison", {})
                    h2h = info.get("h2h", [])

                    st.success(f"Analisi tecnica: {pred.get('advice', 'N/D')}")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Vittoria Casa (1)", pred["percent"]["home"])
                    c2.metric("Pareggio (X)", pred["percent"]["draw"])
                    c3.metric("Vittoria Trasferta (2)", pred["percent"]["away"])

                    if comp:
                        st.markdown("#### ⚖️ Confronto Diretto (%)")
                        voci = {
                            "Forma": "form",
                            "Attacco": "att",
                            "Difesa": "def",
                            "Distribuzione Poisson": "poisson_distribution",
                            "Scontri Diretti": "h2h",
                            "Totale": "total"
                        }
                        for etichetta, chiave in voci.items():
                            if chiave in comp:
                                val_c = comp[chiave].get("home", "50%")
                                val_t = comp[chiave].get("away", "50%")
                                num_c = int(val_c.replace("%", "")) if val_c else 50
                                st.write(f"**{etichetta}**: {casa} `{val_c}` vs `{val_t}` {trasferta}")
                                st.progress(num_c / 100)

                    st.markdown("#### 📊 Forma Recente e Media Gol")
                    f_casa = teams_stats.get("home", {}).get("last_5", {})
                    f_trasf = teams_stats.get("away", {}).get("last_5", {})

                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        st.write(f"**{casa}**")
                        st.write(f"• Forma ultime 5: `{f_casa.get('form', 'N/D')}`")
                        st.write(f"• Attacco / Difesa: `{f_casa.get('att', 'N/D')}` / `{f_casa.get('def', 'N/D')}`")
                        gol_f_c = f_casa.get("goals", {}).get("for", {}).get("average", "N/D")
                        gol_s_c = f_casa.get("goals", {}).get("against", {}).get("average", "N/D")
                        st.write(f"• Media gol fatti / subiti: `{gol_f_c}` / `{gol_s_c}`")

                    with col_f2:
                        st.write(f"**{trasferta}**")
                        st.write(f"• Forma ultime 5: `{f_trasf.get('form', 'N/D')}`")
                        st.write(f"• Attacco / Difesa: `{f_trasf.get('att', 'N/D')}` / `{f_trasf.get('def', 'N/D')}`")
                        gol_f_t = f_trasf.get("goals", {}).get("for", {}).get("average", "N/D")
                        gol_s_t = f_trasf.get("goals", {}).get("against", {}).get("average", "N/D")
                        st.write(f"• Media gol fatti / subiti: `{gol_f_t}` / `{gol_s_t}`")

                    if h2h:
                        st.markdown("#### ⚔️ Ultimi Scontri Diretti")
                        for match in h2h[:5]:
                            data_m = match["fixture"]["date"][:10]
                            sq_c = match["teams"]["home"]["name"]
                            sq_t = match["teams"]["away"]["name"]
                            g_c = match["goals"]["home"]
                            g_t = match["goals"]["away"]
                            st.write(f"• `{data_m}` | {sq_c} **{g_c} - {g_t}** {sq_t}")
                else:
                    st.info("Previsione non ancora disponibile per questa partita.")
