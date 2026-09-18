from pathlib import Path
import csv

root = Path('data/sales')
files = sorted(root.glob('SALES_S01_*.csv'))[:3]
for p in files:
    print('FILE', p)
    with p.open('rb') as f:
        sample = f.read(400)
    print(sample[:200])
    print('---')
