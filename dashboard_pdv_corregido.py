import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import io
import zipfile
import calendar
import re
import unicodedata
import requests
from datetime import datetime

# ══════════════════════════════════════════════════════════════════
#  CONFIG TELEGRAM
# ══════════════════════════════════════════════════════════════════

# 🔧 CONFIGURACIÓN TELEGRAM - DATOS REALES
TELEGRAM_CONFIG = {
    'BOT_TOKEN': '8249353159:AAFvpNkEUdTcuIu_kpMcQbOtqyB0WbZkGTc',
    'CHAT_IDS': {
        'gerencia': '7900265168',        # Tu chat personal
        'administracion': '7900265168',  # Mismo chat (puedes cambiar después)
        'vendedores': '7900265168'       # Mismo chat (puedes cambiar después)
    }
}


def es_super_admin(user_codigo, user_nombre):
    """Verifica si el usuario es Israel (super administrador)"""
    # Criterios para Super Admin
    codigo_israel = str(user_codigo) == '1804140794'
    nombre_israel = 'ISRAEL' in str(user_nombre).upper()
    nombre_completo = 'PAREDES ALTAMIRANO ISRAEL' in str(user_nombre).upper()
    
    return codigo_israel or nombre_israel or nombre_completo


def tiene_permisos_admin(user_rol):
    """Verifica si el usuario tiene permisos básicos de admin"""
    return user_rol.lower() in ('admin', 'administrador', 'gerente', 'supervisor', 'jefe')
def enviar_telegram(mensaje, chat_id=None, imagen=None):
    """Envía mensaje y/o imagen a Telegram"""
    if not chat_id:
        chat_id = TELEGRAM_CONFIG['CHAT_IDS']['gerencia']
    
    bot_token = TELEGRAM_CONFIG['BOT_TOKEN']
    
    try:
        # Enviar mensaje de texto
        if mensaje:
            url_texto = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': mensaje,
                'parse_mode': 'HTML'
            }
            requests.post(url_texto, data=payload)
        
        # Enviar imagen si existe
        if imagen:
            url_foto = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            files = {'photo': imagen}
            data = {'chat_id': chat_id}
            requests.post(url_foto, files=files, data=data)
            
        return True
    except Exception as e:
        st.error(f"❌ Error enviando a Telegram: {str(e)}")
        return False


def generar_reporte_telegram(df_final, mv, md, nombre_rep, m_sel, venta_real, impactos, proy):
    """Genera reporte de texto para Telegram"""
    pct_v = round(venta_real / mv * 100, 1) if mv > 0 else 0
    pct_dn = round(impactos / md * 100, 1) if md > 0 else 0
    
    # Emojis de estado
    emoji_meta = "✅" if pct_v >= 100 else "⚠️" if pct_v >= 80 else "❌"
    emoji_dn = "✅" if pct_dn >= 100 else "⚠️" if pct_dn >= 80 else "❌"
    emoji_proy = "📈" if proy >= mv else "📉"
    
    mensaje = f"""
📊 <b>REPORTE PDV - {nombre_rep}</b>
📅 <b>Período:</b> {m_sel}
🕐 <b>Generado:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}

💰 <b>VENTAS NETAS</b>
├ Venta Real: <b>${venta_real:,.0f}</b>
├ Meta: <b>${mv:,.0f}</b>
└ Avance: <b>{pct_v}%</b> {emoji_meta}

👥 <b>COBERTURA DN</b>
├ Clientes Impactados: <b>{impactos}</b>
├ Meta DN: <b>{int(md)}</b>
└ Cobertura: <b>{pct_dn}%</b> {emoji_dn}

{emoji_proy} <b>PROYECCIÓN CIERRE</b>
└ Estimado: <b>${proy:,.0f}</b>

🎯 <b>TOP 3 MARCAS</b>"""
    
    # Agregar top marcas
    if not df_final.empty:
        top_marcas = df_final.groupby('Marca')['Total'].sum().nlargest(3)
        for i, (marca, venta) in enumerate(top_marcas.items(), 1):
            mensaje += f"\n{i}. {marca}: ${venta:,.0f}"
    
    mensaje += f"\n\n💎 <i>Sistema SOLUTO - PDV Sin Límites</i>"
    
    return mensaje


def configurar_telegram():
    """Panel de configuración de Telegram en sidebar"""
    st.sidebar.markdown("---")
    st.sidebar.markdown("📱 **TELEGRAM CONFIG**")
    
    # Mostrar estado de configuración
    bot_configurado = TELEGRAM_CONFIG['BOT_TOKEN'] != 'TU_TOKEN_AQUI'
    
    if not bot_configurado:
        st.sidebar.error("⚠️ Bot no configurado")
        if st.sidebar.button("ℹ️ Ver instrucciones"):
            st.sidebar.info("""
**PASOS PARA CONFIGURAR:**

1️⃣ **Busca tu bot** en Telegram
2️⃣ **Envía**: /start 
3️⃣ **Ve a esta URL** (reemplaza TOKEN):
   api.telegram.org/botTU_TOKEN/getUpdates
4️⃣ **Busca**: "chat":{"id": NÚMERO
5️⃣ **Copia** ese NÚMERO al código
6️⃣ **Reinicia** la app
            """)
        return False, None
    
    # Bot configurado - mostrar controles
    telegram_activo = st.sidebar.checkbox("🚀 Envío automático", key="telegram_on")
    
    if telegram_activo:
        chat_option = st.sidebar.selectbox(
            "👥 Destinatario:",
            ["gerencia", "administracion", "vendedores"],
            key="telegram_chat"
        )
        
        # Botón de prueba
        if st.sidebar.button("🧪 Probar conexión"):
            chat_id = TELEGRAM_CONFIG['CHAT_IDS'][chat_option]
            mensaje_prueba = f"""
🧪 <b>PRUEBA DE CONEXIÓN</b>
📅 <b>Fecha:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}

✅ <b>Bot configurado correctamente</b>
👤 <b>Destinatario:</b> {chat_option}
💎 <b>Sistema:</b> PDV Sin Límites

🎉 <i>¡Telegram funcionando perfectamente!</i>
"""
            
            with st.spinner("🧪 Probando conexión..."):
                if enviar_telegram(mensaje_prueba, chat_id):
                    st.sidebar.success("✅ ¡Conexión exitosa!")
                else:
                    st.sidebar.error("❌ Error de conexión")
        
        st.sidebar.success("✅ Telegram activo")
        return True, chat_option
    
    return False, None
st.set_page_config(
    page_title="PDV Sin Límites 2026",
    layout="wide",
    page_icon="💎",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Syne:wght@700;800&display=swap');
html,body,[class*="css"]{font-family:'Space Grotesk',sans-serif;background:#0A0F1E;color:#E2E8F0;}
header,footer,#MainMenu{visibility:hidden;}
.block-container{padding:1rem 1.5rem!important;max-width:100%!important;}
div[data-testid="stSidebar"]{background:linear-gradient(180deg,#0A0F1E,#111827);border-right:1px solid #1E3A8A33;}
.login-logo{font-family:'Syne',sans-serif;font-size:2rem;font-weight:800;color:#3B82F6;letter-spacing:-1px;margin-bottom:4px;}
.login-sub{font-size:0.78rem;color:#64748B;text-transform:uppercase;letter-spacing:2px;margin-bottom:28px;}
.login-label{font-size:0.72rem;color:#94A3B8;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px;font-weight:600;}
.error-box{background:#450A0A;border:1px solid #7F1D1D;border-radius:8px;padding:10px 14px;font-size:0.82rem;color:#FCA5A5;margin-top:12px;}
.top-bar{background:linear-gradient(135deg,#0F172A,#1E2940);border:1px solid #1E3A8A44;border-radius:14px;padding:14px 22px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;}
.top-bar-title{font-family:'Syne',sans-serif;font-size:1.3rem;font-weight:800;color:#F8FAFC;}
.top-bar-user{font-size:0.78rem;color:#60A5FA;font-weight:600;text-align:right;}
.top-bar-badge{background:#1E3A8A;border-radius:20px;padding:4px 14px;font-size:0.7rem;color:#BFDBFE;font-weight:700;text-transform:uppercase;display:inline-block;margin-top:4px;}
.kpi-card{background:linear-gradient(145deg,#111827,#1A2540);border:1px solid #1E3A8A33;border-radius:14px;padding:18px 20px;text-align:center;position:relative;overflow:hidden;margin-bottom:8px;}
.kpi-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--accent,#3B82F6);border-radius:14px 14px 0 0;}
.kpi-val{font-family:'Syne',sans-serif;font-size:1.8rem;font-weight:800;color:var(--accent,#3B82F6);line-height:1;margin-bottom:4px;}
.kpi-lbl{font-size:0.62rem;color:#64748B;text-transform:uppercase;letter-spacing:1.5px;font-weight:600;}
.kpi-sub{font-size:0.7rem;color:#94A3B8;margin-top:4px;}
.section-title{font-family:'Syne',sans-serif;font-size:1rem;font-weight:700;color:#CBD5E1;margin:18px 0 10px;text-transform:uppercase;letter-spacing:1px;}
.cruce-ok{background:#052e16;border:1px solid #16a34a;border-radius:8px;padding:8px 14px;font-size:0.8rem;color:#86efac;margin:6px 0;}
.cruce-err{background:#450a0a;border:1px solid #dc2626;border-radius:8px;padding:8px 14px;font-size:0.8rem;color:#fca5a5;margin:6px 0;}
.admin-badge{background:linear-gradient(135deg,#7C3AED,#A855F7);border-radius:6px;padding:2px 10px;font-size:0.65rem;font-weight:700;color:#F5F3FF;text-transform:uppercase;letter-spacing:1px;display:inline-block;margin-left:8px;}
.stButton>button,.stDownloadButton>button{background:linear-gradient(135deg,#1E40AF,#3B82F6)!important;color:white!important;border:none!important;border-radius:8px!important;font-weight:700!important;}
.stTabs [data-baseweb="tab-list"]{background:#111827;border-radius:10px;padding:4px;gap:4px;}
.stTabs [data-baseweb="tab"]{background:transparent!important;color:#64748B!important;border-radius:8px!important;font-weight:600!important;}
.stTabs [aria-selected="true"]{background:#1E3A8A!important;color:#fff!important;}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════
def norm_txt(v):
    """Quita tildes, mayúsculas, colapsa espacios."""
    s = str(v).strip().upper()
    s = ''.join(c for c in unicodedata.normalize('NFD', s)
                if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', s)


def limpiar_columnas(df):
    """Elimina BOM, espacios y caracteres invisibles de los nombres de columna."""
    df.columns = [
        str(c).strip()
          .replace('\ufeff', '')
          .replace('\xa0', '')
          .replace('\u200b', '')
        for c in df.columns
    ]
    return df


def descomponer_vendedor(texto):
    """
    'PDV09 - YANEZ FLORES JENNIFER LISSETTE'  → ('PDV09', 'YANEZ FLORES JENNIFER LISSETTE')
    'PDV10 DARWIN - SANTANA ESTUPINAN DARWIN' → ('PDV10', 'SANTANA ESTUPINAN DARWIN')
    'PDV12 - PAZMIño NARVAEZ MIGUEL ANGEL'    → ('PDV12', 'PAZMIÑO NARVAEZ MIGUEL ANGEL')
    """
    texto = str(texto).strip()
    m = re.match(r'(PDV\d+)', texto.upper())
    codigo = m.group(1) if m else ''

    if ' - ' in texto:
        nombre = texto.split(' - ', 1)[1].strip()
    elif codigo:
        nombre = re.sub(r'^PDV\d+\S*\s*', '', texto, flags=re.IGNORECASE).strip()
    else:
        nombre = texto

    return codigo.upper(), norm_txt(nombre)


# ══════════════════════════════════════════════════════════════════
#  CONEXIÓN GOOGLE SHEETS
# ══════════════════════════════════════════════════════════════════
@st.cache_resource(ttl=300)
def get_gc():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # 🔧 DEBUG: Ver qué secrets están disponibles
    try:
        available_secrets = list(st.secrets.keys())
        st.info(f"🔍 DEBUG: Secrets disponibles: {available_secrets}")
        
        if "google" in st.secrets:
            st.success("✅ google encontrado en secrets")
            creds_dict = dict(st.secrets["google"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            st.success("✅ Credenciales cargadas exitosamente desde secrets")
        else:
            st.error("❌ google NO encontrado en secrets")
            raise Exception("Secrets no configurados correctamente")
            
    except Exception as e:
        st.error(f"❌ Error con secrets: {e}")
        st.info("🔧 Intentando archivo local como fallback...")
        try:
            # Fallback local (usando archivo)
            creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
            st.warning("⚠️ Usando archivo local (no recomendado en producción)")
        except Exception as e2:
            st.error(f"❌ Error final: {e2}")
            st.error("💡 Configura los secrets correctamente en Streamlit Cloud")
            st.stop()
    
    return gspread.authorize(creds)


# ══════════════════════════════════════════════════════════════════
#  CARGA USUARIOS
# ══════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300)
def cargar_usuarios():
    gc = get_gc()
    sh = gc.open("soluto")
    df = pd.DataFrame()

    for hoja in ["Usuario_Roles", "Usuarios", "USUARIOS"]:
        try:
            ws = sh.worksheet(hoja)
            df = pd.DataFrame(ws.get_all_records())
            df = limpiar_columnas(df)
            break
        except Exception:
            continue

    if df.empty:
        return df

    col_nombre = next((c for c in df.columns if 'nombre' in c.lower()), None)
    col_pin    = next((c for c in df.columns if 'pin'    in c.lower()), None)
    col_rol    = next((c for c in df.columns if 'rol'    in c.lower()), None)
    col_zona   = next((c for c in df.columns if 'zona'   in c.lower()), None)
    col_codigo = next((c for c in df.columns if 'codigo' in c.lower()), None)

    df['_nombre_orig'] = df[col_nombre].astype(str).str.strip() if col_nombre else ''
    df['_nombre_norm'] = df['_nombre_orig'].apply(norm_txt)
    df['_pin']         = df[col_pin].astype(str).str.strip()    if col_pin    else ''
    df['_rol']         = df[col_rol].astype(str).str.strip()    if col_rol    else 'Vendedor'
    df['_zona']        = df[col_zona].astype(str).str.strip()   if col_zona   else ''
    df['_codigo_pdv']  = (
        df[col_codigo].astype(str).str.strip().str.upper()
        if col_codigo else ''
    )
    df['_codigo_pdv'] = df['_codigo_pdv'].replace({'NAN': '', 'NONE': ''})
    return df


# ══════════════════════════════════════════════════════════════════
#  CARGA VENTAS + PRESUPUESTO
# ══════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300)
def cargar_ventas_presupuesto():
    gc = get_gc()
    sh = gc.open("soluto")

    # ── VENTAS ────────────────────────────────────────────────────
    ws_v   = sh.worksheet("VENTAS")
    df_raw = pd.DataFrame(ws_v.get_all_records())
    df_raw = limpiar_columnas(df_raw)

    # Detectar columnas por nombre (sin depender de mayúsculas ni acentos)
    def find_col(df, keyword):
        return next((c for c in df.columns if keyword in norm_txt(c)), None)

    col_fecha = find_col(df_raw, 'FECHA')
    col_total = find_col(df_raw, 'TOTAL')
    col_vend  = find_col(df_raw, 'VENDEDOR')
    col_cli   = find_col(df_raw, 'CLIENTE')
    col_marca = find_col(df_raw, 'MARCA')
    col_prov  = find_col(df_raw, 'PROVEEDOR')

    # Mostrar columnas en sesión para diagnóstico (tab auditoría)
    st.session_state['_cols_ventas'] = list(df_raw.columns)

    if col_fecha is None:
        raise ValueError(
            f"❌ No se encontró columna FECHA en la hoja VENTAS.\n"
            f"Columnas encontradas: {list(df_raw.columns)}"
        )
    if col_total is None:
        raise ValueError(
            f"❌ No se encontró columna TOTAL en la hoja VENTAS.\n"
            f"Columnas encontradas: {list(df_raw.columns)}"
        )

    # Parsear fecha y total usando variables locales (sin agregar a df_raw)
    fecha_series = pd.to_datetime(df_raw[col_fecha], errors='coerce', dayfirst=True)
    total_series = pd.to_numeric(
        df_raw[col_total].astype(str).str.replace(r'[$,\s]', '', regex=True),
        errors='coerce'
    ).fillna(0)

    mask_ok       = fecha_series.notna()
    sin_fecha     = df_raw[~mask_ok].copy()
    monto_perdido = total_series[~mask_ok].sum()

    df_v = df_raw[mask_ok].copy()
    df_v['Fecha']    = fecha_series[mask_ok].values
    df_v['Total']    = total_series[mask_ok].values
    df_v['Vendedor'] = df_v[col_vend].astype(str)  if col_vend  else ''
    df_v['Cliente']  = df_v[col_cli].astype(str)   if col_cli   else ''
    df_v['Marca']    = df_v[col_marca].astype(str) if col_marca else ''
    df_v['Proveedor']= df_v[col_prov].astype(str)  if col_prov  else ''

    descomp = df_v['Vendedor'].apply(descomponer_vendedor)
    df_v['_codigo_pdv']  = descomp.apply(lambda x: x[0])
    df_v['_nombre_vend'] = descomp.apply(lambda x: x[1])

    # ── PRESUPUESTO ───────────────────────────────────────────────
    ws_p = sh.worksheet("PRESUPUESTO")
    df_p = pd.DataFrame(ws_p.get_all_records())
    df_p = limpiar_columnas(df_p)

    rename_map = {}
    for c in df_p.columns:
        cn = norm_txt(c)
        if 'VENDEDOR' in cn:
            rename_map[c] = 'V_Orig'
        elif 'OBJETIVO' in cn or cn == 'DN':
            rename_map[c] = 'M_DN'
        elif 'PRESUPUESTO' in cn or 'META' in cn:
            rename_map[c] = 'M_V'
    df_p = df_p.rename(columns=rename_map)

    for col in ['M_V', 'M_DN']:
        if col not in df_p.columns:
            df_p[col] = 0
        df_p[col] = pd.to_numeric(
            df_p[col].astype(str).str.replace(r'[$,\s]', '', regex=True),
            errors='coerce'
        ).fillna(0)

    if 'V_Orig' not in df_p.columns:
        df_p['V_Orig'] = ''

    descomp_p = df_p['V_Orig'].apply(descomponer_vendedor)
    df_p['_codigo_pdv']  = descomp_p.apply(lambda x: x[0])
    df_p['_nombre_norm'] = descomp_p.apply(lambda x: x[1])

    audit = {
        'monto_perdido':   monto_perdido,
        'filas_afectadas': len(sin_fecha),
        'detalle_errores': sin_fecha,
    }
    return df_v, df_p, audit


# ══════════════════════════════════════════════════════════════════
#  CRUCE USUARIO → VENTAS / PRESUPUESTO
# ══════════════════════════════════════════════════════════════════
def filtrar_ventas_usuario(df_v, u):
    codigo = str(u.get('_codigo_pdv', '')).strip().upper()
    nombre = str(u.get('_nombre_norm', '')).strip().upper()

    # 1. Código PDV (único, sin ambigüedad)
    if codigo and codigo not in ('', 'NAN', 'NONE'):
        mask = df_v['_codigo_pdv'] == codigo
        if mask.sum() > 0:
            return df_v[mask].copy(), f"✅ Cruce por código PDV: **{codigo}**", "ok"

    # 2. Nombre completo normalizado
    if nombre:
        mask = df_v['_nombre_vend'] == nombre
        if mask.sum() > 0:
            return df_v[mask].copy(), f"✅ Cruce por nombre: **{nombre}**", "ok"

    return (
        pd.DataFrame(),
        f"❌ Sin datos — código **'{codigo}'** no encontrado en VENTAS. "
        f"Verifica la columna **codigo** en Usuario_Roles (debe ser PDVxx).",
        "err"
    )


def filtrar_presupuesto_usuario(df_p, u):
    codigo = str(u.get('_codigo_pdv', '')).strip().upper()
    nombre = str(u.get('_nombre_norm', '')).strip().upper()

    if codigo and codigo not in ('', 'NAN', 'NONE'):
        row = df_p[df_p['_codigo_pdv'] == codigo]
        if not row.empty:
            return row.iloc[0]

    if nombre:
        row = df_p[df_p['_nombre_norm'] == nombre]
        if not row.empty:
            return row.iloc[0]

    return None


# ══════════════════════════════════════════════════════════════════
#  LOGIN
# ══════════════════════════════════════════════════════════════════
def pantalla_login():
    df_users = cargar_usuarios()
    if df_users.empty:
        st.error("❌ No se pudo cargar la hoja Usuario_Roles.")
        return

    nombres = sorted(df_users['_nombre_orig'].tolist())

    _, col_c, _ = st.columns([1, 1.1, 1])
    with col_c:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown(
            "<div class='login-logo'>💎 PDV Sin Límites</div>"
            "<div class='login-sub'>Panel Comercial · 2026</div>",
            unsafe_allow_html=True
        )

        st.markdown("<div class='login-label'>👤 Selecciona tu nombre</div>",
                    unsafe_allow_html=True)
        nombre_sel = st.selectbox("", ["— Selecciona —"] + nombres,
                                  key="login_nombre", label_visibility="collapsed")

        st.markdown("<div class='login-label' style='margin-top:16px;'>🔐 Ingresa tu PIN</div>",
                    unsafe_allow_html=True)
        pin_inp = st.text_input("", type="password", placeholder="• • • • •",
                                key="login_pin", label_visibility="collapsed", max_chars=6)

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("→ INGRESAR", use_container_width=True, key="btn_login"):
            if nombre_sel == "— Selecciona —":
                st.markdown("<div class='error-box'>⚠️ Selecciona tu nombre.</div>",
                            unsafe_allow_html=True)
                return

            fila = df_users[df_users['_nombre_orig'] == nombre_sel]
            if fila.empty:
                st.markdown("<div class='error-box'>❌ Usuario no encontrado.</div>",
                            unsafe_allow_html=True)
                return

            u = fila.iloc[0]
            try:
                pin_correcto = str(int(float(u['_pin'])))
            except Exception:
                pin_correcto = str(u['_pin'])

            if pin_inp.strip() != pin_correcto:
                st.markdown("<div class='error-box'>🔒 PIN incorrecto.</div>",
                            unsafe_allow_html=True)
                return

            st.session_state.update({
                'logged_in':   True,
                'user_nombre': nombre_sel,
                'user_norm':   str(u['_nombre_norm']),
                'user_rol':    str(u['_rol']),
                'user_zona':   str(u['_zona']),
                'user_codigo': str(u['_codigo_pdv']),
                'user_row':    u.to_dict(),
            })
            st.rerun()

        st.caption("🔒 Acceso restringido — Sistema SOLUTO")


# ══════════════════════════════════════════════════════════════════
#  SCORECARD PLOTLY
# ══════════════════════════════════════════════════════════════════
def calcular_proyeccion(venta, fecha_max):
    """Calcula proyección basada en el día ACTUAL del mes (no el último día de ventas)"""
    if pd.isna(fecha_max):
        return 0
    
    # Usar la fecha ACTUAL para el cálculo de proyección
    fecha_actual = datetime.now()
    mes_actual = fecha_actual.month
    año_actual = fecha_actual.year
    dia_actual = fecha_actual.day
    
    # Verificar que estamos en el mismo mes de las ventas
    if fecha_max.month == mes_actual and fecha_max.year == año_actual:
        # Usar día actual del calendario
        _, dias_total = calendar.monthrange(año_actual, mes_actual)
        if dia_actual > 0:
            return (venta / dia_actual) * dias_total
    else:
        # Si es un mes pasado, usar los días que había hasta la fecha máxima de ventas
        _, dias_total = calendar.monthrange(fecha_max.year, fecha_max.month)
        return (venta / fecha_max.day) * dias_total
    
    return 0


def generar_scorecard(df_v, mv, md, nombre_rep, mes):
    venta_real = df_v['Total'].sum()
    impactos   = df_v[df_v['Total'] > 0]['Cliente'].nunique()
    fecha_max  = df_v['Fecha'].max()
    proy       = calcular_proyeccion(venta_real, fecha_max)

    fig = go.Figure()

    fig.add_trace(go.Indicator(
        mode="number", value=venta_real,
        number={'prefix': "$", 'font': {'size': 65, 'color': '#3B82F6', 'weight': 'bold'}},
        title={'text': "💰 VENTA NETA ACUMULADA", 'font': {'size': 18, 'color': '#94A3B8'}},
        domain={'x': [0, 0.48], 'y': [0.90, 1]}))

    fig.add_trace(go.Indicator(
        mode="number", value=impactos,
        number={'font': {'size': 65, 'color': '#F59E0B', 'weight': 'bold'}},
        title={'text': "👥 CLIENTES IMPACTADOS (DN)", 'font': {'size': 18, 'color': '#94A3B8'}},
        domain={'x': [0.52, 1], 'y': [0.90, 1]}))

    fig.add_trace(go.Indicator(
        mode="gauge+number+delta",
        value=(venta_real / mv * 100) if mv > 0 else 0,
        delta={'reference': 100,
               'increasing': {'color': '#10B981'},
               'decreasing': {'color': '#EF4444'}},
        number={'suffix': "%", 'font': {'size': 35, 'weight': 'bold'}},
        gauge={
            'axis': {'range': [0, 125]},
            'bar':  {'color': '#3B82F6', 'thickness': 0.3},
            'bgcolor': '#1E2940', 'borderwidth': 2, 'bordercolor': '#1E3A8A',
            'threshold': {'line': {'color': '#60A5FA', 'width': 4},
                          'thickness': 0.8, 'value': 100}
        },
        title={'text': f"AVANCE META (${mv:,.0f})", 'font': {'size': 15, 'color': '#3B82F6'}},
        domain={'x': [0.05, 0.45], 'y': [0.72, 0.88]}))

    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=(impactos / md * 100) if md > 0 else 0,
        number={'suffix': "%", 'font': {'size': 35, 'weight': 'bold'}},
        gauge={
            'axis': {'range': [0, 125], 'visible': False},
            'bar':  {'color': '#F59E0B', 'thickness': 0.3},
            'bgcolor': '#1E2940', 'borderwidth': 2, 'bordercolor': '#92400E',
            'threshold': {'line': {'color': '#FCD34D', 'width': 4},
                          'thickness': 0.8, 'value': 100}
        },
        title={'text': f"COBERTURA DN (Meta:{int(md)})", 'font': {'size': 15, 'color': '#F59E0B'}},
        domain={'x': [0.55, 0.95], 'y': [0.72, 0.88]}))

    fig.add_trace(go.Indicator(
        mode="number", value=proy,
        number={'prefix': "$",
                'font': {'size': 55,
                         'color': '#10B981' if proy >= mv else '#EF4444',
                         'weight': 'bold'}},
        title={'text': "📈 PROYECCIÓN ESTIMADA AL CIERRE",
               'font': {'size': 18, 'color': '#94A3B8'}},
        domain={'x': [0, 1], 'y': [0.63, 0.70]}))

    d_marca = (df_v.groupby('Marca')['Total'].sum()
               .reset_index().sort_values('Total', ascending=False).head(8))
    fig.add_annotation(text="<b>🥧 MIX DE MARCAS</b>", x=0.5, y=0.61,
                       xref="paper", yref="paper", showarrow=False,
                       font=dict(size=20, color="#3B82F6"))
    fig.add_trace(go.Pie(
        labels=d_marca['Marca'], values=d_marca['Total'], hole=0.5,
        texttemplate="<b>%{label}</b><br>%{percent}", textposition='outside',
        marker=dict(colors=px.colors.qualitative.Bold,
                    line=dict(color='#0A0F1E', width=2)),
        domain={'x': [0.1, 0.9], 'y': [0.38, 0.58]}))

    d_prov = (df_v.groupby('Proveedor')['Total'].sum()
              .reset_index().sort_values('Total', ascending=True).tail(8))
    fig.add_annotation(text="<b>📊 TOP PROVEEDORES</b>", x=0.5, y=0.36,
                       xref="paper", yref="paper", showarrow=False,
                       font=dict(size=20, color="#3B82F6"))
    fig.add_trace(go.Bar(
        x=d_prov['Total'], y=d_prov['Proveedor'], orientation='h',
        marker_color='#1E40AF',
        text=d_prov['Total'].apply(lambda x: f"<b>${x:,.0f}</b>"),
        textposition='outside', xaxis='x', yaxis='y'))

    d_cli = (df_v.groupby('Cliente')['Total'].sum()
             .reset_index().sort_values('Total', ascending=False)
             .query("Total > 0.01").head(20))
    fig.add_trace(go.Table(
        header=dict(
            values=["<b>CLIENTE TOP 20</b>", "<b>COMPRA TOTAL</b>"],
            fill_color='#1E3A8A', font=dict(color='white', size=16), height=45),
        cells=dict(
            values=[d_cli['Cliente'].str.slice(0, 45),
                    d_cli['Total'].apply(lambda x: f"<b>${x:,.2f}</b>")],
            fill_color=['#111827', '#0F172A'],
            font=dict(color='#E2E8F0', size=14), height=35),
        domain={'x': [0, 1], 'y': [0, 0.18]}))

    fig.update_layout(
        height=2600, width=1200,
        paper_bgcolor='#0A0F1E', plot_bgcolor='#0A0F1E',
        font=dict(color='#E2E8F0'),
        title={
            'text': (f"<b>SCORECARD: {nombre_rep}</b><br>"
                     f"<span style='color:#64748B;font-size:0.8em'>{mes}</span>"),
            'y': 0.99, 'x': 0.5, 'xanchor': 'center',
            'font': dict(color='#F8FAFC', size=26)
        },
        margin=dict(t=160, b=60, l=100, r=100),
        xaxis=dict(domain=[0.1, 0.95], visible=False),
        yaxis=dict(domain=[0.22, 0.35], showline=False),
    )
    return fig


# ══════════════════════════════════════════════════════════════════
#  KPI CARD
# ══════════════════════════════════════════════════════════════════
def kpi_card(col, valor, label, sub="", accent="#3B82F6", prefix="$", suffix=""):
    val_fmt = (f"{prefix}{valor:,.0f}{suffix}"
               if isinstance(valor, (int, float)) else str(valor))
    col.markdown(
        f"<div class='kpi-card' style='--accent:{accent};'>"
        f"<div class='kpi-val'>{val_fmt}</div>"
        f"<div class='kpi-lbl'>{label}</div>"
        f"{'<div class=kpi-sub>' + sub + '</div>' if sub else ''}"
        f"</div>",
        unsafe_allow_html=True
    )


# ══════════════════════════════════════════════════════════════════
#  DASHBOARD PRINCIPAL
# ══════════════════════════════════════════════════════════════════
def dashboard(df_v_all, df_p, usuario_row):
    user_nombre = st.session_state['user_nombre']
    user_rol    = st.session_state['user_rol']
    user_zona   = st.session_state['user_zona']
    user_codigo = st.session_state['user_codigo']
    
    # Sistema de permisos
    is_super_admin = es_super_admin(user_codigo, user_nombre)
    is_admin = tiene_permisos_admin(user_rol)

    # ── Top bar ──────────────────────────────────────────────────
    if is_super_admin:
        admin_badge = "<span class='admin-badge'>SUPER ADMIN</span>"
    elif is_admin:
        admin_badge = "<span class='admin-badge'>Admin</span>"
    else:
        admin_badge = ""
        
    cod_lbl = (f"<span style='color:#475569;font-size:0.7rem;margin-left:8px;'>"
               f"[{user_codigo}]</span>") if user_codigo else ""
    st.markdown(
        f"<div class='top-bar'>"
        f"<div><span class='top-bar-title'>💎 PDV Sin Límites</span>{admin_badge}</div>"
        f"<div><div class='top-bar-user'>👤 {user_nombre}{cod_lbl}</div>"
        f"<div class='top-bar-badge'>{user_zona or 'SIN ZONA'}</div></div>"
        f"</div>",
        unsafe_allow_html=True
    )

    # ── Filtros y Controles Principales ──────────────────────────
    df_v_all['Mes_N'] = df_v_all['Fecha'].dt.strftime('%B %Y')
    meses = sorted(df_v_all['Mes_N'].unique().tolist(), reverse=True)
    
    # Crear columnas para controles
    col_mes, col_telegram, col_destino, col_logout = st.columns([3, 2, 2, 1])
    
    with col_mes:
        m_sel = st.selectbox("📅 Selecciona el período:", meses, key="mes_sel")
    
    with col_telegram:
        telegram_activo = st.checkbox("📱 Envío Telegram", key="telegram_on")
    
    with col_destino:
        if telegram_activo:
            chat_destino = st.selectbox(
                "👥 Destinatario:",
                ["gerencia", "administracion", "vendedores"],
                key="telegram_chat"
            )
        else:
            chat_destino = None
            st.selectbox("👥 Destinatario:", ["(Telegram desactivado)"], disabled=True)
    
    with col_logout:
        if st.button("🚪 Salir", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
    
    st.markdown("---")

    # ── Sidebar (simplificado para info del usuario) ──────────────
    with st.sidebar:
        st.markdown(
            f"<div style='color:#60A5FA;font-weight:700;padding:8px 0;'>"
            f"👤 {user_nombre}</div>",
            unsafe_allow_html=True
        )
        st.markdown(
            f"<div style='color:#64748B;font-size:0.75rem;margin-bottom:12px;'>"
            f"Código: {user_codigo or '—'} · {user_zona or '—'}</div>",
            unsafe_allow_html=True
        )
        
        # Mostrar estado de Telegram
        if telegram_activo:
            st.success(f"📱 Telegram ON → {chat_destino}")
        else:
            st.info("📱 Telegram OFF")
        
        # Botón de prueba rápida
        if telegram_activo and st.button("🧪 Prueba rápida", use_container_width=True):
            chat_id = TELEGRAM_CONFIG['CHAT_IDS'][chat_destino]
            mensaje = f"🧪 Prueba desde {user_nombre}\n📅 {datetime.now().strftime('%H:%M')}"
            
            with st.spinner("Enviando prueba..."):
                if enviar_telegram(mensaje, chat_id):
                    st.success("✅ Mensaje enviado!")
                else:
                    st.error("❌ Error")

    m_sel  = st.session_state.get('mes_sel', meses[0] if meses else '')
    df_mes = df_v_all[df_v_all['Mes_N'] == m_sel].copy()

    # ── Selección vendedor ────────────────────────────────────────
    if is_super_admin:
        # Solo Israel puede ver todos los vendedores individuales + GLOBAL
        vends_raw = sorted(df_mes['Vendedor'].dropna().unique().tolist())
        v_admin = st.selectbox("👤 Vendedor a analizar",
                              ["GLOBAL"] + vends_raw, key="vend_admin")

        if v_admin == "GLOBAL":
            df_final, metodo, tipo = df_mes.copy(), "Vista GLOBAL — todos los vendedores", "ok"
            mv = df_p['M_V'].sum()
            md = df_p['M_DN'].sum()
            nombre_rep = "GLOBAL"
        else:
            cod_v, nom_v = descomponer_vendedor(v_admin)
            u_tmp = pd.Series({'_codigo_pdv': cod_v, '_nombre_norm': nom_v})
            df_final, metodo, tipo = filtrar_ventas_usuario(df_mes, u_tmp)
            pres = filtrar_presupuesto_usuario(df_p, u_tmp)
            mv = float(pres['M_V']) if pres is not None else 0
            md = float(pres['M_DN']) if pres is not None else 0
            nombre_rep = v_admin
            
    elif is_admin:
        # Admins normales solo pueden ver GLOBAL o su propio reporte
        st.info("🔒 Como administrador, solo puedes ver vista GLOBAL o tu reporte personal")
        admin_options = ["GLOBAL", f"Mi reporte ({user_nombre})"]
        v_admin = st.selectbox("👤 Vista disponible:", admin_options, key="vend_admin")
        
        if v_admin == "GLOBAL":
            df_final, metodo, tipo = df_mes.copy(), "Vista GLOBAL — todos los vendedores", "ok"
            mv = df_p['M_V'].sum()
            md = df_p['M_DN'].sum()
            nombre_rep = "GLOBAL"
        else:
            u_row = pd.Series(usuario_row)
            df_final, metodo, tipo = filtrar_ventas_usuario(df_mes, u_row)
            pres = filtrar_presupuesto_usuario(df_p, u_row)
            mv = float(pres['M_V']) if pres is not None else 0
            md = float(pres['M_DN']) if pres is not None else 0
            nombre_rep = user_nombre
    else:
        # Vendedores normales solo ven su propio reporte
        u_row = pd.Series(usuario_row)
        df_final, metodo, tipo = filtrar_ventas_usuario(df_mes, u_row)
        pres = filtrar_presupuesto_usuario(df_p, u_row)
        mv = float(pres['M_V']) if pres is not None else 0
        md = float(pres['M_DN']) if pres is not None else 0
        nombre_rep = user_nombre

    # Banner cruce
    cls = 'cruce-ok' if tipo == 'ok' else 'cruce-err'
    st.markdown(f"<div class='{cls}'>{metodo}</div>", unsafe_allow_html=True)

    if df_final.empty:
        st.warning("⚠️ Sin ventas para este periodo.")
        if not is_admin:
            st.info(
                f"Verifica que la columna **codigo** en Usuario_Roles tenga "
                f"**{user_codigo or 'PDVxx'}**, que debe coincidir con el prefijo "
                f"del campo Vendedor en VENTAS (formato: `PDV09 - NOMBRE`)."
            )
        return

    # ── KPIs ─────────────────────────────────────────────────────
    venta_real = df_final['Total'].sum()
    impactos   = df_final[df_final['Total'] > 0]['Cliente'].nunique()
    fecha_max  = df_final['Fecha'].max()
    proy       = calcular_proyeccion(venta_real, fecha_max)
    pct_v      = round(venta_real / mv * 100, 1) if mv > 0 else 0
    pct_dn     = round(impactos   / md * 100, 1) if md > 0 else 0

    st.markdown(f"<div class='section-title'>📊 {m_sel} — {nombre_rep}</div>",
                unsafe_allow_html=True)

    k1, k2, k3, k4, k5 = st.columns(5)
    kpi_card(k1, venta_real, "Venta Neta",
             f"Meta ${mv:,.0f}", "#3B82F6")
    kpi_card(k2, pct_v, "% Avance Meta",
             f"${venta_real:,.0f}",
             "#10B981" if pct_v >= 100 else "#F59E0B", prefix="", suffix="%")
    kpi_card(k3, impactos, "Clientes DN",
             f"Meta {int(md)}", "#F59E0B", prefix="")
    kpi_card(k4, pct_dn, "% Cobertura DN",
             f"{impactos} visitados",
             "#A855F7" if pct_dn >= 100 else "#60A5FA", prefix="", suffix="%")
    kpi_card(k5, proy, "Proyección Cierre",
             "✅ ON TRACK" if proy >= mv else "⚠️ Riesgo",
             "#10B981" if proy >= mv else "#EF4444")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabs ─────────────────────────────────────────────────────
    if is_super_admin:
        tab1, tab2, tab3, tab4 = st.tabs([
            "📈 Scorecard", "📊 Detalle", "🚀 Envío Masivo", "🛡️ Auditoría"])
        tab3_enabled = True
        tab4_enabled = True
    elif is_admin:
        tab1, tab2 = st.tabs(["📈 Scorecard", "📊 Detalle"])
        tab3 = tab4 = None
        tab3_enabled = False
        tab4_enabled = False
    else:
        tab1, tab2 = st.tabs(["📈 Mi Scorecard", "📊 Mi Detalle"])
        tab3 = tab4 = None
        tab3_enabled = False
        tab4_enabled = False

    # ── Tab 1: Scorecard ──────────────────────────────────────────
    with tab1:
        with st.spinner("Generando scorecard..."):
            fig = generar_scorecard(df_final, mv, md, nombre_rep, m_sel)
            st.plotly_chart(fig, use_container_width=True)
            
            # Botones de descarga y envío
            col_png, col_telegram = st.columns(2)
            
            with col_png:
                # 🔧 FIX: Usar try-catch para PNG, fallback a HTML
                try:
                    img = pio.to_image(fig, format="png", scale=2.0)
                    st.download_button(
                        f"📥 Descargar PNG — {nombre_rep}", img,
                        f"Scorecard_{nombre_rep.replace(' ', '_')}_{m_sel}.png",
                        "image/png", use_container_width=True
                    )
                except Exception as e:
                    # Fallback: Descargar como HTML interactivo
                    html_string = pio.to_html(fig, include_plotlyjs='cdn')
                    st.download_button(
                        f"📥 Descargar HTML — {nombre_rep}", html_string.encode(),
                        f"Scorecard_{nombre_rep.replace(' ', '_')}_{m_sel}.html",
                        "text/html", use_container_width=True
                    )
                    st.info("💡 PNG no disponible en web, descarga como HTML interactivo")
            
            with col_telegram:
                if st.button(f"📱 Enviar por Telegram", use_container_width=True, 
                           key="telegram_scorecard"):
                    if telegram_activo and chat_destino:
                        # Generar reporte de texto
                        mensaje = generar_reporte_telegram(
                            df_final, mv, md, nombre_rep, m_sel, 
                            venta_real, impactos, proy
                        )
                        
                        chat_id = TELEGRAM_CONFIG['CHAT_IDS'][chat_destino]
                        
                        with st.spinner("📱 Enviando a Telegram..."):
                            # 🔧 FIX: Solo texto por limitaciones de Streamlit Cloud
                            try:
                                # Intentar con imagen
                                img = pio.to_image(fig, format="png", scale=2.0)
                                img_bytes = io.BytesIO(img)
                                img_bytes.seek(0)
                                
                                if enviar_telegram(mensaje, chat_id, img_bytes):
                                    st.success(f"✅ Enviado con imagen a Telegram ({chat_destino})")
                                else:
                                    st.error("❌ Error enviando a Telegram")
                            except:
                                # Fallback: Solo texto
                                if enviar_telegram(mensaje, chat_id):
                                    st.success(f"✅ Enviado (solo texto) a Telegram ({chat_destino})")
                                    st.info("📝 Imagen no disponible en versión web")
                                else:
                                    st.error("❌ Error enviando a Telegram")
                    else:
                        st.warning("⚠️ Activa Telegram en los controles superiores")

    # ── Tab 2: Detalle ────────────────────────────────────────────
    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("<div class='section-title'>🥧 Mix Marcas</div>",
                        unsafe_allow_html=True)
            d_m = (df_final.groupby('Marca')['Total'].sum()
                   .reset_index().sort_values('Total', ascending=False).head(8))
            if not d_m.empty:
                fig_p = px.pie(d_m, names='Marca', values='Total', hole=0.45,
                               color_discrete_sequence=px.colors.qualitative.Bold)
                fig_p.update_layout(
                    paper_bgcolor='#111827',
                    plot_bgcolor='#111827',
                    font_color='#E2E8F0',
                    margin=dict(t=20, b=20, l=20, r=20),
                    legend=dict(font=dict(color='#E2E8F0')),
                )
                fig_p.update_traces(
                    textfont=dict(color='#FFFFFF', size=12),
                )
                st.plotly_chart(fig_p, use_container_width=True)

        with c2:
            st.markdown("<div class='section-title'>🏆 Top Clientes</div>",
                        unsafe_allow_html=True)
            d_c = (df_final.groupby('Cliente')['Total'].sum()
                   .reset_index().sort_values('Total', ascending=False).head(10))
            if not d_c.empty:
                fig_b = px.bar(d_c, x='Total', y='Cliente', orientation='h',
                               color='Total', color_continuous_scale='Blues',
                               text=d_c['Total'].apply(lambda x: f"${x:,.0f}"))
                fig_b.update_layout(
                    paper_bgcolor='#111827',
                    plot_bgcolor='#111827',
                    font_color='#E2E8F0',
                    showlegend=False,
                    coloraxis_showscale=False,
                    margin=dict(t=20, b=20, l=20, r=20),
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                              color='#E2E8F0'),
                    yaxis=dict(showgrid=False, color='#E2E8F0',
                              tickfont=dict(color='#E2E8F0', size=11))
                )
                fig_b.update_traces(
                    textposition='outside',
                    textfont=dict(color='#E2E8F0', size=12),
                    marker_line_width=0
                )
                st.plotly_chart(fig_b, use_container_width=True)

        cols_show = [c for c in ['Fecha', 'Cliente', 'Marca', 'Proveedor',
                                  'Total', '_codigo_pdv'] if c in df_final.columns]
        st.dataframe(
            df_final[cols_show].sort_values('Fecha', ascending=False),
            use_container_width=True, hide_index=True, height=320
        )

    # ── Tab 3: Envío Masivo (Solo para Israel) ───────────────────
    if tab3_enabled and tab3:
        with tab3:
            if not is_super_admin:
                st.error("🔒 Esta función es exclusiva del Super Administrador")
                st.info("Solo Israel puede realizar envíos masivos por seguridad del sistema")
                return
            
            st.markdown("### 🚀 ENVÍO MASIVO DE REPORTES - SOLO ISRAEL")
            
            vends_all = sorted(df_mes['Vendedor'].dropna().unique().tolist())
            
            col_info, col_config = st.columns([2, 1])
            
            with col_info:
                st.info(f"📊 {len(vends_all)} vendedores encontrados en {m_sel}")
                st.markdown("**¿Qué va a enviar?**")
                st.markdown("✅ Scorecard individual de cada vendedor (imagen + reporte)")
                st.markdown("✅ Mensaje inicial con resumen consolidado")
                st.markdown("✅ Mensaje final con estadísticas de envío")
            
            with col_config:
                if not telegram_activo:
                    st.error("📱 Activa Telegram arriba primero")
                else:
                    st.success(f"📱 Enviará a: {chat_destino}")
            
            st.markdown("---")
            
            if telegram_activo:
                # Botón principal de envío masivo
                if st.button("🚀📱 ENVIAR TODOS LOS REPORTES (UNO POR UNO)", 
                           use_container_width=True, 
                           type="primary",
                           key="enviar_todos_masivo"):
                    
                    if not st.session_state.get('confirmacion_masiva', False):
                        st.session_state.confirmacion_masiva = True
                        st.rerun()
                    
                    st.markdown("### 📤 ENVIANDO REPORTES MASIVOS...")
                    
                    progress_bar = st.progress(0, text="🚀 Iniciando envío masivo...")
                    chat_id = TELEGRAM_CONFIG['CHAT_IDS'][chat_destino]
                    enviados = 0
                    errores = 0
                    
                    # Mensaje inicial
                    total_venta = df_mes['Total'].sum()
                    total_meta = df_p['M_V'].sum()
                    pct_total = round(total_venta / total_meta * 100, 1) if total_meta > 0 else 0
                    
                    mensaje_inicial = f"""
🚀 <b>ENVÍO MASIVO DE REPORTES INICIADO</b>
👤 <b>Solicitado por:</b> {user_nombre}
📅 <b>Período:</b> {m_sel}
📊 <b>Total vendedores:</b> {len(vends_all)}

💰 <b>RESUMEN CONSOLIDADO:</b>
├ Venta Total: <b>${total_venta:,.0f}</b>
├ Meta Total: <b>${total_meta:,.0f}</b>
├ Cumplimiento Global: <b>{pct_total}%</b>
└ Clientes DN Total: <b>{df_mes[df_mes['Total'] > 0]['Cliente'].nunique()}</b>

⏳ <b>Enviando reportes individuales...</b>
💎 <i>Sistema PDV Sin Límites</i>
"""
                    enviar_telegram(mensaje_inicial, chat_id)
                    
                    # Enviar cada reporte individual
                    for i, v in enumerate(vends_all):
                        progress_bar.progress((i + 1) / len(vends_all), 
                                            text=f"📊 Enviando: {v[:40]}...")
                        
                        cod_v, nom_v = descomponer_vendedor(v)
                        u_tmp = pd.Series({'_codigo_pdv': cod_v, '_nombre_norm': nom_v})
                        dv, _, _ = filtrar_ventas_usuario(df_mes, u_tmp)
                        pr = filtrar_presupuesto_usuario(df_p, u_tmp)
                        mv_i = float(pr['M_V']) if pr is not None else 0
                        md_i = float(pr['M_DN']) if pr is not None else 0
                        
                        if not dv.empty:
                            try:
                                # Generar reporte de texto
                                venta_real = dv['Total'].sum()
                                impactos = dv[dv['Total'] > 0]['Cliente'].nunique()
                                fecha_max_vend = dv['Fecha'].max()
                                proy = calcular_proyeccion(venta_real, fecha_max_vend)
                                
                                mensaje_individual = generar_reporte_telegram(
                                    dv, mv_i, md_i, v, m_sel, venta_real, impactos, proy
                                )
                                
                                # 🔧 FIX: Intentar con imagen, fallback a solo texto
                                try:
                                    # Generar scorecard e imagen
                                    fig = generar_scorecard(dv, mv_i, md_i, v, m_sel)
                                    img_bytes = io.BytesIO(pio.to_image(fig, format="png", scale=2.0))
                                    img_bytes.seek(0)
                                    
                                    # Enviar con imagen
                                    if enviar_telegram(mensaje_individual, chat_id, img_bytes):
                                        enviados += 1
                                        st.success(f"✅ {v}")
                                    else:
                                        errores += 1
                                        st.error(f"❌ {v}")
                                except:
                                    # Fallback: Solo texto
                                    if enviar_telegram(mensaje_individual, chat_id):
                                        enviados += 1
                                        st.success(f"✅ {v} (solo texto)")
                                    else:
                                        errores += 1
                                        st.error(f"❌ {v}")
                                    
                            except Exception as e:
                                errores += 1
                                st.error(f"❌ Error con {v}: {str(e)}")
                        else:
                            st.warning(f"⚠️ Sin datos: {v}")
                    
                    # Mensaje final
                    mensaje_final = f"""
✅ <b>ENVÍO MASIVO COMPLETADO</b>

📊 <b>ESTADÍSTICAS DEL ENVÍO:</b>
├ ✅ Reportes enviados: <b>{enviados}</b>
├ ❌ Errores: <b>{errores}</b>
├ 📊 Total procesados: <b>{len(vends_all)}</b>
└ 📅 Período: <b>{m_sel}</b>

⏰ <b>Completado:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
👤 <b>Enviado por:</b> {user_nombre}

💎 <i>Sistema PDV Sin Límites</i>
"""
                    enviar_telegram(mensaje_final, chat_id)
                    
                    progress_bar.progress(1.0, text="🎉 ¡ENVÍO MASIVO COMPLETADO!")
                    st.balloons()
                    st.success(f"🎉 Proceso completado: {enviados} reportes enviados exitosamente")
                    
                    if errores > 0:
                        st.warning(f"⚠️ Se presentaron {errores} errores durante el envío")
                    
                    # Reset confirmación
                    st.session_state.confirmacion_masiva = False
                
                # Confirmación de seguridad
                if st.session_state.get('confirmacion_masiva', False):
                    st.warning("⚠️ **¿ESTÁS SEGURO?** Esto enviará reportes de TODOS los vendedores")
                    col_si, col_no = st.columns(2)
                    with col_si:
                        if st.button("✅ SÍ, ENVIAR TODO", use_container_width=True):
                            st.rerun()
                    with col_no:
                        if st.button("❌ CANCELAR", use_container_width=True):
                            st.session_state.confirmacion_masiva = False
                            st.rerun()
                            
                # Botón de envío individual (global)
                st.markdown("---")
                st.markdown("### 📊 ENVÍO INDIVIDUAL - REPORTE GLOBAL")
                if st.button("📱 Enviar Solo Reporte Consolidado", use_container_width=True):
                    # Generar y enviar reporte global
                    fig_global = generar_scorecard(df_mes, df_p['M_V'].sum(), df_p['M_DN'].sum(), "GLOBAL", m_sel)
                    img_bytes_global = io.BytesIO(pio.to_image(fig_global, format="png", scale=2.0))
                    img_bytes_global.seek(0)
                    
                    total_venta_glob = df_mes['Total'].sum()
                    total_impactos = df_mes[df_mes['Total'] > 0]['Cliente'].nunique()
                    fecha_max_glob = df_mes['Fecha'].max()
                    proy_global = calcular_proyeccion(total_venta_glob, fecha_max_glob)
                    
                    mensaje_global = generar_reporte_telegram(
                        df_mes, df_p['M_V'].sum(), df_p['M_DN'].sum(), 
                        "CONSOLIDADO GLOBAL", m_sel, total_venta_glob, total_impactos, proy_global
                    )
                    
                    with st.spinner("📱 Enviando reporte global..."):
                        if enviar_telegram(mensaje_global, chat_id, img_bytes_global):
                            st.success("✅ Reporte global enviado exitosamente")
                        else:
                            st.error("❌ Error enviando reporte global")
            else:
                st.error("📱 Debes activar Telegram en los controles superiores")
                st.info("👆 Ve arriba y activa '📱 Envío Telegram'")
                
    # ── Tab 4: Auditoría (Solo para Israel) ──────────────────────
    if tab4_enabled and tab4:
        with tab4:
            _, _, audit = cargar_ventas_presupuesto()

            # Columnas detectadas
            st.markdown("#### 🔬 Columnas detectadas en VENTAS")
            st.code(str(st.session_state.get('_cols_ventas', [])))

            # Integridad de fechas
            st.markdown("#### 🛡️ Integridad de Datos")
            if audit.get('monto_perdido', 0) > 0:
                st.error(
                    f"⚠️ ${audit['monto_perdido']:,.2f} fuera del reporte "
                    f"({audit['filas_afectadas']} filas sin fecha válida)"
                )
                det = audit['detalle_errores']
                cols_det = [c for c in ['Vendedor', 'Total', 'Fecha']
                            if c in det.columns]
                if cols_det:
                    st.dataframe(det[cols_det],
                                 use_container_width=True, hide_index=True)
            else:
                st.success("✅ Fechas 100% íntegras.")

            # Diagnóstico de parsing
            st.markdown("#### 🔬 Diagnóstico parsing — campo Vendedor")
            st.caption("Cómo se interpreta cada valor único del campo Vendedor en VENTAS.")
            muestra = df_mes['Vendedor'].dropna().unique()[:40]
            diag = []
            for v in muestra:
                cod, nom = descomponer_vendedor(v)
                diag.append({
                    'Vendedor original': v,
                    'Código extraído':   cod,
                    'Nombre extraído':   nom,
                })
            st.dataframe(pd.DataFrame(diag),
                         use_container_width=True, hide_index=True)

            # Mapa de cruce
            st.markdown("#### 🔗 Mapa de Cruce — Usuario_Roles ↔ VENTAS ↔ PRESUPUESTO")
            st.caption(
                "Verifica que todos los usuarios tengan Ventas # > 0 y Pres. ✅. "
                "Si no, revisa la columna **codigo** en Usuario_Roles."
            )
            df_users = cargar_usuarios()
            filas = []
            for _, u in df_users.iterrows():
                dv_u, met, _ = filtrar_ventas_usuario(df_mes, u)
                pr_u = filtrar_presupuesto_usuario(df_p, u)
                filas.append({
                    'Usuario':    str(u.get('_nombre_orig', '')),
                    'Código PDV': str(u['_codigo_pdv']),
                    'Ventas #':   len(dv_u),
                    'Total $':    (f"${dv_u['Total'].sum():,.0f}"
                                   if not dv_u.empty else "—"),
                    'Pres. ✓':   "✅" if pr_u is not None else "❌",
                    'Método':     met,
                })
            st.dataframe(pd.DataFrame(filas),
                         use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════
def main():
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        pantalla_login()
        return

    try:
        df_v, df_p, _ = cargar_ventas_presupuesto()
    except ValueError as e:
        st.error(str(e))
        st.stop()

    if df_v.empty:
        st.error("❌ Sin datos de ventas en la hoja VENTAS.")
        return

    dashboard(df_v, df_p, st.session_state.get('user_row', {}))


if __name__ == "__main__":
    main()
