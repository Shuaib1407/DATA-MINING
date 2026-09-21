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

SIGNATURE_SIZE = 128
NGRAM_SIZE = 5

# 32 x 4 = 128
# 16 x 8 = 128
# 8 x 16 = 128
CONFIGURATIONS = {
    "32x4": (32, 4),
    "16x8": (16, 8),
    "8x16": (8, 16)
}

PRIME = 4294967311

random.seed(42)


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text):

    if pd.isna(text):
        return ""

    text = str(text).lower()

    # Remove URLs
    text = re.sub(
        r"https?://\S+",
        " ",
        text
    )

    # Keep letters, numbers and spaces
    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text
    )

    # Remove extra spaces
    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    return text


# ============================================================
# WORD 5-GRAMS
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
# STABLE HASH
# ============================================================

def hash_ngram(ngram):

    text = " ".join(ngram)

    digest = hashlib.md5(
        text.encode("utf-8")
    ).hexdigest()

    return int(digest, 16) % PRIME


# ============================================================
# MINHASH PARAMETERS
# ============================================================

hash_a = [
    random.randint(1, PRIME - 1)
    for _ in range(SIGNATURE_SIZE)
]

hash_b = [
    random.randint(0, PRIME - 1)
    for _ in range(SIGNATURE_SIZE)
]


# ============================================================
# CREATE MINHASH SIGNATURE
# ============================================================

def create_minhash(shingles):

    if not shingles:

        return [
            PRIME
            for _ in range(SIGNATURE_SIZE)
        ]

    base_hashes = [
        hash_ngram(shingle)
        for shingle in shingles
    ]

    signature = []

    for i in range(SIGNATURE_SIZE):

        minimum = PRIME

        a = hash_a[i]
        b = hash_b[i]

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
# LOAD NOTICE FILES
# ============================================================

print("Loading notice files...")

files = sorted(
    glob.glob(
        str(NOTICE_DIR / "*.csv")
    )
)

print(
    "Notice files found:",
    len(files)
)

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

print(
    "Total notices:",
    len(notices)
)


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
# CREATE MINHASH SIGNATURES
# ============================================================

print()
print(
    "Creating 128-value MinHash signatures "
    "for the labelled notices..."
)

signature_cache = {}

unique_ids = set(
    labels["notice_id_a"]
).union(
    set(labels["notice_id_b"])
)

unique_ids = sorted(unique_ids)

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

    signature_cache[notice_id] = (
        create_minhash(shingles)
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
# BUILD LSH BUCKETS
# ============================================================

def build_lsh_buckets(
    signatures,
    bands,
    rows
):

    buckets = {}

    for notice_id, signature in signatures.items():

        for band in range(bands):

            start = band * rows
            end = start + rows

            band_values = tuple(
                signature[start:end]
            )

            key = (
                band,
                band_values
            )

            if key not in buckets:

                buckets[key] = []

            buckets[key].append(
                notice_id
            )

    return buckets


# ============================================================
# GET CANDIDATES
# ============================================================

def get_candidates(
    notice_id,
    signature,
    buckets,
    bands,
    rows
):

    candidates = set()

    for band in range(bands):

        start = band * rows
        end = start + rows

        band_values = tuple(
            signature[start:end]
        )

        key = (
            band,
            band_values
        )

        if key in buckets:

            for candidate in buckets[key]:

                if candidate != notice_id:

                    candidates.add(
                        candidate
                    )

    return candidates


# ============================================================
# LOAD EXACT WORD-5 SIMILARITIES
# ============================================================

similarity_file = (
    RESULT_DIR /
    "similarity_results.csv"
)

similarities = pd.read_csv(
    similarity_file
)

similarity_lookup = {}

for _, row in similarities.iterrows():

    key = (
        row["notice_id_a"],
        row["notice_id_b"]
    )

    similarity_lookup[key] = (
        row["word5_jaccard"]
    )


# ============================================================
# STORAGE FOR ALL RESULTS
# ============================================================

all_candidate_counts = []

all_pair_results = []

configuration_summary = []


# ============================================================
# RUN EACH LSH CONFIGURATION
# ============================================================

for config_name, config in CONFIGURATIONS.items():

    bands, rows = config

    print()
    print(
        "========================================"
    )

    print(
        "LSH CONFIGURATION:",
        config_name
    )

    print(
        "Bands:",
        bands
    )

    print(
        "Rows per band:",
        rows
    )

    print(
        "========================================"
    )


    # ========================================================
    # BUILD BUCKETS
    # ========================================================

    print()
    print(
        "Building LSH buckets..."
    )

    buckets = build_lsh_buckets(
        signature_cache,
        bands,
        rows
    )

    print(
        "Number of buckets:",
        len(buckets)
    )


    # ========================================================
    # BUCKET SIZE STATISTICS
    # ========================================================

    bucket_sizes = [
        len(values)
        for values in buckets.values()
    ]

    bucket_series = pd.Series(
        bucket_sizes
    )

    print()
    print(
        "Bucket statistics:"
    )

    print(
        "Average:",
        round(
            bucket_series.mean(),
            2
        )
    )

    print(
        "Median:",
        round(
            bucket_series.median(),
            2
        )
    )

    print(
        "Maximum:",
        int(
            bucket_series.max()
        )
    )


    # ========================================================
    # CANDIDATE COUNTS
    # ========================================================

    print()
    print(
        "Calculating candidate counts..."
    )

    counts = []

    candidate_cache = {}

    for index, notice_id in enumerate(
        unique_ids,
        start=1
    ):

        candidates = get_candidates(
            notice_id,
            signature_cache[notice_id],
            buckets,
            bands,
            rows
        )

        candidate_cache[notice_id] = candidates

        counts.append(
            {
                "notice_id": notice_id,
                "portal_id": notice_lookup[
                    notice_id
                ]["portal_id"],
                "configuration": config_name,
                "candidate_count": len(
                    candidates
                )
            }
        )

        if index % 500 == 0:

            print(
                f"Processed "
                f"{index}/{len(unique_ids)} notices"
            )


    counts_df = pd.DataFrame(
        counts
    )

    all_candidate_counts.append(
        counts_df
    )


    # ========================================================
    # CANDIDATE DISTRIBUTION
    # ========================================================

    candidate_series = (
        counts_df[
            "candidate_count"
        ]
    )

    mean_candidates = (
        candidate_series.mean()
    )

    p50 = candidate_series.quantile(
        0.50
    )

    p90 = candidate_series.quantile(
        0.90
    )

    p95 = candidate_series.quantile(
        0.95
    )

    p99 = candidate_series.quantile(
        0.99
    )

    maximum = candidate_series.max()


    print()
    print(
        "Candidate count distribution:"
    )

    print(
        "Mean:",
        round(
            mean_candidates,
            2
        )
    )

    print(
        "P50:",
        round(
            p50,
            2
        )
    )

    print(
        "P90:",
        round(
            p90,
            2
        )
    )

    print(
        "P95:",
        round(
            p95,
            2
        )
    )

    print(
        "P99:",
        round(
            p99,
            2
        )
    )

    print(
        "Max:",
        int(maximum)
    )


    # ========================================================
    # EVALUATE LABELLED PAIRS
    # ========================================================

    print()
    print(
        "Evaluating labelled pairs..."
    )

    pair_results = []

    for _, row in labels.iterrows():

        id_a = row["notice_id_a"]
        id_b = row["notice_id_b"]

        candidates_a = candidate_cache[
            id_a
        ]

        survived = (
            id_b in candidates_a
        )

        exact_similarity = (
            similarity_lookup[
                (id_a, id_b)
            ]
        )

        pair_results.append(
            {
                "configuration": config_name,
                "notice_id_a": id_a,
                "notice_id_b": id_b,
                "label": row["label"],
                "word5_jaccard": exact_similarity,
                "candidate_survived": survived
            }
        )

    pair_df = pd.DataFrame(
        pair_results
    )

    all_pair_results.append(
        pair_df
    )


    # ========================================================
    # SAME-PAIR RECALL
    # ========================================================

    same_pairs = pair_df[
        pair_df["label"] == "same"
    ]

    different_pairs = pair_df[
        pair_df["label"] == "different"
    ]

    same_recall = (
        same_pairs[
            "candidate_survived"
        ].mean()
    )

    different_survival = (
        different_pairs[
            "candidate_survived"
        ].mean()
    )


    print()
    print(
        "TRUE DUPLICATE CANDIDATE RECALL:",
        round(
            same_recall * 100,
            2
        ),
        "%"
    )

    print(
        "Different-pair survival:",
        round(
            different_survival * 100,
            2
        ),
        "%"
    )


    # ========================================================
    # SURVIVAL BY SIMILARITY RANGE
    # ========================================================

    pair_df[
        "similarity_bin"
    ] = pd.cut(
        pair_df[
            "word5_jaccard"
        ],
        bins=[
            0.0,
            0.1,
            0.2,
            0.3,
            0.4,
            0.5,
            0.6,
            0.7,
            0.8,
            0.9,
            1.0
        ],
        include_lowest=True
    )

    survival_by_bin = (
        pair_df
        .groupby(
            [
                "configuration",
                "similarity_bin"
            ],
            observed=False
        )
        .agg(
            pairs=(
                "candidate_survived",
                "count"
            ),
            survived=(
                "candidate_survived",
                "sum"
            ),
            survival_rate=(
                "candidate_survived",
                "mean"
            )
        )
        .reset_index()
    )

    survival_by_bin[
        "survival_rate"
    ] = (
        survival_by_bin[
            "survival_rate"
        ] * 100
    ).round(2)

    survival_file = (
        RESULT_DIR /
        f"lsh_survival_{config_name}.csv"
    )

    survival_by_bin.to_csv(
        survival_file,
        index=False
    )


    # ========================================================
    # CONFIGURATION SUMMARY
    # ========================================================

    configuration_summary.append(
        {
            "configuration": config_name,
            "bands": bands,
            "rows": rows,
            "buckets": len(buckets),
            "mean_candidates": mean_candidates,
            "p50_candidates": p50,
            "p90_candidates": p90,
            "p95_candidates": p95,
            "p99_candidates": p99,
            "max_candidates": maximum,
            "same_pair_recall": same_recall,
            "different_pair_survival": different_survival
        }
    )


# ============================================================
# SAVE CANDIDATE COUNTS
# ============================================================

candidate_counts_file = (
    RESULT_DIR /
    "lsh_candidate_counts.csv"
)

candidate_counts_df = pd.concat(
    all_candidate_counts,
    ignore_index=True
)

candidate_counts_df.to_csv(
    candidate_counts_file,
    index=False
)


# ============================================================
# SAVE LABELLED PAIR RESULTS
# ============================================================

pair_results_file = (
    RESULT_DIR /
    "lsh_labelled_pair_results.csv"
)

pair_results_df = pd.concat(
    all_pair_results,
    ignore_index=True
)

pair_results_df.to_csv(
    pair_results_file,
    index=False
)


# ============================================================
# SAVE SUMMARY
# ============================================================

summary_file = (
    RESULT_DIR /
    "lsh_configuration_summary.csv"
)

summary_df = pd.DataFrame(
    configuration_summary
)

summary_df[
    "mean_candidates"
] = summary_df[
    "mean_candidates"
].round(2)

summary_df[
    "p50_candidates"
] = summary_df[
    "p50_candidates"
].round(2)

summary_df[
    "p90_candidates"
] = summary_df[
    "p90_candidates"
].round(2)

summary_df[
    "p95_candidates"
] = summary_df[
    "p95_candidates"
].round(2)

summary_df[
    "p99_candidates"
] = summary_df[
    "p99_candidates"
].round(2)

summary_df[
    "same_pair_recall"
] = (
    summary_df[
        "same_pair_recall"
    ] * 100
).round(2)

summary_df[
    "different_pair_survival"
] = (
    summary_df[
        "different_pair_survival"
    ] * 100
).round(2)

summary_df[
    "same_pair_recall"
] = summary_df[
    "same_pair_recall"
].round(2)

summary_df[
    "different_pair_survival"
] = summary_df[
    "different_pair_survival"
].round(2)

summary_df.to_csv(
    summary_file,
    index=False
)


# ============================================================
# PRINT FINAL SUMMARY
# ============================================================

print()
print(
    "========================================"
)

print(
    "FINAL LSH COMPARISON"
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
# PRINT LABELLED PAIR SUMMARY
# ============================================================

print()
print(
    "========================================"
)

print(
    "LABELLED PAIR SURVIVAL"
)

print(
    "========================================"
)

label_summary = (
    pair_results_df
    .groupby(
        [
            "configuration",
            "label"
        ]
    )[
        "candidate_survived"
    ]
    .agg(
        [
            "count",
            "sum",
            "mean"
        ]
    )
)

print(
    label_summary.round(4).to_string()
)


# ============================================================
# COMPLETE
# ============================================================

print()
print(
    "========================================"
)

print(
    "LSH EXPERIMENT COMPLETE"
)

print(
    "========================================"
)

print()
print(
    "Created files:"
)

print(
    "1.",
    summary_file
)

print(
    "2.",
    candidate_counts_file
)

print(
    "3.",
    pair_results_file
)

print(
    "4. lsh_survival_32x4.csv"
)

print(
    "5. lsh_survival_16x8.csv"
)

print(
    "6. lsh_survival_8x16.csv"
)