"""
Train and evaluate the breakout-prediction model.

Trains two models on breakout_features.csv:
  1. Logistic regression baseline (median-imputed features, since
     LogisticRegression can't handle NaN natively)
  2. LightGBM (native NaN handling -- no imputation, per the EDA decision
     to keep all rows/features rather than dropping to the ~271 complete
     rows)

Split is BY DATE, not random -- earlier as_of_dates train, most recent
as_of_dates test. This matters because multiple rows come from the same
track's trajectory; a random split would let the model see a track's
later behavior during training and "cheat" on an earlier test row from
the same track.

Usage:
    python train_breakout_model.py
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report, roc_auc_score
import lightgbm as lgb

FEATURE_COLS = [
    "current_rank", "velocity_1d", "velocity_3d", "velocity_7d",
    "acceleration", "volatility_14d", "days_tracked_so_far", "n_sources_today",
]
TEST_FRACTION = 0.25  # most recent 25% of DATES (not rows) become the test set


def load_labeled_data(path="breakout_features.csv"):
    df = pd.read_csv(path, parse_dates=["as_of_date"])
    return df.dropna(subset=["label"]).reset_index(drop=True)


def split_by_date(df, test_fraction=TEST_FRACTION):
    """Split by as_of_date, not by row -- all rows from the same date
    land on the same side of the split, and no test date precedes any
    train date."""
    dates = sorted(df["as_of_date"].unique())
    cutoff_idx = int(len(dates) * (1 - test_fraction))
    cutoff_date = dates[cutoff_idx]

    train = df[df["as_of_date"] < cutoff_date]
    test = df[df["as_of_date"] >= cutoff_date]
    return train, test, cutoff_date


def evaluate(name, y_true, y_pred, y_proba):
    print(f"\n=== {name} ===")
    print(classification_report(y_true, y_pred, target_names=["no breakout", "breakout"]))
    try:
        auc = roc_auc_score(y_true, y_proba)
        print(f"ROC-AUC: {auc:.3f}")
    except ValueError:
        print("ROC-AUC: undefined (test set has only one class present)")


def main():
    df = load_labeled_data()
    train, test, cutoff_date = split_by_date(df)

    print(f"Total labeled rows: {len(df)}")
    print(f"Train: {len(train)} rows (dates before {cutoff_date.date()})")
    print(f"Test:  {len(test)} rows (dates from {cutoff_date.date()} onward)")

    if len(test) == 0 or len(train) == 0:
        print("\nNot enough date range to split -- need more accumulated days before "
              "a real train/test split is meaningful.")
        return

    X_train, y_train = train[FEATURE_COLS], train["label"]
    X_test, y_test = test[FEATURE_COLS], test["label"]

    # --- Baseline: logistic regression (needs imputed features) ---
    imputer = SimpleImputer(strategy="median")
    X_train_imputed = imputer.fit_transform(X_train)
    X_test_imputed = imputer.transform(X_test)

    logreg = LogisticRegression(max_iter=1000)
    logreg.fit(X_train_imputed, y_train)
    logreg_pred = logreg.predict(X_test_imputed)
    logreg_proba = logreg.predict_proba(X_test_imputed)[:, 1]
    evaluate("Logistic Regression (baseline, median-imputed)", y_test, logreg_pred, logreg_proba)

    # --- Real model: LightGBM (native NaN handling, no imputation) ---
    lgbm = lgb.LGBMClassifier(random_state=42, verbose=-1)
    lgbm.fit(X_train, y_train)
    lgbm_pred = lgbm.predict(X_test)
    lgbm_proba = lgbm.predict_proba(X_test)[:, 1]
    evaluate("LightGBM (native NaN handling)", y_test, lgbm_pred, lgbm_proba)

    # --- Feature importance ---
    print("\n=== LightGBM feature importance ===")
    importance = pd.Series(lgbm.feature_importances_, index=FEATURE_COLS).sort_values(ascending=False)
    print(importance.to_string())
    print("\nNote: current_rank dominating here is expected -- see EDA notebook, "
          "it's mechanically the strongest signal (closer to top-20 already).")


if __name__ == "__main__":
    main()
