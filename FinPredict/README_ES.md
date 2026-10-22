# FinPredict · Aplicación de escritorio de previsión financiera en tiempo real

**Idioma / Language / Langue / Язык / Idioma**: [中文](README.md) · [English](README_EN.md) · [Français](README_FR.md) · [Русский](README_RU.md) · [Español](README_ES.md)

![Icono de FinPredict](src/finpredict/web/icon.png)

Una aplicación de escritorio de Windows **de doble clic**: obtiene datos oficiales del mercado en tiempo real a través de la red, pronostica tendencias en múltiples horizontes temporales, valida con backtests históricos e incluye análisis de IA multiagente integrado. No requiere instalar Python ni ninguna dependencia.

![Interfaz de cotizaciones en tiempo real](docs/screenshot_quote.png)

## ✨ Funciones principales

| Página | Capacidad |
|--------|-----------|
| 📈 Cotizaciones en vivo | Obtiene velas en línea en 4 horizontes: 1 hora / 3 horas / 1 día / 1 mes; velas + MA + Bandas de Bollinger + RSI + MACD + volumen |
| 🔮 Previsión de tendencias | Dirección multi-horizonte + precio mediano + banda de confianza del 95% (más ancha en horizontes largos); 42 factores + ensamble con probabilidad calibrada |
| 🧪 Backtesting | Validación continua walk-forward: precisión direccional / MAE / Skill / equity de la estrategia vs comprar y mantener |
| 🤖 Asistente de IA | Endpoints compatibles con OpenAI; 5 plantillas de prompt sin escritura; **comité multiagente** (roles técnico / fundamental / riesgo / trader / gestor, inspirado en TradingAgents) |

## 🚀 Inicio rápido

**Opción 1 (recomendada)**: descomprima y haga doble clic en `FinPredict.exe` — cero dependencias, datos precargados al iniciar (instantáneo, sin bloqueos).

**Opción 2 (código fuente)**:
```powershell
py -m pip install -r requirements.txt
py -m finpredict.app
```

**Ejemplos de símbolos**: `000001.SS` (Índice Compuesto SSE) · `0700.HK` (Tencent) · `AAPL` (Apple) · `^GSPC` (S&P 500) · `CL=F` (Petróleo WTI)

## 📡 Fuentes de datos (gratuitas, sin clave API)

| Mercado | Fuente principal | Respaldo |
|---------|------------------|----------|
| Acciones chinas A (.SS/.SZ), acciones de HK (.HK), Hang Seng | Cotizaciones Tencent | — |
| Acciones de EE. UU., índices de EE. UU., materias primas, divisas | yfinance (3 reintentos) | degradación elegante cuando Yahoo limita |

## 🤖 Integración de IA (sin escribir prompts)

Complete cualquier endpoint compatible con OpenAI en la página «Asistente de IA»:

| Endpoint | URL base | Modelo |
|----------|----------|--------|
| Ollama (local) | `http://127.0.0.1:11434/v1` | `qwen2.5:7b` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |

**Plantillas de prompt** (rellenas automáticamente con datos en vivo): Análisis de tendencia · Explicación de anomalías · Atribución de factores · Consejos de acción · Revisión de backtest

**Modo comité**: con un clic ejecuta un análisis multiagente de 5 roles: el analista técnico, el analista fundamental, el analista de riesgo y el trader evalúan de forma independiente; el gestor de cartera pondera todas las opiniones y emite la conclusión final (arquitectura inspirada en TradingAgents / ai-hedge-fund, implementada de forma independiente).

## 🧮 Método de previsión

- **Características**: 42 factores estilo Alpha158 (momentum / precio-volumen / técnico / régimen / estacional, inspirado en Microsoft qlib)
- **Modelos**: ensamble de regresión Ridge + HistGradientBoosting; probabilidades direccionales calibradas mediante regresión isotónica (Logit+HistGBM+ExtraTrees) con ponderaciones de decaimiento temporal
- **Validación**: walk-forward de ventana expansiva, sin mirar el futuro; bandas a partir de cuantiles de residuos móviles
- **Inspirado en**: qlib (ingeniería de factores) · TradingAgents (comité multiagente) · ai-hedge-fund (vistas multiestilo) · Lopez de Prado AFML (calibración + salida selectiva) — solo ideas de arquitectura, cero código copiado

## ⚠️ Límites honestos

**La precisión direccional del 98,7% no es alcanzable fuera de la muestra** (consenso académico; el techo de la previsión direccional diaria ronda el 54-58%). Las previsiones son referencias de escenario; no son consejos de inversión ni ejecutan operaciones.

## 📦 Empaquetado

```powershell
py -m pip install pyinstaller
py -m PyInstaller finpredict.spec --noconfirm
```

## 📄 Licencia

Para investigación y educación. Los derechos de los datos pertenecen a los proveedores originales (Tencent / yfinance); cumpla sus términos.

---

**Proyecto relacionado**: el directorio `../project/` de este repositorio contiene la aplicación hermana **FIN_Terminal** (terminal de investigación multimercado sin conexión: 97 instrumentos, 685 mil filas de historial, fundamentos oficiales de SEC EDGAR, auditoría de precisión del 98,7%), consulte el [README.md](../README.md) raíz.
