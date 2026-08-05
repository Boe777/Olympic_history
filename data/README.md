# Data

The full dataset is not committed. It is 40 MB, which makes the repository slow
to clone and is not what version control is for.

## Getting it

1. Download **120 years of Olympic history: athletes and results** from Kaggle:
   https://www.kaggle.com/datasets/heesoo37/120-years-of-olympic-history-athletes-and-results
2. Unzip it into this directory so you have:

```
data/
├── athlete_events.csv
└── noc_regions.csv
```

A Kaggle account is required; the dataset is free.

## Test fixture

`tests/fixtures/athlete_events_sample.csv` is a small, deterministic slice of
the same data, committed so the test suite and CI run without the download. It
is a sample for testing, not a substitute for the analysis input.
