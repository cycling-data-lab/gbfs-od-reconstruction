# Cover Letter — Computer Standards & Interfaces submission

**To:** The Editor, *Computer Standards & Interfaces*
**From:** Rohan Fossé and Gaël Pallares, CESI LINEACT (EA 7527), Montpellier, France
**Date:** [submission date]
**Re:** Submission of "Standard compliance bounds origin–destination identifiability in GBFS bike-sharing feeds: a cost-learning and sampling-horizon analysis"

---

Dear Editor,

We are pleased to submit our manuscript **"Standard compliance bounds origin–destination identifiability in GBFS bike-sharing feeds"** (Regular Paper) for consideration at *Computer Standards & Interfaces*. The work is co-authored by the two undersigned authors (~[pp] pp main + [pp] pp Supplementary Information) and has not been submitted elsewhere.

**The contribution.** Public GBFS feeds were standardised to advertise availability, not to record trips, so reconstructing origin–destination flows from them is either underdetermined (from station counts) or fragile (from identifier tracking, which the standard's privacy guidance deliberately undermines by recommending identifier rotation). We prove that, in a hybrid estimator combining the two, the transport cost is identifiable only up to additive station effects and the observation bias equals the *non-separable* part of the log-selection probability — so station-emptiness censoring cancels exactly while 60-second polling aliasing, being correlated with travel time, does not. This yields a sampling-horizon law in which the collection time needed to reconstruct OD to accuracy `δ` scales as `δ⁻⁴` and inversely with the identifier-persistence rate `q`, defining a **standard-compliance threshold** below which operational monitoring is provably infeasible. [Insert the headline pilot numbers once collected.]

**Why *Computer Standards & Interfaces*.** The result ties a precise property of a widely deployed open-data standard (GBFS identifier-rotation guidance, issue #146 / v2.0) to the downstream viability of a mathematical model — exactly the standard-to-system bridge the journal exists to publish. It is the dynamic-layer companion to our prior feed-quality audit and speaks directly to standard maintainers (MobilityData) and to regulators relying on these feeds.

All code, derived outputs, and the LaTeX source are openly archived at [github.com/cycling-data-lab/gbfs-od-reconstruction](https://github.com/cycling-data-lab/gbfs-od-reconstruction), DOI [10.5281/zenodo.XXXXXXX](https://doi.org/10.5281/zenodo.XXXXXXX).

Sincerely,
Rohan Fossé (corresponding author, <rfosse@cesi.fr>, ORCID [0009-0002-2195-0198](https://orcid.org/0009-0002-2195-0198))
Gaël Pallares (ORCID [0009-0002-8680-604X](https://orcid.org/0009-0002-8680-604X))

---

## Suggested reviewers

Per the submission portal's optional reviewer-suggestion field, in declining order of fit:

1. **[Reviewer 1]** — [data-standards / open mobility data; e.g. a MobilityData/GBFS or MDS contributor].
2. **[Reviewer 2]** — [micromobility OD inference from public feeds].
3. **[Reviewer 3]** — [optimal transport / OD estimation methodology].

We respectfully request that the manuscript not be assigned to reviewers with a competing identifier-tracking product, whose interests are orthogonal to the standards-compliance framing we develop.

---

*This cover letter is held in the repository at [cover_letter.md](./cover_letter.md). Replace bracketed placeholders before pasting into the submission portal.*
