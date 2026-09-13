# Security policy

This is a research project, not a deployed service. It has no server, no user accounts and no
runtime network dependency — the pipeline runs offline and the interface plays back static JSON.
That removes most of the usual attack surface and leaves three things that genuinely matter:
**credentials**, **sealed evaluation data**, and **the integrity of the numbers**.

## Reporting a problem

Report privately to the maintainer (Akshat) rather than opening a public issue, especially for
anything involving a leaked credential. Include what you found, how you found it, and the minimal
steps to reproduce.

If you have leaked a credential in a commit, say so immediately. Rotating a token is a five-minute
job; a token that sat in a public repository for a week is a different problem.

---

## Credentials

**Nothing in this repository should ever contain a real secret.** `.gitignore` blocks `.env`,
`*.pem`, `credentials.json` and `.earthengine/`, but the ignore file is a safety net, not a
policy.

| Credential | Used by | How it is provided |
|---|---|---|
| `GFW_API_TOKEN` | `scripts/gfw_probe.py`, Stage 3 on the two `gfw_hourly` cases | `.env`, gitignored. Copy `.env.example` and fill it in. |
| Google Earth Engine | `pipeline/export/`, `pipeline/drift/fetch_fields.py` | `earthengine authenticate` once, locally. No key file in the repo. |
| SkyTruth Cerulean | `scripts/fetch_cerulean.py` | None — public OGC API, no authentication. |
| NOAA Marine Cadastre | Stage 3 ingest | None — public bulk download. |

If you add a script that needs a secret, add it to `.env.example` with a comment saying what it is
for and where to get it — never with a value.

### If a token is committed

1. Rotate it at the provider first. Removing the commit does not un-leak it.
2. Then tell the maintainer, so the history rewrite (if any) is coordinated rather than done twice.

---

## Sealed evaluation data

`docs/ANSWERS.md` holds every documented outcome for the case library — the attributions, the
official findings, the dark-vessel identifications. It is gitignored and held by the maintainer
alone. `docs/ANSWERS.README.md` is committed on purpose so the team knows the file exists and who
has it; hiding its existence would be worse than holding it.

This is an integrity control, not a secrecy game. Knowing the answer while tuning a scorer
produces a system that was tuned to the answer, and the difference between *"our system
identified the vessel"* and *"we tuned it until it did"* is the whole claim.

**Treat the following as sensitive to the project's own validity:**

- Vessel names, MMSIs and IMOs associated with a case before that case has been scored.
- The contents of `verification/<case-id>.json` before Stage 3 has run on that case — a
  `verification.json` **is** the answer, and it ships inside the bundle where everyone can read
  it. Several of these files are deliberately held back locally via `.git/info/exclude`.
- Cerulean's `slick_to_source` response. Their API returns the polygon and the attributed MMSIs
  together; `scripts/fetch_cerulean.py` splits them so the polygon can be committed without the
  answer. Attribution only prints with `--answers`.

If you trip over an answer by accident: close it, do not paste it into the repository or the
group chat, and tell the maintainer so the affected case can be declared non-blind rather than
silently reported as blind.

---

## Integrity of reported numbers

The project's binding rule is that internals are defensible: no vessel name that is not in the
real AIS file, no detection the detector did not produce, no accuracy number not measured on a
held-out, scene-level split.

Treat a change that would make a reported figure unverifiable as a defect of the same severity as
a leaked credential:

- Hand-editing a case bundle instead of fixing the producing code. The validator exists so that
  a bundle is evidence of what the code does; a patched bundle silently stops being that.
- Quoting a number without its unit, sample size and split.
- Reporting agreement with another algorithm as ground truth.
- Deleting a `TODO` in `docs/receipts.md` by guessing rather than by finding out.

---

## Dependencies

Dependencies are pinned to exact versions in `requirements.txt`, `requirements-detect.txt` and
`web/package-lock.json`, each with a written justification for why it is present. A new
dependency is pinned, justified in place, and announced — an unpinned or unannounced dependency
is both a reproducibility problem and a supply-chain one.

Model weights are deliberately **not** committed (see the reasoning in `.gitignore`); the training
scripts and the metric JSONs are the reproducible artefact. Nothing in the demo path loads a
pickle from the network.
