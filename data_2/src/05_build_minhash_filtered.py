import re
import hashlib
import random
import csv
import io

import pandas as pd
import psycopg2


# ============================================================
# SETTINGS — SAME AS ORIGINAL MINHASH EXPERIMENT
# ============================================================

NGRAM_SIZE = 5
SIGNATURE_SIZE = 128

PRIME = 4294967311

random.seed(42)

hash_a = []
hash_b = []

for _ in range(SIGNATURE_SIZE):
    hash_a.append(
        random.randint(1, PRIME - 1)
    )
    hash_b.append(
        random.randint(0, PRIME - 1)
    )


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
        tuple(
            tokens[i:i + NGRAM_SIZE]
        )
        for i in range(
            len(tokens) - NGRAM_SIZE + 1
        )
    }


# ============================================================
# STABLE N-GRAM HASH
# ============================================================

def hash_ngram(ngram):

    text = " ".join(ngram)

    digest = hashlib.md5(
        text.encode("utf-8")
    ).hexdigest()

    return int(digest, 16) % PRIME


# ============================================================
# MINHASH
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
# LOAD FILTERED TEXT FROM POSTGRESQL
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

print("\nLoading filtered notice text...")

cur.execute(
    """
    SELECT notice_id, title, lsh_text_filtered
    FROM notices
    ORDER BY notice_id
    """
)

rows = cur.fetchall()

notices = pd.DataFrame(
    rows,
    columns=[
        "notice_id",
        "title",
        "lsh_text_filtered"
    ]
)

print(
    "Total notices:",
    len(notices)
)


# ============================================================
# GENERATE FILTERED MINHASH SIGNATURES
# ============================================================

print("\nGenerating filtered MinHash signatures...")

buffer = io.StringIO()

writer = csv.writer(buffer)

count = 0

for _, row in notices.iterrows():

    notice_id = row["notice_id"]

    text = (
        str(row["title"])
        + " "
        + str(row["lsh_text_filtered"])
    )

    shingles = word_ngrams(text)

    signature = create_minhash(
        shingles
    )

    for position, value in enumerate(
        signature
    ):

        writer.writerow(
            [
                notice_id,
                position,
                value
            ]
        )

    count += 1

    if count % 500 == 0:

        print(
            f"Generated {count}/{len(notices)}"
        )


# ============================================================
# BULK COPY INTO FILTERED TABLE
# ============================================================

buffer.seek(0)

print(
    "\nBulk loading filtered MinHash rows..."
)

cur.copy_expert(
    """
    COPY minhash_signatures_filtered
    (notice_id, hash_position, hash_value)
    FROM STDIN
    WITH (FORMAT csv)
    """,
    buffer
)

conn.commit()

cur.close()
conn.close()


print("\n==========================================")
print("FILTERED MINHASH BULK LOAD COMPLETE")
print("==========================================")

print(
    "Notices:",
    len(notices)
)

print(
    "Expected signature rows:",
    len(notices) * SIGNATURE_SIZE
)