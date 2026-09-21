import re
import glob
from pathlib import Path
import pandas as pd

# ============================================================
# PATHS
# ============================================================

BASE = Path(r"C:\Users\Shuaib Ahmed\Downloads\data_2\data_2")
NOTICE_DIR = BASE / "notices"
LABEL_FILE = BASE / "labelled_pairs.csv"
RESULT_DIR = BASE / "results"

RESULT_DIR.mkdir(exist_ok=True)


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text):
    if pd.isna(text):
        return ""

    text = str(text).lower()

    # Remove URLs
    text = re.sub(r"https?://\S+", " ", text)

    # Keep letters, numbers and spaces
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Remove extra spaces
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ============================================================
# WORD N-GRAMS
# ============================================================

def word_tokens(text):
    return normalize_text(text).split()


def word_ngrams(text, n):
    tokens = word_tokens(text)

    if len(tokens) < n:
        return set()

    return {
        tuple(tokens[i:i+n])
        for i in range(len(tokens) - n + 1)
    }


# ============================================================
# CHARACTER N-GRAMS
# ============================================================

def char_ngrams(text, n):
    text = normalize_text(text)

    if len(text) < n:
        return set()

    return {
        text[i:i+n]
        for i in range(len(text) - n + 1)
    }


# ============================================================
# JACCARD SIMILARITY
# ============================================================

def jaccard(a, b):

    if not a and not b:
        return 1.0

    if not a or not b:
        return 0.0

    intersection = len(a & b)
    union = len(a | b)

    return intersection / union


# ============================================================
# LOAD NOTICE FILES
# ============================================================

print("Loading notice files...")

files = sorted(
    glob.glob(str(NOTICE_DIR / "*.csv"))
)

print("Notice files found:", len(files))

notices = pd.concat(
    [
        pd.read_csv(
            f,
            usecols=[
                "notice_id",
                "portal_id",
                "title",
                "body",
                "estimated_value",
                "closing_date"
            ]
        )
        for f in files
    ],
    ignore_index=True
)

print("Total notices:", len(notices))


# ============================================================
# CREATE NOTICE LOOKUP
# ============================================================

notice_lookup = notices.set_index(
    "notice_id"
).to_dict("index")


# ============================================================
# LOAD LABELLED PAIRS
# ============================================================

labels = pd.read_csv(LABEL_FILE)

print("Labelled pairs:", len(labels))

print("\nLabel distribution:")
print(labels["label"].value_counts())


# ============================================================
# CALCULATE SIMILARITY
# ============================================================

results = []

print("\nProcessing labelled pairs...\n")

for i, row in labels.iterrows():

    id_a = row["notice_id_a"]
    id_b = row["notice_id_b"]

    notice_a = notice_lookup[id_a]
    notice_b = notice_lookup[id_b]

    # Combine title + body
    text_a = (
        str(notice_a["title"])
        + " "
        + str(notice_a["body"])
    )

    text_b = (
        str(notice_b["title"])
        + " "
        + str(notice_b["body"])
    )

    # Word 3-grams
    word3_a = word_ngrams(text_a, 3)
    word3_b = word_ngrams(text_b, 3)

    # Word 5-grams
    word5_a = word_ngrams(text_a, 5)
    word5_b = word_ngrams(text_b, 5)

    # Character 5-grams
    char5_a = char_ngrams(text_a, 5)
    char5_b = char_ngrams(text_b, 5)

    # Calculate Jaccard
    word3_similarity = jaccard(
        word3_a,
        word3_b
    )

    word5_similarity = jaccard(
        word5_a,
        word5_b
    )

    char5_similarity = jaccard(
        char5_a,
        char5_b
    )

    results.append(
        {
            "notice_id_a": id_a,
            "notice_id_b": id_b,
            "label": row["label"],
            "word3_jaccard": word3_similarity,
            "word5_jaccard": word5_similarity,
            "char5_jaccard": char5_similarity
        }
    )

    if (i + 1) % 100 == 0:
        print(
            f"Processed {i + 1}/{len(labels)} pairs"
        )


# ============================================================
# SAVE RESULTS
# ============================================================

results_df = pd.DataFrame(results)

output_file = RESULT_DIR / "similarity_results.csv"

results_df.to_csv(
    output_file,
    index=False
)

print("\nResults saved to:")
print(output_file)


# ============================================================
# SUMMARY
# ============================================================

methods = [
    "word3_jaccard",
    "word5_jaccard",
    "char5_jaccard"
]

for method in methods:

    print("\n========================================")
    print("METHOD:", method)
    print("========================================")

    summary = (
        results_df
        .groupby("label")[method]
        .agg(
            [
                "count",
                "mean",
                "median",
                "min",
                "max"
            ]
        )
        .round(4)
    )

    print(summary)


# ============================================================
# HIGHEST SIMILARITY DIFFERENT PAIRS
# ============================================================

print("\n========================================")
print("HIGHEST-SIMILARITY DIFFERENT PAIRS")
print("========================================")

different_pairs = (
    results_df[
        results_df["label"] == "different"
    ]
    .sort_values(
        "word5_jaccard",
        ascending=False
    )
    .head(10)
)

print(
    different_pairs.to_string(index=False)
)


# ============================================================
# LOWEST SIMILARITY SAME PAIRS
# ============================================================

print("\n========================================")
print("LOWEST-SIMILARITY SAME PAIRS")
print("========================================")

same_pairs = (
    results_df[
        results_df["label"] == "same"
    ]
    .sort_values(
        "word5_jaccard",
        ascending=True
    )
    .head(10)
)

print(
    same_pairs.to_string(index=False)
)


# ============================================================
# HIGHEST-SIMILARITY SAME PAIRS
# ============================================================

print("\n========================================")
print("HIGHEST-SIMILARITY SAME PAIRS")
print("========================================")

same_high = (
    results_df[
        results_df["label"] == "same"
    ]
    .sort_values(
        "word5_jaccard",
        ascending=False
    )
    .head(10)
)

print(
    same_high.to_string(index=False)
)


print("\n========================================")
print("EXPERIMENT COMPLETE")
print("========================================")