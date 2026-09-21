import re
import glob
import hashlib
import random
from pathlib import Path

import pandas as pd
import psycopg2


# ============================================================
# SETTINGS
# ============================================================

BASE = Path(r"C:\Users\Shuaib Ahmed\Downloads\data_2\data_2")
NOTICE_DIR = BASE / "notices"

NGRAM_SIZE = 5
SIGNATURE_SIZE = 128

PRIME = 4294967311
random.seed(42)

# Same random parameters as 03_minhash_experiment.py
hash_a = []
hash_b = []

for _ in range(SIGNATURE_SIZE):
    hash_a.append(random.randint(1, PRIME - 1))
    hash_b.append(random.randint(0, PRIME - 1))


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
# HASH N-GRAM
# ============================================================

def hash_ngram(ngram):

    text = " ".join(ngram)

    digest = hashlib.md5(
        text.encode("utf-8")
    ).hexdigest()

    return int(digest, 16) % PRIME


# ============================================================
# CREATE MINHASH
# ============================================================

def create_minhash(shingles):

    if not shingles:
        return [PRIME] * SIGNATURE_SIZE

    base_hashes = [
        hash_ngram(shingle)
        for shingle in shingles
    ]

    signature = []

    for i in range(SIGNATURE_SIZE):

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
# LOAD ALL NOTICES
# ============================================================

print("Loading notice files...")

files = sorted(
    glob.glob(
        str(NOTICE_DIR / "*.csv")
    )
)

print("Files found:", len(files))

notices = pd.concat(
    [
        pd.read_csv(
            f,
            usecols=[
                "notice_id",
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
# CONNECT TO POSTGRESQL
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
# GENERATE AND INSERT SIGNATURES
# ============================================================

print("\nGenerating 128-hash MinHash signatures...")

insert_sql = """
INSERT INTO minhash_signatures
    (notice_id, hash_position, hash_value)
VALUES
    (%s, %s, %s)
ON CONFLICT (notice_id, hash_position)
DO UPDATE SET hash_value = EXCLUDED.hash_value;
"""

count = 0

for _, row in notices.iterrows():

    notice_id = row["notice_id"]

    text = (
        str(row["title"])
        + " "
        + str(row["body"])
    )

    shingles = word_ngrams(
        text,
        NGRAM_SIZE
    )

    signature = create_minhash(shingles)

    for position, value in enumerate(signature):

        cur.execute(
            insert_sql,
            (
                notice_id,
                position,
                int(value)
            )
        )

    count += 1

    if count % 100 == 0:

        conn.commit()

        print(
            f"Processed {count}/{len(notices)} notices"
        )


# ============================================================
# FINISH
# ============================================================

conn.commit()

print("\nMinHash generation complete.")

cur.close()
conn.close()

print("PostgreSQL connection closed.")