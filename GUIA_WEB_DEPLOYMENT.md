# 🚀 GUÍA: SUBIR DASHBOARD PDV A LA WEB

## 📋 PASOS PARA DEPLOYER EN STREAMLIT CLOUD:

### 1. 📁 PREPARAR ARCHIVOS
Necesitas estos archivos en una carpeta:
```
📁 pdv-dashboard/
├── 📄 dashboard_pdv_corregido.py
├── 📄 requirements.txt
├── 📄 credenciales.json (tu archivo de Google)
└── 📁 .streamlit/
    └── 📄 config.toml
```

### 2. 🔗 CREAR REPOSITORIO EN GITHUB
1. Ve a: https://github.com
2. Haz clic: "New repository"
3. Nombre: `pdv-dashboard-soluto`
4. Público o Privado: elige según prefieras
5. Sube todos los archivos

⚠️ **IMPORTANTE**: NO subas `credenciales.json` a GitHub público por seguridad

### 3. 🌐 DEPLOYER EN STREAMLIT CLOUD
1. Ve a: https://share.streamlit.io
2. Conecta tu cuenta GitHub
3. Haz clic: "New app"
4. Selecciona tu repositorio: `pdv-dashboard-soluto`
5. Main file: `dashboard_pdv_corregido.py`
6. Haz clic: "Deploy!"

### 4. 🔐 CONFIGURAR SECRETOS (PARA CREDENCIALES)
En Streamlit Cloud:
1. Ve a tu app → Settings → Secrets
2. Pega el contenido de `credenciales.json`:

```toml
[google]
type = "service_account"
project_id = "tu-project-id"
private_key_id = "tu-private-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\ntu-private-key\n-----END PRIVATE KEY-----\n"
client_email = "tu-service-email"
client_id = "tu-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
```

### 5. 🔧 MODIFICAR CÓDIGO PARA SECRETOS
Cambia esta línea en tu dashboard:
```python
# ANTES:
creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)

# DESPUÉS:
import json
creds_dict = dict(st.secrets["google"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
```

### 6. 📱 INTEGRAR CON APPSHEET
Una vez deployado tendrás una URL como:
`https://tu-app-name.streamlit.app`

En AppSheet:
1. Crea una vista tipo "Link"
2. URL: `https://tu-app-name.streamlit.app`
3. Tipo: "Web Link"
4. ¡Ya tienes acceso directo!

## 🎯 RESULTADO FINAL:
- ✅ Dashboard accesible desde cualquier dispositivo
- ✅ Link directo desde AppSheet
- ✅ Actualización en tiempo real
- ✅ Sin mensajes debug feos
- ✅ Solo Israel tiene acceso a envío masivo

## 📱 EJEMPLO DE INTEGRACIÓN APPSHEET:
```
[Botón: 📊 Ver Dashboard PDV]
→ Abre: https://tu-dashboard.streamlit.app
→ Login automático por nombre de usuario
→ Ve sus métricas personales
```

## 🔒 SEGURIDAD:
- Login por PIN funciona igual
- Cada vendedor solo ve sus datos
- Israel tiene acceso completo
- Credenciales protegidas en Streamlit Secrets
