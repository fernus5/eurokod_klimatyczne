import streamlit as st
import pandas as pd
import numpy as np
import datetime
import plotly.graph_objects as go

# ==========================================
# KONFIGURACJA STRONY I STYLE CSS
# ==========================================
st.set_page_config(page_title="Generator Obciążeń Klimatycznych (EC1)", layout="wide")

st.markdown("""
    <style>
    .stTabs [data-baseweb="tab"] p {
        font-size: 1.15rem !important;
        font-weight: 600 !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# INICJALIZACJA PARAMETRÓW SESJI
# ==========================================
params = st.query_params
if "client_id" in params:
    session_client = params["client_id"]
    if "session_initialized" not in st.session_state:
        st.session_state.session_initialized = True
        init_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        st.toast(f"Aktywowano instancję dla: {session_client} ({init_time})", icon="⚙️")

# ==========================================
# NAGŁÓWEK APLIKACJI I NOTKA PRAWNA
# ==========================================
st.title("Generator Obciążeń Klimatycznych wg PN-EN 1991-1")
st.markdown("Kompleksowe zestawienie sił dla projektantów konstrukcji. Aplikacja wyposażona w walidację wejścia, wizualizację i eksport MES.")

with st.expander("📚 Podstawa normowa i informacje o programie", expanded=False):
    st.markdown("""
    **Algorytmy obliczeniowe programu zostały oparte na normach (wraz z Polskimi Załącznikami Krajowymi):**
    * ❄️ **PN-EN 1991-1-3:2005/NA:2010** - Eurokod 1: Obciążenie śniegiem.
    * 🌪️ **PN-EN 1991-1-4:2008/NA:2010** - Eurokod 1: Oddziaływania wiatru.
    """)

# ==========================================
# PANEL BOCZNY: PARAMETRY WEJŚCIOWE
# ==========================================
st.sidebar.header("1. Geometria Budynku")
typ_dachu = st.sidebar.selectbox("Typ dachu", ["Dwuspadowy", "Jednospadowy", "Płaski (α = 0°)"])
b = st.sidebar.number_input("Szerokość szczytowa b [m]", min_value=1.0, value=12.0, step=0.5)
d = st.sidebar.number_input("Długość podłużna d [m]", min_value=1.0, value=24.0, step=0.5)
h = st.sidebar.number_input("Wysokość budynku h [m]", min_value=1.0, value=8.0, step=0.5)

if typ_dachu == "Płaski (α = 0°)":
    alfa = 0.0
    st.sidebar.info("Dla dachu płaskiego kąt α wynosi 0°.")
else:
    alfa = st.sidebar.slider("Kąt nachylenia dachu α [°]", min_value=5, max_value=60, value=15, step=1)

st.sidebar.header("2. Lokalizacja i Teren")
strefa_snieg = st.sidebar.selectbox("Strefa obciążenia śniegiem", ["1", "2", "3", "4", "5"])
A = st.sidebar.number_input("Wysokość n.p.m. A [m]", min_value=0, max_value=2500, value=50, step=10)

strefa_wiatr = st.sidebar.selectbox("Strefa obciążenia wiatrem", ["1", "2", "3"])
kat_terenu = st.sidebar.selectbox("Kategoria terenu", ["0", "I", "II", "III", "IV"], index=2)

st.sidebar.header("3. Detale dachu (Śnieg)")
ce_typ = st.sidebar.selectbox("Ekspozycja (C_e)", ["Normalna (C_e = 1.0)", "Wystawiona (C_e = 0.8)", "Osłonięta (C_e = 1.2)"])
c_e = float(ce_typ.split("= ")[1].replace(")", ""))
c_t = st.sidebar.number_input("Wsp. termiczny (C_t)", min_value=0.5, max_value=1.5, value=1.0, step=0.1)
h_attyki = st.sidebar.number_input("Wysokość attyki h_a [m]", min_value=0.0, value=0.0, step=0.1)
plotki = st.sidebar.checkbox("Uwzględnij płotki na okapie") if typ_dachu != "Płaski (α = 0°)" else False

st.sidebar.header("4. Ciśnienie wewnętrzne (Cpi)")
cpi_typ = st.sidebar.radio("Stan otworów:", ["Budynek zamknięty (Cpi = +0.2, -0.3)", "Własna wartość Cpi"])
if "Własna" in cpi_typ:
    cpi_custom = st.sidebar.number_input("Podaj Cpi", min_value=-1.5, max_value=1.5, value=0.2, step=0.1)
    cpi_list = [cpi_custom]
else:
    cpi_list = [0.2, -0.3]

# ==========================================
# SYSTEM WALIDACJI (Ostrzeżenia logiczne)
# ==========================================
walidacja_bledy = []
walidacja_ostrzezenia = []

if h > 200.0:
    walidacja_bledy.append("Wysokość budynku h > 200 m. Przekroczono zakres stosowalności normy PN-EN 1991-1-4. Wymagane badania w tunelu aerodynamicznym.")
if h / min(b, d) > 5.0:
    walidacja_ostrzezenia.append("Budynek wybitnie smukły (h/min(b,d) > 5). Zalecana analiza zjawisk dynamicznych (rezonans, oderwanie wirów).")
if h_attyki >= h:
    walidacja_bledy.append("Nielogiczna geometria: Wysokość attyki nie może być większa lub równa wysokości całego budynku.")
if "Własna" in cpi_typ and (cpi_custom < -0.5 or cpi_custom > 0.8):
    walidacja_ostrzezenia.append("Niestandardowa wartość Cpi. Typowe wartości mieszczą się w przedziale od -0.5 do +0.8. Sprawdź założenia dla otworu dominującego.")
if A > 1500:
    walidacja_ostrzezenia.append("Wysokość > 1500 m n.p.m. Zwróć uwagę na lokalne uwarunkowania górskie (zwiększona akumulacja śniegu).")

if walidacja_bledy:
    for blad in walidacja_bledy:
        st.error(f"🛑 **BŁĄD WEJŚCIA:** {blad}")
    st.stop() # Zatrzymuje dalsze wykonywanie programu, jeśli są błędy krytyczne

if walidacja_ostrzezenia:
    for ostrzezenie in walidacja_ostrzezenia:
        st.warning(f"⚠️ **OSTRZEŻENIE:** {ostrzezenie}")

# ==========================================
# OBLICZENIA BAZOWE
# ==========================================
def oblicz_sk(strefa, A):
    strefa = int(strefa)
    if strefa == 1: return max(0.007 * A - 1.4, 0.7)
    elif strefa == 2: return 0.9
    elif strefa == 3: return max(0.006 * A - 0.6, 1.2)
    elif strefa == 4: return max(0.006 * A - 0.3, 1.6)
    elif strefa == 5: return max(0.93 * np.exp(0.00134 * A), 2.0)
    return 0.0

sk = oblicz_sk(strefa_snieg, A)
mu_1 = 0.8 if alfa <= 30 else (0.8 * (60 - alfa) / 30 if alfa < 60 else 0.0)
s_dach = sk * mu_1 * c_e * c_t

if h_attyki > 0:
    mu_2 = min(max((2.0 * h_attyki) / sk, 0.8), 2.0)
    l_s = min(max(2 * h_attyki, 5.0), 15.0)
    s_zaspa = mu_2 * sk * c_e * c_t
else:
    mu_2, l_s, s_zaspa = mu_1, 0.0, s_dach

se_nawis = (s_dach**2) / 3.0 if alfa > 0 else 0.0
f_plotki = s_dach * (b / 2) * np.sin(np.radians(alfa)) if plotki and alfa > 0 else 0.0

vb0 = 26.0 if strefa_wiatr == "2" else 22.0
z0, zmin = {"0":0.003, "I":0.01, "II":0.05, "III":0.3, "IV":1.0}[kat_terenu], {"0":1.0, "I":1.0, "II":2.0, "III":5.0, "IV":10.0}[kat_terenu]
z = max(h, zmin)
cr = (0.19 * (z0 / 0.05)**0.07) * np.log(z / z0)
qp = (1 + 7 * (1.0 / (cr * np.log(z / z0)))) * 0.5 * 1.25 * ((cr * vb0)**2) / 1000

def cpe_sciany(h, d_w):
    hd = h / d_w
    return {"A": np.interp(hd, [0.25, 1.0, 5.0], [-1.2, -1.2, -1.4]), "B": -0.8, "C": -0.5, "D": np.interp(hd, [0.25, 1.0, 5.0], [0.7, 0.8, 0.8]), "E": np.interp(hd, [0.25, 1.0, 5.0], [-0.3, -0.5, -0.7])}

def cpe_dach_plaski():
    return {"F": -1.8, "G": -1.2, "H": -0.7, "I_pos": 0.2, "I_neg": -0.2}

def cpe_dach_0(alfa):
    return {
        "F_neg": np.interp(alfa, [5, 15, 30, 45, 60], [-1.7, -0.9, -0.5, 0.0, 0.0]),
        "G_neg": np.interp(alfa, [5, 15, 30, 45, 60], [-1.2, -0.8, -0.5, 0.0, 0.0]),
        "H_neg": np.interp(alfa, [5, 15, 30, 45, 60], [-0.6, -0.3, -0.2, 0.0, 0.0]),
        "I_neg": np.interp(alfa, [5, 15, 30, 45, 60], [-0.6, -0.4, -0.4, -0.2, -0.2]),
        "J_neg": np.interp(alfa, [5, 15, 30, 45, 60], [-0.6, -1.0, -0.5, -0.3, -0.3]),
        "F_pos": np.interp(alfa, [5, 15, 30, 45, 60], [0.0, 0.2, 0.7, 0.7, 0.7]),
        "G_pos": np.interp(alfa, [5, 15, 30, 45, 60], [0.0, 0.2, 0.7, 0.7, 0.7]),
        "H_pos": np.interp(alfa, [5, 15, 30, 45, 60], [0.0, 0.2, 0.4, 0.6, 0.7])
    }

def cpe_dach_90(alfa):
    return {
        "F": np.interp(alfa, [5, 15, 30, 45, 60], [-1.6, -1.3, -1.1, -1.1, -1.1]),
        "G": np.interp(alfa, [5, 15, 30, 45, 60], [-1.3, -1.3, -1.4, -1.4, -1.4]),
        "H": np.interp(alfa, [5, 15, 30, 45, 60], [-0.7, -0.6, -0.8, -0.9, -0.9]),
        "I": np.interp(alfa, [5, 15, 30, 45, 60], [-0.6, -0.5, -0.5, -0.5, -0.5])
    }

def format_w(cpe, qp, cpi):
    if cpe == "-": return "-"
    return f"{(float(cpe) - cpi) * qp:.2f}"

df_sc_final = pd.DataFrame()
df_d_final = pd.DataFrame()

# ==========================================
# INTERFEJS APLIKACJI - GŁÓWNY STEROWNIK
# ==========================================
st.divider()
kierunek_wiatru = st.radio(
    "**Wybierz analizowany kierunek wiatru:**", 
    ["θ = 0° (prostopadły do ściany podłużnej d)", "θ = 90° (prostopadły do ściany szczytowej b)"], 
    horizontal=True
)
st.divider()

b_wind, d_wind = (d, b) if kierunek_wiatru.startswith("θ = 0°") else (b, d)
e = min(b_wind, 2*h)

col_w1 = f"W_netto (Cpi={cpi_list[0]})"
col_w2 = f"W_netto (Cpi={cpi_list[1]})" if len(cpi_list)>1 else None

tab_wiatr, tab_wizualizacja, tab_snieg, tab_raport = st.tabs(["🌪️ Tabele Wiatrowe", "🎨 Wizualizacja Stref", "❄️ Obciążenie Śniegiem", "📄 Raport MES"])

with tab_wiatr:
    c1, c2, c3 = st.columns(3)
    c1.metric("Prędkość bazowa (vb,0)", f"{vb0:.1f} m/s")
    c2.metric("Współczynnik szorstkości (cr)", f"{cr:.2f}")
    c3.metric("Szczytowe ciśnienie (qp)", f"{qp:.2f} kN/m²")
    st.divider()
    
    st.latex(f"e = \\min(b_{{wind}}, 2h) = \\min({b_wind}, {2*h}) = {e:.2f} \\text{{ m}}")
    
    col_s, col_d = st.columns(2)
    with col_s:
        st.markdown(f"#### Ściany Pionowe ({kierunek_wiatru.split(' ')[0]} {kierunek_wiatru.split(' ')[2]})")
        cpe_w = cpe_sciany(h, d_wind)
        sz_A = e / 5
        sz_B = max(0, d_wind - sz_A) if d_wind <= e else 0.8 * e
        sz_C = 0.0 if d_wind <= e else d_wind - e
        
        df_sc = {"Strefa": ["A", "B", "C", "D", "E"], "Szer.[m]": [f"{sz_A:.2f}", f"{sz_B:.2f}", f"{sz_C:.2f}" if sz_C>0 else "-", f"{b_wind:.2f}", f"{b_wind:.2f}"], "Cpe": [f"{cpe_w['A']:.2f}", f"{cpe_w['B']:.2f}", f"{cpe_w['C']:.2f}" if sz_C>0 else "-", f"{cpe_w['D']:.2f}", f"{cpe_w['E']:.2f}"], col_w1: [format_w(cpe_w['A'], qp, cpi_list[0]), format_w(cpe_w['B'], qp, cpi_list[0]), format_w(cpe_w['C'] if sz_C>0 else "-", qp, cpi_list[0]), format_w(cpe_w['D'], qp, cpi_list[0]), format_w(cpe_w['E'], qp, cpi_list[0])]}
        if col_w2: df_sc[col_w2] = [format_w(cpe_w['A'], qp, cpi_list[1]), format_w(cpe_w['B'], qp, cpi_list[1]), format_w(cpe_w['C'] if sz_C>0 else "-", qp, cpi_list[1]), format_w(cpe_w['D'], qp, cpi_list[1]), format_w(cpe_w['E'], qp, cpi_list[1])]
        
        df_sc_final = pd.DataFrame(df_sc)
        st.dataframe(df_sc_final, hide_index=True)

    with col_d:
        st.markdown(f"#### Dach {typ_dachu}")
        if typ_dachu == "Płaski (α = 0°)":
            cpe_dp = cpe_dach_plaski()
            df_d = {"Strefa": ["F (Naroża)", "G (Okap)", "H (Brzeg)", "I (Środek - Ssanie)", "I (Środek - Parcie)"],
                    "Cpe": [f"{cpe_dp['F']}", f"{cpe_dp['G']}", f"{cpe_dp['H']}", f"{cpe_dp['I_neg']}", f"{cpe_dp['I_pos']}"],
                    col_w1: [format_w(cpe_dp['F'], qp, cpi_list[0]), format_w(cpe_dp['G'], qp, cpi_list[0]), format_w(cpe_dp['H'], qp, cpi_list[0]), format_w(cpe_dp['I_neg'], qp, cpi_list[0]), format_w(cpe_dp['I_pos'], qp, cpi_list[0])]}
            if col_w2: df_d[col_w2] = [format_w(cpe_dp['F'], qp, cpi_list[1]), format_w(cpe_dp['G'], qp, cpi_list[1]), format_w(cpe_dp['H'], qp, cpi_list[1]), format_w(cpe_dp['I_neg'], qp, cpi_list[1]), format_w(cpe_dp['I_pos'], qp, cpi_list[1])]
            
        elif kierunek_wiatru.startswith("θ = 0°"):
            cpe_d0 = cpe_dach_0(alfa)
            strefy_ds = ["F (Ssanie)", "G (Ssanie)", "H (Ssanie)", "F (Parcie)", "G (Parcie)", "H (Parcie)"] if typ_dachu=="Jednospadowy" else ["F (Ssanie)", "G (Ssanie)", "H (Ssanie)", "I (Ssanie)", "J (Ssanie)", "F (Parcie)", "G (Parcie)", "H (Parcie)"]
            cpe_vals = [cpe_d0['F_neg'], cpe_d0['G_neg'], cpe_d0['H_neg'], cpe_d0['F_pos'] if cpe_d0['F_pos']>0 else "-", cpe_d0['G_pos'] if cpe_d0['G_pos']>0 else "-", cpe_d0['H_pos'] if cpe_d0['H_pos']>0 else "-"] if typ_dachu=="Jednospadowy" else [cpe_d0['F_neg'], cpe_d0['G_neg'], cpe_d0['H_neg'], cpe_d0['I_neg'], cpe_d0['J_neg'], cpe_d0['F_pos'] if cpe_d0['F_pos']>0 else "-", cpe_d0['G_pos'] if cpe_d0['G_pos']>0 else "-", cpe_d0['H_pos'] if cpe_d0['H_pos']>0 else "-"]
            
            df_d = {"Strefa": strefy_ds, "Cpe": [f"{v:.2f}" if type(v) is np.float64 else "-" for v in cpe_vals], col_w1: [format_w(v, qp, cpi_list[0]) for v in cpe_vals]}
            if col_w2: df_d[col_w2] = [format_w(v, qp, cpi_list[1]) for v in cpe_vals]
            
        else:
            cpe_d90 = cpe_dach_90(alfa)
            df_d = {"Strefa": ["F (Naroża)", "G (Krawędź)", "H (Środek)", "I (Środek)"], "Cpe": [f"{cpe_d90['F']:.2f}", f"{cpe_d90['G']:.2f}", f"{cpe_d90['H']:.2f}", f"{cpe_d90['I']:.2f}"], col_w1: [format_w(cpe_d90['F'], qp, cpi_list[0]), format_w(cpe_d90['G'], qp, cpi_list[0]), format_w(cpe_d90['H'], qp, cpi_list[0]), format_w(cpe_d90['I'], qp, cpi_list[0])]}
            if col_w2: df_d[col_w2] = [format_w(cpe_d90['F'], qp, cpi_list[1]), format_w(cpe_d90['G'], qp, cpi_list[1]), format_w(cpe_d90['H'], qp, cpi_list[1]), format_w(cpe_d90['I'], qp, cpi_list[1])]
            
        df_d_final = pd.DataFrame(df_d)
        st.dataframe(df_d_final, hide_index=True)

with tab_wizualizacja:
    st.subheader("Wektorowy rozkład stref aerodynamicznych na dachu")
    st.markdown("Interaktywny rzut (Top-Down) generowany dynamicznie. Użyj **kółka myszy**, aby oddalać/przybliżać, i **lewego przycisku**, aby przesuwać widok.")
    
    fig = go.Figure()
    
    margin_x, margin_y = d * 0.15, b * 0.15
    fig.add_trace(go.Scatter(x=[-margin_x, d + margin_x], y=[-margin_y, b + margin_y], mode="markers", marker=dict(color="rgba(0,0,0,0)"), showlegend=False, hoverinfo="skip"))
    fig.add_shape(type="rect", x0=0, y0=0, x1=d, y1=b, line=dict(color="black", width=3))
    
    def dodaj_strefe(x0, y0, x1, y1, nazwa, kolor):
        fig.add_shape(type="rect", x0=x0, y0=y0, x1=x1, y1=y1, fillcolor=kolor, opacity=0.45, line=dict(color="black", width=1))
        fig.add_annotation(x=(x0+x1)/2, y=(y0+y1)/2, text=nazwa, showarrow=False, font=dict(size=18, color="black", family="Arial Black"))

    if typ_dachu == "Dwuspadowy" and kierunek_wiatru.startswith("θ = 0°"):
        fig.add_shape(type="line", x0=0, y0=b/2, x1=d, y1=b/2, line=dict(color="black", width=2, dash="dash"))
        
        F_x = min(e/4, d/2)
        F_y = min(e/10, b/2)
        
        dodaj_strefe(0, 0, F_x, F_y, "F", "red")
        dodaj_strefe(d-F_x, 0, d, F_y, "F", "red")
        if d > 2*F_x: dodaj_strefe(F_x, 0, d-F_x, F_y, "G", "orange")
        if b/2 > F_y: dodaj_strefe(0, F_y, d, b/2, "H", "gold")
            
        if b/2 > F_y: dodaj_strefe(0, b/2, d, b-F_y, "I", "lightblue")
        dodaj_strefe(0, b-F_y, d, b, "J", "blue")
        
        fig.add_annotation(x=d/2, y=-b*0.15, ax=d/2, ay=-b*0.35, xref="x", yref="y", axref="x", ayref="y", showarrow=True, arrowhead=2, arrowsize=2, arrowwidth=4, arrowcolor="gray")
        fig.add_annotation(x=d/2, y=-b*0.45, text="Kierunek wiatru (θ = 0°)", showarrow=False, font=dict(size=14))

    elif typ_dachu == "Dwuspadowy" and kierunek_wiatru.startswith("θ = 90°"):
        fig.add_shape(type="line", x0=0, y0=b/2, x1=d, y1=b/2, line=dict(color="black", width=2, dash="dash"))
        
        F_x = min(e/10, d) 
        F_y = min(e/4, b/2)
        
        dodaj_strefe(0, 0, F_x, F_y, "F", "red")
        dodaj_strefe(0, b-F_y, F_x, b, "F", "red")
        if b > 2*F_y: dodaj_strefe(0, F_y, F_x, b-F_y, "G", "orange")
            
        H_x = min(e/2, d)
        if H_x > F_x: dodaj_strefe(F_x, 0, H_x, b, "H", "gold")
        if d > H_x: dodaj_strefe(H_x, 0, d, b, "I", "lightblue")
            
        fig.add_annotation(x=-d*0.1, y=b/2, ax=-d*0.25, ay=b/2, xref="x", yref="y", axref="x", ayref="y", showarrow=True, arrowhead=2, arrowsize=2, arrowwidth=4, arrowcolor="gray")
        fig.add_annotation(x=-d*0.32, y=b/2, text="Kierunek wiatru (θ = 90°)", showarrow=False, textangle=-90, font=dict(size=14))

    else:
        fig.add_annotation(x=d/2, y=b/2, text="Wizualizacja rzutu jest obecnie obsługiwana tylko dla dachu dwuspadowego.", showarrow=False, font=dict(size=16))

    fig.update_layout(
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False, scaleanchor="x", scaleratio=1),
        plot_bgcolor="white", height=600, margin=dict(l=20, r=20, t=20, b=20), dragmode="pan"
    )
    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True, 'displayModeBar': True, 'modeBarButtonsToRemove': ['lasso2d', 'select2d']})

with tab_snieg:
    st.subheader(f"Schematy wg PN-EN 1991-1-3 ({typ_dachu})")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### ❄️ Schemat Równomierny (Główny)")
        st.metric("Obciążenie połaci (s)", f"{s_dach:.2f} kN/m²", delta=f"μ1 = {mu_1:.2f}, Ce = {c_e:.2f}, Ct = {c_t:.2f}", delta_color="off")
    
    with c2:
        if typ_dachu == "Dwuspadowy":
            st.markdown("### 🌬️ Schemat Asymetryczny")
            s1, s2 = st.columns(2)
            s1.metric("Połać nawietrzna", f"{0.5 * s_dach:.2f} kN/m²", delta="0.5 * s")
            s2.metric("Połać zawietrzna", f"{s_dach:.2f} kN/m²", delta="1.0 * s")
        else:
            st.markdown("### 🌬️ Schemat Asymetryczny")
            st.success("Dla dachów płaskich i jednospadowych EC1 nie wymaga sprawdzania schematu nierównomiernego.")
    
    st.divider()
    c3, c4 = st.columns(2)
    with c3:
        if typ_dachu == "Płaski (α = 0°)":
            st.markdown("### ⚠️ Zjawiska krawędziowe")
            st.info("Zjawisko zsuwania się śniegu i siły na płotkach nie występują na dachach płaskich.")
        else:
            st.markdown("### ⚠️ Zjawiska krawędziowe (Okap)")
            s1, s2 = st.columns(2)
            s1.metric("Nawis śnieżny (Se)", f"{se_nawis:.2f} kN/m")
            if plotki:
                s2.metric("Siła na płotki (Fs)", f"{f_plotki:.2f} kN/m", delta="Uderzenie śniegu", delta_color="inverse")
                
    with c4:
        if h_attyki > 0:
            st.markdown("### 🏔️ Zaspa przy attyce")
            s1, s2, s3 = st.columns(3)
            s1.metric("Wsp. (μ2)", f"{mu_2:.2f}")
            s2.metric("Zasięg (ls)", f"{l_s:.2f} m")
            s3.metric("Maks. s_max", f"{s_zaspa:.2f} kN/m²")
        else:
            st.markdown("### 🏔️ Zaspa przy attyce")
            st.success("Brak attyki. Pominięto spiętrzanie śniegu.")

with tab_raport:
    st.subheader("Eksport danych do programów obliczeniowych (MES)")
    
    raport_txt = f"""=========================================================
RAPORT OBCIĄŻEŃ KLIMATYCZNYCH WG PN-EN 1991-1
=========================================================
PODSTAWA NORMOWA (Polskie Załączniki Krajowe):
- PN-EN 1991-1-3:2005/NA:2010 (Obciążenie śniegiem)
- PN-EN 1991-1-4:2008/NA:2010 (Oddziaływania wiatru)
=========================================================
Data wygenerowania: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}

[1. PARAMETRY GEOMETRYCZNE I LOKALIZACJA]
Typ dachu:          {typ_dachu}
Wymiary budynku:    b = {b} m | d = {d} m | h = {h} m
Nachylenie połaci:  alfa = {alfa} stopni
Strefa śniegowa:    {strefa_snieg} (Wysokość: {A} m n.p.m.)
Strefa wiatrowa:    {strefa_wiatr} (Kategoria terenu: {kat_terenu})

[2. OBCIĄŻENIE ŚNIEGIEM (PN-EN 1991-1-3)]
Wartość na gruncie (sk):      {sk:.2f} kN/m2
Wsp. kształtu dachu (mu_1):   {mu_1:.2f}
Współczynniki Ce / Ct:        {c_e:.2f} / {c_t:.2f}
=> SCHEMAT 1: Obciążenie równomierne połaci: {s_dach:.2f} kN/m2
"""
    if typ_dachu == "Dwuspadowy":
        raport_txt += f"=> SCHEMAT 2: Asymetryczne (Nawietrzna: {0.5 * s_dach:.2f} kN/m2 | Zawietrzna: {s_dach:.2f} kN/m2)\n"
    if h_attyki > 0:
        raport_txt += f"=> ZASPA PRZY ATTYCE: zasieg ls = {l_s:.2f} m | s_max = {s_zaspa:.2f} kN/m2\n"
    if se_nawis > 0:
        raport_txt += f"=> NAWIS ŚNIEŻNY (okap): {se_nawis:.2f} kN/m\n"
    
    raport_txt += f"""
[3. OBCIĄŻENIE WIATREM (PN-EN 1991-1-4)]
Prędkość bazowa (vb,0):       {vb0:.2f} m/s
Wysokość odniesienia (ze):    {z:.2f} m
Szczytowe ciśnienie (qp):     {qp:.2f} kN/m2

--- ZESTAWIENIE SIŁ (Kierunek wiatru: {kierunek_wiatru.split(' ')[0]}) ---
Wymiar odniesienia e = {e:.2f} m

STREFY ŚCIAN [kN/m2]:
{df_sc_final.to_string(index=False)}

STREFY DACHU [kN/m2]:
{df_d_final.to_string(index=False)}
=========================================================
OGRANICZENIA STOSOWALNOŚCI PROGRAMU I NOTA PRAWNA:
1. Obliczenia dotyczą budynków o rzucie prostokątnym.
2. Wysokość budynku h nie przekracza 200 m.
3. Pominięto efekty dynamiczne (przyjęto wsp. konstrukc. cs cd = 1.0).
4. Program nie uwzględnia wpływu sąsiadującej zabudowy, budynków na 
   zboczach i w dolinach (orografia).

Wyniki niniejszego raportu stanowią pomoc warsztatową i wymagają 
bezwzględnej weryfikacji oraz zatwierdzenia przez Projektanta Konstrukcji 
posiadającego odpowiednie uprawnienia budowlane.
Twórca programu nie ponosi odpowiedzialności za błędy wynikowe.
=========================================================
"""
    st.text_area("Podgląd notki obliczeniowej:", value=raport_txt, height=550)
    st.download_button(label="📥 Pobierz Raport (.txt)", data=raport_txt, file_name=f"Obciazenia_Klimatyczne_{datetime.datetime.now().strftime('%Y%m%d')}.txt", mime="text/plain")