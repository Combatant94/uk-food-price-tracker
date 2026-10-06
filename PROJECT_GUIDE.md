# Project guide: how this project works

This guide explains every file and every step in plain English, so the project is easy to follow, run and talk about. If you're new here, read this first, then open `notebooks/01_walkthrough.ipynb`.

---

## The project in one minute

Food prices in the UK rose sharply after 2021. Everyone knows that. The more useful question for a retailer is **which foods actually drove the rise**, because the foods that rose the most aren't necessarily the ones that moved the shopping bill.

The project answers that with three free ONS files, and checks every headline result against an official ONS figure before trusting it.

---

## What each file is for

| File | What it is | When you'd open it |
|---|---|---|
| `README.md` | The front page: question, findings, method, limits | First thing anyone sees on GitHub |
| `PROJECT_GUIDE.md` | This guide | To understand or explain the project |
| `notebooks/01_walkthrough.ipynb` | The whole analysis step by step, with explanations and outputs | To learn the project, or to show your working |
| `src/food_price_pipeline.py` | The final, tidy version of the analysis as one script | To rerun everything when ONS publishes new data |
| `sql/food_price_analysis.sql` | The same matching and regional analysis written in SQL | To show SQL skills; it gives the same answers as Python |
| `dashboard/index.html` | The interactive dashboard | To explore the results; it's what non-technical people click |
| `reports/UK_Food_Price_Tracker_Summary.pdf` | One-page summary | To attach to emails or send to someone who won't open GitHub |
| `reports/*.csv` | The result tables (categories, products, regions) | To check a specific number |
| `reports/dashboard_data.json` | The numbers the dashboard reads | Created by the script; you don't edit it |
| `reports/figures/` | The charts used in the README | Created by the script |
| `data/` | Where the three ONS files go | They're not uploaded to GitHub because they're large |

---

## The steps, in plain English

### Step 1: Category trends
ONS gives every food category a price **index** that starts at 100 in 2015. Comparing the index in January 2021 with the latest month shows how much each category rose.
**Result:** food is up about 40%, against about 32% for prices overall. Oils and fats rose the most, around 70%.

### Step 2: What drove the rise
A big rise in something people barely buy doesn't move the bill much. So each category's rise is multiplied by its share of food spending (ONS publishes these shares, called **weights**).
**Result:** dairy and bread drove the most. Oils and fats, the biggest riser, added under one point to the 19.2% peak.
**Check:** the pieces add up to the official food inflation rate within 0.07 points.

### Step 3: Real shop prices, like for like
ONS also publishes individual shop prices. Comparing average prices between years is misleading, because different shops are visited each year. So the analysis matches the **same product in the same shop** in January 2021 and January 2025 (21,766 pairs), then averages the price changes.
It uses a **geometric mean** because price changes multiply: a price that doubles then halves ends where it started, and only a geometric mean gets that right.
**Check:** the typical like-for-like rise (33.4%) lands close to ONS's official food figure (34.4%).

### Step 4: Regions and shop types
A fixed basket of 138 products priced in all 12 regions shows every region rose by a similar amount (29% to 35%). Chains rose faster than independent shops, but the independent sample is small, so that's treated as a lead, not a firm finding.

### Step 5: Cleaning decisions
Price changes above 5× or below a fifth are excluded, because they're almost always a different product or pack size. Building the analysis in both SQL and Python, then comparing them, revealed one central price copied into all 12 regions with an exact 5× jump. It's now excluded consistently in both.

---

## How to run it

1. Download the three ONS files into `data/` (links in the README).
2. `pip install -r requirements.txt`
3. Either open `notebooks/01_walkthrough.ipynb` and run it top to bottom, or run `python src/food_price_pipeline.py` to rebuild every output.

---

## Questions to be ready for

**Why not just compare average prices?**
Different shops are sampled each year, so averages mix price change with sampling change. Matching the same shop compares like with like.

**Why weight by spending?**
What moves the shopping bill depends on how much people buy, not just how much the price rose.

**Why a geometric mean?**
Price changes multiply. A geometric mean treats a doubling and a halving as cancelling out, which is correct; an ordinary average doesn't.

**How do you know the results are right?**
Two checks against official ONS figures: contributions match the official rate within 0.07 points, and the like-for-like estimate is within one point of the official food change.

**What are the limitations?**
Like-for-like stops at January 2025 because ONS stopped publishing food shop prices in 2026. The contribution method is a close approximation of ONS's chain-linked method. The independent-shop finding rests on a small sample.

**What would you do with a retailer's own data?**
The same analysis on the retailer's sales and prices: which categories drive basket cost, by store and region, and which lines need the closest monitoring.

**Did you use AI?**
Answer honestly: AI tools helped write parts of the code, especially the dashboard. The question, the method, the checks against ONS, and the decisions about what to exclude and what to trust are things you understand and can explain.

---

## Before uploading to GitHub

1. **Write your own "Why I built this" paragraph** at the top of the README, in your own words. Two or three sentences on what made you curious, for example something you noticed working in food retail. Nobody else can write this part honestly.
2. **Run the notebook yourself once**, and add short notes in your own words wherever something clicks.
3. **Upload in stages over a few days**, the way real projects grow:
   - Day 1: `README.md`, `requirements.txt`, `.gitignore`, `data/README.md`, `src/`
   - Day 2: `notebooks/`, `sql/`
   - Day 3: `reports/`, `dashboard/`, then turn on GitHub Pages
