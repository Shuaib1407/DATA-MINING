import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = BASE_DIR / "results"

# Prefer the 16x8 LSH survival output if available, otherwise use the first survival file
preferred = RESULTS_DIR / "lsh_survival_16x8.csv"
if preferred.exists():
    csv_path = preferred
else:
    files = sorted(RESULTS_DIR.glob("lsh_survival_*.csv"))
    if not files:
        raise FileNotFoundError(f"No LSH survival CSV files found in {RESULTS_DIR}")
    csv_path = files[0]

OUTPUT_PATH = RESULTS_DIR / "lsh_candidate_survival_vs_similarity.png"

# Read the survival table
survival = pd.read_csv(csv_path)

# Parse interval bins like "(0.5, 0.6]" into midpoints for the x-axis
midpoints = []
for label in survival["similarity_bin"]:
    nums = [float(x) for x in re.findall(r"-?\d+\.?\d*", str(label))]
    if len(nums) >= 2:
        midpoints.append((nums[0] + nums[1]) / 2)
    else:
        midpoints.append(float(nums[0]))

survival = survival.copy()
survival["similarity_midpoint"] = midpoints
survival["survival_prob"] = survival["survival_rate"] / 100.0

# Plot the survival curve with a step line and points, matching the example style
fig, ax = plt.subplots(figsize=(12, 7.5))
ax.step(
    survival["similarity_midpoint"],
    survival["survival_prob"],
    where="post",
    color="#1f77b4",
    linewidth=2.5,
    label="",
)
ax.plot(
    survival["similarity_midpoint"],
    survival["survival_prob"],
    "o",
    color="#1f77b4",
    markersize=6,
)

# Operating point marker at 0.75
op = 0.75
ax.axvline(op, color="#1f77b4", linestyle="--", linewidth=1.5, alpha=0.9)
ax.text(
    op + 0.01,
    1.02,
    f"Operating point = {op}",
    color="#1f77b4",
    bbox={"boxstyle": "square,pad=0.25", "facecolor": "white", "edgecolor": "#1f77b4"},
    fontsize=12,
    va="bottom",
)

ax.set_title("LSH Candidate Survival vs True Similarity", fontsize=18)
ax.set_xlabel("True Jaccard similarity", fontsize=14)
ax.set_ylabel("Probability pair survives LSH", fontsize=14)
ax.set_xlim(0.0, 1.0)
ax.set_ylim(0.0, 1.05)
ax.grid(True, which="major", linestyle="-", linewidth=0.8, alpha=0.5)
ax.set_xticks([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])

# Make the axes look clean and similar to the reference image
for spine in ax.spines.values():
    spine.set_linewidth(1.2)

plt.tight_layout()
plt.savefig(OUTPUT_PATH, dpi=300, bbox_inches="tight")
print(f"Saved LSH survival graph to: {OUTPUT_PATH}")