import os
import re
import psycopg2
import pandas as pd


DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "postgres",
    "user": "admin",
    "password": "admin123"
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABEL_FILE = os.path.join(BASE_DIR, "labelled_pairs.csv")
OUTPUT_FILE = os.path.join(BASE_DIR, "results", "threshold_evaluation_filtered.csv")


def normalize_text(text):
    if text is None:
        return ""

    text = str(text).lower()
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def word_ngrams(text, n=5):
    tokens = normalize_text(text).split()

    if len(tokens) < n:
        return set()

    return {
        " ".join(tokens[i:i+n])
        for i in range(len(tokens) - n + 1)
    }


def jaccard(a, b):
    if not a and not b:
        return 1.0

    union = a | b

    if not union:
        return 0.0

    return len(a & b) / len(union)


print("Connecting to PostgreSQL...")

conn = psycopg2.connect(**DB_CONFIG)

print("Connected.")
print()
print("Loading filtered notice representations...")

query = """
SELECT notice_id, title, lsh_text_filtered
FROM notices
"""

df_notices = pd.read_sql(query, conn)

print(f"Total notices: {len(df_notices)}")

print()
print("Creating word-5-gram representations...")

representations = {}

for _, row in df_notices.iterrows():
    title = row["title"] or ""
    body = row["lsh_text_filtered"] or ""

    combined = f"{title} {body}"

    representations[row["notice_id"]] = word_ngrams(
        combined,
        n=5
    )

print(f"Representations created: {len(representations)}")

print()
print("Loading labelled pairs...")

pairs = pd.read_csv(LABEL_FILE)

print(f"Labelled pairs: {len(pairs)}")

print()
print("Label distribution:")
print(pairs["label"].value_counts())

print()
print("Calculating Jaccard similarities...")

scores = []

for _, row in pairs.iterrows():

    a = row["notice_id_a"]
    b = row["notice_id_b"]

    score = jaccard(
        representations[a],
        representations[b]
    )

    scores.append(score)

pairs["jaccard"] = scores

thresholds = [
    0.50,
    0.55,
    0.60,
    0.65,
    0.70,
    0.75,
    0.80,
    0.85,
    0.90,
    0.95
]

results = []

print()
print("=" * 46)
print("FILTERED REPRESENTATION THRESHOLD EVALUATION")
print("=" * 46)

for threshold in thresholds:

    predicted_same = pairs["jaccard"] >= threshold

    actual_same = pairs["label"] == "same"
    actual_different = pairs["label"] == "different"

    tp = int((predicted_same & actual_same).sum())
    fp = int((predicted_same & actual_different).sum())
    tn = int((~predicted_same & actual_different).sum())
    fn = int((~predicted_same & actual_same).sum())

    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0

    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0
    )

    results.append({
        "threshold": threshold,
        "TP": tp,
        "FP": fp,
        "TN": tn,
        "FN": fn,
        "precision": precision,
        "recall": recall,
        "F1": f1
    })

    print()
    print(f"Threshold = {threshold:.2f}")
    print(f"TP={tp}  FP={fp}  TN={tn}  FN={fn}")
    print(f"Precision={precision:.4f}  Recall={recall:.4f}  F1={f1:.4f}")


results_df = pd.DataFrame(results)

print()
print("=" * 46)
print("COST SENSITIVITY ANALYSIS")
print("=" * 46)

for ratio in [10, 50, 100]:

    print()
    print(
        f"Assumed cost ratio: "
        f"False Merge : False Split = {ratio}:1"
    )

    results_df[f"cost_{ratio}_to_1"] = (
        results_df["FP"] * ratio +
        results_df["FN"]
    )

    for _, row in results_df.iterrows():

        print(
            f"Threshold {row['threshold']:.2f} "
            f"-> FP={int(row['FP'])}, "
            f"FN={int(row['FN'])}, "
            f"cost={int(row[f'cost_{ratio}_to_1'])}"
        )

    best = results_df.loc[
        results_df[f"cost_{ratio}_to_1"].idxmin()
    ]

    print(f"Minimum measured cost: {int(best[f'cost_{ratio}_to_1'])}")
    print(
        f"Threshold achieving it: "
        f"{best['threshold']:.2f}"
    )


os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

results_df.to_csv(
    OUTPUT_FILE,
    index=False
)

print()
print("=" * 46)
print("FILTERED THRESHOLD EVALUATION COMPLETE")
print("=" * 46)
print(f"Results saved to: {OUTPUT_FILE}")

conn.close()