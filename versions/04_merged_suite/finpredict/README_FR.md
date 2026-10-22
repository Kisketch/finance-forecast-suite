# FinPredict · Application de bureau de prévision financière en temps réel

**Langue / Language / Langue / Язык / Idioma** : [中文](README.md) · [English](README_EN.md) · [Français](README_FR.md) · [Русский](README_RU.md) · [Español](README_ES.md)

![Icône FinPredict](src/finpredict/web/icon.png)

Une application de bureau Windows **à double-clic** : récupère en temps réel les données officielles de marché, prévoit les tendances sur plusieurs horizons temporels, valide par backtests historiques et inclut une analyse IA multi-agents intégrée. Aucune installation de Python ni de dépendance requise.

![Interface de cotations en temps réel](docs/screenshot_quote.png)

## ✨ Fonctionnalités principales

| Page | Capacité |
|------|----------|
| 📈 Cotations en direct | Récupération en ligne de chandeliers sur 4 horizons : 1 heure / 3 heures / 1 jour / 1 mois ; chandelier + MM + Bandes de Bollinger + RSI + MACD + volumes |
| 🔮 Prévision de tendance | Direction multi-horizons + prix médian + intervalle de confiance à 95 % (plus large pour les horizons longs) ; 42 facteurs + ensemble calibré en probabilité |
| 🧪 Backtest | Validation glissante walk-forward : précision directionnelle / MAE / Skill / equity de la stratégie vs achat-conservation |
| 🤖 Assistant IA | Points de terminaison compatibles OpenAI ; 5 modèles de prompts sans écriture ; **comité multi-agents** (rôles technique / fondamental / risque / trader / gestionnaire, inspiré de TradingAgents) |

## 🚀 Démarrage rapide

**Option 1 (recommandée)** : décompressez puis double-cliquez sur `FinPredict.exe` — zéro dépendance, données pré-chargées au lancement (instantané, sans blocage).

**Option 2 (code source)** :
```powershell
py -m pip install -r requirements.txt
py -m finpredict.app
```

**Exemples de symboles** : `000001.SS` (Composite SSE) · `0700.HK` (Tencent) · `AAPL` (Apple) · `^GSPC` (S&P 500) · `CL=F` (Pétrole WTI)

## 📡 Sources de données (gratuites, sans clé API)

| Marché | Source principale | Secours |
|--------|-------------------|---------|
| Actions chinoises A (.SS/.SZ), actions HK (.HK), Hang Seng | Cotations Tencent | — |
| Actions US, indices US, matières premières, FX | yfinance (3 tentatives) | dégradation élégante en cas de limitation Yahoo |

## 🤖 Intégration IA (sans écrire de prompts)

Saisissez n'importe quel point de terminaison compatible OpenAI sur la page « Assistant IA » :

| Point de terminaison | URL de base | Modèle |
|----------------------|-------------|--------|
| Ollama (local) | `http://127.0.0.1:11434/v1` | `qwen2.5:7b` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |

**Modèles de prompts** (remplis automatiquement avec les données en direct) : Analyse de tendance · Explication d'anomalies · Attribution factorielle · Conseils d'action · Revue de backtest

**Mode comité** : en un clic, lancez une analyse multi-agents à 5 rôles — l'analyste technique, l'analyste fondamental, l'analyste risque et le trader évaluent indépendamment ; le gestionnaire de portefeuille pèse toutes les opinions et livre la conclusion finale (architecture inspirée de TradingAgents / ai-hedge-fund, implémentée de manière indépendante).

## 🧮 Méthode de prévision

- **Caractéristiques** : 42 facteurs de style Alpha158 (momentum / prix-volume / technique / régime / saisonnier, inspiré de Microsoft qlib)
- **Modèles** : ensemble de régression Ridge + HistGradientBoosting ; probabilités directionnelles calibrées par régression isotonique (Logit+HistGBM+ExtraTrees) avec pondération à décroissance temporelle
- **Validation** : walk-forward à fenêtre extensible, aucune fuite du futur ; bandes issues de quantiles de résidus glissants
- **Inspirations** : qlib (ingénierie factorielle) · TradingAgents (comité multi-agents) · ai-hedge-fund (vues multi-styles) · Lopez de Prado AFML (calibration + sortie sélective) — idées d'architecture uniquement, aucun code copié

## ⚠️ Limites honnêtes

**Une précision directionnelle de 98,7 % est inatteignable hors échantillon** (consensus académique ; le plafond de la prévision directionnelle quotidienne est d'environ 54-58 %). Les prévisions sont des références de scénario — pas des conseils de trading, aucune exécution d'ordres.

## 📦 Empaquetage

```powershell
py -m pip install pyinstaller
py -m PyInstaller finpredict.spec --noconfirm
```

## 📄 Licence

À des fins de recherche et d'éducation. Les droits sur les données appartiennent aux fournisseurs d'origine (Tencent / yfinance) ; veuillez respecter leurs conditions.

---

**Projet associé** : le répertoire `../project/` de ce dépôt contient l'application sœur **FIN_Terminal** (terminal de recherche multi-marchés hors ligne : 97 instruments, 685 000 lignes d'historique, données fondamentales officielles SEC EDGAR, audit de précision de 98,7 %), voir le [README.md](../README.md) racine.
