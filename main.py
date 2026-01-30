import streamlit as st
import pandas as pd
from fpdf import FPDF
import datetime
import json
import os
import re
import io # Para manejo de memoria en descargas
from gemini_service import transcribir_audio_fluido, procesar_pedido_con_ia
from streamlit_mic_recorder import mic_recorder

# --- PERSISTENCIA DE DATOS REFORZADA ---
ARCHIVO_DB = "inventario_morita.json"

def guardar_datos(datos):
    with open(ARCHIVO_DB, "w", encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=4)

def cargar_datos():
    if os.path.exists(ARCHIVO_DB):
        try:
            with open(ARCHIVO_DB, "r", encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return [{"Producto": "ejemplo", "Precio": 100.0, "Stock": 10}]

# --- FUNCIÓN PARA EXCEL PROFESIONAL ---
def exportar_excel(datos):
    df = pd.DataFrame(datos)
    if not df.empty:
        df.columns = ["PRODUCTO", "PRECIO ($)", "STOCK"]
    
    output = io.BytesIO()
    # Usamos xlsxwriter para generar columnas reales e independientes
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventario_Morita')
        # Auto-ajuste de columnas
        worksheet = writer.sheets['Inventario_Morita']
        for i, col in enumerate(df.columns):
            column_len = max(df[col].astype(str).str.len().max(), len(col)) + 2
            worksheet.set_column(i, i, column_len)
    return output.getvalue()

if 'inventario' not in st.session_state:
    st.session_state.inventario = cargar_datos()
if 'carrito' not in st.session_state:
    st.session_state.carrito = []

st.set_page_config(layout="wide", page_title="MORITA - SISTEMA DE GESTION")

# --- 🎨 INTERFAZ UNIFORME DE ALTA VISIBILIDAD (CSS) ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap');
        html, body, [class*="css"] { font-family: 'Roboto', sans-serif !important; }
        label, p, span { font-size: 22px !important; font-weight: 600 !important; color: #000000 !important; }
        h1 { font-size: 50px !important; color: #D32F2F !important; text-align: center; border-bottom: 3px solid #D32F2F; }
        h2 { font-size: 38px !important; background-color: #f0f2f6; padding: 10px; border-radius: 5px; }
        h3 { font-size: 30px !important; color: #1976D2 !important; }
        .stSelectbox div[data-baseweb="select"], .stNumberInput input, .stTextInput input {
            font-size: 26px !important; height: 60px !important; border: 2px solid #1976D2 !important;
        }
        .stButton button {
            background-color: #1976D2 !important; color: white !important;
            font-size: 24px !important; font-weight: bold !important;
            height: 70px !important; border-radius: 10px !important;
            box-shadow: 2px 2px 5px rgba(0,0,0,0.2) !important;
        }
        button[kind="secondary"] { background-color: #FF5252 !important; color: white !important; }
        button[data-baseweb="tab"] p { font-size: 28px !important; }
    </style>
""", unsafe_allow_html=True)

# --- LOGICA DE PDF ---
def generar_ticket_pdf(cliente, items, total, pago, vuelto):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", 'B', 22)
    pdf.cell(190, 15, "MORITA MINIMERCADO", ln=True, align='C')
    pdf.set_font("helvetica", '', 14)
    pdf.cell(190, 10, f"FECHA: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
    pdf.cell(190, 10, f"CLIENTE: {cliente.upper()}", ln=True)
    pdf.ln(5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    pdf.set_font("helvetica", 'B', 14)
    for i in items:
        pdf.cell(90, 10, f"{i['Producto'].upper()}")
        pdf.cell(40, 10, f"X{i['Cantidad']}")
        pdf.cell(60, 10, f"${i['Subtotal']:,.2f}", ln=True, align='R')
    
    pdf.ln(5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    pdf.set_font("helvetica", 'B', 18)
    pdf.cell(130, 12, "TOTAL:", align='R'); pdf.cell(60, 12, f"${total:,.2f}", ln=True, align='R')
    pdf.set_font("helvetica", '', 16)
    pdf.cell(130, 10, "PAGA CON:", align='R'); pdf.cell(60, 10, f"${pago:,.2f}", ln=True, align='R')
    pdf.cell(130, 12, "VUELTO:", align='R'); pdf.cell(60, 12, f"${vuelto:,.2f}", ln=True, align='R')
    
    return bytes(pdf.output())

# --- ESTRUCTURA DE LA APP ---
st.title("🍎 SISTEMA MORITA")

# CONSULTOR DE PRECIOS
with st.expander("🔍 CONSULTAR PRECIO / ACTUALIZAR", expanded=False):
    c1, c2, c3 = st.columns([2,1,1])
    nombres = sorted([p['Producto'] for p in st.session_state.inventario])
    p_busq = c1.selectbox("SELECCIONE PRODUCTO:", [""] + nombres, key="busq")
    if p_busq:
        idx = next(i for i, p in enumerate(st.session_state.inventario) if p['Producto'] == p_busq)
        nuevo_p = c2.number_input("PRECIO ($):", value=float(st.session_state.inventario[idx]['Precio']))
        if c3.button("ACTUALIZAR"):
            st.session_state.inventario[idx]['Precio'] = nuevo_p
            guardar_datos(st.session_state.inventario)
            st.rerun()

tabs = st.tabs(["🛒 VENTA (CAJA)", "📦 INVENTARIO / STOCK"])

# --- TAB 1: PUNTO DE VENTA ---
with tabs[0]:
    col1, col2 = st.columns([1, 1.2])
    with col1:
        st.subheader("🎤 CARGA POR VOZ")
        audio = mic_recorder(start_prompt="HABLAR PEDIDO 🎤", stop_prompt="LISTO ⚡", key='voz_final')
        if audio:
            with open("temp.wav", "wb") as f: f.write(audio['bytes'])
            t = transcribir_audio_fluido("temp.wav")
            st.success(f"ENTENDÍ: {t}")
            res = procesar_pedido_con_ia(t, str(st.session_state.inventario))
            if st.button("CONFIRMAR Y AGREGAR"):
                for l in res.strip().split('\n'):
                    if '|' in l:
                        p, c, pr = l.split('|')
                        cant = int(re.findall(r'\d+', c)[0])
                        pre = float(re.findall(r'\d+\.?\d*', pr)[0])
                        st.session_state.carrito.append({"Producto": p.strip(), "Cantidad": cant, "Precio Unit.": pre, "Subtotal": cant * pre})
                st.rerun()
        
        st.divider()
        st.subheader("⌨️ CARGA MANUAL")
        sel = st.selectbox("PRODUCTO:", [""] + nombres)
        can = st.number_input("CANTIDAD:", min_value=1, value=1)
        if st.button("➕ AGREGAR A CAJA") and sel != "":
            p_data = next(i for i in st.session_state.inventario if i["Producto"] == sel)
            st.session_state.carrito.append({"Producto": sel, "Cantidad": can, "Precio Unit.": p_data['Precio'], "Subtotal": p_data['Precio']*can})
            st.rerun()

    with col2:
        st.subheader("📋 FACTURA ACTUAL")
        if st.session_state.carrito:
            for idx, item in enumerate(st.session_state.carrito):
                cx1, cx2, cx3, cx4 = st.columns([3, 1, 1.5, 0.5])
                cx1.markdown(f"**{item['Producto'].upper()}**")
                cx2.write(f"x{item['Cantidad']}")
                cx3.write(f"${item['Subtotal']:,.2f}")
                if cx4.button("❌", key=f"del_{idx}"):
                    st.session_state.carrito.pop(idx); st.rerun()
            
            total = sum(i['Subtotal'] for i in st.session_state.carrito)
            st.markdown(f"# TOTAL: ${total:,.2f}")
            paga = st.number_input("PAGA CON ($):", min_value=float(total))
            st.warning(f"## VUELTO: ${paga - total:,.2f}")
            cli = st.text_input("NOMBRE CLIENTE:", "CONSUMIDOR FINAL")
            
            pdf = generar_ticket_pdf(cli, st.session_state.carrito, total, paga, paga - total)
            if st.download_button("📥 FINALIZAR Y TICKET", data=pdf, file_name=f"ticket_{cli}.pdf"):
                for i in st.session_state.carrito:
                    for p in st.session_state.inventario:
                        if p['Producto'].lower() == i['Producto'].lower(): p['Stock'] -= i['Cantidad']
                guardar_datos(st.session_state.inventario)
                st.session_state.carrito = []
                st.rerun()

# --- TAB 2: ADMINISTRACION ---
with tabs[1]:
    st.subheader("📦 GESTIÓN DE PRODUCTOS")
    
    # Botón de Descarga Excel (Lado derecho superior)
    c_ex1, c_ex2 = st.columns([2,1])
    with c_ex2:
        datos_xlsx = exportar_excel(st.session_state.inventario)
        st.download_button(
            label="📊 DESCARGAR EXCEL DE PRECIOS",
            data=datos_xlsx,
            file_name=f"inventario_morita_{datetime.date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    with st.form("admin_form"):
        f1, f2, f3 = st.columns(3)
        n_n = f1.text_input("NOMBRE DEL PRODUCTO")
        n_p = f2.number_input("PRECIO UNITARIO ($)")
        n_s = f3.number_input("STOCK INICIAL", min_value=0)
        if st.form_submit_button("REGISTRAR PRODUCTO"):
            found = False
            for i in st.session_state.inventario:
                if i['Producto'].lower() == n_n.lower():
                    i['Precio'], i['Stock'], found = n_p, n_s, True
            if not found: st.session_state.inventario.append({"Producto": n_n, "Precio": n_p, "Stock": n_s})
            guardar_datos(st.session_state.inventario); st.rerun()
    
    st.write("### LISTADO DE PRODUCTOS EN SISTEMA")
    st.dataframe(pd.DataFrame(st.session_state.inventario), use_container_width=True, height=400)
    
    p_del = st.selectbox("BORRAR PRODUCTO:", [""] + [x['Producto'] for x in st.session_state.inventario])
    if st.button("🚨 ELIMINAR TOTALMENTE"):
        st.session_state.inventario = [x for x in st.session_state.inventario if x['Producto'] != p_del]
        guardar_datos(st.session_state.inventario); st.rerun()