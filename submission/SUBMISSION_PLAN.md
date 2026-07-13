# Submission plan — OPLAH structure-to-screen

**Deadline:** Mon Jul 13, 2026, 9:00 PM ET · **Track:** Researcher · **Team:** Antonio Esquivel Gaytan
**Submit at:** cerebralvalley.ai (CV platform)

## The 3 required deliverables
| # | Item | Status | Where |
|---|------|--------|-------|
| 1 | Demo video (≤3:00) | ⬜ record | `demo_player.html` + `NARRATION_wordforword.md` |
| 2 | Open-source repo / write-up | ⬜ push | this repo (README.md + code + results) |
| 3 | Written summary (100–200 w) | ✅ 178 w | `submission/SUMMARY_100-200w.md` |

---

## A) Demo video
- **Source:** open the self-playing demo full-screen → press **Play** → narrate over it with `NARRATION_wordforword.md`.
  Demo URL: https://claude.ai/code/artifact/42d8d76a-acdb-4e0a-945c-5bdf6cb592f0
- **Record:** `Cmd+Shift+5` (or Loom for screen+voice). Keep **≤3:00** (narration ≈2:50; trim the parenthetical asides if you run long). Light room, no background noise.
- **Upload:** YouTube (unlisted) or Loom → copy the link into the form.
- **Ready-to-use title:**
  > OPLAH: finding a heart-failure drug target's binding site — without pre-deciding the answer | Built with Claude
- **Ready-to-use description:**
  > Heart failure represses OPLAH, a protective enzyme; its activator 5′-AMP has no known binding site because OPLAH has no solved 3D structure. Using Claude Code, we find where AMP binds — without the homolog-transplant bias that pre-decides the answer — then screen for mimics and better binders. Built with Claude: Life Sciences Hackathon 2026 · Researcher Track. Repo: <REPO_URL> #BuiltWithClaude
- ⚠️ **Record AFTER the 5k number swap** (see §F) so the on-screen figure matches.

## B) GitHub repo
`.gitignore` is already in place (keeps repo to a few MB; excludes ~2.3 GB of data/tools/dead-ends).
```bash
cd /Users/antonioesquivel/Desktop/claude_code_handoff
git init && git add .
git status                     # confirm ligs_50k/, tools/, DiffDock, _archive are NOT staged
git commit -m "OPLAH structure-to-screen — Built with Claude: Life Sciences (Researcher Track)"
gh repo create oplah-structure-to-screen --public --source=. --remote=origin --push
#   (or make the repo on github.com, then: git remote add origin <url> && git push -u origin main)
```
- **Repo name:** `oplah-structure-to-screen` · **Description:** "Finding a heart-failure drug target's binding site with no solved structure — unbiased pocket detection + docking, driven by Claude Code."
- **Included:** README, LICENSE (MIT), all scripts, results CSVs, `submission/` (one_pager.html, demo_player.html, summary, narration), pipeline_src, HANDOFF files.
- **Excluded (via .gitignore):** prepared ligand libraries, docking poses, P2Rank tool, DiffDock venv/model, tarballs, `_archive_claude_science/`.

## C) Written summary
`submission/SUMMARY_100-200w.md` — **178 words**, already reworded (no "50k", hedge included). Paste as-is. *(Says "a diverse ZINC screen" with no number → no 5k swap needed here.)*

## D) Submission form — pre-filled answers
- **Project title:** OPLAH structure-to-screen: finding a modulator's binding site without pre-deciding the answer
- **Track:** Researcher
- **Team:** Antonio Esquivel Gaytan
- **Summary:** paste `SUMMARY_100-200w.md`
- **Repo URL:** _<fill after push>_
- **Video URL:** _<fill after upload>_

## E) Final pre-submit checklist
- [ ] 5k dock finished → `analyze_5k.py` run → numbers swapped (§F)
- [ ] Demo video recorded (≤3:00) + uploaded → URL
- [ ] Repo pushed (public, MIT); `git status` confirmed heavy data excluded → URL
- [ ] Summary pasted (178 w) · Team name present · Track = Researcher
- [ ] Citations spot-verified (Claude Science action item — authors/DOI in each paper)
- [ ] Submitted before **Mon Jul 13, 9:00 PM ET**

## F) 5k swap — ✅ DONE (2026-07-13)
5k local screen finished (4,998 usable). Final numbers now in all materials + artifacts republished:
- **775 of 5,000 out-score AMP** (396 enrichment + **379 novel** diversity arm)
- **Top hit ZINC4126706, −10.81 kcal/mol** (diversity arm, Tanimoto to AMP 0.06)
- Verified: no stale numbers left; SUMMARY 186 words. Anonymous auditor re-run to verify the outcome.

## G) Still for the user (on return)
- Fine-tune speech tone; decide on demo animations (light proposal pending)
- **Record video** (≤3:00, after reviewing the updated on-screen numbers) → upload → URL
- **git push** (commands in §B) → repo URL
- **Submit** on CV platform before Mon Jul 13, 9:00 PM ET
