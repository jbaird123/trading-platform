import dash
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

# --- Configuration ---
# Using absolute paths for clarity (wrapped to respect 88-char limit)
OHLC_DATA_PATH = (
    "/Users/jbaird/Documents/personal/trading-platform/data/full/"
    "eurusd_interval_minute_1_20130101_20250823.csv"
)
TRADES_DATA_PATH = (
    "/Users/jbaird/Documents/personal/trading-platform/runs/cli_demo/"
    "run_20250919_235047_utc/trades.csv"
)
RUN_START_DATE = "2023-01-01"
RUN_END_DATE = "2023-01-03"  # Extended to see data after the last trade
FAST_EMA = 10
SLOW_EMA = 20

# --- Data Loading and Preparation ---
# Load OHLC data
ohlc_df = pd.read_csv(
    OHLC_DATA_PATH,
    names=["timestamp", "open", "high", "low", "close", "volume"],
    parse_dates=["timestamp"],
    skiprows=1,  # Added to skip the header row
)

# Filter data to the relevant period for performance
ohlc_df = ohlc_df[
    (ohlc_df["timestamp"] >= pd.to_datetime(RUN_START_DATE, utc=True))
    & (ohlc_df["timestamp"] <= pd.to_datetime(RUN_END_DATE, utc=True))
]
ohlc_df.set_index("timestamp", inplace=True)


# Load trades data
trades_df = pd.read_csv(TRADES_DATA_PATH, parse_dates=["entry_time", "exit_time"])

# Calculate indicators
ohlc_df["ema_fast"] = ohlc_df["close"].ewm(span=FAST_EMA, adjust=False).mean()
ohlc_df["ema_slow"] = ohlc_df["close"].ewm(span=SLOW_EMA, adjust=False).mean()


# --- Chart Creation ---
fig = go.Figure()

# 1. Add Candlestick trace
fig.add_trace(
    go.Candlestick(
        x=ohlc_df.index,
        open=ohlc_df["open"],
        high=ohlc_df["high"],
        low=ohlc_df["low"],
        close=ohlc_df["close"],
        name="OHLC",
    )
)

# 2. Add EMA overlays
fig.add_trace(
    go.Scatter(
        x=ohlc_df.index,
        y=ohlc_df["ema_fast"],
        mode="lines",
        name=f"EMA({FAST_EMA})",
        line=dict(color="cyan", width=1),
    )
)
fig.add_trace(
    go.Scatter(
        x=ohlc_df.index,
        y=ohlc_df["ema_slow"],
        mode="lines",
        name=f"EMA({SLOW_EMA})",
        line=dict(color="magenta", width=1),
    )
)

# 3. Add Trade Markers
fig.add_trace(
    go.Scatter(
        x=trades_df["entry_time"],
        y=trades_df["entry_price"],
        mode="markers",
        name="Entries",
        marker=dict(color="green", symbol="triangle-up", size=10),
    )
)
fig.add_trace(
    go.Scatter(
        x=trades_df["exit_time"],
        y=trades_df["exit_price"],
        mode="markers",
        name="Exits",
        marker=dict(color="red", symbol="triangle-down", size=10),
    )
)

# --- Figure Layout ---
fig.update_layout(
    title="Backtest Run Visualization",
    xaxis_title="Timestamp",
    yaxis_title="Price",
    xaxis_rangeslider_visible=False,
    template="plotly_dark",
)


# --- Dash App ---
app = dash.Dash(__name__)

app.layout = html.Div(
    [
        html.H1("Trade Brief Chart"),
        dcc.Graph(id="trade_chart", figure=fig),
    ]
)

if __name__ == "__main__":
    app.run_server(debug=True)
