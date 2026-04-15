# SWITCH Proposal — Polish Plan

## Context

This document tracks the work needed to bring the SWITCH proposal to a state
that the MoQ Working Group can accept into the base specification.

**PR:** moq-wg/moq-transport#1378 — "SWITCH for Client-side ABR"
**Branch:** `gwendalsimon:switch` → open against `moq-wg/moq-transport:main`
**Status:** Open since 2025-11-24. Labels: ABR, Design, Needs Discussion.
**Pending formal reviews from:** ianswett, vasilvv (both WG editors — critical)
**Has commented:** acbegen, sharmafb, suhasHere, tobbee, yekuiwang, yuyou

---

## What SWITCH Is

SWITCH is a new MOQT control message (type `0x12`) that lets a subscriber
request a coordinated Track transition at a Relay. Instead of combining
SUBSCRIBE + SUBSCRIBE_UPDATE + UNSUBSCRIBE (which is racy and produces 3
simultaneous data flows), the subscriber sends one SWITCH that bundles:
- the **From** subscription (existing, being abandoned),
- the **To** subscription (new Request ID, to be created by the Relay), and
- a paired **To Fetch Request ID** for past-content delivery.

The Relay identifies the earliest common Group boundary (`G_switch`) across
both Tracks and executes the cutover atomically: FETCH for past objects at or
after `G_switch`, SUBSCRIBE for new objects, then terminates the From
subscription with `PUBLISH_DONE`.

**Primary use case:** Client-side ABR streaming over CMAF switching sets. The
subscriber decides when and to which Track to switch; the Relay only executes
the mechanism. The Relay does not verify track equivalence.

**Motivation for SWITCH over existing primitives** (documented in PR/issue):
- UNSUBSCRIBE + SUBSCRIBE + Absolute Joining FETCH + SUBSCRIBE_UPDATE requires
  4 messages with race conditions at each step.
- At the transition point, 3 concurrent data flows exist (old SUBSCRIBE, new
  SUBSCRIBE, new FETCH) — practically unmanageable under congestion despite
  priorities (#1101).
- Subscriber does not know the Relay's cache state, so Absolute Joining FETCH
  may time out silently or cause unexpected delays.

---

## Current State of the Branch

The branch (`switch`) adds 239 lines to `draft-ietf-moq-transport.md` across
four commits:

| Commit | Summary |
|--------|---------|
| `1bd6f6af` | Initial SWITCH addition (section structure, message definition) |
| `02dd366f` | Refine: target group, common boundary, liveness, cached delivery |
| `c0b81ca7` | Remove trailing whitespace |
| `c40a3486` | Clarify boundary evidence, gating, and parameters |

Sections added:
- **`§ Subscriber Interactions`** — intro paragraph + ABR sub-section
- **`§ Relay Processing of SWITCH` (`{#relay-switch}`)** — six sub-sections:
  Common Group Boundaries, Processing Steps (G_switch algorithm, T_switch),
  Completing SWITCH using FETCH+SUBSCRIBE, Terminating the From subscription,
  Error Handling Guidance, Subscriber Considerations
- **Message table** — entry `0x12 | SWITCH`
- **`§ SWITCH` (`{#message-switch}`)** — wire format + field semantics

**Design history note:** `switch_PR_update.patch` in the repo root preserves
the February 2026 intermediate design (Old/New Request IDs, Close-After-Switch
flag, Target Group ID, Auth Info). The current branch uses a cleaner design
(From/To/Fetch, Minimum Switching Group ID, parameters). Keep the patch for
reference only — do not re-apply it.

---

## Open Issues: Strategic / WG-Level

These require a WG position or explicit reply before implementing a fix.

### S1. Server-side ABR Scope (ianswett's request)

**Thread:** PR top-level comment, 2025-11-25.

ianswett: *"I would prefer a mechanism that supports at least simple
server-side ABR as well as client-side ABR."*

wilaw's rebuttal (agreed by acbegen): server-side ABR is persistent and
requires threshold values — fundamentally different from a one-shot FROM→TO
switch. The right vehicle is a filter-based mechanism (e.g., extend the FILTER
TOP-N proposal). Mixing both into SWITCH would over-complicate the message.

**Status:** No WG consensus yet. ianswett and vasilvv have not formally
reviewed. This is the highest-risk blocker — if ianswett insists, scope needs
to be discussed at the next WG meeting before merging.

**Action:** Prepare a clear, concise counter-argument (or compromise proposal)
for the next interim. Possible compromise: explicitly state in the spec that
SWITCH is intentionally client-side only and that server-side ABR is out of
scope, to be addressed by a separate mechanism.

---

### S2. Absolute Joining FETCH Sufficiency (suhasHere's challenge)

**Thread:** PR top-level comment, 2025-12-01.

suhasHere: *"Absolute Joining FETCH was added by WG consensus to support this
exact functionality."* — implying SWITCH is redundant.

gwendalsimon's rebuttal: Absolute Joining FETCH requires 4 messages, produces
3 simultaneous data flows under congestion, and the subscriber cannot know
relay cache state.

**Status:** suhasHere did not reply to the rebuttal. The argument appears to
be accepted but not formally acknowledged. Should confirm at the next interim
that this objection is resolved.

---

### S3. New Bidirectional Stream? (yuyou's question, unanswered)

**Thread:** PR top-level comment, 2026-03-12.

yuyou: *"Does this new SWITCH control message create a new bidirectional
stream, similar to the other six message types defined in v17?"*

**Status:** No response yet (as of April 2026). SWITCH is a control-stream
message — it does NOT create a new bidirectional stream. It rides on the
existing control stream. This needs an explicit answer either in the PR or in
the spec text.

**Action:** Reply to yuyou directly on the PR. Also consider adding a
clarifying sentence to the spec intro paragraph: *"The SWITCH message is sent
on the control stream and does not create a new stream."*

---

## Open Issues: Technical / Inline Review Comments

These are concrete spec defects raised as inline review comments. Most have
been addressed in subsequent commits but a few remain open or need
verification.

### T1. Relay aggregation — cross-reference §8.4 (sharmafb + yekuiwang)

**Threads:** Comment IDs 2557844131, 2557926911, 2559833205.

sharmafb: When reusing an existing subscription for the To Track, the relay
may need to issue `SUBSCRIBE_UPDATE` to widen or narrow the filter parameters.

gwendalsimon: Confirmed — the aggregation procedure is the same as §8.4.
Proposed adding a cross-reference.

**Status:** The current branch text says parameters are applied per
`{#message-switch}` but does not explicitly cross-reference §8.4 for the
upstream aggregation path.

**Action:** Add a sentence in the Processing Steps section referencing §8.4
(subscriber interactions / relay aggregation) for upstream subscription
management.

---

### T2. Track equivalence — relay responsibility (sharmafb + acbegen)

**Threads:** Comment IDs 2557851556, 2558105736, 2558183961, 2558869341,
2558877053, 2559636968, 2560030792.

sharmafb: What prevents a subscriber from sending `SWITCH(track_a, track_b)`
where the tracks are not aligned?

acbegen: The relay does not verify equivalence — that is the subscriber's
responsibility (e.g., it knows from catalog metadata that tracks form a CMAF
switching set). If the relay cannot find a common boundary, it returns an
error.

tobbee: The spec should explicitly state that switchable tracks must have
aligned Group IDs for SWITCH to succeed.

**Status:** The current spec says SWITCH is "intended for use in applications
where the publisher defines the two Tracks as switchable." The relay does not
verify this. Error handling covers the no-common-boundary case. But the
language around Group ID alignment is weak.

**Action:** Strengthen the intro text: add one sentence explicitly stating
that SWITCH assumes the two Tracks have aligned Group IDs (i.e., they are part
of a CMAF switching set or equivalent), and that if no common boundary is
found, the relay MUST return REQUEST_ERROR.

---

### T3. SHOULD NOT vs. MUST NOT for upstream forwarding (suhasHere)

**Thread:** Comment IDs 2589352942, 2591490856.

suhasHere: Why `SHOULD NOT forward upstream` instead of `MUST NOT`?

gwendalsimon: A proxy-like relay with no cache and a single subscriber might
legitimately forward SWITCH upstream. `SHOULD NOT` captures this edge case.

**Status:** The current branch uses `MUST NOT` (commit `c40a3486`). This
change was already made. **Verify this is still the text.** (It is: line 1229.)

**Action:** No code change needed. Confirm in PR that this was addressed.

---

### T4. Forward flag semantics for To subscription (tobbee)

**Thread:** Comment ID 2560058867.

tobbee: The spec implies the To subscription starts with `forward=0` and
transitions to `forward=1` at G_switch, but this is not stated explicitly.

**Status:** Not explicitly addressed in the current text. The "Completing the
SWITCH" section describes the delivery mechanics but does not mention the
forward state of the To subscription before G_switch.

**Action:** Add a sentence clarifying that, while SWITCH is pending and before
G_switch is reached, the Relay MUST NOT forward Objects from the To Track on
the To subscription (equivalent to forward=0), and transitions to delivery
(forward=1) only after the FETCH range is exhausted.

---

### T5. Grammar fix: "SHOULD performs" → "SHOULD perform" (sharmafb)

**Thread:** Comment ID 2677617059.

**Status:** Fixed in the current branch (line 1230 reads "SHOULD perform").
**Verified — no action needed.**

---

### T6. Close-After-Switch field encoding (sharmafb)

**Thread:** Comment ID 2677631153.

sharmafb: questions using a varint for a boolean-valued `Close-After-Switch`
field.

**Status:** The `Close-After-Switch` field was **removed entirely** in the
current branch design. The relay always terminates the From subscription via
`PUBLISH_DONE`. This feedback is no longer applicable.

**Action:** Confirm in PR that this field was removed and briefly explain the
design rationale.

---

## Open Issues: Structural / Editorial

### E1. Unanswered "bidirectional stream" question (yuyou)

Covered under S3 above.

---

### E2. IANA Registration

The IANA Considerations section (`{#iana}`, line 4380) has a TODO item for
message type registration. SWITCH type `0x12` is not registered.

**Action:** Add `0x12 = SWITCH` to the MOQT Message Types table when the IANA
section is filled in. (Note: `0x12` is used as an error code in the Session
Termination and Request Error namespaces — separate IANA tables, no collision.)

---

### E3. Section Depth Inconsistency

The ABR sub-section (`#### Coordinated Track Switching...`) uses four levels
of nesting; surrounding headings use two. Inconsistent with the document style.

**Action:** Flatten the ABR sub-section to a `###` heading or remove the
sub-heading entirely and fold its content into the intro paragraph.

---

### E4. Extension Negotiation

The spec states (line 1920): *"An endpoint that receives an unknown message
type MUST close the session."* The current branch does not include a
`SWITCH_SUPPORTED` Setup parameter.

**Positions:**
- If SWITCH is in the base protocol version: no negotiation needed;
  implementations must handle it or respond with `NOT_SUPPORTED`.
- If SWITCH is an extension: a `SWITCH_SUPPORTED` Setup parameter is needed.

An earlier design (`switch_PR_update.patch`) had the extension negotiation
section. It was dropped deliberately to simplify the proposal.

**Action:** Confirm the WG's position on this during the next interim or by
explicitly asking ianswett/vasilvv in the PR. This may be a blocker.

---

### E5. T_switch — No Timeout Guidance

`T_switch` is implementation-specific. No guidance on range or relationship to
other timeouts (`DELIVERY_TIMEOUT`, `RENDEZVOUS_TIMEOUT`).

**Action:** Add a non-normative note explaining intent: T_switch should be
long enough to allow relay cache population or upstream subscription
establishment, but short enough to avoid holding subscriber state indefinitely.

---

## Work Plan

### Phase 1 — Respond to PR / WG Alignment (no code changes yet)

- [ ] Reply to yuyou on PR: SWITCH is a control-stream message, creates no
  new bidirectional stream. (S3)
- [ ] Confirm with suhasHere that Absolute Joining FETCH argument is resolved.
  (S2)
- [ ] Prepare response/proposal for ianswett's server-side ABR concern. (S1)
- [ ] Confirm status of T3 (MUST NOT) and T5 (grammar) in PR — mark as
  addressed.
- [ ] Confirm T6 (Close-After-Switch removal) in PR — explain design decision.

### Phase 2 — Targeted Spec Changes

- [ ] Add clarifying sentence: SWITCH is sent on the control stream, not a new
  stream. (S3)
- [ ] Add cross-reference to §8.4 for upstream subscription aggregation. (T1)
- [ ] Strengthen Group ID alignment language in the intro paragraph. (T2)
- [ ] Add forward-state semantics for the To subscription before G_switch. (T4)
- [ ] Add T_switch guidance note. (E5)
- [ ] Flatten ABR sub-section heading depth. (E3)

### Phase 3 — Final Polish and Review

- [ ] Add IANA registration for `0x12 = SWITCH`. (E2)
- [ ] Confirm extension negotiation position with WG; add section if needed.
  (E4)
- [ ] Run `make` to verify no kramdown build errors.
- [ ] Full diff review against `main` for editorial consistency.
- [ ] Update PR description summarizing all changes.
- [ ] Request formal re-review from ianswett and vasilvv.

---

## WG Presentation — End of April 2026

### Three Decks: Evolution

| Deck | Date | Authors | Design Used |
|------|------|---------|------------|
| `SWITCH at Relay.txt` | Feb 2025 | Simon, Law | `(oldSubID, newSubID, trackAlias, trackName, authInfo)` |
| `SWITCH Feb 2026.txt` | Feb 2026 | Simon, Law, Begen, Gurel | `Old/New Request ID, Auth Info, Close-After-Switch, Parameters` |
| `SWITCH April 2026.txt` | Apr 2026 | (current, to be prepared) | `From/To Subscribe, To Fetch, Min Switching Group, Parameters` |

The design evolved substantially: `Close-After-Switch` was dropped (relay always terminates the From subscription); `To Fetch Request ID` was added as an explicit field; `Minimum Switching Group` replaced `Target Group ID`; auth info was removed (handled by parameters). This is progress but the April deck does not yet explain *why* the design changed — reviewers who saw the Feb deck will ask.

### What the April 2026 Deck Currently Has

1. ABR use case in live TV (quality metrics, switching criteria)
2. Other SWITCH use cases (multi-view, audio language, VR, zapping)
3. "Other Noteworthy Requirement" — subscriber lag and the case for Joining FETCH during a switch
4. SWITCH API Proposal (current message format with From/To/Fetch fields)
5. Relay Behavior summary (7 steps)
6. Appendix: step-by-step relay algorithm with example (G_switch=33, past+future cases)

### What the April 2026 Deck Is Missing

The following topics must be addressed before the end-of-April meeting:

**A. Response to ianswett's server-side ABR request (HIGH — main objection)**

The Feb 2026 deck had an appendix showing server-side ABR as a possible add-on
(conditional SWITCH with metrics, threshold, and a `downstream` flag). The April
deck dropped this entirely. ianswett will raise this again.

Options:
- Explicitly position SWITCH as intentionally client-triggered only, and show
  server-side ABR as a separate mechanism (e.g., extend the FILTER TOP-N
  proposal). Make the separation architectural.
- Or: bring back the appendix slide showing server-side add-on as a *future*
  extension, to defuse the objection without expanding the current PR scope.

**B. Why SWITCH cannot be replaced by Absolute Joining FETCH (MEDIUM — suhasHere)**

The Feb 2026 deck had the most important slide for this: a step-by-step diagram
showing the current API (SUBSCRIBE B Latest + Absolute Joining FETCH B + UNSUBSCRIBE A)
with explicit problems:
- 3 concurrent subscriptions on wire
- Priorities cannot help (#1101)
- Risk of gap before B-34 arrives
- Uncertainty about relay cache state for B-34

The April deck dropped this slide. It must come back — this is the strongest
factual argument for SWITCH's existence and directly counters suhasHere's
objection.

**C. Design delta from Feb to April 2026 (MEDIUM — for credibility)**

Reviewers who attended the Feb interim saw a different message format. The April
deck must include one slide explaining what changed and why:
- `Close-After-Switch` removed → relay always terminates From via PUBLISH_DONE
- Auth info removed from message → handled via Parameters (uniform)
- `To Fetch Request ID` added → Joining FETCH is now explicit and tied to SWITCH
- `Minimum Switching Group` replaces `Target Group ID` → clearer semantics

**D. Answer to yuyou's question (LOW — but easy to handle)**

yuyou asked (March 2026): "Does SWITCH create a new bidirectional stream?"
Add one sentence on the Relay Behavior slide: *"SWITCH is sent on the existing
control stream — it does not create a new bidirectional stream."*

**E. Demo reference (LOW — builds confidence)**

The deck should reference the live demo at `https://abr.moqtail.dev/`. The Feb
deck mentioned it was forthcoming; the April deck should confirm it exists.

### Presentation Checklist

- [ ] Add / restore "why SWITCH can't be replaced by current API" slide with the
  3-concurrent-subscriptions diagram (from Feb deck appendix)
- [ ] Add a clear position on server-side ABR scope (either architectural
  separation or appendix showing future add-on)
- [ ] Add "design evolution" slide: what changed from Feb to April and why
- [ ] Add one sentence clarifying SWITCH is on the control stream (no new stream)
- [ ] Add demo reference (`abr.moqtail.dev`)
- [ ] Update the relay behavior step summary to match current spec (currently
  slide 6 is a blank placeholder; step detail is in the appendix only)
- [ ] Verify step-by-step appendix example matches current branch behavior
  exactly (especially: example uses `Minimum Switching Group = 31` and
  `G_switch = 33`, covering both past-FETCH and future-SUBSCRIBE cases)

---

## PUBLISH-Based Redesign (draft-17 alignment)

### Motivation

The current SWITCH design uses three bidi streams in draft-17 terms: a
SWITCH bidi (Request-First), a FETCH bidi (for past content), and a
SUBSCRIBE bidi (for live content). This has a fatal **2-RTT problem**:
the relay communicates G_switch in SUBSCRIBE_OK → the subscriber must
then open a Joining FETCH bidi referencing G_switch → by the second RTT,
G_switch info is potentially stale (new groups have started).

The fix: keep SWITCH as a **control-plane message** (unidirectional
subscriber→relay, no response expected on the SWITCH itself), and have
the relay respond by opening a single **PUBLISH bidi** for Track B that
delivers all Track B content (cached past objects from G_switch onwards,
then new live objects) in one seamless stream.

### Why PUBLISH Works

1. Subscriber sends SWITCH on the control stream (fire-and-forget).
2. Relay determines G_switch internally — no subscriber involvement.
3. Relay opens a PUBLISH bidi for Track B, delivers everything from
   {G_switch, 0} in order via PUBLISH subgroup data streams.
4. Subscriber receives PUBLISH, responds PUBLISH_OK — done.

One RTT total from SWITCH to receiving Track B data. The subscriber never
needs to know G_switch explicitly.

### Correlation (no Required Request ID Delta)

`Required Request ID Delta` cannot cross parity boundaries: the relay's
PUBLISH has an **odd** Request ID; the subscriber's From SUBSCRIBE has an
**even** Request ID. Their difference is odd, not divisible by 2, so the
delta encoding is structurally invalid for cross-endpoint references.

**Correlation rule:** the subscriber matches the PUBLISH's Track
namespace/name against its pending SWITCH state. The spec enforces: a
subscriber MUST NOT have more than one pending SWITCH targeting the same
target Track at a time.

### Error Signaling

Since SWITCH is a one-way control message, the relay signals failure by
opening the PUBLISH bidi for Track B and immediately sending PUBLISH_DONE
with the appropriate Status Code:

| Failure condition | PUBLISH_DONE Status Code |
|---|---|
| G_switch not found within T_switch | TIMEOUT |
| Target Track not at publisher | DOES_NOT_EXIST |
| Authorization failure | UNAUTHORIZED |
| Relay does not support SWITCH | NOT_SUPPORTED |

### Stream Count vs. Current Design

| Design | Bidi streams per switch |
|---|---|
| Current branch (FETCH+SUBSCRIBE, Request-First SWITCH) | 3 |
| Proposed (PUBLISH, control-plane SWITCH) | 1 |

### PR #1604 Dependency Analysis

**Key architectural constraint (from REWIND rejection):** A relay MUST
NOT deliver past cached objects via a PUBLISH or SUBSCRIBE stream. Past
content requires FETCH semantics. The REWIND proposal
(draft-duke-moq-subscribe-rewind, analyzed in `REWIND_ANALYSIS.md`) was
the attempt to break this rule — it was rejected by the WG. The analysis
file documents why this matters for SWITCH.

**Consequence for SWITCH:** when G_switch < current live edge
(subscriber is lagging), objects in [G_switch, live_edge - 1] are cached
past content that CANNOT be pushed via the PUBLISH stream. The subscriber
must issue a FETCH for that range.

PR #1604 ("Joining FETCH with subscription", moq-wg/moq-transport#1604,
author: martinduke) changes the Joining FETCH mechanism:

- **Before PR #1604:** Joining FETCH is a new bidi stream; the
  `Joining Request ID` field explicitly names the associated SUBSCRIBE
  Request ID. Only SUBSCRIBE can be referenced — not PUBLISH.
- **After PR #1604:** Joining FETCH is sent **on the existing SUBSCRIBE
  or PUBLISH bidi stream** — association by stream context; PUBLISH is
  now a valid association target; `Joining Request ID` field removed.

**If PR #1604 lands:**
Subscriber sends Joining FETCH on the PUBLISH bidi. No new bidi needed.
Total streams per switch: 1 PUBLISH bidi + FETCH data stream.

**If PR #1604 does not land:**
Joining FETCH cannot reference a PUBLISH (pre-#1604 restriction). The
subscriber opens a new bidi and sends a **Standalone FETCH** with
absolute range [{G_switch, 0}, {live_edge_group - 1, MAX_OBJECT_ID}].
For the subscriber to compute this range, the relay MUST include G_switch
and the current live-edge group in the PUBLISH parameters (C5 below).
The subscriber sends PUBLISH_OK and the Standalone FETCH in the same
round trip (1 RTT, no 2-RTT problem). Total streams: 2 bidis.

**Conclusion:** PR #1604 is needed for the cleanest single-bidi
implementation. Without it, SWITCH still works in 1 RTT but uses an
extra bidi for the Standalone FETCH.

### The 8 Spec Changes (all in `draft-ietf-moq-transport.md`)

#### C1 — SWITCH wire format (lines 3227–3245)
Remove `To Subscribe Request ID (vi64)` and `To Fetch Request ID (vi64)`
fields. New format:

```
SWITCH Message {
  Type (vi64) = 0x12,
  Length (16),
  From Subscribe Request ID (vi64),
  Track Namespace (..),
  Track Name Length (vi64),
  Track Name (..),
  Minimum Switching Group ID (vi64),
  Number of Parameters (vi64),
  Parameters (..) ...,
}
```

#### C2 — SWITCH section intro (lines 3222–3225)
Replace "The Relay serves 'past content' of the To Track using a FETCH
and serves new content using a SUBSCRIBE" with a description of the
relay opening a PUBLISH bidi for the To Track.

#### C3 — SWITCH field semantics (lines 3248–3295)
- Remove `To Subscribe Request ID` and `To Fetch Request ID` field
  definitions entirely.
- Update the "Upon receiving SWITCH" paragraph: replace SUBSCRIBE_OK /
  REQUEST_ERROR language with PUBLISH-based response description
  (relay opens PUBLISH bidi for To Track; on failure, relay opens
  PUBLISH bidi and immediately sends PUBLISH_DONE with error code).

#### C4 — Processing Steps (lines 1727–1767)
- Replace "REQUEST_ERROR for the To Subscribe Request ID" (all
  occurrences) with: relay opens PUBLISH bidi for To Track and
  immediately sends PUBLISH_DONE with the appropriate Status Code.
- Replace "send SUBSCRIBE_OK for the To Subscribe Request ID" with:
  relay opens a PUBLISH bidi for the To Track.
- Replace "SWITCH operation is considered successful" trigger (currently
  at SUBSCRIBE_OK) with: SWITCH is considered successful when the relay
  opens the PUBLISH for the To Track.

#### C5 — Replace "Completing the SWITCH using FETCH + SUBSCRIBE
semantics" (lines 1769–1802) ✅ APPLIED

**Final design (relay-proactive catch-up stream):**

**PUBLISH for live content:**
- The relay opens a PUBLISH bidi for the To Track (Required Request ID
  Delta = 0).
- The PUBLISH MUST include a `SWITCH_TRANSITION` parameter
  ({#switch-transition-param}) carrying {G_switch, live_edge_group}.
- The relay delivers live To Track Objects (from live_edge_group
  onwards) via PUBLISH subgroup data streams. The relay MUST NOT push
  cached past objects via the PUBLISH stream.

**Catch-up stream for past content (when G_switch < live_edge_group):**
- The relay MUST proactively open a relay-initiated unidirectional data
  stream (the "catch-up stream") — NO subscriber FETCH needed.
- Stream begins with FETCH_HEADER carrying the From Subscribe Request ID
  as the Request ID field (correlation without new header type).
- Relay delivers Objects in [G_switch, live_edge_group) in order and
  closes with FIN.
- Subscriber correlates by: FETCH_HEADER.Request_ID == pending
  SWITCH.From_Subscribe_Request_ID for matching target Track.
- If G_switch == live_edge_group: no catch-up stream opened.

**Key property: no subscriber-initiated FETCH needed.** SWITCH (with
Minimum Switching Group ID) is the implicit authorization. The relay
owns both streams; zero extra RTTs required.

**Priority model:**
- While catch-up stream is open: HIGH priority for catch-up stream,
  LOW for PUBLISH subgroup streams.
- After catch-up stream closes (FIN): NORMAL priority for PUBLISH
  subgroup streams.
- Relay controls both streams' QUIC priorities. No subscriber parameter
  needed.

**PR #1604 dependency status:** NOT REQUIRED. The new design is
self-contained — subscriber does not send any FETCH. PR #1604 is still
useful for other joining-FETCH use cases but is no longer a dependency
for SWITCH.

#### C6 — Error Handling Guidance ✅ APPLIED
- Replaced REQUEST_ERROR opening with PUBLISH_DONE-based description.
- Removed "To Fetch Request ID" paragraph.
- Updated UNSUBSCRIBE paragraph: relay abandons SWITCH; if PUBLISH
  already opened, sends PUBLISH_DONE with SUBSCRIPTION_ENDED.

#### C7 — Subscriber intro ✅ APPLIED
Added: "The Relay responds by opening a PUBLISH for the To Track; the
subscriber need not pre-allocate any Request IDs for the SWITCH."

#### C8 — Subscriber Considerations ✅ APPLIED (no changes needed)
No residual "To Fetch/Subscribe Request ID" references. Existing
(GroupID, ObjectID) overlap text remains valid.

### Note on Control Stream Compatibility with draft-17

Line 1845 reads "MOQT uses a single bidirectional stream to exchange
control messages" — this is pre-existing text from before the switch
branch was opened, not SWITCH-specific. It is **incompatible with
draft-17's unidirectional control stream model** and must be updated
when the switch branch is rebased onto upstream/main. This is tracked
as a prerequisite to the rebase, not part of the 8 changes above.

---

## Key References

- **PR:** https://github.com/moq-wg/moq-transport/pull/1378
- **Motivation issue:** moq-wg/moq-transport#1354 (still open — "Why do we
  need a dedicated SWITCH message?")
- **Original track switching problem:** moq-wg/moq-transport#1101 (closed)
- **Related open PR:** moq-wg/moq-transport#1604 "Joining FETCH with
  subscription" — hard dependency for single-bidi SWITCH; full analysis
  in `PR1604_ANALYSIS.md`
- **Live demo:** https://abr.moqtail.dev/
- **Spec file:** `draft-ietf-moq-transport.md`
- **Joining FETCH anchor:** `{#joining-fetches}` — SWITCH reuses this pattern
- **Extension negotiation anchor:** `{#extension-negotiation}` (line 804)
- **Earlier design patch:** `switch_PR_update.patch` — reference only
