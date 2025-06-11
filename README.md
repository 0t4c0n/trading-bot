# 🚀 Trading Bot Automatizado

Sistema automatizado que analiza acciones del NYSE y NASDAQ usando 6 filtros técnicos para generar recomendaciones diarias de inversión.

## 📱 Acceso Móvil

**Tu dashboard estará disponible en:**
`https://[tu-usuario].github.io/[nombre-repo]/`

## ⚙️ Configuración Inicial

### 1. Crear repositorio en GitHub
```bash
# Crear nuevo repositorio público en GitHub llamado "trading-bot"
```

### 2. Estructura de archivos necesaria
```
trading-bot/
├── script.py                 # Tu script original
├── script_automated.py       # Versión para automatización  
├── create_dashboard_data.py   # Generador de JSON
├── requirements.txt           # Dependencias Python
├── .github/
│   └── workflows/
│       └── daily-trading-analysis.yml  # GitHub Action
└── docs/
    └── index.html            # Dashboard móvil
```

### 3. Activar GitHub Pages
1. Ve a **Settings** > **Pages** en tu repositorio
2. En **Source** selecciona **GitHub Actions**
3. Guarda los cambios

### 4. Configurar automatización
El script se ejecutará automáticamente:
- **Horario estándar (Nov-Mar)**: 01:00 UTC = 5h después del cierre (20:00 UTC)
- **Horario de verano (Mar-Nov)**: 00:00 UTC = 5h después del cierre (19:00 UTC)  
- **Días**: Martes a Sábado UTC (equivale a Lunes-Viernes días de mercado US)
- **Duración**: 45-90 minutos (análisis completo de ~3,000-8,000 acciones)
- **Ejecución manual**: Pestaña "Actions" > "Run workflow"

### Horarios de mercado US:
- **EST (Nov-Mar)**: 9:30 AM - 4:00 PM = 14:30 - 20:00 UTC
- **EDT (Mar-Nov)**: 9:30 AM - 4:00 PM = 13:30 - 19:00 UTC

### Hora en España:
- **Horario estándar**: 02:00 (2 AM) 
- **Horario de verano**: 01:00 (1 AM)

## 🔍 Filtros Aplicados

El bot aplica 6 filtros técnicos estrictos:

1. **Volumen**: Promedio 50 días ≥ 300,000
2. **Precio vs MA50**: Entre 0% y +5%
3. **Tendencia MA200**: Debe ser positiva
4. **Último día**: Debe cerrar en positivo
5. **Beneficios**: Último trimestre positivo
6. **Volumen boost**: Último día +25% vs promedio 50d

## 📊 Dashboard Móvil

### Características:
- ✅ **Responsive** para móvil
- 🔥 **Top 10** acciones filtradas con score
- 📈 **Métricas clave** en tiempo real
- 🎯 **Niveles de medias móviles**
- 🔄 **Auto-refresh** cada 5 minutos
- 📱 **Optimizado** para pantallas pequeñas

### Información mostrada:
- **Score total** (0-200 puntos)
- **Precio actual** y variación del día
- **Distancia a MA50** (objetivo: 0-5%)
- **Boost de volumen** vs promedio 50d
- **Niveles MA**: 10, 21, 50, 200 días
- **Sector** y nombre de la empresa

## 🚀 Proceso de Ejecución

### Automático (GitHub Actions):
1. **01:00 UTC (horario estándar) / 00:00 UTC (horario verano)** - Se ejecuta el análisis completo (5h después del cierre)
2. **Descarga** datos de TODAS las acciones NYSE + NASDAQ (~3,000-8,000 acciones)
3. **Procesa** en lotes de 100 acciones para optimizar memoria
4. **Aplica** los 6 filtros técnicos a todo el universo de acciones
5. **Calcula** scores y ranking de las mejores oportunidades
6. **Genera** JSON para dashboard con análisis completo
7. **Publica** en GitHub Pages
8. **Disponible** desde la madrugada en España (análisis del mercado completo)

**⏱️ Duración total**: 45-90 minutos dependiendo del número de acciones disponibles

### Manual:
```bash
# Ejecutar localmente
python script_automated.py
python create_dashboard_data.py
```

## 📈 Interpretación del Score

**Score Total (máximo 200 puntos):**
- **Tendencia** (0-100): Alcista fuerte = 100 pts
- **Volumen** (0-50): Mayor actividad = más puntos  
- **Último día** (0-30): Mayor subida = más puntos
- **MA50 óptimo** (0-20): Cerca del 2.5% ideal = más puntos

**Clasificación:**
- **180-200**: Excelente oportunidad
- **160-179**: Muy buena
- **140-159**: Buena
- **120-139**: Aceptable
- **<120**: Revisar con cuidado

## ⚠️ Consideraciones del Análisis Completo

- **Cobertura total**: ~3,000-8,000 acciones (NYSE + NASDAQ completos)
- **Duración**: 45-90 minutos (vs 3-5 minutos con muestra de 200)
- **Timeout**: GitHub Actions configurado con 2 horas máximo
- **Procesamiento en lotes**: 100 acciones por lote con pausas de 30 segundos
- **Delay**: Datos con 15-20 min de retraso (APIs gratuitas)
- **Filtros estrictos**: Mayor universo = más oportunidades encontradas
- **No es asesoramiento financiero**: Solo análisis técnico automatizado completo

## 🔧 Personalización

### Modificar tamaño de lotes:
Edita `batch_size = 100` en `script_automated.py` (recomendado: 50-150)

### Modificar filtros:
Edita `script_automated.py` en la función `get_current_ma_status()`

### Cambiar horario:
Modifica el `cron` en `.github/workflows/daily-trading-analysis.yml`

### Volver a muestra limitada:
Cambia `symbols_to_process = all_symbols` por `symbols_to_process = all_symbols[:200]`

## 📞 Solución de Problemas

### Error "No data found":
- Verificar conexión a APIs de Yahoo Finance
- Comprobar que no sea fin de semana

### Error en GitHub Actions:
- Revisar logs en pestaña "Actions"
- Verificar que GitHub Pages esté activado

### Dashboard no actualiza:
- Forzar refresh del navegador
- Verificar que el Action se ejecutó correctamente

## 🎯 Próximos Pasos

1. **Copia** todos los archivos a tu repositorio
2. **Activa** GitHub Pages
3. **Espera** a las 22:00 UTC