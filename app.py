import os
import math
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

api_key = st.secrets.get("API_FOOTBALL_KEY", os.getenv("API_FOOTBALL_KEY", ""))
RAPID_HOST = "api-football-v1." + "://rapidapi.com"
BASE_URL = "https://" + RAPID_HOST + "/v3"

headers = {
    "x-rapidapi-key": api_key.strip(),
    "x-rapidapi-host": RAPID_HOST
}

def poisson_prob(lmbda, k):
    return (math.exp(-lmbda) * (lmbda ** k)) / math.factorial(k)

def calcola_mercati_statistici(att_casa, att_trasf):
    p_gg = 0.0
    p_over15 = 0.0
    p_over25 = 0.0
    p_over35 = 0.0
    risultati = []

    for g_c in range(7):
        for g_t in range(7):
            prob = poisson_prob(att_casa, g_c) * poisson_prob(att_trasf, g_t)
            risultati.append((f"{g_c}-{g_t}", prob * 100))
            if g_c > 0 and g_t > 0:
                p_gg += prob
            tot = g_c + g_t
            if tot > 1.5:
                p_over15 += prob
            if tot > 2.5:
                p_over25 += prob
            if tot > 3.5:
                p_over35 += prob

    risultati.sort(key=lambda x: x[1], reverse=True)
    return {
        "GG": round(p_gg * 100, 1),
        "NG": round((1 - p_gg) * 100, 1),
        "Over 1.5": round(p_over15 * 100, 1),
        "Under 1.5": round((1 - p_over15) * 100, 1),
        "Over 2.5": round(p_over25 * 100, 1),
        "Under 2.5": round((1 - p_over25) * 100, 1),
        "Over 3.5": round(p_over35 * 100, 1),
        "Under 3.5": round((1 - p_over35) * 100, 1),
        "Top3": risultati[:3]
    }

def somma_gol_tempo(minuti_dict, chiavi):
    totale = 0
    for k in chiavi:
        val = minuti_dict.get(k, {}).get("total")
        if isinstance(val, int):
            totale += val
    return totale

st.title("⚽ Analisi Partite e Pronostici")

@st.cache_data(ttl=600)
def carica_partite(data_str):
    if not api_key:
        st.error("Chiave API_FOOTBALL_KEY mancante nei Secrets!")
        return []
    url = f"{BASE_URL}/fixtures?date={data_str}"
    r = requests.get(url, headers=headers).json()
    if r.get("errors"):
        st.error(f"Risposta API: {r['errors']}")
    if r.get("message"):
        st.error(f"Messaggio RapidAPI: {r['message']}")
    return r.get("response", [])

@st.cache_data(ttl=3600)
def carica_pronostico(id_partita):
    url = f"{BASE_URL}/predictions?fixture={id_partita}"
    r = requests.get(url, headers=headers).json()
    return r.get("response", [])

@st.cache_data(ttl=3600)
def carica_classifica(id_lega, stagione):
    url = f"{BASE_URL}/standings?league={id_lega}&season={stagione}"
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

            if st.button("Analizza Pronostico Completo", key=f"btn_{id_p}"):
                dati = carica_pronostico(id_p)
                if dati:
                    info = dati[0]
                    pred = info["predictions"]
                    teams_stats = info.get("teams", {})
                    comp = info.get("comparison", {})
                    h2h = info.get("h2h", [])

                    st.success(f"Analisi tecnica: {pred.get('advice', 'N/D')}")

                    p1 = int(float(pred["percent"]["home"].replace("%", "")))
                    px = int(float(pred["percent"]["draw"].replace("%", "")))
                    p2 = int(float(pred["percent"]["away"].replace("%", "")))

                    st.markdown("#### 🎯 Esito Finale (1X2) e Doppia Chance")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("1 (Casa)", f"{p1}%")
                    c2.metric("X (Pareggio)", f"{px}%")
                    c3.metric("2 (Trasferta)", f"{p2}%")

                    dc1, dc2, dc3 = st.columns(3)
                    dc1.metric("Doppia Chance 1X", f"{p1 + px}%")
                    dc2.metric("Doppia Chance X2", f"{px + p2}%")
                    dc3.metric("Doppia Chance 12", f"{p1 + p2}%")

                    f_casa = teams_stats.get("home", {}).get("last_5", {})
                    f_trasf = teams_stats.get("away", {}).get("last_5", {})

                    try:
                        gf_c = float(f_casa.get("goals", {}).get("for", {}).get("average", 1.2))
                        gs_c = float(f_casa.get("goals", {}).get("against", {}).get("average", 1.2))
                        gf_t = float(f_trasf.get("goals", {}).get("for", {}).get("average", 1.1))
                        gs_t = float(f_trasf.get("goals", {}).get("against", {}).get("average", 1.1))
                    except (ValueError, TypeError):
                        gf_c, gs_c, gf_t, gs_t = 1.2, 1.2, 1.1, 1.1

                    attesa_casa = max(0.2, (gf_c + gs_t) / 2)
                    attesa_trasf = max(0.2, (gf_t + gs_c) / 2)
                    mercati = calcola_mercati_statistici(attesa_casa, attesa_trasf)

                    st.markdown("#### ⚽ Gol/NoGol (GG/NG) e Under/Over")
                    g1, g2, g3, g4 = st.columns(4)
                    g1.metric("GG (Entrambe segnano)", f"{mercati['GG']}%")
                    g2.metric("NG (NoGol)", f"{mercati['NG']}%")
                    g3.metric("Over 1.5", f"{mercati['Over 1.5']}%")
                    g4.metric("Under 1.5", f"{mercati['Under 1.5']}%")

