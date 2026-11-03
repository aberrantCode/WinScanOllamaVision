# Onboarding & Flow Redesign — Design Proposal

**Scope:** empty states, in-app error visibility, and a fast path from launch to the list of analyzed documents waiting for a decision. Design only — no code changes yet.

## Current state (verified against the code)

- `DocumentPipelineWindow` is a hard-coded linear wizard: `_current_stage = STAGE_IMPORT` on every launch (`src/ui/pipeline/window.py:101`), regardless of what work is already queued. A returning user with 40 bundles waiting for review still lands on Import and has to click forward three times (or manually click the Bundle node in the header rail).
- The Bundle panel already computes exactly the number we'd want to greet the user with: `_compute_bundle_stats()` tallies `"Not Reviewed"` vs `Accepted`/`Rejected`/`Skipped` (`src/ui/pipeline/bundle_panel.py:307-339`), and `refresh_bundle_count()` will jump straight into the embedded review workflow if one is already live (`bundle_panel.py:263-305`). This data just isn't consulted at startup.
- Import already has a working precedent for "smart routing": `maybe_show_analyze_nudge_after_discovery()` computes pending/error counts and either auto-advances to Analyze or shows a dismissible nudge banner, gated by `SourceDirectories.auto_advance_on_empty_discovery` (`src/ui/pipeline/import_panel.py:405-437`). It just isn't applied at launch, and it doesn't reach past Analyze into Bundle.
- Empty states are inconsistent. Import's preview pane has a real one — dashed card, icon, title, hint (`import_panel.py:293-332`). Bundle's "no bundles" and "could not load" cases are a single status label (`bundle_panel.py:281-289`). Analyze's "no source directories" case is a `StatusEvent` line in the status bar, not an in-panel state. Directories-empty on manual scan is a blocking `QMessageBox` (`import_panel.py:621`).
- Failures are easy to miss. Startup preflight (Ollama down, model missing, CLI not found) never blocks — it logs and fires a Windows toast (`services/llm_readiness_service.py`, `services/notification_service.py:133-145`). If OS toasts are off, the user sees nothing. `test_connection()` exists on every provider (`base_provider.py:60` and each subclass) but its only caller in the whole codebase is the background preflight worker — there is no button anywhere that lets a user check their own setup on demand.
- On first launch with zero directories configured, `_seed_default_source_directory()` silently creates and adds `~/Pictures/Scans` with no dialog (`main.py:186-205`) — a folder appears in the user's config that they never chose.

## Design goals

1. A user with analyzed-but-undecided documents reaches that list in one launch, not four clicks.
2. Every "nothing here" and "something's wrong" state explains what's missing and gives one clickable next action — never a bare label or a silent toast.
3. Reuse the nudge-banner/auto-advance pattern that already exists in Import rather than inventing a second mechanism.

## Proposed changes

### 1. Smart landing stage (replaces the hard-coded Import start)

After the splash/preflight worker finishes, compute readiness cheaply from the DB (no network calls) and land on the *most actionable* stage instead of always Import:

```
if bundles_not_reviewed > 0:      land on Bundle   # the decision-ready list
elif pages_pending_analysis > 0:  land on Analyze
else:                              land on Import   # true first-run / nothing queued
```

- `bundles_not_reviewed` — already available via `_compute_bundle_stats()`; expose it as a cheap standalone query so it doesn't require generating full bundle recommendations just to get a count.
- `pages_pending_analysis` — same query already used in `maybe_show_analyze_nudge_after_discovery()`.
- The header rail still marks earlier stages complete/skipped using the same logic `_go_to_stage()` already applies when jumping forward, so it doesn't look broken when you land on Bundle with Import/Analyze un-visited.
- Manual navigation is untouched — clicking any rail node still works exactly as it does today.
- New setting `Pipeline.smart_landing` (default `True`) so a user who prefers to always start at Import can turn it off. Mirrors the existing `auto_advance_on_empty_discovery` toggle in the same settings tab.

This is the direct fix for "quick to get to the list of images ready for decisions" — it's the same data the Bundle panel already has, just consulted one screen earlier.

### 2. Consistent empty states

Extract Import's dashed-card pattern (`_build_preview_placeholder`) into a shared `EmptyStateCard` widget (icon, title, hint, optional CTA button) and apply it everywhere a panel currently has nothing or a bare label:

| Location | Today | Proposed |
|---|---|---|
| Analyze grid, nothing pending | Status-bar line only | 🔍 "Nothing to analyze yet" / "Import some documents first, or add a source folder." + **Go to Import** |
| Bundle, zero bundles in DB | Plain label (`bundle_panel.py:288`) | 📦 "No analyzed documents yet" / "Run analysis first, then come back here." + **Go to Analyze** |
| Bundle, load failure | Plain label (`bundle_panel.py:282`) | ⚠ "Couldn't load bundles" / short reason + **Retry** |
| Directories tab, zero configured | (silently auto-seeded, no visible state) | 📁 "No folders configured" / "WinScanLLM won't know where to look for scans." + **Add a folder** |
| Import scan, zero directories | Blocking `QMessageBox` (`import_panel.py:621`) | Same card inline instead of a modal — doesn't stop the user cold |

Side effect: replacing the Directories-empty state with a visible card means the silent `~/Pictures/Scans` auto-seed in `main.py:186-205` should go away — a folder appearing in config with no announcement works against "make empty states honest." First launch would show the empty-directories card instead.

### 3. In-app error visibility

- Add a persistent, dismissible status strip under the pipeline header — same row treatment as the existing `UpdateBanner` (`window.py:132-135`) — driven by `NotificationService`. Every place that currently calls `show_preflight_toast()` also pushes this in-window banner, so a provider failure is visible even when OS toasts are suppressed.
- Give Settings → Provider tab a **Test Connection** button wired to the `test_connection()` methods that already exist on every provider but are currently only called by the background preflight worker. Small status pill next to it: ✅ Connected / ❌ Not reachable / ⏳ Testing. This turns "discover the provider is broken when a job fails" into "check before you start."
- Directory-scan-with-nothing-configured stops being a blocking `QMessageBox` and becomes the empty-state card from section 2 — visible, not modal.

## Decisions

1. **Smart landing default: opt-in.** Ships off by default (`Pipeline.smart_landing = False`); discoverable via a settings toggle next to `auto_advance_on_empty_discovery`. Landing still always starts at Import unless the user turns it on.
2. **`~/Pictures/Scans` auto-seed: keep as-is.** No change to `main.py:186-205` — the silent seed stays. The new empty-directories card (section 2) still applies to the general "zero directories configured" case (e.g. after a user removes all folders), it just won't be the very-first-launch experience.
3. **Test Connection: main window too.** Status pill lives in Settings → Provider tab (button + pill) *and* a read-only version of the same pill sits in the pipeline window footer next to the Settings button, so provider health is glanceable without opening the dialog.

## Out of scope (raised but not requested)

No dedicated first-run wizard / welcome screen — you didn't select that priority. Smart landing handles the "first launch with nothing configured" case by landing on Import with the new empty-directories card, which covers the same need without a separate wizard flow.
