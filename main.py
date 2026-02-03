import streamlit as st
import pandas as pd
from fpdf import FPDF
import datetime
import json
import os
import io
from gemini_service import transcribir_audio_fluido, procesar_pedido_con_ia
from streamlit_mic_recorder import mic_recorder

# --- PERSISTENCIA ---
ARCHIVO_DB = "inventario_morita.json"

def guardar_datos(datos):
    with open(ARCHIVO_DB, "w", encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=4)

def cargar_datos():
    if os.path.exists(ARCHIVO_DB):
        try:
            with open(ARCHIVO_DB, "r", encoding='utf-8') as f:
                return json.load(f)
        except: return []
    return []

def generar_ticket_pdf(items, total, paga, vuelto):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", 'B', 22)
    pdf.cell(190, 15, "MORITA MINIMERCADO", ln=True, align='C')
    pdf.set_font("helvetica", '', 14)
    pdf.cell(190, 10, f"FECHA: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
    pdf.ln(5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    pdf.set_font("helvetica", 'B', 14)
    for i in items:
        pdf.cell(90, 10, f"{i['Producto'].upper()}")
        pdf.cell(40, 10, f"x{i['Cant']}")
        pdf.cell(60, 10, f"${i['Subtotal']:,.2f}", ln=True, align='R')
    pdf.ln(5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    pdf.set_font("helvetica", 'B', 18)
    pdf.cell(130, 12, "TOTAL:", align='R'); pdf.cell(60, 12, f"${total:,.2f}", ln=True, align='R')
    pdf.set_font("helvetica", '', 16)
    pdf.cell(130, 10, "PAGA CON:", align='R'); pdf.cell(60, 10, f"${paga:,.2f}", ln=True, align='R')
    pdf.cell(130, 12, "VUELTO:", align='R'); pdf.cell(60, 12, f"${vuelto:,.2f}", ln=True, align='R')
    return bytes(pdf.output())

if 'inventario' not in st.session_state:
    st.session_state.inventario = cargar_datos()
if 'carrito' not in st.session_state:
    st.session_state.carrito = []
if 'texto_ia' not in st.session_state:
    st.session_state.texto_ia = ""

st.set_page_config(layout="wide", page_title="SISTEMA MORITA")

# --- CSS ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@700&display=swap');
        [data-testid="InputInstructions"] { display: none !important; }
        html, body, [class*="st-"] { font-size: 1.15rem !important; }
        .titulo-contenedor { background-color: #1E1E1E; padding: 20px; border-radius: 15px; border-bottom: 8px solid #D32F2F; margin-bottom: 25px; }
        .titulo-texto { font-family: 'Oswald', sans-serif !important; font-size: 60px !important; color: #FFFFFF !important; text-align: center; text-transform: uppercase; margin: 0; }
        div.stButton > button { background-color: #FF4B4B !important; color: white !important; font-weight: bold !important; height: 60px !important; border-radius: 10px !important; }
        .box-entendi { background-color: #E8F5E9; padding: 15px; border-radius: 10px; border-left: 5px solid #4CAF50; font-weight: bold; margin: 10px 0; font-size: 1.3rem; color: #1B5E20; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="titulo-contenedor"><h1 class="titulo-texto">SISTEMA MORITA</h1></div>', unsafe_allow_html=True)

tabs = st.tabs(["🛒 CAJA DE VENTAS", "📦 GESTIÓN DE INVENTARIO"])

# --- TAB 1: CAJA ---
with tabs[0]:
    col1, col2 = st.columns([1, 1.4])
    with col1:
        st.subheader("🎙️ COMANDO DE VOZ")
        audio = mic_recorder(start_prompt="🎤 HABLAR", stop_prompt="🛑 DETENER", key='recorder')
        if audio:
            with st.spinner("IA Procesando..."):
                with open("temp_audio.wav", "wb") as f: f.write(audio['bytes'])
                transcripcion = transcribir_audio_fluido("temp_audio.wav")
                st.session_state.texto_ia = procesar_pedido_con_ia(transcripcion, str(st.session_state.inventario))
        
        if st.session_state.texto_ia and st.session_state.texto_ia.strip() != "":
            st.markdown(f'<div class="box-entendi">ENTENDÍ:<br>{st.session_state.texto_ia}</div>', unsafe_allow_html=True)
            c_v1, c_v2 = st.columns(2)
            if c_v1.button("✅ AGREGAR TODO"):
                lineas = st.session_state.texto_ia.split('\n')
                for l in lineas:
                    if '|' in l:
                        parts = l.split('|')
                        p_nom, p_cant, p_subt = parts[0].strip(), float(parts[1].strip()), float(parts[2].strip())
                        st.session_state.carrito.append({"Producto": p_nom, "Cant": p_cant, "Precio": p_subt/p_cant if p_cant!=0 else 0, "Subtotal": p_subt})
                st.session_state.texto_ia = ""
                st.rerun()
            if c_v2.button("🗑️ LIMPIAR IA"):
                st.session_state.texto_ia = ""
                st.rerun()

        st.divider()
        st.subheader("⌨️ SELECCIÓN MANUAL")
        prods = sorted([p['Producto'] for p in st.session_state.inventario])
        s_p = st.selectbox("BUSCAR PRODUCTO:", [""] + prods)
        if s_p:
            p_data = next(i for i in st.session_state.inventario if i["Producto"] == s_p)
            st.info(f"📊 STOCK: {p_data['Stock']} | 💰 PRECIO: ${p_data['Precio']}")
            c_v = st.number_input("CANTIDAD:", min_value=0.01, value=1.0)
            if st.button("➕ AÑADIR A FACTURA"):
                st.session_state.carrito.append({"Producto": s_p, "Cant": c_v, "Precio": p_data['Precio'], "Subtotal": p_data['Precio'] * c_v})
                st.rerun()

    with col2:
        st.subheader("🧾 DETALLE DE FACTURA")
        if st.session_state.carrito:
            total_factura = sum(i['Subtotal'] for i in st.session_state.carrito)
            for idx, item in enumerate(st.session_state.carrito):
                c_f1, c_f2, c_f3, c_f4 = st.columns([3, 1, 1, 0.5])
                c_f1.write(f"**{item['Producto'].upper()}**")
                c_f2.write(f"x{item['Cant']}")
                c_f3.write(f"${item['Subtotal']:,.2f}")
                if c_f4.button("❌", key=f"del_{idx}"): st.session_state.carrito.pop(idx); st.rerun()
            
            st.divider()
            st.markdown(f"## TOTAL: ${total_factura:,.2f}")
            paga = st.number_input("PAGA CON ($):", min_value=0.0, value=float(total_factura))
            vuelto = max(0.0, paga - total_factura)
            st.warning(f"VUELTO: ${vuelto:,.2f}")
            
            b1, b2, b3 = st.columns(3)
            if b1.button("⚡ VENTA RÁPIDA"):
                for it in st.session_state.carrito:
                    for p in st.session_state.inventario:
                        if p['Producto'].lower() == it['Producto'].lower(): p['Stock'] -= it['Cant']
                guardar_datos(st.session_state.inventario)
                st.session_state.carrito = []
                st.session_state.texto_ia = "" # LIMPIEZA IA
                st.rerun()
            
            # TICKET PDF (Generación y limpieza de IA al presionar cualquier otro botón de acción)
            pdf_data = generar_ticket_pdf(st.session_state.carrito, total_factura, paga, vuelto)
            # Nota: download_button en Streamlit refresca la página, pero para asegurar limpieza total:
            if st.download_button("🖨️ TICKET PDF", data=pdf_data, file_name="ticket_morita.pdf", mime="application/pdf"):
                st.session_state.texto_ia = "" # Esto actúa en el siguiente ciclo
            
            if b3.button("🔄 REINICIAR"):
                st.session_state.carrito = []
                st.session_state.texto_ia = "" # LIMPIEZA IA
                st.rerun()
        else:
            st.info("Caja vacía.")

# --- TAB 2: INVENTARIO ---
with tabs[1]:
    st.subheader("📊 LISTADO Y ACTUALIZACIÓN")
    if st.session_state.inventario:
        df_inv = pd.DataFrame(st.session_state.inventario)
        edited_df = st.data_editor(df_inv[['Producto', 'Precio', 'Stock', 'Rubro']], use_container_width=True, height=400)
        if st.button("💾 GUARDAR CAMBIOS DE TABLA"):
            st.session_state.inventario = edited_df.to_dict(orient='records')
            guardar_datos(st.session_state.inventario); st.rerun()

    st.divider()
    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("➕ REGISTRAR / ELIMINAR")
        with st.form("reg_manual", clear_on_submit=True):
            f1, f2, f3, f4 = st.columns(4)
            n_n = f1.text_input("NOMBRE")
            n_p = f2.number_input("PRECIO", min_value=0.0)
            n_s = f3.number_input("STOCK", min_value=0.0)
            n_r = f4.selectbox("RUBRO", ["Almacén", "Bebidas", "Limpieza", "Verdura", "Otros"])
            if st.form_submit_button("REGISTRAR"):
                st.session_state.inventario.append({"Producto": n_n, "Precio": n_p, "Stock": n_s, "Rubro": n_r})
                guardar_datos(st.session_state.inventario); st.rerun()
        
        p_del = st.selectbox("ELIMINAR:", [""] + sorted([p['Producto'] for p in st.session_state.inventario]))
        if st.button("🗑️ BORRAR SELECCIONADO") and p_del:
            st.session_state.inventario = [p for p in st.session_state.inventario if p['Producto'] != p_del]
            guardar_datos(st.session_state.inventario); st.rerun()

    with col_b:
        st.subheader("📂 RESPALDO Y EXCEL")
        # Descarga
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            pd.DataFrame(st.session_state.inventario).to_excel(writer, index=False)
        st.download_button("📥 DESCARGAR XLS", data=output.getvalue(), file_name="Inventario_Morita.xlsx")
        
        # SUBIR COPIA DE RESPALDO (AGREGADO)
        st.write("---")
        up_file = st.file_uploader("📤 SUBIR COPIA DE RESPALDO (Excel)", type=["xlsx"])
        if up_file:
            if st.button("🚀 RESTAURAR INVENTARIO"):
                try:
                    df_up = pd.read_excel(up_file)
                    st.session_state.inventario = df_up.to_dict(orient='records')
                    guardar_datos(st.session_state.inventario)
                    st.success("Inventario restaurado con éxito")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al leer el archivo: {e}")


