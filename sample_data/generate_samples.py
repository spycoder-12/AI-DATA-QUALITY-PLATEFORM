"""Generate demo datasets (deterministic). Run:  python sample_data/generate_samples.py

Creates in sample_data/:
  customers_reference.csv   clean baseline (for drift comparison)
  customers_current.csv     same schema with realistic problems + distribution shift
  series/customers_v1..v6.csv  six uploads of the "same" dataset with gradually worsening quality
                               (upload them in order, all named customers.csv, to build monitoring history)
"""
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).parent
CITIES = ["Mumbai", "Delhi", "Pune", "Chennai", "Kolkata"]


def base(n, seed, income_scale=1.0, city_p=None, age_mu=38):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "customer_id": np.arange(1, n + 1),
        "age": np.clip(rng.normal(age_mu, 10, n), 18, 80).round().astype(int),
        "annual_income": (rng.lognormal(10.9, 0.35, n) * income_scale).round(-2),
        "city": rng.choice(CITIES, n, p=city_p or [0.30, 0.25, 0.2, 0.15, 0.10]),
        "gender": rng.choice(["M", "F"], n),
        "monthly_purchases": rng.poisson(6, n),
        "satisfaction_score": np.clip(rng.normal(72, 12, n), 0, 100).round(1),
    })
    return df


def degrade(df, seed, level):
    """level 0 = clean ... 5 = badly broken."""
    rng = np.random.default_rng(seed)
    df = df.copy()
    n = len(df)
    if level >= 1:
        df.loc[rng.choice(n, int(n * 0.01 * level), replace=False), "annual_income"] = np.nan
    if level >= 2:
        df.loc[rng.choice(n, int(n * 0.005 * level), replace=False), "age"] = np.nan
        df = pd.concat([df, df.sample(int(n * 0.004 * level), random_state=seed)], ignore_index=True)
    if level >= 2:
        idx = rng.choice(len(df), 2 * level, replace=False)
        df.loc[idx, "age"] = rng.choice([150, 185, 200, -5], len(idx))
        idx = rng.choice(len(df), level, replace=False)
        df.loc[idx, "annual_income"] = df["annual_income"].max() * rng.uniform(8, 15, len(idx))
    if level >= 3:
        idx = rng.choice(len(df), 6 * level, replace=False)
        df.loc[idx, "city"] = df.loc[idx, "city"].str.upper()
        idx = rng.choice(len(df), 4 * level, replace=False)
        df.loc[idx, "city"] = " " + df.loc[idx, "city"].astype(str)
    return df


if __name__ == "__main__":
    (OUT / "series").mkdir(exist_ok=True)
    base(800, 1).to_csv(OUT / "customers_reference.csv", index=False)
    cur = base(800, 2, income_scale=1.35, city_p=[0.12, 0.18, 0.25, 0.20, 0.25], age_mu=44)
    degrade(cur, 22, 3).to_csv(OUT / "customers_current.csv", index=False)
    for v in range(1, 7):
        degrade(base(800, 100 + v), 200 + v, min(v - 1, 5)).to_csv(OUT / "series" / f"customers_v{v}.csv", index=False)
    print("sample datasets written to", OUT)
