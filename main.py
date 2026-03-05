import pandas as pd
from statsmodels.tsa.arima.model import ARIMA

# -----------------------------
# Read Transactions File
# -----------------------------
# If CSV
transactions = pd.read_csv("/home/paramesh/Downloads/sellsanyhome/data/transactions_clean.csv")

# If Excel (use this instead if your file is .xlsx)
# transactions = pd.read_excel("transactions.xlsx")

# -----------------------------
# Parameters
# -----------------------------


# -----------------------------
# Select required columns
# -----------------------------
df = transactions[['Area', 'Property Type', 'Transaction Date', 'Amount']].copy()

# Convert Transaction Date to datetime
df['Transaction Date'] = pd.to_datetime(df['Transaction Date'], errors='coerce')

# Sort hierarchy
df = df.sort_values(
    by=['Area', 'Property Type', 'Transaction Date'],
    ascending=[True, True, True]
)

area_name = "AL Athbah"
property_type = "Land"
# Reset index
df = df.reset_index(drop=True)

# -----------------------------
# Filter specific Area & Property Type
# -----------------------------
df_ts = df[
    (df['Area'] == area_name) &
    (df['Property Type'] == property_type)
].copy()

# Set datetime index
df_ts = df_ts.set_index('Transaction Date')

# -----------------------------
# Create Daily Time Series
# -----------------------------
daily_data = df_ts['Amount'].resample('D').mean()

# Fill missing values
daily_data = daily_data.interpolate()

# -----------------------------
# Train-Test Split
# -----------------------------
train_size = int(len(daily_data) * 0.8)

train = daily_data[:train_size]
test = daily_data[train_size:]

# -----------------------------
# ARIMA Model
# -----------------------------
model = ARIMA(train, order=(1,1,1))
model_fit = model.fit()

# Forecast
forecast = model_fit.forecast(steps=len(test))

# -----------------------------
# Results
# -----------------------------
results = pd.DataFrame({
    "Actual": test.values,
    "Predicted": forecast.values
}, index=test.index)

print(results.head())