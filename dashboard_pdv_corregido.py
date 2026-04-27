"""
Módulo: Presupuesto vs Cumplimiento — Solo Super Admin
Sheets "soluto":
  - PRESUPUESTO  → VENDEDOR | # OBJETIVO DN | # PRESUPUESTO | zona
  - VENTAS_NETAS → Vendedor | SubT RL. | # Cli.
  - VENTAS       → Vendedor | Cliente | Fecha | Marca | Grupo ...
Join por código PDV (PDV01, PDV02 …) — robusto ante diferencias de formato.

MEJORAS v2.0:
✅ Gráfico dual treemap: Ventas vs DN en el mismo panel
✅ Mismo color en ambos treemaps para comparación visual
✅ Cuenta clientes únicos por marca
✅ Top 10 marcas (antes era 8)
✅ Mejor hover con información detallada
"""

import re
import os
import calendar
import requests
import gspread
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from pathlib import Path

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
BASE_DIR         = Path(__file__).parent
CREDS_PATH       = BASE_DIR / 'credenciales.json'
TELEGRAM_TOKEN   = st.secrets.get('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = st.secrets.get('TELEGRAM_CHAT_ID', '')

ZONA_COLOR = {'ORIENTE': '#FF6B35', 'SIERRA': '#1E88E5'}


# ─── HELPERS ──────────────────────────────────────────────────────────────────

@st.cache_resource
def _gc():
    """Conectar a Google Sheets con manejo robusto de errores"""
    try:
        # Intentar con Secrets primero (Streamlit Cloud)
        try:
            if len(st.secrets) > 0 and "type" in st.secrets:
                st.write('📍 Usando Secrets de Streamlit Cloud')
                creds_dict = {key: st.secrets[key] for key in st.secrets}
                return gspread.service_account(info=creds_dict)
        except Exception as secrets_err:
            st.write(f'ℹ️ Secrets no disponibles: {secrets_err}')

        # Si no, intentar con archivo local
        if CREDS_PATH.exists():
            st.write('📍 Usando credenciales.json local')
            return gspread.service_account(filename=str(CREDS_PATH))

        # Si nada funcionó
        st.error('❌ NO SE ENCONTRÓ CREDENCIALES:')
        st.write('  - No hay credenciales.json en el directorio')
        st.write('  - No hay Secrets configurados en Streamlit Cloud')
        return None
    except Exception as e:
        st.error(f'❌ Error autenticando con Google: {e}')
        return None


def _extraer_pdv(texto: str) -> str:
    """Extrae el código PDV## de cualquier cadena. Ej: 'PDV03 - GUAMAN...' → 'PDV03'"""
    m = re.search(r'PDV\d+', str(texto).upper())
    return m.group(0) if m else ''


def _normalizar_nombre(texto: str) -> str:
    """Nombre sin código PDV, limpio."""
    s = str(texto).strip()
    if ' - ' in s:
        partes = s.split(' - ', 1)
        return partes[1].strip()
    return s


def pct_mes() -> float:
    hoy = datetime.now()
    return hoy.day / calendar.monthrange(hoy.year, hoy.month)[1]


def cump(real: float, meta: float) -> float:
    return round(real / meta * 100, 1) if meta > 0 else 0.0


def color_c(pct: float) -> str:
    return '#4CAF50' if pct >= 100 else '#FF9800' if pct >= 80 else '#F44336'


def emoji_c(pct: float) -> str:
    return '🟢' if pct >= 100 else '🟡' if pct >= 80 else '🔴'


# ─── CARGA DE DATOS ───────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def cargar_presupuesto() -> pd.DataFrame:
    """
    Hoja PRESUPUESTO → VENDEDOR | # OBJETIVO DN | # PRESUPUESTO | zona
    """
    gc = _gc()
    if gc is None:
        st.error('❌ No se pudo conectar a Google Sheets')
        return pd.DataFrame()

    try:
        ws = gc.open('soluto').worksheet('PRESUPUESTO')
    except Exception as e:
        st.error(f'❌ Error abriendo hoja PRESUPUESTO: {e}')
        st.write('Verifica que:')
        st.write('  1. El Google Sheet se llama "soluto"')
        st.write('  2. Existe una hoja llamada "PRESUPUESTO"')
        st.write('  3. El SERVICE ACCOUNT tiene acceso al sheet')
        return pd.DataFrame()

    raw = ws.get_all_values()
    if not raw:
        return pd.DataFrame()

    headers = [str(h).strip() for h in raw[0]]
    df = pd.DataFrame(raw[1:], columns=headers)
    df = df[df[headers[0]].astype(str).str.strip() != '']

    def _find(keywords):
        for c in df.columns:
            cu = c.upper().replace('#', '').strip()
            if all(k in cu for k in keywords):
                return c
        return None

    col_vend = _find(['VENDEDOR'])
    col_dn   = _find(['OBJETIVO']) or _find(['DN'])
    col_pres = _find(['PRESUPUESTO'])
    col_zona = _find(['ZONA'])

    if not col_vend:
        st.error(f"No se encontró columna VENDEDOR. Columnas: {list(df.columns)}")
        return pd.DataFrame()

    rename = {col_vend: 'VENDEDOR'}
    if col_dn:   rename[col_dn]   = 'META_DN'
    if col_pres: rename[col_pres] = 'META_V'
    if col_zona: rename[col_zona] = 'ZONA'
    df = df.rename(columns=rename)

    def _solo_digitos(val):
        if isinstance(val, (int, float)):
            return float(int(val))
        s = str(val).strip()
        s = re.sub(r'[$\s]', '', s)
        s = re.sub(r'[.,]\d{1,2}$', '', s)
        digits = re.sub(r'\D', '', s)
        return float(digits) if digits else 0.0

    for c in ['META_DN', 'META_V']:
        if c in df.columns:
            df[c] = df[c].apply(_solo_digitos)

    if 'ZONA' not in df.columns:
        df['ZONA'] = 'SIERRA'
    df['ZONA']    = df['ZONA'].astype(str).str.upper().str.strip()
    df['VENDEDOR'] = df['VENDEDOR'].astype(str).str.strip()
    df = df[df['VENDEDOR'] != '']

    df['NOMBRE']  = df['VENDEDOR'].apply(_normalizar_nombre)
    df['KEY_PDV'] = df['VENDEDOR'].apply(_extraer_pdv)

    return df.reset_index(drop=True)


@st.cache_data(ttl=300, show_spinner=False)
def cargar_ventas_netas() -> pd.DataFrame:
    """
    Hoja VENTAS_NETAS → Vendedor | SubT RL. | # Cli.
    Solo filas con código PDV válido.
    """
    gc = _gc()
    if gc is None:
        return pd.DataFrame()

    try:
        ws = gc.open('soluto').worksheet('VENTAS_NETAS')
        raw = ws.get_all_values()
    except Exception as e:
        st.error(f'❌ Error abriendo VENTAS_NETAS: {e}')
        return pd.DataFrame()

    if not raw:
        return pd.DataFrame()

    headers = [str(h).strip() for h in raw[0]]
    df = pd.DataFrame(raw[1:], columns=headers)

    def _find(keywords):
        for c in df.columns:
            cu = c.upper()
            if all(k in cu for k in keywords):
                return c
        return None

    col_vend = _find(['VENDEDOR'])
    col_sub  = _find(['SUBT', 'RL']) or _find(['SUBTRL'])
    col_cli  = _find(['CLI'])

    if not col_vend:
        col_vend = headers[0]

    if not col_sub:
        st.error(f"No se encontró columna SubT RL en VENTAS_NETAS. Columnas: {headers}")
        return pd.DataFrame()

    cols = [col_vend, col_sub] + ([col_cli] if col_cli else [])
    df = df[cols].copy()
    df.columns = ['VENDEDOR', 'SubT_RL'] + (['DN_CLI'] if col_cli else [])

    df['SubT_RL'] = pd.to_numeric(df['SubT_RL'], errors='coerce').fillna(0)
    if 'DN_CLI' in df.columns:
        df['DN_CLI'] = pd.to_numeric(df['DN_CLI'], errors='coerce').fillna(0)

    df['VENDEDOR'] = df['VENDEDOR'].astype(str).str.strip()

    df['KEY_PDV'] = df['VENDEDOR'].apply(_extraer_pdv)
    df = df[df['KEY_PDV'] != ''].copy()

    agg = {'SubT_RL': 'sum'}
    if 'DN_CLI' in df.columns:
        agg['DN_CLI'] = 'max'
    df = df.groupby('KEY_PDV', as_index=False).agg(agg)

    return df.reset_index(drop=True)


@st.cache_data(ttl=300, show_spinner=False)
def cargar_ventas_detalle() -> pd.DataFrame:
    """Hoja VENTAS: detalle por transacción para gráfico de marcas."""
    gc = _gc()
    if gc is None:
        return pd.DataFrame()

    try:
        ws = gc.open('soluto').worksheet('VENTAS')
        raw = ws.get_all_values()
    except Exception as e:
        st.error(f'❌ Error abriendo VENTAS: {e}')
        return pd.DataFrame()
    if not raw:
        return pd.DataFrame()

    headers = [str(h).strip() for h in raw[0]]
    df = pd.DataFrame(raw[1:], columns=headers)

    rename = {}
    for c in df.columns:
        cu = c.upper()
        if cu == 'VENDEDOR':                       rename[c] = 'Vendedor'
        elif cu == 'CLIENTE':                      rename[c] = 'Cliente'
        elif cu == 'FECHA':                        rename[c] = 'Fecha'
        elif cu == 'CIUDAD':                       rename[c] = 'Ciudad'
        elif cu == 'MARCA':                        rename[c] = 'Marca'
        elif cu == 'GRUPO':                        rename[c] = 'Grupo'
        elif cu == 'SUBGRUPO':                     rename[c] = 'SubGrupo'
        elif 'TOTAL' in cu and 'FACTURA' in cu:   rename[c] = 'TotalFactura'
    df = df.rename(columns=rename)

    if 'Fecha' in df.columns:
        df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
    if 'TotalFactura' in df.columns:
        df['TotalFactura'] = pd.to_numeric(df['TotalFactura'], errors='coerce').fillna(0)
    if 'Vendedor' in df.columns:
        df['KEY_PDV'] = df['Vendedor'].apply(_extraer_pdv)

    return df


# ─── TABLA MAESTRA ────────────────────────────────────────────────────────────

def construir_tabla(df_pres: pd.DataFrame,
                    df_vn: pd.DataFrame,
                    df_vd: pd.DataFrame) -> pd.DataFrame:
    hoy      = datetime.now()
    dia      = hoy.day
    dias_mes = calendar.monthrange(hoy.year, hoy.month)[1]

    tabla = df_pres.copy()
    tabla = tabla.merge(
        df_vn[['KEY_PDV', 'SubT_RL'] + (['DN_CLI'] if 'DN_CLI' in df_vn.columns else [])],
        on='KEY_PDV', how='left'
    )

    tabla['VENTA_REAL'] = pd.to_numeric(tabla.get('SubT_RL', 0), errors='coerce').fillna(0)
    tabla['DN_REAL']    = pd.to_numeric(tabla.get('DN_CLI',  0), errors='coerce').fillna(0)

    tabla['PROY_V']  = (tabla['VENTA_REAL'] / dia * dias_mes).round(0)
    tabla['PROY_DN'] = (tabla['DN_REAL']    / dia * dias_mes).round(0)

    tabla['CUMP_V']    = tabla.apply(lambda r: cump(r['VENTA_REAL'], r['META_V']),  axis=1)
    tabla['CUMP_DN']   = tabla.apply(lambda r: cump(r['DN_REAL'],    r['META_DN']), axis=1)
    tabla['CUMP_PROY_V']  = tabla.apply(lambda r: cump(r['PROY_V'],  r['META_V']),  axis=1)
    tabla['CUMP_PROY_DN'] = tabla.apply(lambda r: cump(r['PROY_DN'], r['META_DN']), axis=1)

    return tabla.reset_index(drop=True)


# ─── GRÁFICOS ─────────────────────────────────────────────────────────────────

def _dark(fig, height, ml=190, mr=30):
    fig.update_layout(
        height=height, paper_bgcolor='#0d1117', plot_bgcolor='#0d1117',
        font=dict(color='#cbd5e1', size=12), showlegend=True,
        legend=dict(orientation='h', x=0.5, xanchor='center', y=1.07,
                    bgcolor='rgba(0,0,0,0)', font=dict(size=11)),
        margin=dict(t=50, b=30, l=ml, r=mr),
        hovermode='closest',
    )
    return fig


def _base_layout(fig, height, left_margin):
    return _dark(fig, height, ml=left_margin, mr=30)


def estilo_A(df_z: pd.DataFrame, titulo: str,
             col_v: str, col_m: str, col_p: str, col_c: str, es_dinero=True) -> go.Figure:
    fmt  = (lambda v: f'${v:,.0f}') if es_dinero else (lambda v: f'{v:.0f}')
    noms = df_z['NOMBRE'].str[:13].tolist()
    n    = len(noms)
    fig  = go.Figure()

    fig.add_bar(
        name='Real',
        x=noms, y=df_z[col_v],
        marker=dict(color=[color_c(p) for p in df_z[col_c]],
                    opacity=0.9, line=dict(color='rgba(0,0,0,0.2)', width=0.5)),
        text=[f'<b>{p:.0f}%</b>' for p in df_z[col_c]],
        textposition='inside',
        textfont=dict(size=11, color='white'),
        hovertemplate='<b>%{x}</b><br>Real: ' + ('$%{y:,.0f}' if es_dinero else '%{y:.0f}') +
                      '<extra></extra>',
    )

    fig.add_scatter(
        name='Meta',
        x=noms, y=df_z[col_m],
        mode='markers+text',
        marker=dict(symbol='line-ew', size=22, color='#f8fafc',
                    line=dict(color='#f8fafc', width=2.5)),
        text=[fmt(v) for v in df_z[col_m]],
        textposition='top center',
        textfont=dict(size=8.5, color='#94a3b8'),
        hovertemplate='Meta: ' + ('$%{y:,.0f}' if es_dinero else '%{y:.0f}') + '<extra></extra>',
    )

    col_proy = ['#22c55e' if p >= 100 else '#f59e0b' if p >= 80 else '#ef4444'
                for p in df_z[col_c]]
    fig.add_scatter(
        name='Proyección',
        x=noms, y=df_z[col_p],
        mode='markers+text',
        marker=dict(symbol='diamond', size=10, color=col_proy,
                    line=dict(color='white', width=1.2)),
        text=[fmt(v) for v in df_z[col_p]],
        textposition='bottom center',
        textfont=dict(size=8, color='#64748b'),
        hovertemplate='Proy: ' + ('$%{y:,.0f}' if es_dinero else '%{y:.0f}') + '<extra></extra>',
    )

    fig.update_layout(
        barmode='group',
        title=dict(
            text=f'<b>{titulo}</b>',
            font=dict(size=13, color='#f1f5f9'),
            x=0.01, xanchor='left', y=0.99, yanchor='top',
        ),
        legend=dict(
            orientation='h',
            x=1.0, xanchor='right',
            y=1.01, yanchor='bottom',
            bgcolor='rgba(0,0,0,0)',
            font=dict(size=10, color='#94a3b8'),
            itemsizing='constant',
        ),
        xaxis=dict(tickangle=-28, gridcolor='#1a2235', color='#64748b',
                   tickfont=dict(size=9.5), showline=False),
        yaxis=dict(gridcolor='#1a2235', color='#64748b', tickformat=',.0f'),
        bargap=0.28,
        margin=dict(t=45, b=80, l=55, r=40),
    )
    return _dark(fig, max(380, n * 52 + 120), ml=55, mr=40)


def estilo_B(df_z: pd.DataFrame, titulo: str,
             col_v: str, col_m: str, col_p: str, col_c: str, es_dinero=True) -> go.Figure:
    fmt = (lambda v: f'${v:,.0f}') if es_dinero else (lambda v: f'{v:.0f}')
    n   = len(df_z)
    h   = max(340, n * 50 + 90)
    nombres = df_z['NOMBRE'].tolist()
    fig = go.Figure()
    fig.add_bar(
        name='🎯 Meta', y=nombres, x=df_z[col_m], orientation='h',
        marker=dict(color='rgba(255,255,255,0.05)', line=dict(color='#334155', width=1)),
        hovertemplate='Meta: %{x:,.0f}<extra></extra>',
    )
    fig.add_bar(
        name='✅ Real', y=nombres, x=df_z[col_v], orientation='h',
        marker=dict(color=[color_c(p) for p in df_z[col_c]], opacity=0.88),
        text=[f' {fmt(v)}  {p:.0f}%' for v, p in zip(df_z[col_v], df_z[col_c])],
        textposition='inside', textfont=dict(size=10.5, color='white'),
        hovertemplate='Real: %{x:,.0f}<extra></extra>',
    )
    fig.add_scatter(
        name='📈 Proyección', y=nombres, x=df_z[col_p],
        mode='markers+text',
        marker=dict(symbol='diamond', size=12,
                    color=['#22c55e' if v >= m else '#f59e0b' if v >= m*0.8 else '#ef4444'
                           for v, m in zip(df_z[col_p], df_z[col_m])],
                    line=dict(color='white', width=1.5)),
        text=[f'  {fmt(v)}' for v in df_z[col_p]],
        textposition='middle right', textfont=dict(size=9.5, color='#94a3b8'),
    )
    fig.update_layout(
        barmode='overlay',
        title=dict(text=f'<b>{titulo}</b>', font=dict(size=13, color='#f1f5f9'), x=0.5),
        xaxis=dict(gridcolor='#1e2536', color='#94a3b8'),
        yaxis=dict(gridcolor='#0d1117', color='#e2e8f0', autorange='reversed'),
    )
    return _dark(fig, h, ml=max(180, df_z['NOMBRE'].str.len().max()*7), mr=120)


def estilo_C(df_z: pd.DataFrame, titulo: str,
             col_v: str, col_m: str, col_p: str, col_c: str,
             col_cp: str, es_dinero=True):
    fmt = (lambda v: f'${v:,.0f}') if es_dinero else (lambda v: f'{int(v)}')
    df_sorted = df_z.sort_values(col_cp, ascending=False).reset_index(drop=True)

    GRUPOS = [
        ('🚀 En camino',  df_sorted[df_sorted[col_cp] >= 100],
         '#34d399', '#052e16', '#d1fae5'),
        ('⚠️ En riesgo',  df_sorted[(df_sorted[col_cp] >= 80) & (df_sorted[col_cp] < 100)],
         '#fbbf24', '#1c1400', '#fef9c3'),
        ('🔴 Crítico',    df_sorted[df_sorted[col_cp] < 80],
         '#f87171', '#1a0505', '#fee2e2'),
    ]

    st.markdown(
        f'<div style="font-family:\'DM Sans\',sans-serif;font-size:13px;'
        f'font-weight:700;color:#64748b;letter-spacing:0.05em;'
        f'margin:14px 0 8px 0;text-transform:uppercase;">{titulo}</div>',
        unsafe_allow_html=True,
    )

    for label, df_g, acento, bg_card, txt_claro in GRUPOS:
        if df_g.empty:
            continue

        st.markdown(f"""
<div style="display:inline-flex;align-items:center;gap:6px;
            background:{bg_card};border:1px solid {acento}40;
            border-radius:20px;padding:3px 12px 3px 8px;
            margin:10px 0 8px 0;">
  <span style="font-size:11px;color:{acento};font-weight:800;
               font-family:'DM Sans',sans-serif;">{label}</span>
  <span style="font-size:10px;color:{acento}90;font-weight:600;">{len(df_g)}</span>
</div>""", unsafe_allow_html=True)

        cols = st.columns(4)
        for i, (_, row) in enumerate(df_g.iterrows()):
            pct   = row[col_c]
            cproy = row[col_cp]
            real  = row[col_v]
            meta  = row[col_m]
            proy  = row[col_p]
            bw    = min(pct, 100)
            with cols[i % 4]:
                st.markdown(f"""
<div style="background:#0d0f14;border:1px solid #1e2536;border-top:2px solid {acento};
            border-radius:14px;padding:11px 12px 10px;margin-bottom:10px;
            font-family:'DM Sans',sans-serif;transition:border-color .2s;">
  <div style="display:flex;justify-content:space-between;align-items:center;
              margin-bottom:5px;">
    <div style="font-size:9.5px;color:#94a3b8;font-weight:600;
                overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
                max-width:68%;">{row['NOMBRE']}</div>
    <div style="background:{acento}18;color:{acento};font-size:8.5px;
                font-weight:800;padding:1px 6px;border-radius:20px;
                white-space:nowrap;">P {cproy:.0f}%</div>
  </div>
  <div style="font-size:22px;font-weight:900;color:{acento};
              line-height:1.1;margin:2px 0;">{pct:.1f}%</div>
  <div style="font-size:9px;color:#64748b;margin-bottom:6px;">
    <span style="color:#f8fafc;font-weight:700;">{fmt(real)}</span>
    &nbsp;/&nbsp;{fmt(meta)}
  </div>
  <div style="background:#1e2536;border-radius:6px;height:4px;overflow:hidden;">
    <div style="background:{acento};width:{bw:.0f}%;height:4px;border-radius:6px;"></div>
  </div>
  <div style="font-size:8.5px;color:#475569;margin-top:5px;">
    📈 <span style="color:{acento}aa;">{fmt(proy)}</span>
  </div>
</div>""", unsafe_allow_html=True)


def generar_pdf(tabla: pd.DataFrame, mes_lbl: str) -> bytes:
    """Genera PDF con tarjetas de cumplimiento usando matplotlib."""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib.backends.backend_pdf import PdfPages
        import io as _io

        hoy = datetime.now()
        zonas = [z for z in ['SIERRA', 'ORIENTE'] if z in tabla['ZONA'].unique()]
        buf = _io.BytesIO()

        with PdfPages(buf) as pdf:
            for zona in zonas:
                df_z = tabla[tabla['ZONA'] == zona].sort_values('CUMP_PROY_V', ascending=False)
                n = len(df_z)
                cols_pdf = 4
                rows_pdf = -(-n // cols_pdf)

                fig = plt.figure(figsize=(16, 3 + rows_pdf * 2.8), facecolor='#0d1117')
                fig.suptitle(
                    f'PDV Sin Límites — Presupuesto vs Cumplimiento\n{zona}  ·  {mes_lbl}  ·  {hoy.strftime("%d/%m/%Y")}',
                    fontsize=14, fontweight='bold', color='white', y=0.98,
                )

                for idx, (_, row) in enumerate(df_z.iterrows()):
                    ax = fig.add_subplot(rows_pdf, cols_pdf, idx + 1)
                    ax.set_facecolor('#0d1117')
                    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
                    ax.axis('off')

                    pct   = row['CUMP_V']
                    cproy = row['CUMP_PROY_V']
                    real  = row['VENTA_REAL']
                    meta  = row['META_V']
                    proy  = row['PROY_V']

                    if cproy >= 100:
                        c_borde, c_bg = '#22c55e', '#0a2218'
                    elif cproy >= 80:
                        c_borde, c_bg = '#f59e0b', '#231a06'
                    else:
                        c_borde, c_bg = '#ef4444', '#1f0808'

                    rect = mpatches.FancyBboxPatch((0.02, 0.04), 0.96, 0.92,
                        boxstyle='round,pad=0.02', facecolor=c_bg,
                        edgecolor=c_borde, linewidth=1.5)
                    ax.add_patch(rect)

                    bw = min(pct / 100, 1.0) * 0.88
                    ax.add_patch(mpatches.Rectangle((0.06, 0.09), 0.88, 0.06,
                        facecolor='#1e2a3a', edgecolor='none'))
                    ax.add_patch(mpatches.Rectangle((0.06, 0.09), bw, 0.06,
                        facecolor=c_borde, edgecolor='none'))

                    nombre = row['NOMBRE'][:22]
                    ax.text(0.5, 0.94, nombre, ha='center', va='top',
                            fontsize=7, color='#cbd5e1', fontweight='bold',
                            transform=ax.transAxes)
                    ax.text(0.5, 0.76, f'{pct:.1f}%', ha='center', va='center',
                            fontsize=17, color='white', fontweight='black',
                            transform=ax.transAxes)
                    ax.text(0.5, 0.58, f'${real:,.0f} / ${meta:,.0f}', ha='center', va='center',
                            fontsize=6.5, color='#94a3b8', transform=ax.transAxes)
                    ax.text(0.5, 0.26, f'Proy: ${proy:,.0f}  ({cproy:.0f}%)',
                            ha='center', va='center', fontsize=6, color=c_borde,
                            transform=ax.transAxes)

                plt.tight_layout(rect=[0, 0, 1, 0.95])
                pdf.savefig(fig, facecolor='#0d1117', bbox_inches='tight')
                plt.close(fig)

        buf.seek(0)
        return buf.read()
    except Exception as e:
        return b''


def _render_zona_graficos(df_z, zona, estilo):
    """Renderiza ventas + DN con el estilo seleccionado."""
    if estilo == 'A — Barras verticales agrupadas':
        st.plotly_chart(estilo_A(df_z, f'💰 Ventas — {zona}',
            'VENTA_REAL','META_V','PROY_V','CUMP_V', True), use_container_width=True)
        st.plotly_chart(estilo_A(df_z, f'👥 DN — {zona}',
            'DN_REAL','META_DN','PROY_DN','CUMP_DN', False), use_container_width=True)
    elif estilo == 'B — Barras horizontales con $':
        st.plotly_chart(estilo_B(df_z, f'💰 Ventas — {zona}',
            'VENTA_REAL','META_V','PROY_V','CUMP_V', True), use_container_width=True)
        st.plotly_chart(estilo_B(df_z, f'👥 DN — {zona}',
            'DN_REAL','META_DN','PROY_DN','CUMP_DN', False), use_container_width=True)
    else:
        estilo_C(df_z, f'💰 Ventas — {zona}',
                 'VENTA_REAL','META_V','PROY_V','CUMP_V','CUMP_PROY_V', True)
        estilo_C(df_z, f'👥 DN — {zona}',
                 'DN_REAL','META_DN','PROY_DN','CUMP_DN','CUMP_PROY_DN', False)


def _grafico_progreso(df_z: pd.DataFrame, zona: str,
                       col_real: str, col_proy: str, col_meta: str,
                       col_cump: str, col_cump_proy: str,
                       titulo: str, es_dinero: bool = True) -> go.Figure:
    """
    Gráfico de progreso horizontal en PORCENTAJE.
    ─ Barra gris clarita = 100% (meta completa, referencia)
    ─ Barra coloreada    = % alcanzado real
    ─ Diamante           = % proyectado al cierre
    """
    n   = len(df_z)
    h   = max(320, n * 52 + 90)
    l   = max(180, df_z['NOMBRE'].str.len().max() * 7 + 20)

    nombres  = df_z['NOMBRE'].tolist()
    reales_v = df_z[col_real].tolist()
    proy_v   = df_z[col_proy].tolist()
    meta_v   = df_z[col_meta].tolist()
    pct_r    = df_z[col_cump].tolist()
    pct_p    = df_z[col_cump_proy].tolist()

    col_r = [color_c(p) for p in pct_r]
    col_p = ['#22c55e' if p >= 100 else '#f59e0b' if p >= 80 else '#ef4444'
             for p in pct_p]

    fmt = (lambda v: f'${v:,.0f}') if es_dinero else (lambda v: f'{v:.0f}')

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='🎯 Meta (100%)',
        y=nombres, x=[100] * n,
        orientation='h',
        marker=dict(color='rgba(255,255,255,0.06)',
                    line=dict(color='rgba(255,255,255,0.12)', width=1)),
        hovertemplate='<b>%{y}</b><br>Meta: ' +
                      '<br>'.join([f'{fmt(m)}' for m in meta_v]) +
                      '<extra>Meta Mes</extra>',
        showlegend=True,
    ))

    hover_r = [
        f'<b>{nom}</b><br>'
        f'Real: <b>{fmt(rv)}</b>  ({pr:.1f}% de meta)<br>'
        f'Meta mes: {fmt(mv)}'
        for nom, rv, pr, mv in zip(nombres, reales_v, pct_r, meta_v)
    ]
    fig.add_trace(go.Bar(
        name='📊 Avance real',
        y=nombres, x=pct_r,
        orientation='h',
        marker=dict(color=col_r, opacity=0.88,
                    line=dict(color='rgba(0,0,0,0.2)', width=0.5)),
        text=[f'  {fmt(rv)}  ({pr:.1f}%)' for rv, pr in zip(reales_v, pct_r)],
        textposition='inside',
        textfont=dict(size=10.5, color='white', family='monospace'),
        customdata=hover_r,
        hovertemplate='%{customdata}<extra></extra>',
        showlegend=True,
    ))

    hover_p = [
        f'<b>{nom}</b><br>'
        f'Proyección: <b>{fmt(pv)}</b>  ({pp:.1f}%)<br>'
        f'Al ritmo actual de {datetime.now().day} días'
        for nom, pv, pp in zip(nombres, proy_v, pct_p)
    ]
    fig.add_trace(go.Scatter(
        name='📈 Proyección al cierre',
        y=nombres, x=pct_p,
        mode='markers+text',
        marker=dict(symbol='diamond', size=13, color=col_p,
                    line=dict(color='white', width=1.5)),
        text=[f'  {pp:.0f}%' for pp in pct_p],
        textposition='middle right',
        textfont=dict(size=9.5, color='#94a3b8'),
        customdata=hover_p,
        hovertemplate='%{customdata}<extra></extra>',
        showlegend=True,
    ))

    fig.add_vline(x=100, line_color='#ef4444', line_dash='dash',
                  line_width=1.5, opacity=0.7,
                  annotation_text='Meta', annotation_font_color='#ef4444',
                  annotation_position='top')

    fig.update_layout(
        barmode='overlay',
        title=dict(
            text=f'<b>{titulo} — Zona {zona}</b>'
                 f'<span style="font-size:11px;color:#64748b">'
                 f'  ·  Barra = avance real  ◆ = proyección al cierre  | línea roja = 100% meta</span>',
            font=dict(size=13, color='#f1f5f9'), x=0, xanchor='left',
        ),
        xaxis=dict(range=[0, max(130, max(pct_p, default=0) + 15)]),
    )
    return _base_layout(fig, h, l)


def grafico_ventas_zona(df_z: pd.DataFrame, zona: str) -> go.Figure:
    return _grafico_progreso(
        df_z, zona,
        col_real='VENTA_REAL', col_proy='PROY_V', col_meta='META_V',
        col_cump='CUMP_V', col_cump_proy='CUMP_PROY_V',
        titulo='💰 Ventas Netas', es_dinero=True,
    )


def grafico_dn_zona(df_z: pd.DataFrame, zona: str) -> go.Figure:
    return _grafico_progreso(
        df_z, zona,
        col_real='DN_REAL', col_proy='PROY_DN', col_meta='META_DN',
        col_cump='CUMP_DN', col_cump_proy='CUMP_PROY_DN',
        titulo='👥 Impactos DN', es_dinero=False,
    )


def grafico_marcas(df_vd: pd.DataFrame, key_pdv: str, nombre: str) -> go.Figure:
    """Treemap dual: Distribución por Venta vs DN (clientes nuevos) — MEJORADO v2.0"""
    if df_vd.empty or 'Marca' not in df_vd.columns or 'KEY_PDV' not in df_vd.columns:
        return go.Figure()

    hoy = datetime.now()
    df  = df_vd[df_vd['KEY_PDV'] == key_pdv].copy()
    if 'Fecha' in df.columns:
        df = df[(df['Fecha'].dt.year == hoy.year) & (df['Fecha'].dt.month == hoy.month)]
    if df.empty:
        return go.Figure()

    col = 'TotalFactura' if 'TotalFactura' in df.columns else None

    agg_dict = {}
    if col:
        agg_dict[col] = 'sum'
    agg_dict['Cliente'] = 'nunique'

    top = df.groupby('Marca').agg(agg_dict).reset_index()
    if col:
        top = top.sort_values(col, ascending=False).head(10)
    else:
        top = top.sort_values('Cliente', ascending=False).head(10)

    top = top.sort_values(col if col else 'Cliente')
    pal = ['#6366f1','#3b82f6','#06b6d4','#10b981',
           '#f59e0b','#f97316','#ef4444','#8b5cf6','#a855f7','#ec4899']

    n = len(top)
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=('💰 Distribución por Venta', '👥 Distribución por Clientes'),
        specs=[[{'type': 'treemap'}, {'type': 'treemap'}]],
        horizontal_spacing=0.05,
    )

    if col:
        fig.add_trace(
            go.Treemap(
                labels=top['Marca'],
                parents=[''] * n,
                values=top[col],
                marker=dict(colors=pal[:n], opacity=0.85,
                           line=dict(color='#0d1117', width=2)),
                text=[f"<b>{m}</b><br>${v:,.0f}" for m, v in zip(top['Marca'], top[col])],
                textposition='middle center',
                textfont=dict(size=11, color='white'),
                hovertemplate='<b>%{label}</b><br>Venta: $%{value:,.0f}<extra></extra>',
            ),
            row=1, col=1
        )

    fig.add_trace(
        go.Treemap(
            labels=top['Marca'],
            parents=[''] * n,
            values=top['Cliente'],
            marker=dict(colors=pal[:n], opacity=0.85,
                       line=dict(color='#0d1117', width=2)),
            text=[f"<b>{m}</b><br>👥{int(c)} clientes" for m, c in zip(top['Marca'], top['Cliente'])],
            textposition='middle center',
            textfont=dict(size=11, color='white'),
            hovertemplate='<b>%{label}</b><br>Clientes: %{value}<extra></extra>',
        ),
        row=1, col=2
    )

    fig.update_layout(
        title=dict(
            text=f'<b>🏷️ Marcas — {nombre}</b><br><span style="font-size:11px;color:#94a3b8">Izquierda: Impacto por ventas  •  Derecha: Impacto por clientes nuevos</span>',
            font=dict(size=14, color='#f1f5f9'), x=0.5, xanchor='center'
        ),
        height=500,
        paper_bgcolor='#0d1117',
        font=dict(color='#cbd5e1', size=12),
        margin=dict(t=80, b=20, l=10, r=10),
        showlegend=False,
    )
    return fig


# ─── TABLA ESTILIZADA ─────────────────────────────────────────────────────────

def _tabla_zona(df_z: pd.DataFrame):
    disp = df_z[[
        'NOMBRE', 'VENTA_REAL', 'PROY_V', 'META_V', 'CUMP_V', 'CUMP_PROY_V',
        'DN_REAL', 'PROY_DN', 'META_DN', 'CUMP_DN',
    ]].copy()
    disp.columns = [
        'Vendedor',
        'Venta Real $', 'Proyección $', 'Meta Mes $', 'Avance %', 'Proy %',
        'DN Real', 'Proy DN', 'Meta DN', 'Avance DN %',
    ]
    styled = (
        disp.style
        .map(lambda v: f'color:{color_c(v)};font-weight:bold',
             subset=['Avance %', 'Proy %', 'Avance DN %'])
        .format({
            'Venta Real $': '${:,.0f}',
            'Proyección $': '${:,.0f}',
            'Meta Mes $':   '${:,.0f}',
            'Avance %':     '{:.1f}%',
            'Proy %':       '{:.1f}%',
            'DN Real':      '{:.0f}',
            'Proy DN':      '{:.0f}',
            'Meta DN':      '{:.0f}',
            'Avance DN %':  '{:.1f}%',
        })
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)


# ─── TELEGRAM ─────────────────────────────────────────────────────────────────

def _enviar_telegram(mensaje: str, chat_id: str = TELEGRAM_CHAT_ID) -> bool:
    try:
        r = requests.post(
            f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage',
            data={'chat_id': chat_id, 'text': mensaje, 'parse_mode': 'HTML'},
            timeout=10,
        )
        return r.status_code == 200
    except Exception as e:
        st.error(f'Error Telegram: {e}')
        return False


def _mensaje_telegram(tabla: pd.DataFrame, zona: str, mes_lbl: str) -> str:
    hoy      = datetime.now()
    dias_mes = calendar.monthrange(hoy.year, hoy.month)[1]
    df_z     = tabla[tabla['ZONA'] == zona]

    v_tot    = df_z['VENTA_REAL'].sum()
    mv_tot   = df_z['META_V'].sum()
    proy_tot = df_z['PROY_V'].sum()
    dn_tot   = df_z['DN_REAL'].sum()
    md_tot   = df_z['META_DN'].sum()

    lineas = [
        f'🌙 <b>REPORTE NOCTURNO — {zona}</b>',
        f'━━━━━━━━━━━━━━━━━━━━━━━━━',
        f'📅 {hoy.strftime("%d/%m/%Y")}  Día {hoy.day}/{dias_mes}  {mes_lbl}',
        '',
        '<b>💰 VENTAS NETAS</b>  (Real → Meta Mes)',
    ]
    for _, r in df_z.iterrows():
        em = emoji_c(r['CUMP_PROY_V'])
        nb = str(r['NOMBRE'])[:20]
        lineas.append(
            f'{em} {nb}: <b>${r["VENTA_REAL"]:,.0f}</b> / ${r["META_V"]:,.0f}'
            f'  ({r["CUMP_V"]}%)  📈Proy:{r["CUMP_PROY_V"]:.0f}%'
        )
    lineas += ['', '<b>👥 IMPACTOS DN</b>  (Real → Meta Mes)']
    for _, r in df_z.iterrows():
        em = emoji_c(r['CUMP_PROY_DN'])
        nb = str(r['NOMBRE'])[:20]
        lineas.append(
            f'{em} {nb}: <b>{r["DN_REAL"]:.0f}</b> / {r["META_DN"]:.0f}'
            f'  ({r["CUMP_DN"]}%)  📈Proy:{r["CUMP_PROY_DN"]:.0f}%'
        )
    lineas += [
        '',
        '━━━━━━━━━━━━━━━━━━━━━━━━━',
        f'<b>📊 TOTAL ZONA {zona}</b>',
        f'💵 Ventas: <b>${v_tot:,.0f}</b> ({cump(v_tot,mv_tot)}%) → Proy: ${proy_tot:,.0f} ({cump(proy_tot,mv_tot):.0f}%)',
        f'🎯 DN:     <b>{dn_tot:.0f}</b> ({cump(dn_tot,md_tot)}%)',
        '',
        f'💎 <i>PDV Sin Límites — {hoy.strftime("%H:%M")}</i>',
    ]
    return '\n'.join(lineas)


# ─── PÁGINA PRINCIPAL ─────────────────────────────────────────────────────────

def pagina_presupuesto_cumplimiento():
    hoy     = datetime.now()
    dias_mes = calendar.monthrange(hoy.year, hoy.month)[1]
    mes_lbl  = hoy.strftime('%B %Y').upper()

    st.set_page_config(
        page_title='PDV Sin Límites — Presupuesto vs Cumplimiento',
        page_icon='📊',
        layout='wide',
        initial_sidebar_state='expanded',
    )

    # ════ DEBUG MODE ════
    with st.sidebar:
        st.write('🔧 **DEBUG MODE**')
        st.write(f'✅ Fecha: {hoy}')
        st.write(f'✅ BASE_DIR: {BASE_DIR}')
        st.write(f'✅ CREDS_PATH: {CREDS_PATH}')
        st.write(f'✅ CREDS existe local: {CREDS_PATH.exists()}')
        st.write(f'✅ Secrets disponibles: {"type" in st.secrets}')

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Poppins:wght@500;600;700;800&display=swap');

    * { font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Poppins', sans-serif; font-weight: 700; }

    .main { padding: 2rem 2.5rem; }
    .block-container { padding-top: 1rem; padding-bottom: 1rem; max-width: 100%; }

    .header-principal {
        background: linear-gradient(135deg, #0f172a 0%, #1a2e4a 100%);
        padding: 2.5rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        border-left: 4px solid #fbbf24;
    }

    .header-principal h1 {
        color: #f1f5f9;
        font-size: 2.2rem;
        margin: 0 0 0.5rem 0;
        font-weight: 800;
        letter-spacing: -0.5px;
    }

    .header-principal .subtitle {
        color: #cbd5e1;
        font-size: 0.95rem;
        font-weight: 500;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }

    .kpi-container { display: grid; grid-template-columns: repeat(5, 1fr); gap: 1rem; margin-bottom: 2rem; }

    .kpi-card {
        background: linear-gradient(135deg, #1a2e4a 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.5rem;
        transition: all 0.3s ease;
    }

    .kpi-card:hover {
        border-color: #fbbf24;
        box-shadow: 0 8px 24px rgba(251, 191, 36, 0.15);
        transform: translateY(-2px);
    }

    .kpi-label {
        color: #94a3b8;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.5rem;
    }

    .kpi-value {
        color: #f1f5f9;
        font-size: 1.8rem;
        font-weight: 700;
        font-family: 'Poppins', sans-serif;
        margin-bottom: 0.3rem;
    }

    .kpi-delta {
        color: #fbbf24;
        font-size: 0.85rem;
        font-weight: 500;
    }

    .section-title {
        color: #f1f5f9;
        font-size: 1.4rem;
        font-weight: 700;
        margin: 2rem 0 1.2rem 0;
        padding-bottom: 0.8rem;
        border-bottom: 2px solid #fbbf24;
        display: inline-block;
    }

    .stRadio > label { font-family: 'Poppins', sans-serif; font-weight: 600; }
    .dataframe { font-size: 0.9rem; }

    .stButton > button {
        font-family: 'Poppins', sans-serif;
        font-weight: 600;
        border-radius: 8px;
        padding: 0.6rem 1.5rem;
        transition: all 0.2s ease;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(251, 191, 36, 0.3);
    }

    .metric-container {
        background: linear-gradient(135deg, #1a2e4a 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1.2rem;
    }

    hr { border: 0; height: 1px; background: linear-gradient(to right, transparent, #334155, transparent); margin: 2rem 0; }
    .stAlert { border-radius: 10px; border-left: 4px solid #fbbf24 !important; }
    .streamlit-expanderHeader { background-color: #1a2e4a; border: 1px solid #334155; border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="header-principal">
        <h1>📊 Presupuesto vs Cumplimiento</h1>
        <div class="subtitle">
            Día {hoy.day}/{dias_mes} ({pct_mes()*100:.1f}% del mes)  •  {mes_lbl}  •  Solo Super Admin
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner('Cargando desde Google Sheets...'):
        try:
            st.write('🔄 Conectando a Google Sheets...')
            df_pres = cargar_presupuesto()
            st.write(f'✅ PRESUPUESTO: {len(df_pres)} registros')
            df_vn   = cargar_ventas_netas()
            st.write(f'✅ VENTAS_NETAS: {len(df_vn)} registros')
            df_vd   = cargar_ventas_detalle()
            st.write(f'✅ VENTAS DETALLE: {len(df_vd)} registros')
        except Exception as e:
            st.error(f'❌ Error conectando a Google Sheets:')
            st.error(f'  {type(e).__name__}: {str(e)}')
            st.info('**Soluciones:**')
            st.write('1. Verifica que `credenciales.json` exista en el directorio')
            st.write('2. Verifica que las hojas "PRESUPUESTO", "VENTAS_NETAS", "VENTAS" existan en el Google Sheet')
            st.write('3. En Streamlit Cloud, agrega credenciales.json en Secrets')
            return

    if df_pres.empty:
        st.error('❌ Sin datos en hoja PRESUPUESTO. Verifica:')
        st.write('- Que existe una hoja llamada "PRESUPUESTO"')
        st.write('- Que tiene columnas: VENDEDOR, PRESUPUESTO, OBJETIVO DN, ZONA')
        st.write('- Que hay datos en esa hoja')
        return

    if df_vn.empty:
        st.warning('⚠️ Sin datos en VENTAS_NETAS')
        return

    with st.expander('🔍 Verificar datos cargados (abre si los % son raros)', expanded=True):
        c1, c2 = st.columns(2)
        c1.markdown('**PRESUPUESTO — valores tal como llegan de Sheets**')
        c1.dataframe(df_pres[['KEY_PDV','NOMBRE','META_V','META_DN','ZONA']],
                     use_container_width=True, hide_index=True)
        c2.markdown('**VENTAS_NETAS — SubT_RL y DN_CLI**')
        c2.dataframe(df_vn, use_container_width=True, hide_index=True)

    tabla = construir_tabla(df_pres, df_vn, df_vd)
    zonas = [z for z in ['SIERRA', 'ORIENTE'] if z in tabla['ZONA'].unique()]

    estilo = st.radio(
        '🎨 Estilo de gráfico — escoge el que prefieras:',
        options=[
            'A — Barras verticales agrupadas',
            'B — Barras horizontales con $',
            'C — Tarjetas por vendedor',
        ],
        horizontal=True,
        key='estilo_grafico',
    )

    st.markdown('<h2 class="section-title">🌍 Resumen Global</h2>', unsafe_allow_html=True)
    tv   = tabla['VENTA_REAL'].sum()
    mv   = tabla['META_V'].sum()
    pv   = tabla['PROY_V'].sum()
    tdn  = tabla['DN_REAL'].sum()
    mdn  = tabla['META_DN'].sum()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f"""
        <div class="metric-container">
            <div class="kpi-label">💰 Venta Real</div>
            <div class="kpi-value">${tv:,.0f}</div>
            <div class="kpi-delta">{cump(tv,mv):.1f}% de meta</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-container">
            <div class="kpi-label">🎯 Meta Mes</div>
            <div class="kpi-value">${mv:,.0f}</div>
            <div class="kpi-delta">Faltan: ${max(0,mv-tv):,.0f}</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-container">
            <div class="kpi-label">📈 Proyección</div>
            <div class="kpi-value">${pv:,.0f}</div>
            <div class="kpi-delta">{cump(pv,mv):.1f}% al cierre</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="metric-container">
            <div class="kpi-label">👥 DN Real</div>
            <div class="kpi-value">{tdn:.0f}</div>
            <div class="kpi-delta">{cump(tdn,mdn):.1f}% de meta</div>
        </div>
        """, unsafe_allow_html=True)

    with col5:
        st.markdown(f"""
        <div class="metric-container">
            <div class="kpi-label">📊 Proy. DN</div>
            <div class="kpi-value">{tabla["PROY_DN"].sum():.0f}</div>
            <div class="kpi-delta">{cump(tabla["PROY_DN"].sum(),mdn):.1f}% al cierre</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('---')

    for zona in zonas:
        df_z  = tabla[tabla['ZONA'] == zona].copy()
        emoji = '🌴' if zona == 'ORIENTE' else '🏔️'
        st.markdown(f'<h2 class="section-title">{emoji} Zona {zona}</h2>', unsafe_allow_html=True)

        vz   = df_z['VENTA_REAL'].sum()
        mvz  = df_z['META_V'].sum()
        pz   = df_z['PROY_V'].sum()
        dz   = df_z['DN_REAL'].sum()
        mdz  = df_z['META_DN'].sum()
        pdz  = df_z['PROY_DN'].sum()

        kz1, kz2, kz3, kz4, kz5 = st.columns(5)
        with kz1:
            st.markdown(f"""
            <div class="metric-container">
                <div class="kpi-label">💰 Venta Real</div>
                <div class="kpi-value">${vz:,.0f}</div>
                <div class="kpi-delta">{cump(vz,mvz):.1f}% de meta</div>
            </div>
            """, unsafe_allow_html=True)

        with kz2:
            st.markdown(f"""
            <div class="metric-container">
                <div class="kpi-label">🎯 Meta Mes</div>
                <div class="kpi-value">${mvz:,.0f}</div>
                <div class="kpi-delta">Faltan: ${max(0,mvz-vz):,.0f}</div>
            </div>
            """, unsafe_allow_html=True)

        with kz3:
            st.markdown(f"""
            <div class="metric-container">
                <div class="kpi-label">📈 Proyección</div>
                <div class="kpi-value">${pz:,.0f}</div>
                <div class="kpi-delta">{cump(pz,mvz):.1f}% al cierre</div>
            </div>
            """, unsafe_allow_html=True)

        with kz4:
            st.markdown(f"""
            <div class="metric-container">
                <div class="kpi-label">👥 DN Real</div>
                <div class="kpi-value">{dz:.0f}</div>
                <div class="kpi-delta">{cump(dz,mdz):.1f}% de meta</div>
            </div>
            """, unsafe_allow_html=True)

        with kz5:
            st.markdown(f"""
            <div class="metric-container">
                <div class="kpi-label">📊 Proy. DN</div>
                <div class="kpi-value">{pdz:.0f}</div>
                <div class="kpi-delta">{cump(pdz,mdz):.1f}% al cierre</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('')

        # ──── GRÁFICOS CON ESTILOS ────
        st.markdown(f'<h3 style="color:#cbd5e1; margin-top:1.5rem; margin-bottom:1rem; font-size:1.1rem; font-weight:600;">📊 Gráficos de Desempeño — {zona}</h3>', unsafe_allow_html=True)
        _render_zona_graficos(df_z, zona, estilo)

        # ──── TABLA DETALLADA ────
        st.markdown('<h3 style="color:#cbd5e1; font-size:1rem; margin-top:2rem; margin-bottom:1rem; font-weight:600;">📋 Análisis por Vendedor</h3>', unsafe_allow_html=True)
        _tabla_zona(df_z)

        # ──── GRÁFICO COMPARATIVO: VENTAS vs DN POR VENDEDOR ────
        st.markdown(f'<h4 style="color:#94a3b8; font-size:0.9rem; margin-top:1.5rem; margin-bottom:0.8rem;">💰 Ventas vs 👥 DN — Comparación {zona}</h4>', unsafe_allow_html=True)

        fig_venta_dn = make_subplots(
            rows=1, cols=2,
            subplot_titles=('💰 Venta Real $', '👥 Clientes Nuevos (DN)'),
            specs=[[{'type': 'bar'}, {'type': 'bar'}]],
            horizontal_spacing=0.15,
        )

        nombres_sorted = df_z.sort_values('VENTA_REAL', ascending=True)['NOMBRE'].tolist()
        ventas_sorted = df_z[df_z['NOMBRE'].isin(nombres_sorted)]['VENTA_REAL'].tolist()
        dn_sorted = df_z[df_z['NOMBRE'].isin(nombres_sorted)]['DN_REAL'].tolist()

        fig_venta_dn.add_trace(
            go.Bar(
                y=nombres_sorted, x=ventas_sorted, orientation='h',
                marker=dict(color='#3b82f6', opacity=0.8),
                text=[f'${v:,.0f}' for v in ventas_sorted],
                textposition='outside',
                textfont=dict(size=9, color='#cbd5e1'),
                hovertemplate='<b>%{y}</b><br>Venta: $%{x:,.0f}<extra></extra>',
            ),
            row=1, col=1
        )

        fig_venta_dn.add_trace(
            go.Bar(
                y=nombres_sorted, x=dn_sorted, orientation='h',
                marker=dict(color='#10b981', opacity=0.8),
                text=[f'{int(v)} clientes' for v in dn_sorted],
                textposition='outside',
                textfont=dict(size=9, color='#cbd5e1'),
                hovertemplate='<b>%{y}</b><br>DN: %{x}<extra></extra>',
            ),
            row=1, col=2
        )

        fig_venta_dn.update_xaxes(gridcolor='#1e2536', color='#64748b', row=1, col=1)
        fig_venta_dn.update_xaxes(gridcolor='#1e2536', color='#64748b', row=1, col=2)
        fig_venta_dn.update_yaxes(color='#e2e8f0', showgrid=False, row=1, col=1)
        fig_venta_dn.update_yaxes(color='#e2e8f0', showgrid=False, row=1, col=2)

        fig_venta_dn.update_layout(
            height=max(300, len(df_z) * 35 + 80),
            paper_bgcolor='#0d1117',
            plot_bgcolor='#0d1117',
            font=dict(color='#cbd5e1', size=11),
            showlegend=False,
            margin=dict(t=40, b=20, l=140, r=100),
        )

        st.plotly_chart(fig_venta_dn, use_container_width=True)

        # ──── ANÁLISIS DN POR MARCA EN ZONA ────
        st.markdown(f'<h3 style="color:#cbd5e1; font-size:1rem; margin-top:2rem; margin-bottom:1rem; font-weight:600;">🏷️ Análisis DN por Marca — {zona}</h3>', unsafe_allow_html=True)

        # Agrupar DN por marca en la zona
        if not df_vd.empty:
            df_vd_zona = df_vd[df_vd['KEY_PDV'].isin(df_z['KEY_PDV'])].copy()
            hoy = datetime.now()
            if 'Fecha' in df_vd_zona.columns:
                df_vd_zona = df_vd_zona[(df_vd_zona['Fecha'].dt.year == hoy.year) & (df_vd_zona['Fecha'].dt.month == hoy.month)]

            if not df_vd_zona.empty and 'Marca' in df_vd_zona.columns:
                # DN por marca
                dn_marca = df_vd_zona.groupby('Marca')['Cliente'].nunique().sort_values(ascending=False).head(10)

                if not dn_marca.empty:
                    fig_dn = go.Figure(go.Bar(
                        x=dn_marca.values,
                        y=dn_marca.index,
                        orientation='h',
                        marker=dict(color=['#34d399','#10b981','#059669','#047857','#065f46',
                                          '#f59e0b','#d97706','#b45309','#92400e','#78350f'],
                                   opacity=0.85),
                        text=[f'{int(v)} clientes' for v in dn_marca.values],
                        textposition='outside',
                        textfont=dict(size=10, color='#cbd5e1'),
                        hovertemplate='<b>%{y}</b><br>👥 Clientes: %{x}<extra></extra>',
                    ))
                    fig_dn.update_layout(
                        height=350,
                        title=dict(text=f'<b>Top Marcas por Clientes Nuevos — {zona}</b>',
                                  font=dict(size=13, color='#f1f5f9')),
                        paper_bgcolor='#0d1117',
                        plot_bgcolor='#0d1117',
                        font=dict(color='#cbd5e1'),
                        xaxis=dict(gridcolor='#1e2536', color='#64748b'),
                        yaxis=dict(color='#e2e8f0', showgrid=False),
                        margin=dict(t=45, b=20, l=150, r=80),
                    )
                    st.plotly_chart(fig_dn, use_container_width=True)

        st.markdown('---')

    st.markdown('<h2 class="section-title">🔍 Top Marcas por Vendedor</h2>', unsafe_allow_html=True)
    vend_opts = tabla[['KEY_PDV', 'NOMBRE', 'ZONA']].copy()
    vend_opts['label'] = vend_opts.apply(
        lambda r: f"{r['NOMBRE']}  ({r['ZONA']})", axis=1)
    sel     = st.selectbox('Selecciona vendedor:', options=vend_opts.index,
                           format_func=lambda i: vend_opts.loc[i, 'label'],
                           key='vendedor_select')
    key_sel = vend_opts.loc[sel, 'KEY_PDV']
    nom_sel = vend_opts.loc[sel, 'NOMBRE']
    if key_sel and not df_vd.empty:
        fig_m = grafico_marcas(df_vd, key_sel, nom_sel)
        if fig_m.data:
            st.plotly_chart(fig_m, use_container_width=True)
        else:
            st.info('Sin detalle de productos para este vendedor en el mes actual.')

    st.markdown('---')

    st.markdown('<h2 class="section-title">📄 Descargar Reporte</h2>', unsafe_allow_html=True)
    pdf_col1, pdf_col2 = st.columns([2, 1])
    with pdf_col1:
        st.write('Genera un PDF profesional con tarjetas de cumplimiento para todas las zonas.')
    with pdf_col2:
        if st.button('⬇️ Generar PDF', type='primary', use_container_width=True):
            with st.spinner('Generando PDF...'):
                pdf_bytes = generar_pdf(tabla, mes_lbl)
            if pdf_bytes:
                st.download_button(
                    label='📥 Descargar PDF',
                    data=pdf_bytes,
                    file_name=f'reporte_pdv_{hoy.strftime("%Y%m%d")}.pdf',
                    mime='application/pdf',
                    type='primary',
                    use_container_width=True,
                )
            else:
                st.error('Error generando PDF. Verifica que matplotlib esté instalado.')

    st.markdown('---')

    st.markdown('<h2 class="section-title">📨 Enviar Reportes a Telegram</h2>', unsafe_allow_html=True)
    st.info(f'⏰ Hora actual: **{hoy.strftime("%H:%M")}**  •  Recomendado enviar a las **21:00**')

    tg_cols = st.columns(len(zonas) + 1)
    for i, zona in enumerate(zonas):
        with tg_cols[i]:
            if st.button(f'📨 {zona}', key=f'tg_{zona}',
                        type='primary', use_container_width=True):
                with st.spinner(f'Enviando {zona}...'):
                    msg = _mensaje_telegram(tabla, zona, mes_lbl)
                    ok  = _enviar_telegram(msg)
                    if ok:
                        st.success(f'✅ {zona} enviado')
                    else:
                        st.error(f'❌ Error en {zona}')

    with tg_cols[-1]:
        if st.button('📨 Todas', key='tg_todas',
                    type='primary', use_container_width=True):
            with st.spinner('Enviando todas las zonas...'):
                errores = [z for z in zonas
                           if not _enviar_telegram(_mensaje_telegram(tabla, z, mes_lbl))]
                if errores:
                    st.error(f'Error en: {", ".join(errores)}')
                else:
                    st.success('✅ Todas las zonas enviadas')

    with st.expander('👀 Vista previa de mensajes', expanded=False):
        for zona in zonas:
            with st.expander(f'📨 {zona}', expanded=False):
                st.code(_mensaje_telegram(tabla, zona, mes_lbl), language='markdown')

    st.markdown('---')

    col_refresh1, col_refresh2, col_refresh3 = st.columns([1, 1, 2])
    with col_refresh1:
        if st.button('🔄 Actualizar datos', use_container_width=True, key='refresh_btn'):
            st.cache_data.clear()
            st.rerun()

    st.markdown(
        '<div style="text-align:center; color:#64748b; font-size:0.8rem; margin-top:2rem;">'
        f'Última actualización: {hoy.strftime("%d/%m/%Y %H:%M")} • '
        'Datos se actualizan cada 5 minutos'
        '</div>',
        unsafe_allow_html=True
    )


if __name__ == '__main__':
    pagina_presupuesto_cumplimiento()
