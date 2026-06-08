---
title: "Point and Figure Counting"
type: concept
status: active
updated: 2026-06-08
sources:
  - path: raw/book/pages/page_057.md
    note: "point-and-figure charts as volatility-based cause measurement; right-to-left count boundaries"
  - path: raw/book/pages/page_058.md
    note: "structure-specific count rules and projection grades"
  - path: raw/book/pages/page_059.md
    note: "modern-market subjectivity warning and alternative projection tools"
  - path: raw/book/pages/page_221.md
    note: "chapter 27 take-profit context — original Wyckoff target method"
  - path: raw/crypto_archive/html/wyckoff-crypto-report-vol-29.html
    note: "GBTC 3% scaling P&F swing and confirmation counts"
  - path: raw/crypto_archive/html/wyckoff-crypto-report-vol-48.html
    note: "Bitcoin 2018-2020 campaign count and recent swing-count discipline"
  - path: raw/bruce_fraser/posts/articles-wyckoff-2016-01-intro-to-point-and-figure-construction.md
    note: "Fraser construction emphasis: volatility axis, 1-box/3-box guidance"
  - path: raw/bruce_fraser/posts/articles-wyckoff-2016-01-unlocking-the-mysteries-of-point-and-figure-charts.md
    note: "Fraser accumulation count mechanics and down-column boundary rule"
  - path: raw/bruce_fraser/posts/articles-wyckoff-2016-01-secrets-of-point-and-figure-distribution.md
    note: "Fraser distribution count mechanics and up-column boundary rule"
  - path: raw/bruce_fraser/posts/articles-wyckoff-2017-05-segmenting-pnf-counts.md
    note: "Fraser segmentation discipline for valid accumulation cause"
  - path: raw/bruce_fraser/posts/articles-wyckoff-2023-09-percent-scale-pnf-technique-nv-456.md
    note: "Fraser percent-scale/log P&F adaptation and limits"
---

# Point and Figure Counting

## Summary

**Point-and-figure counting** is the classical Wyckoff tool for turning
the [[cause-and-effect]] law into a target estimate. The book states that
Wyckoff used point-and-figure charts to quantify the cause and estimate
the effect through horizontal counting
([book p.57](../../../raw/book/pages/page_057.md)).

Unlike time-based bar charts, point-and-figure charts are based on
volatility: a new column appears only after price moves in the opposite
direction by the required amount
([book p.57](../../../raw/book/pages/page_057.md)). The method gives
an objective target framework, but the book also warns that modern
preparation choices make P&F subjective enough that many traders prefer
other projection tools
([book p.59](../../../raw/book/pages/page_059.md)).

## Key Points

### What Gets Counted

The count is taken **horizontally, from right to left**, between the
first and last events where the controlling force appeared
([book p.57](../../../raw/book/pages/page_057.md)). The controlling
force determines the direction:

- [[structures/accumulation]] produces an upward count.
- [[structures/distribution]] produces a downward count.
- [[structures/reaccumulation]] and [[structures/redistribution]] use
  shorter continuation counts because the prior trend has already done
  part of the work.

### Count Boundaries By Structure

The book gives different count boundaries for each structure type
([book p.57–58](../../../raw/book/pages/page_057.md)):

- **Accumulation:** count from the [[events/last-point-of-support|LPS]]
  back to the [[events/preliminary-support|PS]] or
  [[events/selling-climax|SC]].
- **Distribution:** count from the
  [[events/last-point-of-supply|LPSY]] back to the PSY or
  [[events/buying-climax|BC]].
- **Reaccumulation:** count from the LPS back to the
  [[events/automatic-reaction|AR]].
- **Redistribution:** count from the LPSY back to the AR, where supply
  first appeared.

After counting the boxes that make up the range, multiply by the box
value ([book p.58](../../../raw/book/pages/page_058.md)).

### Three Projection Grades

The book separates the projection into three grades
([book p.58](../../../raw/book/pages/page_058.md)):

- **Classic projection:** add the resulting count to the price where the
  LPS or LPSY appears.
- **Moderate projection:** add the count to the structure extreme
  (usually Spring/SC in accumulation, UT/BC in distribution).
- **Conservative projection:** divide the range into phases and create
  smaller counts from phase-to-phase turns.

The conservative version exists because a large range does not prove the
entire area was true accumulation or distribution; not all of the apparent
cause necessarily belongs to the campaign
([book p.58](../../../raw/book/pages/page_058.md)).

### Modern-Use Warning

The book is cautious about using P&F mechanically in modern markets. It
names preparation subjectivity as the reason confidence can break down, and
notes that some traders prefer Fibonacci, Elliott, or harmonic range
projection instead
([book p.59](../../../raw/book/pages/page_059.md)).

Chapter 27 repeats the same operational stance: original Wyckoff used
point-and-figure charts for targets, but the author considers other tools
more useful in today's market structure
([book p.221](../../../raw/book/pages/page_221.md)).

## Cross-Author Readings

### As Used By Bruce Fraser (bruce_fraser)

Fraser keeps the same horizontal cause-counting premise, but puts unusual
weight on construction discipline: the P&F axis advances by volatility rather
than time, and 1-box/3-box choices change the operating timeframe
([Fraser construction](../../../raw/bruce_fraser/posts/articles-wyckoff-2016-01-intro-to-point-and-figure-construction.md)).
He also insists that vertical-chart labels be transferred to P&F before the
count is taken; accumulation counts begin/end on down columns, while
distribution counts begin/end on up columns
([accumulation count](../../../raw/bruce_fraser/posts/articles-wyckoff-2016-01-unlocking-the-mysteries-of-point-and-figure-charts.md);
[distribution count](../../../raw/bruce_fraser/posts/articles-wyckoff-2016-01-secrets-of-point-and-figure-distribution.md)).

Fraser's distinct applied emphasis is count quality: segment a large base when
only part of it shows true accumulation, and treat percent-scale P&F as a
specialized log-scale extension rather than the default count method
([segmenting](../../../raw/bruce_fraser/posts/articles-wyckoff-2017-05-segmenting-pnf-counts.md);
[percent scale](../../../raw/bruce_fraser/posts/articles-wyckoff-2023-09-percent-scale-pnf-technique-nv-456.md)).

### As Used By Wyckoff Analytics Crypto Archive (crypto_archive)

Vol 29 applies a 3% scaling point-and-figure chart to GBTC and warns that
laggard assets should be counted conservatively by focusing on recent price
action
([vol 29](../../../raw/crypto_archive/html/wyckoff-crypto-report-vol-29.html)).
Vol 48 applies Bitcoin counts across the 2018-2020 multi-year structure, but
still emphasizes recent campaign segments and intraday swing counts before
acting on very large long-term objectives
([vol 48](../../../raw/crypto_archive/html/wyckoff-crypto-report-vol-48.html)).

## Why It Matters For Wyckoff Reading

- It is the quantitative bridge from a [[trading-range]] to a target: the
  range is not only a pattern, it is a measured cause.
- It prevents treating all ranges equally. A larger valid cause implies a
  larger effect, but an invalid or random range should not be counted.
- It explains why continuation structures have shorter target logic than
  full accumulation/distribution structures.
- It belongs downstream of structure quality. Count only after the range
  has been identified as purposeful, not before.

## Links

- Parent law: [[cause-and-effect]]
- Fraser applications: [[pnf-count-segmentation]],
  [[pnf-count-confirmation]], [[pnf-distribution-paradox]],
  [[intraday-pnf-reading]], [[percent-scale-pnf]]
- Structure inputs: [[structures/accumulation]], [[structures/distribution]],
  [[structures/reaccumulation]], [[structures/redistribution]]
- Boundary events: [[events/last-point-of-support]],
  [[events/last-point-of-supply]], [[events/selling-climax]],
  [[events/buying-climax]]
- Related target/exit context: [[significant-bar]],
  [[reversal-of-movement]]
- Sources: [[book-chapter-08]], [[book-chapter-27]],
  [[crypto-report-vol-29]], [[crypto-report-vol-48]],
  [[fraser-pnf-construction-and-counting]],
  [[fraser-pnf-segmentation-and-confirmation]],
  [[fraser-pnf-intraday-and-percent-scale]]
