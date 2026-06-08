---
title: "Percent-Scale P&F"
type: concept
status: active
updated: 2026-06-08
primary_source: bruce_fraser
sources:
  - path: raw/bruce_fraser/posts/articles-wyckoff-2020-07-a-nasdaq-100-throwover-is-the-783.md
    note: "2% intraday percent-scale P&F case and cause exhaustion"
  - path: raw/bruce_fraser/posts/articles-wyckoff-2023-09-percent-scale-pnf-technique-nv-456.md
    note: "3% log-scale P&F method, compounding, and usage limits"
---

# Percent-Scale P&F

## Summary

**Percent-scale P&F** is Fraser's log-scale adaptation of horizontal
[[point-and-figure-counting]]. Instead of a fixed price box, the chart moves by
a percentage step, so each counted column represents a compounding event
([Percent Scale](../../../raw/bruce_fraser/posts/articles-wyckoff-2023-09-percent-scale-pnf-technique-nv-456.md)).

Fraser treats the method as useful for dynamically growing financial assets,
while still applying the traditional horizontal count rules to range-bound
structures
([Percent Scale](../../../raw/bruce_fraser/posts/articles-wyckoff-2023-09-percent-scale-pnf-technique-nv-456.md)).

## Key Points

### Percent Scale Changes The Math

In the 2020 Nasdaq example, Fraser reads a 23-column count on a 2% scale as 23
periods of 2% compounded growth
([NASDAQ Throwover](../../../raw/bruce_fraser/posts/articles-wyckoff-2020-07-a-nasdaq-100-throwover-is-the-783.md)).
In the later Nvidia case, he generalizes the idea: a 10-column structure at 3%
represents 10 compounding periods at 3%
([Percent Scale](../../../raw/bruce_fraser/posts/articles-wyckoff-2023-09-percent-scale-pnf-technique-nv-456.md)).

### Use It For Dynamic Upside Structures

Fraser says log-scale P&F is best for dramatically rising and volatile
instruments, while arithmetic scaling remains more effective for smaller swing
trading structures
([Percent Scale](../../../raw/bruce_fraser/posts/articles-wyckoff-2023-09-percent-scale-pnf-technique-nv-456.md)).

### Count Conservatively

His usage notes recommend starting with 1% scaling, trying 2%, defaulting to
1-box reversal, avoiding 3-box charts, and counting conservatively because big
log-scale counts can produce very large objectives
([Percent Scale](../../../raw/bruce_fraser/posts/articles-wyckoff-2023-09-percent-scale-pnf-technique-nv-456.md)).

### Avoid Log-Scale Downside Over-Counting

Fraser says distribution and redistribution downside targets should default to
arithmetic scale because log scale will typically over-count downside
objectives
([Percent Scale](../../../raw/bruce_fraser/posts/articles-wyckoff-2023-09-percent-scale-pnf-technique-nv-456.md)).

### The Objective Still Needs Tape Reading

In the Nasdaq throwover case, fulfillment of the percent-scale count means the
cause may be nearly used up; Fraser still waits for tape-reading evidence such
as an Automatic Reaction before treating the uptrend as stopped
([NASDAQ Throwover](../../../raw/bruce_fraser/posts/articles-wyckoff-2020-07-a-nasdaq-100-throwover-is-the-783.md)).

## Why It Matters For Wyckoff Reading

- It extends P&F cause/effect work to strongly compounding instruments.
- It separates dynamic upside estimation from arithmetic downside counting.
- It keeps percent-scale P&F as an applied tool, not a replacement for range
  quality and tape-reading confirmation.

## Links

- Parent method: [[point-and-figure-counting]]
- Companion concept: [[intraday-pnf-reading]]
- Distribution caution: [[pnf-distribution-paradox]]
- Source group: [[fraser-pnf-intraday-and-percent-scale]]
