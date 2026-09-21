import re
import glob
import hashlib
import random
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
# SETTINGS
# ============================================================

# Number of MinHash values we want to test
SIGNATURE_SIZES = [32, 64, 128, 256]

# Word 5-grams are our selected representation from A(a)
NGRAM_SIZE = 5

# Large prime used by MinHash
PRIME = 4294967311

# Maximum 32-bit value
MAX_HASH = 4294967295

# Reproducible random coefficients
random.seed(42)


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

    # Remove repeated whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ============================================================
# WORD N-GRAMS
# ============================================================

def word_ngrams(text, n):

    tokens = normalize_text(text).split()

    if len(tokens) < n:
        return set()

    return {
        tuple(tokens[i:i+n])
        for i in range(len(tokens) - n + 1)
    }


# ============================================================
# EXACT JACCARD
# ============================================================

def jaccard(set_a, set_b):

    if not set_a and not set_b:
        return 1.0

    if not set_a or not set_b:
        return 0.0

    return len(set_a & set_b) / len(set_a | set_b)


# ============================================================
# STABLE HASH FOR AN N-GRAM
# ============================================================

def hash_ngram(ngram):

    # Convert tuple to one stable string
    text = " ".join(ngram)

    digest = hashlib.md5(
        text.encode("utf-8")
    ).hexdigest()

    return int(digest, 16) % PRIME


# ============================================================
# CREATE MINHASH PARAMETERS
# ============================================================

MAX_SIGNATURE_SIZE = max(SIGNATURE_SIZES)

hash_a = []
hash_b = []

for _ in range(MAX_SIGNATURE_SIZE):

    a = random.randint(1, PRIME - 1)
    b = random.randint(0, PRIME - 1)

    hash_a.append(a)
    hash_b.append(b)


# ============================================================
# CREATE MINHASH SIGNATURE
# ============================================================

def create_minhash(shingles):

    if not shingles:

        return [
            PRIME
            for _ in range(MAX_SIGNATURE_SIZE)
        ]

    base_hashes = [
        hash_ngram(shingle)
        for shingle in shingles
    ]

    signature = []

    for i in range(MAX_SIGNATURE_SIZE):

        a = hash_a[i]
        b = hash_b[i]

        minimum = PRIME

        for h in base_hashes:

            value = (
                (a * h + b)
                % PRIME
            )

            if value < minimum:
                minimum = value

        signature.append(minimum)

    return signature


# ============================================================
# MINHASH SIMILARITY
# ============================================================

def minhash_similarity(signature_a, signature_b, k):

    if k == 0:
        return 0.0

    equal_count = 0

    for i in range(k):

        if signature_a[i] == signature_b[i]:
            equal_count += 1

    return equal_count / k


# ============================================================
# LOAD NOTICES
# ============================================================

print("Loading notice files...")

files = sorted(
    glob.glob(
        str(NOTICE_DIR / "*.csv")
    )
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
                "body"
            ]
        )
        for f in files
    ],
    ignore_index=True
)

print("Total notices:", len(notices))


# ============================================================
# NOTICE LOOKUP
# ============================================================

notice_lookup = notices.set_index(
    "notice_id"
).to_dict("index")


# ============================================================
# LOAD LABELLED PAIRS
# ============================================================

labels = pd.read_csv(
    LABEL_FILE
)

print(
    "Labelled pairs:",
    len(labels)
)


# ============================================================
# CACHE MINHASH SIGNATURES
# ============================================================

print("\nCreating MinHash signatures...")

signature_cache = {}

unique_ids = set(
    labels["notice_id_a"]
).union(
    set(labels["notice_id_b"])
)

for count, notice_id in enumerate(
    unique_ids,
    start=1
):

    notice = notice_lookup[notice_id]

    text = (
        str(notice["title"])
        + " "
        + str(notice["body"])
    )

    shingles = word_ngrams(
        text,
        NGRAM_SIZE
    )

    signature_cache[notice_id] = create_minhash(
        shingles
    )

    if count % 100 == 0:
        print(
            f"Created signatures for "
            f"{count}/{len(unique_ids)} notices"
        )


print(
    "Signature creation complete."
)


# ============================================================
# LOAD EXACT WORD-5 RESULTS
# ============================================================

exact_file = (
    RESULT_DIR /
    "similarity_results.csv"
)

exact_results = pd.read_csv(
    exact_file
)

exact_lookup = {}

for _, row in exact_results.iterrows():

    key = (
        row["notice_id_a"],
        row["notice_id_b"]
    )

    exact_lookup[key] = row[
        "word5_jaccard"
    ]


# ============================================================
# RUN MINHASH EXPERIMENT
# ============================================================

results = []

print(
    "\nRunning MinHash experiments..."
)

for index, row in labels.iterrows():

    id_a = row["notice_id_a"]
    id_b = row["notice_id_b"]

    signature_a = signature_cache[id_a]
    signature_b = signature_cache[id_b]

    exact = exact_lookup[
        (id_a, id_b)
    ]

    result = {
        "notice_id_a": id_a,
        "notice_id_b": id_b,
        "label": row["label"],
        "exact_word5_jaccard": exact
    }

    for k in SIGNATURE_SIZES:

        estimated = minhash_similarity(
            signature_a,
            signature_b,
            k
        )

        error = abs(
            estimated - exact
        )

        result[
            f"minhash_{k}"
        ] = estimated

        result[
            f"error_{k}"
        ] = error

    results.append(result)

    if (index + 1) % 100 == 0:

        print(
            f"Processed "
            f"{index + 1}/{len(labels)} pairs"
        )


results_df = pd.DataFrame(
    results
)


# ============================================================
# SAVE DETAILED RESULTS
# ============================================================

detailed_file = (
    RESULT_DIR /
    "minhash_results.csv"
)

results_df.to_csv(
    detailed_file,
    index=False
)

print(
    "\nDetailed results saved to:"
)

print(detailed_file)


# ============================================================
# ERROR SUMMARY
# ============================================================

summary_rows = []

for k in SIGNATURE_SIZES:

    errors = results_df[
        f"error_{k}"
    ]

    mae = errors.mean()

    rmse = (
        (errors ** 2).mean()
        ** 0.5
    )

    p95 = errors.quantile(
        0.95
    )

    maximum = errors.max()

    summary_rows.append(
        {
            "signature_size": k,
            "MAE": mae,
            "RMSE": rmse,
            "P95_absolute_error": p95,
            "MAX_absolute_error": maximum
        }
    )


summary_df = pd.DataFrame(
    summary_rows
)

summary_df = summary_df.round(6)


# ============================================================
# SAVE SUMMARY
# ============================================================

summary_file = (
    RESULT_DIR /
    "minhash_error_summary.csv"
)

summary_df.to_csv(
    summary_file,
    index=False
)


# ============================================================
# PRINT SUMMARY
# ============================================================

print(
    "\n========================================"
)

print(
    "MINHASH ERROR SUMMARY"
)

print(
    "========================================"
)

print(
    summary_df.to_string(
        index=False
    )
)


# ============================================================
# ERROR BY LABEL
# ============================================================

print(
    "\n========================================"
)

print(
    "ERROR BY LABEL"
)

print(
    "========================================"
)

for k in SIGNATURE_SIZES:

    print(
        f"\nMinHash size: {k}"
    )

    grouped = (
        results_df
        .groupby("label")[
            f"error_{k}"
        ]
        .agg(
            [
                "count",
                "mean",
                "median",
                "max"
            ]
        )
        .round(6)
    )

    print(grouped)


# ============================================================
# SHOW WORST ERRORS
# ============================================================

print(
    "\n========================================"
)

print(
    "WORST MINHASH ERRORS"
)

print(
    "========================================"
)

for k in SIGNATURE_SIZES:

    print(
        f"\nMinHash size: {k}"
    )

    worst = (
        results_df
        .sort_values(
            f"error_{k}",
            ascending=False
        )
        .head(5)
    )

    print(
        worst[
            [
                "notice_id_a",
                "notice_id_b",
                "label",
                "exact_word5_jaccard",
                f"minhash_{k}",
                f"error_{k}"
            ]
        ].to_string(
            index=False
        )
    )


# ============================================================
# FINAL MESSAGE
# ============================================================

print(
    "\n========================================"
)

print(
    "MINHASH EXPERIMENT COMPLETE"
)

print(
    "========================================"
)

print(
    "\nCreated files:"
)

print(
    "1.",
    detailed_file
)

print(
    "2.",
    summary_file
)