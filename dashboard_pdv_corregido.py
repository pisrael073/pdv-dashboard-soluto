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

TELEGRAM_CONFIG = {
    'BOT_TOKEN': '8249353159:AAFvpNkEUdTcuIu_kpMcQbOtqyB0WbZkGTc',
    'CHAT_IDS': {
        'gerencia': '7900265168',
        'administracion': '7900265168',
        'vendedores': '-5180849774'
    }
}


def es_super_admin(user_codigo, user_nombre):
    codigo_israel = str(user_codigo) == '1804140794'
    nombre_israel = 'ISRAEL' in str(user_nombre).upper()
    nombre_completo = 'PAREDES ALTAMIRANO ISRAEL' in str(user_nombre).upper()
    return codigo_israel or nombre_israel or nombre_completo


def tiene_permisos_admin(user_rol):
    return user_rol.lower() in ('admin', 'administrador', 'gerente', 'supervisor', 'jefe')


def enviar_telegram(mensaje, chat_id=None, imagen=None):
    if not chat_id:
        chat_id = TELEGRAM_CONFIG['CHAT_IDS']['gerencia']
    bot_token = TELEGRAM_CONFIG['BOT_TOKEN']
    try:
        if mensaje:
            url_texto = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {'chat_id': chat_id, 'text': mensaje, 'parse_mode': 'HTML'}
            requests.post(url_texto, data=payload)
        if imagen:
            try:
                url_foto = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
                files = {'photo': imagen}
                data = {'chat_id': chat_id}
                response = requests.post(url_foto, files=files, data=data)
                return True
            except:
                return True
        return True
    except Exception as e:
        return False


def generar_grafico_telegram(df_v, mv, md, nombre_rep, m_sel, venta_real=None, impactos=None):
    from plotly.subplots import make_subplots
    if venta_real is None:
        venta_real = df_v['Total'].sum() if 'Total' in df_v.columns else 0
    if impactos is None:
        impactos = df_v[df_v['Total'] > 0]['Cliente'].nunique() if 'Total' in df_v.columns else 0
    pct_v = round(venta_real / mv * 100, 1) if mv > 0 else 0
    pct_dn = round(impactos / md * 100, 1) if md > 0 else 0
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('💰 Venta vs Meta', '👥 Cobertura DN', '🏆 Top Marcas', '📈 Tendencia'),
        specs=[[{"type": "indicator"}, {"type": "indicator"}],
               [{"type": "pie"}, {"type": "bar"}]]
    )
    fig.add_trace(go.Indicator(
        mode="gauge+number", value=pct_v,
        title={'text': f"Venta: ${venta_real:,.0f}"},
        gauge={'axis': {'range': [0, 150]},
               'bar': {'color': "lightgreen" if pct_v >= 100 else "orange" if pct_v >= 80 else "red"},
               'threshold': {'line': {'color': "blue", 'width': 4}, 'value': 100}},
        number={'suffix': "%"}, domain={'x': [0, 1], 'y': [0, 1]}
    ), row=1, col=1)
    fig.add_trace(go.Indicator(
        mode="gauge+number", value=pct_dn,
        title={'text': f"DN: {impactos}/{int(md)}"},
        gauge={'axis': {'range': [0, 150]},
               'bar': {'color': "lightgreen" if pct_dn >= 100 else "orange" if pct_dn >= 80 else "red"},
               'threshold': {'line': {'color': "blue", 'width': 4}, 'value': 100}},
        number={'suffix': "%"}, domain={'x': [0, 1], 'y': [0, 1]}
    ), row=1, col=2)
    if not df_v.empty and 'Marca' in df_v.columns and 'Total' in df_v.columns:
        marcas = df_v.groupby('Marca')['Total'].sum().nlargest(4)
        fig.add_trace(go.Pie(labels=marcas.index, values=marcas.values, textinfo="label+percent"), row=2, col=1)
    if not df_v.empty and 'Fecha' in df_v.columns and 'Total' in df_v.columns:
        try:
            df_v2 = df_v.copy()
            df_v2['Fecha_parsed'] = pd.to_datetime(df_v2['Fecha'])
            tendencia = df_v2.groupby(df_v2['Fecha_parsed'].dt.day)['Total'].sum().tail(7)
            fig.add_trace(go.Bar(x=[f"Día {d}" for d in tendencia.index], y=tendencia.values, marker_color='lightblue'), row=2, col=2)
        except:
            pass
    fig.update_layout(height=800, title_text=f"📊 {nombre_rep} - {m_sel}", title_x=0.5, font=dict(size=14), showlegend=False)
    return fig


def generar_imagen_matplotlib(df_v, mv, md, nombre_rep, m_sel, venta_real=None, impactos=None):
    try:
        import matplotlib.pyplot as plt
        import io as _io
        if venta_real is None:
            venta_real = df_v['Total'].sum() if 'Total' in df_v.columns else 0
        if impactos is None:
            impactos = df_v[df_v['Total'] > 0]['Cliente'].nunique() if 'Total' in df_v.columns else 0
        pct_v = round(venta_real / mv * 100, 1) if mv > 0 else 0
        pct_dn = round(impactos / md * 100, 1) if md > 0 else 0
        def get_color(pct):
            if pct >= 100: return '#4CAF50'
            elif pct >= 80: return '#FF9800'
            else: return '#F44336'
        plt.style.use('dark_background')
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10), facecolor='#1a1a2e')
        fig.suptitle(f'📊 REPORTE EJECUTIVO - {nombre_rep}\n{m_sel} • {datetime.now().strftime("%d/%m/%Y %H:%M")}',
                    fontsize=20, fontweight='bold', color='#00D4FF', y=0.95)
        ax1.clear()
        valores_venta = [venta_real, mv]
        etiquetas_venta = ['VENTA REAL', 'META']
        colores_venta = [get_color(pct_v), '#2196F3']
        bars = ax1.bar(etiquetas_venta, valores_venta, color=colores_venta, edgecolor='white', linewidth=2, alpha=0.9, width=0.6)
        for bar, valor in zip(bars, valores_venta):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + max(valores_venta)*0.02,
                    f'${valor:,.0f}', ha='center', va='bottom', color='white', fontweight='bold', fontsize=14)
        ax1.axhline(y=mv, color='#2196F3', linestyle='--', alpha=0.7, linewidth=2)
        ax1.text(0.5, max(valores_venta) * 0.8, f'{pct_v}%', transform=ax1.transData,
                ha='center', va='center', fontsize=24, fontweight='bold', color=get_color(pct_v),
                bbox=dict(boxstyle="round,pad=0.3", facecolor='black', alpha=0.7))
        ax1.set_ylabel('Valor ($)', color='white', fontweight='bold', fontsize=12)
        ax1.set_title('💰 VENTAS VS META', fontsize=16, fontweight='bold', color='#00D4FF', pad=15)
        ax1.tick_params(colors='white', labelsize=11)
        ax1.grid(True, alpha=0.3, axis='y')
        ax2.clear()
        valores_dn = [impactos, md]
        etiquetas_dn = ['DN REAL', 'META DN']
        colores_dn = [get_color(pct_dn), '#2196F3']
        bars_dn = ax2.barh(etiquetas_dn, valores_dn, color=colores_dn, edgecolor='white', linewidth=2, alpha=0.9, height=0.5)
        for bar, valor in zip(bars_dn, valores_dn):
            width = bar.get_width()
            ax2.text(width + max(valores_dn)*0.02, bar.get_y() + bar.get_height()/2.,
                    f'{valor:.0f}', ha='left', va='center', color='white', fontweight='bold', fontsize=14)
        ax2.text(max(valores_dn) * 0.7, 0.5, f'{pct_dn}%', ha='center', va='center', fontsize=24, fontweight='bold',
                color=get_color(pct_dn), bbox=dict(boxstyle="round,pad=0.3", facecolor='black', alpha=0.7))
        ax2.set_xlabel('Cantidad de Clientes', color='white', fontweight='bold', fontsize=12)
        ax2.set_title('👥 COBERTURA DN', fontsize=16, fontweight='bold', color='#00D4FF', pad=15)
        ax2.tick_params(colors='white', labelsize=11)
        ax2.grid(True, alpha=0.3, axis='x')
        ax3.clear()
        if not df_v.empty and 'Marca' in df_v.columns and 'Total' in df_v.columns:
            marcas = df_v.groupby('Marca')['Total'].sum().nlargest(5)
            colores_marcas = ['#FF5722', '#4CAF50', '#2196F3', '#FF9800', '#9C27B0']
            wedges, texts, autotexts = ax3.pie(marcas.values,
                                              labels=[f'{m[:12]}...' if len(m) > 12 else m for m in marcas.index],
                                              autopct='%1.1f%%', colors=colores_marcas, startangle=45,
                                              explode=[0.05] * len(marcas),
                                              textprops={'color': 'white', 'fontweight': 'bold', 'fontsize': 10})
            for autotext in autotexts:
                autotext.set_fontsize(11); autotext.set_fontweight('bold'); autotext.set_color('black')
        else:
            ax3.text(0.5, 0.5, 'Sin datos\nde marcas', ha='center', va='center', fontsize=16, color='white', transform=ax3.transAxes)
        ax3.set_title('🏆 TOP 5 MARCAS', fontsize=16, fontweight='bold', color='#00D4FF', pad=15)
        ax4.clear()
        proy = calcular_proyeccion(venta_real, df_v['Fecha'].max()) if not df_v.empty and 'Fecha' in df_v.columns else 0
        valores_comp = [venta_real, mv, proy]
        etiquetas_comp = ['ACTUAL', 'META', 'PROYECCIÓN']
        colores_comp = [get_color(pct_v), '#2196F3', '#9C27B0']
        bars_comp = ax4.bar(etiquetas_comp, valores_comp, color=colores_comp, edgecolor='white', linewidth=2, alpha=0.9, width=0.6)
        for bar, valor in zip(bars_comp, valores_comp):
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height + max(valores_comp)*0.02,
                    f'${valor:,.0f}', ha='center', va='bottom', color='white', fontweight='bold', fontsize=12)
        ax4.axhline(y=mv, color='#2196F3', linestyle='--', alpha=0.7, linewidth=2)
        ax4.text(2.2, mv, 'META', va='center', ha='left', color='#2196F3', fontweight='bold')
        ax4.set_ylabel('Valor ($)', color='white', fontweight='bold', fontsize=12)
        ax4.set_title('📈 ACTUAL vs META vs PROYECCIÓN', fontsize=16, fontweight='bold', color='#00D4FF', pad=15)
        ax4.tick_params(colors='white', labelsize=10)
        ax4.grid(True, alpha=0.3, axis='y')
        if pct_v >= 100: status = "🟢 EXCELENTE - Meta Superada"; status_color = '#4CAF50'
        elif pct_v >= 90: status = "🟡 EN RUTA - Muy Cerca de Meta"; status_color = '#FF9800'
        elif pct_v >= 80: status = "🟠 ATENCIÓN - Acelerar Ventas"; status_color = '#FF9800'
        else: status = "🔴 CRÍTICO - Acción Inmediata Requerida"; status_color = '#F44336'
        fig.text(0.5, 0.02, f'{status} • 💎 Sistema PDV Sin Límites', ha='center', va='bottom',
                fontsize=14, color=status_color, fontweight='bold',
                bbox=dict(boxstyle="round,pad=0.5", facecolor='black', alpha=0.8))
        plt.tight_layout()
        plt.subplots_adjust(top=0.88, bottom=0.12, hspace=0.3, wspace=0.3)
        img_buffer = _io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight', facecolor='#1a1a2e', edgecolor='none')
        img_buffer.seek(0)
        plt.close()
        return img_buffer
    except Exception as e:
        print(f"Error en gráfico: {e}")
        return None


def generar_reporte_matutino():
    try:
        df_v, df_p, _ = cargar_ventas_presupuesto()
        fecha_ayer = (datetime.now() - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        ventas_ayer = df_v[df_v['Fecha'].dt.strftime('%Y-%m-%d') == fecha_ayer]
        total_ayer = ventas_ayer['Total'].sum()
        clientes_ayer = ventas_ayer[ventas_ayer['Total'] > 0]['Cliente'].nunique()
        mes_actual = datetime.now().strftime('%B %Y')
        df_mes = df_v[df_v['Fecha'].dt.strftime('%B %Y') == mes_actual]
        total_mes = df_mes['Total'].sum()
        meta_mes = df_p['M_V'].sum()
        pct_mes = round(total_mes / meta_mes * 100, 1) if meta_mes > 0 else 0
        if not ventas_ayer.empty:
            top_vendedor = ventas_ayer.groupby('Vendedor')['Total'].sum().idxmax()
            top_monto = ventas_ayer.groupby('Vendedor')['Total'].sum().max()
            top_nombre = top_vendedor.split(' - ')[1] if ' - ' in top_vendedor else top_vendedor
        else:
            top_nombre = "Sin ventas"; top_monto = 0
        dia_actual = datetime.now().day
        dias_mes = pd.Timestamp.now().days_in_month
        mensaje = f"""
🌅 <b>REPORTE MATUTINO - EQUIPO PDV</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 <b>{datetime.now().strftime('%A, %d de %B %Y')}</b>
🕐 <b>Generado:</b> {datetime.now().strftime('%H:%M')}

📊 <b>RESUMEN DE AYER ({datetime.now() - pd.Timedelta(days=1):%d/%m})</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Venta Total: <b>${total_ayer:,.0f}</b>
👥 Clientes Visitados: <b>{clientes_ayer}</b>
🏆 Top Performer: <b>{top_nombre}</b> (${top_monto:,.0f})

📈 <b>ESTADO DEL MES ({mes_actual})</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💵 Acumulado: <b>${total_mes:,.0f}</b>
🎯 Meta Mensual: <b>${meta_mes:,.0f}</b>
📊 Progreso: <b>{pct_mes}%</b>
📅 Días transcurridos: <b>{dia_actual}/{dias_mes}</b>

⚡ <b>MOTIVACIÓN DEL DÍA</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
        if pct_mes >= 100: mensaje += f"\n🎉 <b>¡FELICITACIONES!</b> Meta mensual SUPERADA"
        elif pct_mes >= 90: mensaje += f"\n🔥 <b>¡EXCELENTE!</b> Muy cerca de la meta - ¡Empuje final!"
        elif pct_mes >= 80: mensaje += f"\n💪 <b>¡VAMOS EQUIPO!</b> Estamos en la recta final"
        else: mensaje += f"\n🚀 <b>¡A ACELERAR!</b> Tenemos todo para lograrlo"
        mensaje += f"""

🎯 <b>OBJETIVO DE HOY:</b>
├ Necesitamos: <b>${(meta_mes-total_mes)/(dias_mes-dia_actual) if (dias_mes-dia_actual) > 0 else 0:,.0f}/día</b>
└ Para cerrar: <b>${max(0, meta_mes-total_mes):,.0f}</b>

💎 <b>¡A BRILLAR EQUIPO PDV SIN LÍMITES!</b>
🚀 <b>Que tengan un día lleno de éxitos</b>
"""
        return mensaje
    except Exception as e:
        return f"🌅 <b>REPORTE MATUTINO</b>\n⚠️ Error: {str(e)}\n📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}"


def generar_reporte_nocturno():
    try:
        df_v, df_p, _ = cargar_ventas_presupuesto()
        fecha_hoy = datetime.now().strftime('%Y-%m-%d')
        ventas_hoy = df_v[df_v['Fecha'].dt.strftime('%Y-%m-%d') == fecha_hoy]
        total_hoy = ventas_hoy['Total'].sum()
        clientes_hoy = ventas_hoy[ventas_hoy['Total'] > 0]['Cliente'].nunique()
        mes_actual = datetime.now().strftime('%B %Y')
        df_mes = df_v[df_v['Fecha'].dt.strftime('%B %Y') == mes_actual]
        total_mes = df_mes['Total'].sum()
        meta_mes = df_p['M_V'].sum()
        pct_mes = round(total_mes / meta_mes * 100, 1) if meta_mes > 0 else 0
        ranking_hoy = []
        if not ventas_hoy.empty:
            ranking_data = ventas_hoy.groupby('Vendedor')['Total'].sum().nlargest(5)
            for i, (vendedor, monto) in enumerate(ranking_data.items(), 1):
                nombre = vendedor.split(' - ')[1] if ' - ' in vendedor else vendedor
                nombre_corto = nombre[:20] + "..." if len(nombre) > 20 else nombre
                emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                ranking_hoy.append(f"{emoji} <b>{nombre_corto}</b>: ${monto:,.0f}")
        dia_actual = datetime.now().day
        dias_mes = pd.Timestamp.now().days_in_month
        proyeccion = (total_mes / dia_actual) * dias_mes if dia_actual > 0 else 0
        mensaje = f"""
🌙 <b>REPORTE NOCTURNO - EQUIPO PDV</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 <b>{datetime.now().strftime('%A, %d de %B %Y')}</b>
🕐 <b>Generado:</b> {datetime.now().strftime('%H:%M')}

📊 <b>RESUMEN DEL DÍA ({datetime.now():%d/%m})</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 Venta de Hoy: <b>${total_hoy:,.0f}</b>
👥 Clientes Atendidos: <b>{clientes_hoy}</b>
📈 Acumulado Mes: <b>${total_mes:,.0f}</b>
🎯 Progreso: <b>{pct_mes}%</b> de la meta

🏆 <b>TOP 5 DEL DÍA</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
        if ranking_hoy:
            for rank in ranking_hoy: mensaje += f"\n{rank}"
        else:
            mensaje += f"\n📝 Sin ventas registradas hoy"
        mensaje += f"""

📈 <b>PROYECCIÓN ACTUALIZADA</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔮 Estimado Cierre: <b>${proyeccion:,.0f}</b>
📊 Vs Meta: <b>{proyeccion/meta_mes*100 if meta_mes > 0 else 0:.1f}%</b>
⏳ Días Restantes: <b>{dias_mes - dia_actual}</b>

💡 <b>REFLEXIÓN DEL DÍA</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
        if total_hoy >= total_mes / dia_actual: mensaje += f"\n🎉 <b>¡EXCELENTE DÍA!</b> Por encima del promedio necesario"
        elif total_hoy >= (total_mes / dia_actual) * 0.8: mensaje += f"\n👍 <b>BUEN DÍA</b> Dentro del rango esperado"
        else: mensaje += f"\n💪 <b>MAÑANA SERÁ MEJOR</b> Oportunidad de recuperar"
        mensaje += f"\n\n🌟 <b>EQUIPO PDV SIN LÍMITES</b>\n💤 <b>¡Que descansen y mañana a brillar!</b>"
        return mensaje
    except Exception as e:
        return f"🌙 <b>REPORTE NOCTURNO</b>\n⚠️ Error: {str(e)}\n📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}"


def enviar_telegram_con_imagen_alternativa(df_v, mv, md, nombre_rep, m_sel, mensaje, chat_id, venta_real=None, impactos=None):
    try:
        img_buffer = generar_imagen_matplotlib(df_v, mv, md, nombre_rep, m_sel, venta_real, impactos)
        if img_buffer:
            img_buffer.seek(0)
            if enviar_telegram(mensaje, chat_id, img_buffer):
                return True, "MATPLOTLIB"
    except Exception as e:
        print(f"Matplotlib falló: {e}")
    try:
        fig_telegram = generar_grafico_telegram(df_v, mv, md, nombre_rep, m_sel, venta_real, impactos)
        img_buffer2 = io.BytesIO()
        pio.write_image(fig_telegram, img_buffer2, format='png')
        img_buffer2.seek(0)
        if enviar_telegram(mensaje, chat_id, img_buffer2):
            return True, "PLOTLY"
    except Exception as e:
        print(f"Plotly falló: {e}")
    if enviar_telegram(mensaje, chat_id):
        return True, "TEXTO"
    return False, "ERROR"


def enviar_dashboard_automatico(tipo="matutino", chat_destino="vendedores"):
    try:
        mensaje = generar_reporte_matutino() if tipo == "matutino" else generar_reporte_nocturno()
        chat_id = TELEGRAM_CONFIG['CHAT_IDS'][chat_destino]
        try:
            df_v, df_p, _ = cargar_ventas_presupuesto()
            mes_actual = datetime.now().strftime('%B %Y')
            df_mes = df_v[df_v['Fecha'].dt.strftime('%B %Y') == mes_actual]
            if not df_mes.empty:
                total_mes = df_mes['Total'].sum()
                meta_mes = df_p['M_V'].sum()
                img_buffer = generar_imagen_matplotlib(df_mes, meta_mes, df_p['M_DN'].sum(), "EQUIPO CONSOLIDADO", mes_actual)
                if img_buffer:
                    img_buffer.seek(0)
                    return enviar_telegram(mensaje, chat_id, img_buffer)
        except:
            pass
        return enviar_telegram(mensaje, chat_id)
    except Exception as e:
        return False


def generar_reporte_telegram(df_final, mv, md, nombre_rep, m_sel, venta_real, impactos, proy):
    pct_v = round(venta_real / mv * 100, 1) if mv > 0 else 0
    pct_dn = round(impactos / md * 100, 1) if md > 0 else 0
    emoji_meta = "🟢" if pct_v >= 100 else "🟡" if pct_v >= 80 else "🔴"
    emoji_dn = "🟢" if pct_dn >= 100 else "🟡" if pct_dn >= 80 else "🔴"
    emoji_proy = "📈" if proy >= mv else "📉"
    top_marcas_text = ""
    if not df_final.empty and 'Marca' in df_final.columns and 'Total' in df_final.columns:
        top_marcas = df_final.groupby('Marca')['Total'].sum().nlargest(5)
        for i, (marca, venta) in enumerate(top_marcas.items(), 1):
            pct_marca = round(venta / venta_real * 100, 1) if venta_real > 0 else 0
            top_marcas_text += f"\n{i}. <b>{marca}</b>: ${venta:,.0f} ({pct_marca}%)"
    top_clientes_text = ""
    if not df_final.empty and 'Cliente' in df_final.columns and 'Total' in df_final.columns:
        top_clientes = df_final.groupby('Cliente')['Total'].sum().nlargest(3)
        for i, (cliente, venta) in enumerate(top_clientes.items(), 1):
            cliente_short = cliente[:25] + "..." if len(cliente) > 25 else cliente
            top_clientes_text += f"\n{i}. <b>{cliente_short}</b>: ${venta:,.0f}"
    fecha_actual = datetime.now()
    dia_actual = fecha_actual.day
    dias_mes = calendar.monthrange(fecha_actual.year, fecha_actual.month)[1]
    pct_mes = round(dia_actual / dias_mes * 100, 1)
    mensaje = f"""
📊 <b>REPORTE EJECUTIVO PDV</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
👤 <b>{nombre_rep}</b>
📅 <b>Período:</b> {m_sel}
🕐 <b>Generado:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}

💰 <b>PERFORMANCE VENTAS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
├ 💵 Venta Neta: <b>${venta_real:,.0f}</b>
├ 🎯 Meta Mes: <b>${mv:,.0f}</b>
├ 📊 Avance: <b>{pct_v}%</b> {emoji_meta}
└ 📈 Ritmo: <b>${venta_real/dia_actual:,.0f}/día</b>

👥 <b>COBERTURA DN</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
├ 🏪 Clientes Impactados: <b>{impactos}</b>
├ 🎯 Meta DN: <b>{int(md)}</b>
├ 📊 Cobertura: <b>{pct_dn}%</b> {emoji_dn}
└ 📍 Promedio: <b>${venta_real/impactos if impactos > 0 else 0:,.0f}/cliente</b>

{emoji_proy} <b>PROYECCIÓN CIERRE</b>
━━━━━━━━━━━━━━━━━━━━━━━━━
├ 📈 Estimado Mes: <b>${proy:,.0f}</b>
├ 📅 Días transcurridos: <b>{dia_actual}/{dias_mes} ({pct_mes}%)</b>
├ 🚀 Para meta faltan: <b>${max(0, mv-venta_real):,.0f}</b>
└ 📊 Ritmo requerido: <b>${max(0, mv-venta_real)/(dias_mes-dia_actual) if (dias_mes-dia_actual) > 0 else 0:,.0f}/día</b>

🏆 <b>TOP 5 MARCAS</b>
━━━━━━━━━━━━━━━━━━━━━━━━━{top_marcas_text}

👑 <b>TOP 3 CLIENTES</b>
━━━━━━━━━━━━━━━━━━━━━━━━━{top_clientes_text}

📋 <b>RESUMEN EJECUTIVO</b>
━━━━━━━━━━━━━━━━━━━━━━━━━"""
    if pct_v >= 100: mensaje += f"\n✅ <b>EXCELENTE</b>: Meta superada"
    elif pct_v >= 90: mensaje += f"\n🟡 <b>EN RUTA</b>: Muy cerca de meta"
    elif pct_v >= 80: mensaje += f"\n🟠 <b>ATENCIÓN</b>: Requiere aceleración"
    else: mensaje += f"\n🔴 <b>CRÍTICO</b>: Urgente intervención"
    mensaje += f"\n\n💎 <i>Sistema PDV Sin Límites</i>"
    mensaje += f"\n🤖 <i>Reporte automático #{datetime.now().strftime('%Y%m%d%H%M')}</i>"
    return mensaje


st.set_page_config(page_title="PDV Sin Límites 2026", layout="wide", page_icon="💎", initial_sidebar_state="expanded")

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
@media (max-width: 768px) {
    .block-container{padding:0.5rem 0.75rem!important;}
    .top-bar{flex-direction:column!important;text-align:center!important;padding:12px 16px!important;gap:8px;}
    .top-bar-title{font-size:1.1rem!important;}
    .stButton>button{width:100%!important;height:48px!important;font-size:16px!important;margin:8px 0!important;}
    .kpi-val{font-size:1.5rem!important;}
}
</style>
""", unsafe_allow_html=True)


def norm_txt(v):
    s = str(v).strip().upper()
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', s)


def limpiar_columnas(df):
    df.columns = [str(c).strip().replace('\ufeff','').replace('\xa0','').replace('\u200b','') for c in df.columns]
    return df


def descomponer_vendedor(texto):
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


@st.cache_resource(ttl=300)
def get_gc():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = dict(st.secrets["google"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    except Exception:
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)
        except Exception as e:
            st.error("❌ Error de conexión con Google Sheets")
            st.stop()
    return gspread.authorize(creds)


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
    df['_codigo_pdv']  = df[col_codigo].astype(str).str.strip().str.upper() if col_codigo else ''
    df['_codigo_pdv']  = df['_codigo_pdv'].replace({'NAN': '', 'NONE': ''})
    return df


@st.cache_data(ttl=300)
def cargar_ventas_presupuesto():
    gc = get_gc()
    sh = gc.open("soluto")
    ws_v   = sh.worksheet("VENTAS")
    df_raw = pd.DataFrame(ws_v.get_all_records())
    df_raw = limpiar_columnas(df_raw)
    def find_col(df, keyword):
        return next((c for c in df.columns if keyword in norm_txt(c)), None)
    col_fecha = find_col(df_raw, 'FECHA')
    col_total = find_col(df_raw, 'TOTAL')
    col_vend  = find_col(df_raw, 'VENDEDOR')
    col_cli   = find_col(df_raw, 'CLIENTE')
    col_marca = find_col(df_raw, 'MARCA')
    col_prov  = find_col(df_raw, 'PROVEEDOR')
    st.session_state['_cols_ventas'] = list(df_raw.columns)
    if col_fecha is None:
        raise ValueError(f"❌ No se encontró columna FECHA en VENTAS.\nColumnas: {list(df_raw.columns)}")
    if col_total is None:
        raise ValueError(f"❌ No se encontró columna TOTAL en VENTAS.\nColumnas: {list(df_raw.columns)}")
    fecha_series = pd.to_datetime(df_raw[col_fecha], errors='coerce', dayfirst=True)
    total_series = pd.to_numeric(df_raw[col_total].astype(str).str.replace(r'[$,\s]', '', regex=True), errors='coerce').fillna(0)
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
    ws_p = sh.worksheet("PRESUPUESTO")
    df_p = pd.DataFrame(ws_p.get_all_records())
    df_p = limpiar_columnas(df_p)
    rename_map = {}
    for c in df_p.columns:
        cn = norm_txt(c)
        if 'VENDEDOR' in cn: rename_map[c] = 'V_Orig'
        elif 'OBJETIVO' in cn or cn == 'DN': rename_map[c] = 'M_DN'
        elif 'PRESUPUESTO' in cn or 'META' in cn: rename_map[c] = 'M_V'
    df_p = df_p.rename(columns=rename_map)
    for col in ['M_V', 'M_DN']:
        if col not in df_p.columns: df_p[col] = 0
        df_p[col] = pd.to_numeric(df_p[col].astype(str).str.replace(r'[$,\s]', '', regex=True), errors='coerce').fillna(0)
    if 'V_Orig' not in df_p.columns: df_p['V_Orig'] = ''
    descomp_p = df_p['V_Orig'].apply(descomponer_vendedor)
    df_p['_codigo_pdv']  = descomp_p.apply(lambda x: x[0])
    df_p['_nombre_norm'] = descomp_p.apply(lambda x: x[1])
    audit = {'monto_perdido': monto_perdido, 'filas_afectadas': len(sin_fecha), 'detalle_errores': sin_fecha}
    return df_v, df_p, audit


# ══════════════════════════════════════════════════════════════════
#  ✅ NUEVA FUNCIÓN: Carga VENTAS_NETAS (una fila por vendedor)
# ══════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300)
def cargar_ventas_netas():
    """
    Carga la hoja VENTAS_NETAS con una fila por vendedor:
      SubT RL.  → valor de venta que va contra el presupuesto
      # Cli.    → clientes con compra = DN real
    """
    gc = get_gc()
    sh = gc.open("soluto")
    try:
        ws = sh.worksheet("VENTAS_NETAS")
    except Exception:
        return pd.DataFrame()
    df = pd.DataFrame(ws.get_all_records())
    df = limpiar_columnas(df)
    if df.empty:
        return df
    def find_col(df, keyword):
        return next((c for c in df.columns if keyword in norm_txt(c)), None)
    col_vend = find_col(df, 'VENDEDOR')
    col_subt = find_col(df, 'SUBT RL')
    col_cli  = find_col(df, 'CLI')
    df['Vendedor'] = df[col_vend].astype(str).str.strip() if col_vend else ''
    if col_subt:
        df['SubT_RL'] = pd.to_numeric(
            df[col_subt].astype(str).str.replace(r'[$,\s]', '', regex=True), errors='coerce'
        ).fillna(0)
    else:
        df['SubT_RL'] = 0
    if col_cli:
        df['Num_Cli'] = pd.to_numeric(
            df[col_cli].astype(str).str.replace(r'[$,\s]', '', regex=True), errors='coerce'
        ).fillna(0).astype(int)
    else:
        df['Num_Cli'] = 0
    descomp = df['Vendedor'].apply(descomponer_vendedor)
    df['_codigo_pdv']  = descomp.apply(lambda x: x[0])
    df['_nombre_vend'] = descomp.apply(lambda x: x[1])
    return df


def filtrar_ventas_usuario(df_v, u):
    codigo = str(u.get('_codigo_pdv', '')).strip().upper()
    nombre = str(u.get('_nombre_norm', '')).strip().upper()
    if codigo and codigo not in ('', 'NAN', 'NONE'):
        mask = df_v['_codigo_pdv'] == codigo
        if mask.sum() > 0:
            return df_v[mask].copy(), f"✅ Cruce por código PDV: **{codigo}**", "ok"
    if nombre:
        mask = df_v['_nombre_vend'] == nombre
        if mask.sum() > 0:
            return df_v[mask].copy(), f"✅ Cruce por nombre: **{nombre}**", "ok"
    return (pd.DataFrame(), f"❌ Sin datos — código **'{codigo}'** no encontrado en VENTAS.", "err")


def filtrar_presupuesto_usuario(df_p, u):
    codigo = str(u.get('_codigo_pdv', '')).strip().upper()
    nombre = str(u.get('_nombre_norm', '')).strip().upper()
    if codigo and codigo not in ('', 'NAN', 'NONE'):
        row = df_p[df_p['_codigo_pdv'] == codigo]
        if not row.empty: return row.iloc[0]
    if nombre:
        row = df_p[df_p['_nombre_norm'] == nombre]
        if not row.empty: return row.iloc[0]
    return None


# ══════════════════════════════════════════════════════════════════
#  ✅ NUEVA FUNCIÓN: Obtiene KPIs desde VENTAS_NETAS
# ══════════════════════════════════════════════════════════════════
def obtener_kpis_ventas_netas(df_vn, u):
    """
    Devuelve (venta_real, impactos, metodo, tipo) desde VENTAS_NETAS.
      venta_real = SubT RL.   |   impactos = # Cli.
    """
    codigo = str(u.get('_codigo_pdv', '')).strip().upper()
    nombre = str(u.get('_nombre_norm', '')).strip().upper()
    if df_vn.empty:
        return 0, 0, "⚠️ Hoja VENTAS_NETAS no disponible", "warn"
    if codigo and codigo not in ('', 'NAN', 'NONE'):
        mask = df_vn['_codigo_pdv'] == codigo
        if mask.sum() > 0:
            f = df_vn[mask].iloc[0]
            return float(f['SubT_RL']), int(f['Num_Cli']), f"✅ KPIs de VENTAS_NETAS — {codigo}", "ok"
    if nombre:
        mask = df_vn['_nombre_vend'] == nombre
        if mask.sum() > 0:
            f = df_vn[mask].iloc[0]
            return float(f['SubT_RL']), int(f['Num_Cli']), f"✅ KPIs de VENTAS_NETAS — {nombre}", "ok"
    return 0, 0, f"❌ Sin fila en VENTAS_NETAS para {codigo or nombre}", "err"


def pantalla_login():
    df_users = cargar_usuarios()
    if df_users.empty:
        st.error("❌ No se pudo cargar la hoja Usuario_Roles.")
        return
    nombres = sorted(df_users['_nombre_orig'].tolist())
    _, col_c, _ = st.columns([1, 1.1, 1])
    with col_c:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<div class='login-logo'>💎 PDV Sin Límites</div><div class='login-sub'>Panel Comercial · 2026</div>", unsafe_allow_html=True)
        st.markdown("<div class='login-label'>👤 Selecciona tu nombre</div>", unsafe_allow_html=True)
        nombre_sel = st.selectbox("", ["— Selecciona —"] + nombres, key="login_nombre", label_visibility="collapsed")
        st.markdown("<div class='login-label' style='margin-top:16px;'>🔐 Ingresa tu PIN</div>", unsafe_allow_html=True)
        pin_inp = st.text_input("", type="password", placeholder="• • • • •", key="login_pin", label_visibility="collapsed", max_chars=6)
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("→ INGRESAR", use_container_width=True, key="btn_login"):
            if nombre_sel == "— Selecciona —":
                st.markdown("<div class='error-box'>⚠️ Selecciona tu nombre.</div>", unsafe_allow_html=True); return
            fila = df_users[df_users['_nombre_orig'] == nombre_sel]
            if fila.empty:
                st.markdown("<div class='error-box'>❌ Usuario no encontrado.</div>", unsafe_allow_html=True); return
            u = fila.iloc[0]
            try:
                pin_correcto = str(int(float(u['_pin'])))
            except Exception:
                pin_correcto = str(u['_pin'])
            if pin_inp.strip() != pin_correcto:
                st.markdown("<div class='error-box'>🔒 PIN incorrecto.</div>", unsafe_allow_html=True); return
            st.session_state.update({
                'logged_in': True, 'user_nombre': nombre_sel, 'user_norm': str(u['_nombre_norm']),
                'user_rol': str(u['_rol']), 'user_zona': str(u['_zona']),
                'user_codigo': str(u['_codigo_pdv']), 'user_row': u.to_dict(),
            })
            st.rerun()
        st.caption("🔒 Acceso restringido — Sistema SOLUTO")


def calcular_proyeccion(venta, fecha_max):
    if pd.isna(fecha_max): return 0
    fecha_actual = datetime.now()
    mes_actual = fecha_actual.month; año_actual = fecha_actual.year; dia_actual = fecha_actual.day
    if fecha_max.month == mes_actual and fecha_max.year == año_actual:
        _, dias_total = calendar.monthrange(año_actual, mes_actual)
        if dia_actual > 0: return (venta / dia_actual) * dias_total
    else:
        _, dias_total = calendar.monthrange(fecha_max.year, fecha_max.month)
        return (venta / fecha_max.day) * dias_total
    return 0


def generar_scorecard(df_v, mv, md, nombre_rep, mes):
    venta_real = df_v['Total'].sum() if 'Total' in df_v.columns else 0
    impactos   = df_v[df_v['Total'] > 0]['Cliente'].nunique() if 'Total' in df_v.columns else 0
    fecha_max  = df_v['Fecha'].max() if 'Fecha' in df_v.columns else pd.NaT
    proy       = calcular_proyeccion(venta_real, fecha_max)
    fig = go.Figure()
    fig.add_trace(go.Indicator(mode="number", value=venta_real, number={'prefix': "$", 'font': {'size': 65, 'color': '#3B82F6', 'weight': 'bold'}}, title={'text': "💰 VENTA NETA ACUMULADA", 'font': {'size': 18, 'color': '#94A3B8'}}, domain={'x': [0, 0.48], 'y': [0.90, 1]}))
    fig.add_trace(go.Indicator(mode="number", value=impactos, number={'font': {'size': 65, 'color': '#F59E0B', 'weight': 'bold'}}, title={'text': "👥 CLIENTES IMPACTADOS (DN)", 'font': {'size': 18, 'color': '#94A3B8'}}, domain={'x': [0.52, 1], 'y': [0.90, 1]}))
    fig.add_trace(go.Indicator(mode="gauge+number+delta", value=(venta_real / mv * 100) if mv > 0 else 0,
        delta={'reference': 100, 'increasing': {'color': '#10B981'}, 'decreasing': {'color': '#EF4444'}},
        number={'suffix': "%", 'font': {'size': 35, 'weight': 'bold'}},
        gauge={'axis': {'range': [0, 125]}, 'bar': {'color': '#3B82F6', 'thickness': 0.3}, 'bgcolor': '#1E2940', 'borderwidth': 2, 'bordercolor': '#1E3A8A', 'threshold': {'line': {'color': '#60A5FA', 'width': 4}, 'thickness': 0.8, 'value': 100}},
        title={'text': f"AVANCE META (${mv:,.0f})", 'font': {'size': 15, 'color': '#3B82F6'}}, domain={'x': [0.05, 0.45], 'y': [0.72, 0.88]}))
    fig.add_trace(go.Indicator(mode="gauge+number", value=(impactos / md * 100) if md > 0 else 0,
        number={'suffix': "%", 'font': {'size': 35, 'weight': 'bold'}},
        gauge={'axis': {'range': [0, 125], 'visible': False}, 'bar': {'color': '#F59E0B', 'thickness': 0.3}, 'bgcolor': '#1E2940', 'borderwidth': 2, 'bordercolor': '#92400E', 'threshold': {'line': {'color': '#FCD34D', 'width': 4}, 'thickness': 0.8, 'value': 100}},
        title={'text': f"COBERTURA DN (Meta:{int(md)})", 'font': {'size': 15, 'color': '#F59E0B'}}, domain={'x': [0.55, 0.95], 'y': [0.72, 0.88]}))
    fig.add_trace(go.Indicator(mode="number", value=proy, number={'prefix': "$", 'font': {'size': 55, 'color': '#10B981' if proy >= mv else '#EF4444', 'weight': 'bold'}}, title={'text': "📈 PROYECCIÓN ESTIMADA AL CIERRE", 'font': {'size': 18, 'color': '#94A3B8'}}, domain={'x': [0, 1], 'y': [0.63, 0.70]}))
    if 'Marca' in df_v.columns and 'Total' in df_v.columns:
        d_marca = df_v.groupby('Marca')['Total'].sum().reset_index().sort_values('Total', ascending=False).head(8)
        fig.add_annotation(text="<b>🥧 MIX DE MARCAS</b>", x=0.5, y=0.61, xref="paper", yref="paper", showarrow=False, font=dict(size=20, color="#3B82F6"))
        fig.add_trace(go.Pie(labels=d_marca['Marca'], values=d_marca['Total'], hole=0.5, texttemplate="<b>%{label}</b><br>%{percent}", textposition='outside', marker=dict(colors=px.colors.qualitative.Bold, line=dict(color='#0A0F1E', width=2)), domain={'x': [0.1, 0.9], 'y': [0.38, 0.58]}))
    if 'Proveedor' in df_v.columns and 'Total' in df_v.columns:
        d_prov = df_v.groupby('Proveedor')['Total'].sum().reset_index().sort_values('Total', ascending=True).tail(8)
        fig.add_annotation(text="<b>📊 TOP PROVEEDORES</b>", x=0.5, y=0.36, xref="paper", yref="paper", showarrow=False, font=dict(size=20, color="#3B82F6"))
        fig.add_trace(go.Bar(x=d_prov['Total'], y=d_prov['Proveedor'], orientation='h', marker_color='#1E40AF', text=d_prov['Total'].apply(lambda x: f"<b>${x:,.0f}</b>"), textposition='outside', xaxis='x', yaxis='y'))
    if 'Cliente' in df_v.columns and 'Total' in df_v.columns:
        d_cli = df_v.groupby('Cliente')['Total'].sum().reset_index().sort_values('Total', ascending=False).query("Total > 0.01").head(20)
        fig.add_trace(go.Table(header=dict(values=["<b>CLIENTE TOP 20</b>", "<b>COMPRA TOTAL</b>"], fill_color='#1E3A8A', font=dict(color='white', size=16), height=45),
            cells=dict(values=[d_cli['Cliente'].str.slice(0, 45), d_cli['Total'].apply(lambda x: f"<b>${x:,.2f}</b>")], fill_color=['#111827', '#0F172A'], font=dict(color='#E2E8F0', size=14), height=35), domain={'x': [0, 1], 'y': [0, 0.18]}))
    fig.update_layout(height=2600, width=1200, paper_bgcolor='#0A0F1E', plot_bgcolor='#0A0F1E', font=dict(color='#E2E8F0'),
        title={'text': f"<b>SCORECARD: {nombre_rep}</b><br><span style='color:#64748B;font-size:0.8em'>{mes}</span>", 'y': 0.99, 'x': 0.5, 'xanchor': 'center', 'font': dict(color='#F8FAFC', size=26)},
        margin=dict(t=160, b=60, l=100, r=100), xaxis=dict(domain=[0.1, 0.95], visible=False), yaxis=dict(domain=[0.22, 0.35], showline=False))
    return fig


def kpi_card(col, valor, label, sub="", accent="#3B82F6", prefix="$", suffix=""):
    val_fmt = (f"{prefix}{valor:,.0f}{suffix}" if isinstance(valor, (int, float)) else str(valor))
    col.markdown(f"<div class='kpi-card' style='--accent:{accent};'><div class='kpi-val'>{val_fmt}</div><div class='kpi-lbl'>{label}</div>{'<div class=kpi-sub>' + sub + '</div>' if sub else ''}</div>", unsafe_allow_html=True)


def dashboard(df_v_all, df_p, usuario_row):
    user_nombre = st.session_state['user_nombre']
    user_rol    = st.session_state['user_rol']
    user_zona   = st.session_state['user_zona']
    user_codigo = st.session_state['user_codigo']
    is_super_admin = es_super_admin(user_codigo, user_nombre)
    is_admin = tiene_permisos_admin(user_rol)

    if is_super_admin: admin_badge = "<span class='admin-badge'>SUPER ADMIN</span>"
    elif is_admin: admin_badge = "<span class='admin-badge'>Admin</span>"
    else: admin_badge = ""
    cod_lbl = (f"<span style='color:#475569;font-size:0.7rem;margin-left:8px;'>[{user_codigo}]</span>") if user_codigo else ""
    st.markdown(f"<div class='top-bar'><div><span class='top-bar-title'>💎 PDV Sin Límites</span>{admin_badge}</div><div><div class='top-bar-user'>👤 {user_nombre}{cod_lbl}</div><div class='top-bar-badge'>{user_zona or 'SIN ZONA'}</div></div></div>", unsafe_allow_html=True)

    df_v_all['Mes_N'] = df_v_all['Fecha'].dt.strftime('%B %Y')
    meses = sorted(df_v_all['Mes_N'].unique().tolist(), reverse=True)
    col_mes, col_telegram, col_destino, col_logout = st.columns([3, 2, 2, 1])
    with col_mes:
        m_sel = st.selectbox("📅 Selecciona el período:", meses, key="mes_sel")
    with col_telegram:
        telegram_activo = st.checkbox("📱 Envío Telegram", key="telegram_on")
    with col_destino:
        if telegram_activo:
            chat_destino = st.selectbox("👥 Destinatario:", ["gerencia", "administracion", "vendedores"], key="telegram_chat")
        else:
            chat_destino = None
            st.selectbox("👥 Destinatario:", ["(Telegram desactivado)"], disabled=True)
    with col_logout:
        if st.button("🚪 Salir", use_container_width=True):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()
    st.markdown("---")

    with st.sidebar:
        st.markdown(f"<div style='color:#60A5FA;font-weight:700;padding:8px 0;'>👤 {user_nombre}</div>", unsafe_allow_html=True)
        st.markdown(f"<div style='color:#64748B;font-size:0.75rem;margin-bottom:12px;'>Código: {user_codigo or '—'} · {user_zona or '—'}</div>", unsafe_allow_html=True)
        if telegram_activo: st.success(f"📱 Telegram ON → {chat_destino}")
        else: st.info("📱 Telegram OFF")
        if telegram_activo and st.button("🧪 Prueba rápida", use_container_width=True):
            chat_id = TELEGRAM_CONFIG['CHAT_IDS'][chat_destino]
            with st.spinner("Enviando prueba..."):
                if enviar_telegram(f"🧪 Prueba desde {user_nombre}\n📅 {datetime.now().strftime('%H:%M')}", chat_id):
                    st.success("✅ Mensaje enviado!")
                else: st.error("❌ Error")

    m_sel  = st.session_state.get('mes_sel', meses[0] if meses else '')
    df_mes = df_v_all[df_v_all['Mes_N'] == m_sel].copy()

    v_admin = None
    if is_super_admin:
        vends_raw = sorted(df_mes['Vendedor'].dropna().unique().tolist())
        v_admin = st.selectbox("👤 Vendedor a analizar", ["GLOBAL"] + vends_raw, key="vend_admin")
        if v_admin == "GLOBAL":
            df_final, metodo, tipo = df_mes.copy(), "Vista GLOBAL — todos los vendedores", "ok"
            mv = df_p['M_V'].sum(); md = df_p['M_DN'].sum(); nombre_rep = "GLOBAL"
        else:
            cod_v, nom_v = descomponer_vendedor(v_admin)
            u_tmp = pd.Series({'_codigo_pdv': cod_v, '_nombre_norm': nom_v})
            df_final, metodo, tipo = filtrar_ventas_usuario(df_mes, u_tmp)
            pres = filtrar_presupuesto_usuario(df_p, u_tmp)
            mv = float(pres['M_V']) if pres is not None else 0
            md = float(pres['M_DN']) if pres is not None else 0
            nombre_rep = v_admin
    elif is_admin:
        st.info("🔒 Como administrador, solo puedes ver vista GLOBAL o tu reporte personal")
        v_admin = st.selectbox("👤 Vista disponible:", ["GLOBAL", f"Mi reporte ({user_nombre})"], key="vend_admin")
        if v_admin == "GLOBAL":
            df_final, metodo, tipo = df_mes.copy(), "Vista GLOBAL — todos los vendedores", "ok"
            mv = df_p['M_V'].sum(); md = df_p['M_DN'].sum(); nombre_rep = "GLOBAL"
        else:
            u_row = pd.Series(usuario_row)
            df_final, metodo, tipo = filtrar_ventas_usuario(df_mes, u_row)
            pres = filtrar_presupuesto_usuario(df_p, u_row)
            mv = float(pres['M_V']) if pres is not None else 0
            md = float(pres['M_DN']) if pres is not None else 0
            nombre_rep = user_nombre
    else:
        u_row = pd.Series(usuario_row)
        df_final, metodo, tipo = filtrar_ventas_usuario(df_mes, u_row)
        pres = filtrar_presupuesto_usuario(df_p, u_row)
        mv = float(pres['M_V']) if pres is not None else 0
        md = float(pres['M_DN']) if pres is not None else 0
        nombre_rep = user_nombre

    cls = 'cruce-ok' if tipo == 'ok' else 'cruce-err'
    st.markdown(f"<div class='{cls}'>{metodo}</div>", unsafe_allow_html=True)

    if df_final.empty:
        st.warning("⚠️ Sin ventas para este periodo.")
        if not is_admin:
            st.info(f"Verifica que la columna **codigo** en Usuario_Roles tenga **{user_codigo or 'PDVxx'}**.")
        return

    # ══════════════════════════════════════════════════════════════
    #  ✅ KPIs DESDE VENTAS_NETAS (SubT RL. y # Cli.)
    # ══════════════════════════════════════════════════════════════
    df_vn = cargar_ventas_netas()

    if nombre_rep == "GLOBAL":
        if not df_vn.empty:
            venta_real = float(df_vn['SubT_RL'].sum())
            impactos   = int(df_vn['Num_Cli'].sum())
            metodo_vn  = "✅ KPIs GLOBAL desde VENTAS_NETAS (SubT RL. + # Cli.)"
        else:
            venta_real = df_final['Total'].sum()
            impactos   = df_final[df_final['Total'] > 0]['Cliente'].nunique()
            metodo_vn  = "⚠️ Fallback GLOBAL — hoja VENTAS (VENTAS_NETAS no disponible)"
    else:
        # Determinar qué usuario buscar en VENTAS_NETAS
        if is_super_admin and v_admin and v_admin != "GLOBAL":
            cod_vn, nom_vn = descomponer_vendedor(v_admin)
            u_vn = {'_codigo_pdv': cod_vn, '_nombre_norm': nom_vn}
        elif is_admin and v_admin and v_admin != "GLOBAL":
            u_vn = usuario_row
        else:
            u_vn = usuario_row

        venta_real, impactos, metodo_vn, tipo_vn = obtener_kpis_ventas_netas(df_vn, u_vn)

        # Fallback si no se encontró en VENTAS_NETAS
        if venta_real == 0 and impactos == 0:
            venta_real = df_final['Total'].sum()
            impactos   = df_final[df_final['Total'] > 0]['Cliente'].nunique()
            metodo_vn  = "⚠️ Fallback — hoja VENTAS (no encontrado en VENTAS_NETAS)"

    cls_vn = 'cruce-ok' if 'VENTAS_NETAS' in metodo_vn else 'cruce-err'
    st.markdown(f"<div class='{cls_vn}'>📊 {metodo_vn}</div>", unsafe_allow_html=True)

    fecha_max = df_final['Fecha'].max()
    proy      = calcular_proyeccion(venta_real, fecha_max)
    pct_v     = round(venta_real / mv * 100, 1) if mv > 0 else 0
    pct_dn    = round(impactos   / md * 100, 1) if md > 0 else 0

    st.markdown(f"<div class='section-title'>📊 {m_sel} — {nombre_rep}</div>", unsafe_allow_html=True)
    k1, k2, k3, k4, k5 = st.columns(5)
    kpi_card(k1, venta_real, "Venta Neta", f"Meta ${mv:,.0f}", "#3B82F6")
    kpi_card(k2, pct_v, "% Avance Meta", f"${venta_real:,.0f}", "#10B981" if pct_v >= 100 else "#F59E0B", prefix="", suffix="%")
    kpi_card(k3, impactos, "Clientes DN", f"Meta {int(md)}", "#F59E0B", prefix="")
    kpi_card(k4, pct_dn, "% Cobertura DN", f"{impactos} visitados", "#A855F7" if pct_dn >= 100 else "#60A5FA", prefix="", suffix="%")
    kpi_card(k5, proy, "Proyección Cierre", "✅ ON TRACK" if proy >= mv else "⚠️ Riesgo", "#10B981" if proy >= mv else "#EF4444")
    st.markdown("<br>", unsafe_allow_html=True)

    if is_super_admin:
        tab1, tab2, tab3, tab4 = st.tabs(["📈 Scorecard", "📊 Detalle", "🚀 Envío Masivo", "🛡️ Auditoría"])
        tab3_enabled = True; tab4_enabled = True
    elif is_admin:
        tab1, tab2 = st.tabs(["📈 Scorecard", "📊 Detalle"])
        tab3 = tab4 = None; tab3_enabled = False; tab4_enabled = False
    else:
        tab1, tab2 = st.tabs(["📈 Mi Scorecard", "📊 Mi Detalle"])
        tab3 = tab4 = None; tab3_enabled = False; tab4_enabled = False

    with tab1:
        with st.spinner("Generando scorecard..."):
            st.markdown("### 📊 DASHBOARD EJECUTIVO")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                delta_v = f"+{pct_v-100:.1f}%" if pct_v >= 100 else f"{pct_v-100:.1f}%"
                st.metric("💰 Venta Real", f"${venta_real:,.0f}", delta_v)
            with col2:
                st.metric("🎯 Meta", f"${mv:,.0f}", f"{pct_v:.1f}%")
            with col3:
                delta_dn = f"+{pct_dn-100:.1f}%" if pct_dn >= 100 else f"{pct_dn-100:.1f}%"
                st.metric("👥 Cobertura DN", f"{impactos}/{int(md)}", delta_dn)
            with col4:
                st.metric("📈 Proyección", f"${proy:,.0f}", f"{'🟢' if proy >= mv else '🟡' if proy >= mv*0.9 else '🔴'}")
            st.markdown("---")
            col_left, col_right = st.columns(2)
            with col_left:
                fig_ventas = go.Figure()
                fig_ventas.add_trace(go.Bar(x=['Venta Real', 'Meta'], y=[venta_real, mv],
                    marker_color=['#4CAF50' if pct_v >= 100 else '#FF9800' if pct_v >= 80 else '#F44336', '#2196F3'],
                    text=[f'${venta_real:,.0f}', f'${mv:,.0f}'], textposition='auto', textfont_color='white', textfont_size=14))
                fig_ventas.update_layout(title=f'💰 Ventas vs Meta ({pct_v}%)', template='plotly_dark', height=300, showlegend=False, title_font_color='#00D4FF', title_font_size=16)
                st.plotly_chart(fig_ventas, use_container_width=True)
            with col_right:
                fig_dn = go.Figure()
                fig_dn.add_trace(go.Bar(x=['DN Real', 'Meta DN'], y=[impactos, md],
                    marker_color=['#4CAF50' if pct_dn >= 100 else '#FF9800' if pct_dn >= 80 else '#F44336', '#2196F3'],
                    text=[f'{impactos}', f'{int(md)}'], textposition='auto', textfont_color='white', textfont_size=14))
                fig_dn.update_layout(title=f'👥 Cobertura DN ({pct_dn}%)', template='plotly_dark', height=300, showlegend=False, title_font_color='#00D4FF', title_font_size=16)
                st.plotly_chart(fig_dn, use_container_width=True)
            col_marcas, col_proy = st.columns(2)
            with col_marcas:
                if not df_final.empty and 'Marca' in df_final.columns and 'Total' in df_final.columns:
                    marcas_data = df_final.groupby('Marca')['Total'].sum().nlargest(5)
                    fig_marcas = go.Figure(data=[go.Pie(labels=marcas_data.index, values=marcas_data.values, hole=0.4, textinfo='label+percent', textfont_size=12, marker_colors=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57'])])
                    fig_marcas.update_layout(title='🏆 Top 5 Marcas', template='plotly_dark', height=300, title_font_color='#00D4FF', title_font_size=16)
                    st.plotly_chart(fig_marcas, use_container_width=True)
            with col_proy:
                fig_comp = go.Figure()
                fig_comp.add_trace(go.Bar(x=['Actual', 'Meta', 'Proyección'], y=[venta_real, mv, proy],
                    marker_color=['#4CAF50' if pct_v >= 100 else '#FF9800', '#2196F3', '#9C27B0'],
                    text=[f'${v:,.0f}' for v in [venta_real, mv, proy]], textposition='auto', textfont_color='white', textfont_size=12))
                fig_comp.add_hline(y=mv, line_dash="dash", line_color="#2196F3", annotation_text="Meta", annotation_position="top right")
                fig_comp.update_layout(title='📈 Actual vs Proyección', template='plotly_dark', height=300, showlegend=False, title_font_color='#00D4FF', title_font_size=16)
                st.plotly_chart(fig_comp, use_container_width=True)

            col_png, col_tg = st.columns(2)
            with col_png:
                try:
                    fig_completo = generar_scorecard(df_final, mv, md, nombre_rep, m_sel)
                    img = pio.to_image(fig_completo, format="png", scale=2.0)
                    st.download_button(f"📥 Descargar PNG — {nombre_rep}", img, f"Scorecard_{nombre_rep.replace(' ','_')}_{m_sel}.png", "image/png", use_container_width=True)
                except Exception as e:
                    st.info("💡 PNG no disponible en este entorno")
            with col_tg:
                if st.button("📱 Enviar por Telegram", use_container_width=True, key="telegram_scorecard"):
                    if telegram_activo and chat_destino:
                        chat_id = TELEGRAM_CONFIG['CHAT_IDS'][chat_destino]
                        with st.spinner("📱 Generando reporte completo..."):
                            mensaje = generar_reporte_telegram(df_final, mv, md, nombre_rep, m_sel, venta_real, impactos, proy)
                            exito, met = enviar_telegram_con_imagen_alternativa(df_final, mv, md, nombre_rep, m_sel, mensaje, chat_id, venta_real, impactos)
                            if exito: st.success(f"✅ Enviado ({met})")
                            else: st.error("❌ Error enviando a Telegram")
                    else:
                        st.warning("⚠️ Activa Telegram en los controles superiores")

    with tab2:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("<div class='section-title'>🥧 Mix Marcas</div>", unsafe_allow_html=True)
            if 'Marca' in df_final.columns and 'Total' in df_final.columns:
                d_m = df_final.groupby('Marca')['Total'].sum().reset_index().sort_values('Total', ascending=False).head(8)
                if not d_m.empty:
                    fig_p = px.pie(d_m, names='Marca', values='Total', hole=0.45, color_discrete_sequence=px.colors.qualitative.Bold)
                    fig_p.update_layout(paper_bgcolor='#111827', plot_bgcolor='#111827', font_color='#E2E8F0', margin=dict(t=20,b=20,l=20,r=20), legend=dict(font=dict(color='#E2E8F0')))
                    fig_p.update_traces(textfont=dict(color='#FFFFFF', size=12))
                    st.plotly_chart(fig_p, use_container_width=True)
        with c2:
            st.markdown("<div class='section-title'>🏆 Top Clientes</div>", unsafe_allow_html=True)
            if 'Cliente' in df_final.columns and 'Total' in df_final.columns:
                d_c = df_final.groupby('Cliente')['Total'].sum().reset_index().sort_values('Total', ascending=False).head(10)
                if not d_c.empty:
                    fig_b = px.bar(d_c, x='Total', y='Cliente', orientation='h', color='Total', color_continuous_scale='Blues', text=d_c['Total'].apply(lambda x: f"${x:,.0f}"))
                    fig_b.update_layout(paper_bgcolor='#111827', plot_bgcolor='#111827', font_color='#E2E8F0', showlegend=False, coloraxis_showscale=False, margin=dict(t=20,b=20,l=20,r=20), xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, color='#E2E8F0'), yaxis=dict(showgrid=False, color='#E2E8F0', tickfont=dict(color='#E2E8F0', size=11)))
                    fig_b.update_traces(textposition='outside', textfont=dict(color='#E2E8F0', size=12), marker_line_width=0)
                    st.plotly_chart(fig_b, use_container_width=True)
        cols_show = [c for c in ['Fecha', 'Cliente', 'Marca', 'Proveedor', 'Total', '_codigo_pdv'] if c in df_final.columns]
        if cols_show:
            st.dataframe(df_final[cols_show].sort_values('Fecha', ascending=False), use_container_width=True, hide_index=True, height=320)

    if tab3_enabled and tab3:
        with tab3:
            if not is_super_admin:
                st.error("🔒 Función exclusiva del Super Administrador"); return
            st.markdown("### 🚀 ENVÍO MASIVO DE REPORTES - SOLO ISRAEL")
            vends_all = sorted(df_mes['Vendedor'].dropna().unique().tolist())
            col_info, col_config = st.columns([2, 1])
            with col_info:
                st.info(f"📊 {len(vends_all)} vendedores encontrados en {m_sel}")
            with col_config:
                if not telegram_activo: st.error("📱 Activa Telegram arriba primero")
                else: st.success(f"📱 Enviará a: {chat_destino}")
            st.markdown("---")
            if telegram_activo:
                if st.button("🚀📱 ENVIAR TODOS LOS REPORTES", use_container_width=True, type="primary", key="enviar_todos_masivo"):
                    if not st.session_state.get('confirmacion_masiva', False):
                        st.session_state.confirmacion_masiva = True; st.rerun()
                    st.markdown("### 📤 ENVIANDO REPORTES MASIVOS...")
                    progress_bar = st.progress(0, text="🚀 Iniciando...")
                    chat_id = TELEGRAM_CONFIG['CHAT_IDS'][chat_destino]
                    enviados = 0; errores = 0
                    total_venta = df_vn['SubT_RL'].sum() if not df_vn.empty else df_mes['Total'].sum()
                    total_meta = df_p['M_V'].sum()
                    pct_total = round(total_venta / total_meta * 100, 1) if total_meta > 0 else 0
                    enviar_telegram(f"🚀 <b>ENVÍO MASIVO INICIADO</b>\n📅 {m_sel} | {len(vends_all)} vendedores\n💰 Venta: ${total_venta:,.0f} | Meta: ${total_meta:,.0f} | {pct_total}%", chat_id)
                    for i, v in enumerate(vends_all):
                        progress_bar.progress((i + 1) / len(vends_all), text=f"📊 Enviando: {v[:40]}...")
                        cod_v, nom_v = descomponer_vendedor(v)
                        u_tmp = pd.Series({'_codigo_pdv': cod_v, '_nombre_norm': nom_v})
                        dv, _, _ = filtrar_ventas_usuario(df_mes, u_tmp)
                        pr = filtrar_presupuesto_usuario(df_p, u_tmp)
                        mv_i = float(pr['M_V']) if pr is not None else 0
                        md_i = float(pr['M_DN']) if pr is not None else 0
                        # Obtener KPIs desde VENTAS_NETAS para el reporte masivo
                        vr_i, imp_i, _, _ = obtener_kpis_ventas_netas(df_vn, u_tmp)
                        if vr_i == 0 and imp_i == 0 and not dv.empty:
                            vr_i = dv['Total'].sum()
                            imp_i = dv[dv['Total'] > 0]['Cliente'].nunique()
                        if not dv.empty or vr_i > 0:
                            try:
                                fecha_max_vend = dv['Fecha'].max() if not dv.empty else pd.Timestamp.now()
                                proy_i = calcular_proyeccion(vr_i, fecha_max_vend)
                                msg_i = generar_reporte_telegram(dv if not dv.empty else pd.DataFrame(), mv_i, md_i, v, m_sel, vr_i, imp_i, proy_i)
                                exito, met = enviar_telegram_con_imagen_alternativa(dv if not dv.empty else pd.DataFrame(), mv_i, md_i, v, m_sel, msg_i, chat_id, vr_i, imp_i)
                                if exito: enviados += 1; st.success(f"✅ {v} ({met})")
                                else: errores += 1; st.error(f"❌ {v}")
                            except Exception as e:
                                errores += 1; st.error(f"❌ Error con {v}: {str(e)}")
                        else:
                            st.warning(f"⚠️ Sin datos: {v}")
                    enviar_telegram(f"✅ <b>ENVÍO MASIVO COMPLETADO</b>\n✅ Enviados: {enviados} | ❌ Errores: {errores}\n📅 {m_sel}", chat_id)
                    progress_bar.progress(1.0, text="🎉 ¡COMPLETADO!")
                    st.balloons(); st.success(f"🎉 {enviados} reportes enviados")
                    st.session_state.confirmacion_masiva = False

                if st.session_state.get('confirmacion_masiva', False):
                    st.warning("⚠️ ¿ESTÁS SEGURO? Enviará reportes de TODOS los vendedores")
                    col_si, col_no = st.columns(2)
                    with col_si:
                        if st.button("✅ SÍ, ENVIAR TODO", use_container_width=True): st.rerun()
                    with col_no:
                        if st.button("❌ CANCELAR", use_container_width=True):
                            st.session_state.confirmacion_masiva = False; st.rerun()

                st.markdown("---")
                st.markdown("### 🌅🌙 DASHBOARDS AUTOMÁTICOS")
                col_mat, col_noc = st.columns(2)
                with col_mat:
                    st.markdown("#### 🌅 Dashboard Matutino")
                    if st.button("🌅 Vista Previa", use_container_width=True, key="preview_mat"):
                        st.code(generar_reporte_matutino(), language=None)
                    if st.button("📤 Enviar Matutino", use_container_width=True, type="primary", key="send_mat"):
                        with st.spinner("Enviando..."):
                            if enviar_dashboard_automatico("matutino", chat_destino): st.success("✅ Enviado")
                            else: st.error("❌ Error")
                with col_noc:
                    st.markdown("#### 🌙 Dashboard Nocturno")
                    if st.button("🌙 Vista Previa", use_container_width=True, key="preview_noc"):
                        st.code(generar_reporte_nocturno(), language=None)
                    if st.button("📤 Enviar Nocturno", use_container_width=True, type="primary", key="send_noc"):
                        with st.spinner("Enviando..."):
                            if enviar_dashboard_automatico("nocturno", chat_destino): st.success("✅ Enviado")
                            else: st.error("❌ Error")
            else:
                st.error("📱 Activa Telegram en los controles superiores")

    if tab4_enabled and tab4:
        with tab4:
            _, _, audit = cargar_ventas_presupuesto()
            st.markdown("#### 🔬 Columnas detectadas en VENTAS")
            st.code(str(st.session_state.get('_cols_ventas', [])))
            st.markdown("#### 🔬 Columnas detectadas en VENTAS_NETAS")
            st.code(str(list(df_vn.columns)) if not df_vn.empty else "⚠️ Hoja VENTAS_NETAS no encontrada")
            st.markdown("#### 🛡️ Integridad de Datos")
            if audit.get('monto_perdido', 0) > 0:
                st.error(f"⚠️ ${audit['monto_perdido']:,.2f} fuera del reporte ({audit['filas_afectadas']} filas sin fecha válida)")
                det = audit['detalle_errores']
                cols_det = [c for c in ['Vendedor', 'Total', 'Fecha'] if c in det.columns]
                if cols_det: st.dataframe(det[cols_det], use_container_width=True, hide_index=True)
            else:
                st.success("✅ Fechas 100% íntegras.")
            st.markdown("#### 🔬 Diagnóstico parsing — campo Vendedor")
            muestra = df_mes['Vendedor'].dropna().unique()[:40]
            diag = []
            for v in muestra:
                cod, nom = descomponer_vendedor(v)
                diag.append({'Vendedor original': v, 'Código extraído': cod, 'Nombre extraído': nom})
            st.dataframe(pd.DataFrame(diag), use_container_width=True, hide_index=True)
            st.markdown("#### 🔗 Mapa de Cruce — Usuario_Roles ↔ VENTAS ↔ VENTAS_NETAS ↔ PRESUPUESTO")
            df_users = cargar_usuarios()
            filas = []
            for _, u in df_users.iterrows():
                dv_u, met, _ = filtrar_ventas_usuario(df_mes, u)
                pr_u = filtrar_presupuesto_usuario(df_p, u)
                vr_u, imp_u, met_vn, _ = obtener_kpis_ventas_netas(df_vn, u)
                filas.append({
                    'Usuario': str(u.get('_nombre_orig', '')), 'Código PDV': str(u['_codigo_pdv']),
                    'Ventas #': len(dv_u), 'VENTAS_NETAS $': f"${vr_u:,.0f}" if vr_u > 0 else "—",
                    'DN Netas': imp_u if imp_u > 0 else "—",
                    'Pres. ✓': "✅" if pr_u is not None else "❌", 'Método VN': met_vn,
                })
            st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)


def main():
    if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
    if not st.session_state['logged_in']:
        pantalla_login(); return
    try:
        df_v, df_p, _ = cargar_ventas_presupuesto()
    except ValueError as e:
        st.error(str(e)); st.stop()
    if df_v.empty:
        st.error("❌ Sin datos de ventas en la hoja VENTAS."); return
    dashboard(df_v, df_p, st.session_state.get('user_row', {}))


if __name__ == "__main__":
    main()
