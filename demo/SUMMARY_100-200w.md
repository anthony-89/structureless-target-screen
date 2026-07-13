# Written summary (submission field, ~180 words)

**OPLAH structure-to-screen: finding where a heart-failure target's activator binds — without pre-deciding the answer.**

Heart failure represses the enzyme OPLAH, letting toxic 5-oxoproline accumulate and drive the
oxidative stress that damages the heart. In our prior work, a screen of 1,280 FDA-approved compounds identified 5′-AMP as an OPLAH
activator — but with no solved structure and no known binding site, a better activator
can't be designed. Using Claude Code, we built a pipeline that turns a target plus one known
modulator into a screen shortlist, and removes a hidden bias: the naive approach transplants a
site from a homolog, pre-deciding where the ligand binds. Instead, we detect pockets unbiasedly
across the full 1,288-residue AlphaFold model (P2Rank + fpocket), then let AMP choose its own
site by docking. Three independent methods converge on one pocket — a glycine-rich phosphate
cleft with a repeated DxGGT motif. Screening it recovers AMP-mimics like dGMP and cAMP plus
approved antivirals (entecavir, sofosbuvir), and — from a 5,000-compound diverse screen (10% of
the library, AMP-guided) — 775 scaffolds that outscore AMP in silico, the top-ranked ones novel
and unlike AMP (docking ranks hypotheses, not measured affinities). Open-source, reproducible from one environment file.
