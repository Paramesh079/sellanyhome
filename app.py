import pandas as pd
import numpy as np

from statsmodels.tsa.arima.model import ARIMA
from pmdarima import auto_arima
from xgboost import XGBRegressor
from prophet import Prophet

from sklearn.metrics import mean_squared_error

import tkinter as tk
from tkinter import ttk

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# -------------------------
# Load dataset
# -------------------------

transactions = pd.read_csv(
"/home/paramesh/Downloads/sellsanyhome/data/transactions_clean.csv"
)

transactions['Transaction Date'] = pd.to_datetime(transactions['Transaction Date'])

transactions = transactions.sort_values("Transaction Date")

areas = sorted(transactions['Area'].dropna().unique())
property_types = sorted(transactions['Property Type'].dropna().unique())


# -------------------------
# Forecast function
# -------------------------

def run_forecast():

    area = area_var.get()
    ptype = property_var.get()

    df = transactions[
        (transactions['Area'] == area) &
        (transactions['Property Type'] == ptype)
    ]

    if df.empty:

        result_box.delete("1.0", tk.END)
        result_box.insert(tk.END, "No transaction data")

        return

    df = df.set_index('Transaction Date')

    # Weekly aggregation (better for real estate)
    series = df['Amount'].resample("W").median().interpolate()

    split = int(len(series) * 0.8)

    train = series[:split]
    test = series[split:]

    results = {}
    predictions = {}

    # -------------------------
    # ARIMA
    # -------------------------

    auto_model = auto_arima(train, seasonal=False, suppress_warnings=True)

    model = ARIMA(train, order=auto_model.order)
    model_fit = model.fit()

    pred_arima = model_fit.forecast(len(test))

    rmse_arima = np.sqrt(mean_squared_error(test, pred_arima))

    results["ARIMA"] = rmse_arima
    predictions["ARIMA"] = pred_arima


    # -------------------------
    # XGBoost
    # -------------------------
    df_lag = pd.DataFrame({"y": series})

    for i in range(1,6):
        df_lag[f"lag_{i}"] = series.shift(i)

    df_lag.dropna(inplace=True)

    X = df_lag.drop("y", axis=1)
    y = df_lag["y"]

    split2 = int(len(X)*0.8)

    X_train, X_test = X[:split2], X[split2:]
    y_train, y_test = y[:split2], y[split2:]

    model = XGBRegressor(n_estimators=400, max_depth=6)

    model.fit(X_train, y_train)

    pred_xgb = model.predict(X_test)
    print("XGBoost predictions:", len(pred_xgb))

    
    # Create correct datetime index
    xgb_index = y_test.index

    rmse_xgb = np.sqrt(mean_squared_error(y_test, pred_xgb))

    results["XGBoost"] = rmse_xgb
    predictions["XGBoost"] = (xgb_index, pred_xgb)

    
    # -------------------------
    # Prophet
    # -------------------------

    df_prophet = pd.DataFrame()

    df_prophet["ds"] = series.index
    df_prophet["y"] = series.values

    split3 = int(len(df_prophet)*0.8)

    train_p = df_prophet[:split3]
    test_p = df_prophet[split3:]

    model = Prophet()

    model.fit(train_p)

    future = model.make_future_dataframe(periods=len(test_p), freq="W")

    forecast = model.predict(future)

    pred_prophet = forecast["yhat"][-len(test_p):]

    rmse_prophet = np.sqrt(mean_squared_error(test_p["y"], pred_prophet))

    results["Prophet"] = rmse_prophet
    predictions["Prophet"] = pred_prophet


    # -------------------------
    # Model ranking
    # -------------------------

    ranking = pd.DataFrame(
        sorted(results.items(), key=lambda x: x[1]),
        columns=["Model", "RMSE"]
    )

    best_model = ranking.iloc[0]["Model"]

    result_box.delete("1.0", tk.END)

    result_box.insert(tk.END, "Model Ranking\n\n")
    result_box.insert(tk.END, ranking.to_string(index=False))
    result_box.insert(tk.END, f"\n\nBest Model: {best_model}")


    # -------------------------
    # Visualization
    # -------------------------

    ax.clear()

    # Historical transactions
    ax.plot(
        series.index,
        series.values,
        label="Transactions",
        linewidth=2,
        color="black"
    )

    # ARIMA
    ax.plot(
        test.index,
        predictions["ARIMA"],
        label="ARIMA Forecast",
        linestyle="--"
    )

    # Prophet
    ax.plot(
        test.index,
        predictions["Prophet"],
        label="Prophet Forecast",
        linestyle="--"
    )
    
    #xgboost
    xgb_index, xgb_preds = predictions["XGBoost"]

    ax.plot(
        xgb_index,
        xgb_preds,
        label="XGBoost Forecast",
        linestyle="--",
        color="green"
    )
    ax.set_title("Real Estate Price Forecast")

    ax.set_xlabel("Date")
    ax.set_ylabel("Price")

    ax.legend()

    ax.grid(True)

    canvas.draw()


# -------------------------
# GUI
# -------------------------

root = tk.Tk()

root.title("AI Real Estate Forecast Dashboard")

root.geometry("1200x850")


control_frame = tk.Frame(root)
control_frame.pack(pady=10)


tk.Label(control_frame, text="Area").grid(row=0, column=0)

area_var = tk.StringVar()
ttk.Combobox(
    control_frame,
    textvariable=area_var,
    values=areas,
    width=25
).grid(row=0, column=1)


tk.Label(control_frame, text="Property Type").grid(row=0, column=2)

property_var = tk.StringVar()
ttk.Combobox(
    control_frame,
    textvariable=property_var,
    values=property_types,
    width=25
).grid(row=0, column=3)


tk.Button(
    control_frame,
    text="Run Forecast",
    command=run_forecast
).grid(row=0, column=4, padx=10)


result_box = tk.Text(root, height=10, width=140)
result_box.pack()


fig, ax = plt.subplots(figsize=(10,5))

canvas = FigureCanvasTkAgg(fig, master=root)

canvas.get_tk_widget().pack(fill="both", expand=True)


root.mainloop()