import re
import csv
import time
import pandas as pd
import psycopg2


# ============================================================
# SETTINGS
# ============================================================

BASE = r"C:\Users\Shuaib Ahmed\Downloads\data_2\data_2"
OUTPUT = BASE + r"\results\scored_candidates.csv"

NGRAM_SIZE = 5


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_text(text):

    if pd.isna(text):
        return ""

    text = str(text).lower()

    text = re.sub(
        r"https?://\S+",
        " ",
        text
    )

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    return text


# ============================================================
# WORD 5-GRAMS
# ============================================================

def word_ngrams(text):

    tokens = normalize_text(text).split()

    if len(tokens) < NGRAM_SIZE:
        return set()

    return {
        tuple(tokens[i:i + NGRAM_SIZE])
        for i in range(
            len(tokens) - NGRAM_SIZE + 1
        )
    }


# ============================================================
# JACCARD
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
# CONNECT
# ============================================================

print("Connecting to PostgreSQL...")

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="postgres",
    user="admin",
    password="admin123"
)

cur = conn.cursor()

print("Connected.")


# ============================================================
# LOAD VALID LSH BUCKETS
# ============================================================

print("\nLoading CAP=100 candidate buckets...")

cur.execute("""
    SELECT band, bucket_hash
    FROM lsh_buckets_filtered
    GROUP BY band, bucket_hash
    HAVING COUNT(*) <= 100
""")

valid_buckets = set(cur.fetchall())

print(
    "Valid buckets:",
    len(valid_buckets)
)


# ============================================================
# LOAD CANDIDATE PAIRS
# ============================================================

print("\nGenerating candidate pairs...")

cur.execute("""
    SELECT DISTINCT
        b1.notice_id AS notice_id_a,
        b2.notice_id AS notice_id_b
    FROM lsh_buckets_filtered b1
    JOIN lsh_buckets_filtered b2
      ON b1.band = b2.band
     AND b1.bucket_hash = b2.bucket_hash
    WHERE b1.notice_id < b2.notice_id
      AND EXISTS (
          SELECT 1
          FROM lsh_buckets_filtered bx
          WHERE bx.band = b1.band
            AND bx.bucket_hash = b1.bucket_hash
          GROUP BY bx.band, bx.bucket_hash
          HAVING COUNT(*) <= 100
      )
""")

candidate_pairs = cur.fetchall()

print(
    "Candidate pairs:",
    len(candidate_pairs)
)


# ============================================================
# LOAD ONLY REQUIRED NOTICES
# ============================================================

notice_ids = set()

for a, b in candidate_pairs:
    notice_ids.add(a)
    notice_ids.add(b)

print(
    "Unique notices to score:",
    len(notice_ids)
)

cur.execute("""
    SELECT notice_id, title, lsh_text_filtered
    FROM notices
    WHERE notice_id = ANY(%s)
""", (list(notice_ids),))

rows = cur.fetchall()

texts = {}

for notice_id, title, body in rows:

    text = (
        str(title)
        + " "
        + str(body)
    )

    texts[notice_id] = word_ngrams(text)

print(
    "Loaded notice representations:",
    len(texts)
)


# ============================================================
# SCORE CANDIDATES
# ============================================================

print("\nScoring candidates...")

start = time.perf_counter()

threshold_counts = {
    0.30: 0,
    0.40: 0,
    0.50: 0,
    0.60: 0,
    0.70: 0,
    0.80: 0,
    0.90: 0
}

with open(
    OUTPUT,
    "w",
    newline="",
    encoding="utf-8"
) as f:

    writer = csv.writer(f)

    writer.writerow([
        "notice_id_a",
        "notice_id_b",
        "jaccard"
    ])

    for i, (a, b) in enumerate(candidate_pairs, start=1):

        score = jaccard(
            texts[a],
            texts[b]
        )

        writer.writerow([
            a,
            b,
            score
        ])

        for threshold in threshold_counts:

            if score >= threshold:
                threshold_counts[threshold] += 1

        if i % 50000 == 0:

            print(
                f"Scored {i}/{len(candidate_pairs)}"
            )

elapsed = time.perf_counter() - start


# ============================================================
# RESULTS
# ============================================================

print("\n==========================================")
print("CANDIDATE SCORING COMPLETE")
print("==========================================")

print(
    "Candidates:",
    len(candidate_pairs)
)

print(
    "Scoring time:",
    round(elapsed, 3),
    "seconds"
)

print("\nThreshold counts:")

for threshold, count in threshold_counts.items():

    print(
        f"Jaccard >= {threshold:.2f}: {count}"
    )

print(
    "\nOutput:",
    OUTPUT
)


cur.close()
conn.close()