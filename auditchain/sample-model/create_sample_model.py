"""
Creates a sample loan approval classifier for demo and testing purposes.

Usage: python create_sample_model.py
Output: loan_classifier.pkl, loan_dataset.csv
"""

import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report

np.random.seed(42)
N = 2000

# Simulate realistic loan approval features
credit_score = np.clip(np.random.normal(680, 80, N), 300, 850)
annual_income = np.clip(np.random.lognormal(10.5, 0.8, N), 20_000, 500_000)
debt_to_income = np.clip(np.random.beta(2, 5, N) * 0.6, 0, 0.6)
employment_years = np.clip(np.random.exponential(5, N), 0, 30)
loan_amount = np.clip(np.random.lognormal(10, 0.6, N), 5_000, 200_000)
num_credit_lines = np.clip(np.random.poisson(5, N), 0, 20)
payment_history = np.clip(np.random.normal(95, 10, N), 0, 100)
loan_purpose = np.random.randint(0, 5, N)
state = np.random.randint(0, 50, N)
age_group = np.random.randint(0, 5, N)  # 0-4 age groups
gender = np.random.binomial(1, 0.45, N)  # 0=male, 1=female

# Target: loan approval (biased slightly toward higher credit + income)
approval_prob = (
    0.4 * (credit_score / 850)
    + 0.25 * (np.log(annual_income) / np.log(500_000))
    + 0.15 * (1 - debt_to_income)
    + 0.1 * (payment_history / 100)
    + 0.1 * np.random.random(N)
)
# Introduce slight gender bias for fairness testing
approval_prob[gender == 1] *= 0.95
approved = (approval_prob > 0.5).astype(int)

X = np.column_stack([
    credit_score, annual_income, debt_to_income, employment_years,
    loan_amount, num_credit_lines, payment_history, loan_purpose, state, age_group
])
y = approved

feature_names = [
    "credit_score", "annual_income", "debt_to_income", "employment_years",
    "loan_amount", "num_credit_lines", "payment_history", "loan_purpose_enc",
    "state_enc", "age_group"
]

# Save dataset
df = pd.DataFrame(X, columns=feature_names)
df["approved"] = y
df["gender"] = gender  # Sensitive attribute for fairness analysis
df.to_csv("loan_dataset.csv", index=False)
print(f"Dataset saved: {len(df)} samples")

# Train model
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

pipeline = Pipeline([
    ("scaler", StandardScaler()),
    ("classifier", RandomForestClassifier(
        n_estimators=100,
        max_depth=8,
        random_state=42,
        n_jobs=-1,
    ))
])

pipeline.fit(X_train, y_train)
y_pred = pipeline.predict(X_test)

print("\nModel Performance:")
print(classification_report(y_test, y_pred, target_names=["Denied", "Approved"]))

# Save model
with open("loan_classifier.pkl", "wb") as f:
    pickle.dump(pipeline, f)

print("\nSample model saved: loan_classifier.pkl")
print("Use this model for testing the AuditChain audit engine.")
