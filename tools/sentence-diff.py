#!/usr/bin/env python3
"""Sentence-level semantic diff between two revisions of an I-D.

Line-based diffs are useless for a draft that has been reorganized: moving a
paragraph and re-wrapping it looks identical to rewriting it.  This tool throws
away the things reorganization changes (line wrapping, ordering, section
nesting, cross-reference targets) and compares what is left: the set of
sentences.

Sentences that appear in both revisions cancel out, no matter where they moved
to.  What survives is reported as ADDED, REMOVED, or -- when a leftover pair is
similar enough -- MODIFIED with a word-level diff.

Usage:
    tools/sentence-diff.py                       # draft-20 tag vs working tree
    tools/sentence-diff.py draft-ietf-moq-transport-20 draft-21-retro
    tools/sentence-diff.py OLD NEW --format md > review.md

OLD and NEW are each either a git revision (tag, branch, sha) or a path to a
markdown file.  Run with --help for the full option list.
"""

import argparse
import difflib
import os
import re
import subprocess
import sys
from collections import defaultdict

DEFAULT_DRAFT = "draft-ietf-moq-transport.md"

# ---------------------------------------------------------------- extraction

FENCE_RE = re.compile(r"^\s*(~~~+|```+)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
ATTR_RE = re.compile(r"^\s*\{:")
LIST_RE = re.compile(r"^\s*([*+-]|\d+\.)\s+")
DL_BODY_RE = re.compile(r"^:\s+")
TABLE_RE = re.compile(r"^\s*\|")


class Unit:
    """One comparable chunk of the document."""

    __slots__ = ("text", "norm", "kind", "path", "line")

    def __init__(self, text, norm, kind, path, line):
        self.text = text
        self.norm = norm
        self.kind = kind  # sentence | table | figure
        self.path = path
        self.line = line


def strip_front_matter(lines):
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() in ("---", "..."):
                return lines[i + 1 :], i + 1
    return lines, 0


def heading_path(stack):
    return " > ".join(t for _, t in stack)


def parse(md, include_tables, include_figures, skip_sections):
    """Split a markdown document into comparable units."""
    lines, offset = strip_front_matter(md.splitlines())
    units = []
    stack = []          # [(level, title)]
    para = []           # accumulated wrapped lines
    para_line = 0
    fence = None
    figure = []
    figure_line = 0
    skipping = None     # heading level we are skipping under

    def flush_para():
        nonlocal para
        if not para:
            return
        text = " ".join(s.strip() for s in para)
        text = re.sub(r"\s+", " ", text).strip()
        if text and skipping is None:
            for sent in split_sentences(text):
                units.append(Unit(sent, "", "sentence", heading_path(stack), para_line))
        para = []

    for idx, raw in enumerate(lines, start=offset + 1):
        line = raw.rstrip()

        m = FENCE_RE.match(line)
        if m:
            marker = m.group(1)[0] * 3
            if fence is None:
                flush_para()
                fence = marker
                figure = []
                figure_line = idx
            elif line.strip().startswith(fence):
                if include_figures and skipping is None:
                    body = "\n".join(figure).strip()
                    if body:
                        units.append(
                            Unit(body, "", "figure", heading_path(stack), figure_line)
                        )
                fence = None
            continue
        if fence is not None:
            figure.append(line)
            continue

        m = HEADING_RE.match(line)
        if m:
            flush_para()
            level, title = len(m.group(1)), m.group(2)
            clean = re.sub(r"\s*\{#[^}]*\}\s*$", "", title).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, clean))
            if skipping is not None and level <= skipping:
                skipping = None
            if skipping is None and any(
                re.search(p, clean, re.I) for p in skip_sections
            ):
                skipping = level
            continue

        if ATTR_RE.match(line):
            continue

        if TABLE_RE.match(line):
            flush_para()
            if include_tables and skipping is None:
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c or "-") for c in cells):
                    units.append(
                        Unit(line.strip(), "", "table", heading_path(stack), idx)
                    )
            continue

        if not line.strip():
            flush_para()
            continue

        if LIST_RE.match(line) or DL_BODY_RE.match(line):
            flush_para()
            para_line = idx
            para = [line]
            continue

        if not para:
            para_line = idx
        para.append(line)

    flush_para()
    return units


# ------------------------------------------------------------------ sentences

_ABBREV = r"e\.g|i\.e|etc|cf|vs|Fig|Sec|No|approx|resp|al|Ch|pp"
_SENT_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z`*\[(\"'\u2018\u201c]|\d)")


def split_sentences(text):
    t = re.sub(r"\b(%s)\." % _ABBREV, lambda m: m.group(1) + "\x00", text, flags=re.I)
    t = re.sub(r"(\d)\.(\d)", "\\1\x00\\2", t)          # decimals
    t = re.sub(r"\b([A-Z])\.", "\\1\x00", t)             # initials
    out = []
    for part in _SENT_END.split(t):
        part = part.replace("\x00", ".").strip()
        if part:
            out.append(part)
    return out


# --------------------------------------------------------------- normalization

REF_RE = re.compile(r"\{\{[^}]*\}\}")
ANCHOR_RE = re.compile(r"\{#[^}]*\}")
ATTRBLK_RE = re.compile(r"\{:[^}]*\}")
MDLINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")


def normalize(s, ignore_case=False, keep_refs=False):
    # Refs collapse to a placeholder rather than vanishing, so that "(§)" still
    # reads as a cross-reference while retargeting it stays invisible.
    if not keep_refs:
        s = REF_RE.sub("§", s)
    s = ANCHOR_RE.sub(" ", s)
    s = ATTRBLK_RE.sub(" ", s)
    s = MDLINK_RE.sub(r"\1", s)
    s = LIST_RE.sub("", s)
    s = DL_BODY_RE.sub("", s)
    # Underscores are part of protocol identifiers here, not emphasis.
    s = s.replace("`", "").replace("**", "").replace("*", "")
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\u2014", "--").replace("\u2013", "-")
    s = re.sub(r"\s+", " ", s).strip()
    if ignore_case:
        s = s.lower()
    return s


# ------------------------------------------------------------------- matching

def cancel_exact(old, new):
    """Remove units whose normalized form appears on both sides."""
    old_by = defaultdict(list)
    for u in old:
        old_by[u.norm].append(u)
    new_by = defaultdict(list)
    for u in new:
        new_by[u.norm].append(u)

    kept_old, kept_new, same = [], [], 0
    for key, olds in old_by.items():
        news = new_by.get(key, [])
        n = min(len(olds), len(news))
        same += n
        kept_old.extend(olds[n:])
    for key, news in new_by.items():
        olds = old_by.get(key, [])
        n = min(len(olds), len(news))
        kept_new.extend(news[n:])
    return kept_old, kept_new, same


def pair_modified(removed, added, threshold):
    """Greedily pair leftovers that are similar enough to call a rewrite."""
    cands = []
    for i, r in enumerate(removed):
        sm = difflib.SequenceMatcher()
        sm.set_seq2(r.norm)
        for j, a in enumerate(added):
            sm.set_seq1(a.norm)
            if sm.real_quick_ratio() < threshold or sm.quick_ratio() < threshold:
                continue
            ratio = sm.ratio()
            if ratio >= threshold:
                cands.append((ratio, i, j))
    cands.sort(key=lambda t: -t[0])

    used_r, used_a, pairs = set(), set(), []
    for ratio, i, j in cands:
        if i in used_r or j in used_a:
            continue
        used_r.add(i)
        used_a.add(j)
        pairs.append((ratio, removed[i], added[j]))
    pairs.sort(key=lambda p: -p[0])
    return (
        pairs,
        [r for i, r in enumerate(removed) if i not in used_r],
        [a for j, a in enumerate(added) if j not in used_a],
    )


# -------------------------------------------------------------------- output

class Style:
    def __init__(self, color, fmt):
        self.color = color
        self.fmt = fmt

    def dele(self, s):
        if self.fmt == "md":
            return "~~%s~~" % s
        return "\033[31m[-%s-]\033[0m" % s if self.color else "[-%s-]" % s

    def ins(self, s):
        if self.fmt == "md":
            return "**%s**" % s
        return "\033[32m{+%s+}\033[0m" % s if self.color else "{+%s+}" % s

    def dim(self, s):
        return "\033[2m%s\033[0m" % s if self.color and self.fmt != "md" else s

    def head(self, s):
        if self.fmt == "md":
            return "\n## %s\n" % s
        return "\033[1m%s\033[0m" % s if self.color else s


def word_diff(a, b, st):
    aw, bw = a.split(), b.split()
    sm = difflib.SequenceMatcher(None, aw, bw)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            out.append(" ".join(aw[i1:i2]))
        elif tag == "delete":
            out.append(st.dele(" ".join(aw[i1:i2])))
        elif tag == "insert":
            out.append(st.ins(" ".join(bw[j1:j2])))
        else:
            out.append(st.dele(" ".join(aw[i1:i2])))
            out.append(st.ins(" ".join(bw[j1:j2])))
    return " ".join(x for x in out if x)


ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def wrap(text, width, indent):
    """Wrap to `width` columns, not counting ANSI escapes toward the width."""
    if width <= 0:
        return indent + text
    lines, cur, curlen = [], [], len(indent)
    for w in text.split():
        wlen = len(ANSI_RE.sub("", w))
        if cur and curlen + 1 + wlen > width:
            lines.append(indent + " ".join(cur))
            cur, curlen = [w], len(indent) + wlen
        else:
            curlen += (1 if cur else 0) + wlen
            cur.append(w)
    if cur:
        lines.append(indent + " ".join(cur))
    return "\n".join(lines)


# ---------------------------------------------------------------------- input

def load(spec, draft, repo):
    """Read a document from a file path or `git show <rev>:<draft>`."""
    if os.path.exists(spec) and not os.path.isdir(spec):
        with open(spec, encoding="utf-8") as fh:
            return fh.read()
    target = spec if ":" in spec else "%s:%s" % (spec, draft)
    try:
        return subprocess.run(
            ["git", "-C", repo, "show", target],
            check=True, capture_output=True, text=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        sys.exit("error: cannot read %r as a file or a git object\n%s"
                 % (spec, exc.stderr.strip()))


# ----------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(
        description="Sentence-level semantic diff between two revisions of an I-D.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Usage:")[1] if "Usage:" in __doc__ else None,
    )
    ap.add_argument("old", nargs="?", default="draft-ietf-moq-transport-20",
                    help="old revision or file (default: %(default)s)")
    ap.add_argument("new", nargs="?", default=None,
                    help="new revision or file (default: the working tree)")
    ap.add_argument("--draft", default=DEFAULT_DRAFT,
                    help="draft filename inside a git revision (default: %(default)s)")
    ap.add_argument("-C", "--repo", default=".", help="repository root")
    ap.add_argument("-t", "--threshold", type=float, default=0.6,
                    help="similarity 0-1 above which a pair counts as MODIFIED "
                         "rather than separate ADDED/REMOVED (default: %(default)s)")
    ap.add_argument("--ignore-case", action="store_true",
                    help="treat casing changes as identical")
    ap.add_argument("--keep-refs", action="store_true",
                    help="do NOT strip {{section-refs}}; retargeting will show up")
    ap.add_argument("--tables", action="store_true", help="also compare table rows")
    ap.add_argument("--figures", action="store_true",
                    help="also compare fenced blocks (wire diagrams)")
    ap.add_argument("--skip-section", action="append", default=[],
                    metavar="REGEX",
                    help="skip sections whose title matches (repeatable), "
                         "e.g. --skip-section 'Change Log'")
    ap.add_argument("--only", metavar="REGEX",
                    help="only compare units whose section path matches; note that "
                         "text moved OUT of the matched section then reads as REMOVED")
    ap.add_argument("--format", choices=("text", "md"), default="text")
    ap.add_argument("--color", choices=("auto", "always", "never"), default="auto")
    ap.add_argument("--width", type=int, default=88,
                    help="wrap width for text output, 0 to disable")
    ap.add_argument("--no-context", action="store_true",
                    help="omit the section path shown above each finding")
    ap.add_argument("--stats", action="store_true", help="print only the summary")
    ap.add_argument("--exit-code", action="store_true",
                    help="exit 1 when there are findings (for CI)")
    args = ap.parse_args()

    if args.new is None:
        args.new = os.path.join(args.repo, args.draft)

    color = args.color == "always" or (
        args.color == "auto" and sys.stdout.isatty() and args.format == "text"
    )
    st = Style(color, args.format)

    old_md = load(args.old, args.draft, args.repo)
    new_md = load(args.new, args.draft, args.repo)

    old = parse(old_md, args.tables, args.figures, args.skip_section)
    new = parse(new_md, args.tables, args.figures, args.skip_section)
    for u in old + new:
        u.norm = normalize(u.text, args.ignore_case, args.keep_refs)
    old = [u for u in old if u.norm]
    new = [u for u in new if u.norm]

    if args.only:
        pat = re.compile(args.only, re.I)
        old = [u for u in old if pat.search(u.path)]
        new = [u for u in new if pat.search(u.path)]

    kept_old, kept_new, same = cancel_exact(old, new)
    pairs, removed, added = pair_modified(kept_old, kept_new, args.threshold)

    total_new = len(new)
    changed = len(pairs) + len(removed) + len(added)
    pct = (100.0 * same / total_new) if total_new else 0.0
    counts = [
        ("old units", len(old)), ("new units", len(new)),
        ("unchanged", "%d (%.1f%% of new)" % (same, pct)),
        ("modified", len(pairs)), ("added", len(added)),
        ("removed", len(removed)), ("total findings", changed),
    ]
    note = ("Section references and anchors are normalized to `§`, so "
            "retargeting a reference is not reported. Pass `--keep-refs` to "
            "include them.")

    if args.format == "md":
        out = render_md(args, st, counts, note, pairs, added, removed)
    else:
        out = render_text(args, st, counts, note, pairs, added, removed)

    while out and not out[-1].strip():
        out.pop()
    print("\n".join(out))
    return 1 if (args.exit_code and changed) else 0


def render_text(args, st, counts, note, pairs, added, removed):
    out = [st.head("SUMMARY")]
    for label, value in counts:
        out.append("  %-18s %s" % (label, value))
    if not args.keep_refs:
        plain = re.sub(r"`", "", note)
        out.append(st.dim(wrap(plain, args.width, "  ")))
    if args.stats:
        return out

    ind = "    "
    for title, items in (("MODIFIED", pairs), ("ADDED", added), ("REMOVED", removed)):
        if not items:
            continue
        out.append(st.head("%s  (%d)" % (title, len(items))))
        for item in items:
            if title == "MODIFIED":
                ratio, r, a = item
                ctx = a.path if a.path == r.path else "%s  <-  %s" % (a.path, r.path)
                meta = "  [%s]  %.0f%% similar  L%d" % (ctx, ratio * 100, a.line)
                body = word_diff(r.norm, a.norm, st)
            else:
                u = item
                meta = "  [%s]  L%d" % (u.path, u.line)
                body = st.ins(u.norm) if title == "ADDED" else st.dele(u.norm)
            if not args.no_context:
                out.append(st.dim(meta))
            out.append(wrap(body, args.width, ind))
            out.append("")
    return out


def render_md(args, st, counts, note, pairs, added, removed):
    """Markdown suitable for pasting into a GitHub issue or PR."""
    out = ["# Sentence diff: `%s` → `%s`" % (args.old, args.new), ""]
    out.append("| | |")
    out.append("|---|---:|")
    for label, value in counts:
        bold = "**%s**" % label if label == "total findings" else label
        val = "**%s**" % value if label == "total findings" else value
        out.append("| %s | %s |" % (bold, val))
    out += ["", "_%s_" % note, ""]
    if args.stats:
        return out

    for title, items in (("Modified", pairs), ("Added", added), ("Removed", removed)):
        if not items:
            continue
        out += ["## %s (%d)" % (title, len(items)), ""]
        for item in items:
            if title == "Modified":
                ratio, r, a = item
                ctx = md_path(a.path)
                if a.path != r.path:
                    ctx += " ← %s" % md_path(r.path)
                meta = "%s · %.0f%% similar · L%d" % (ctx, ratio * 100, a.line)
                body = word_diff(r.norm, a.norm, st)
            else:
                u = item
                meta = "%s · L%d" % (md_path(u.path), u.line)
                body = st.ins(u.norm) if title == "Added" else st.dele(u.norm)
            if not args.no_context:
                out += [meta, ""]
            # Blockquote keeps the sentence visually distinct from the heading.
            out += ["> " + ln for ln in wrap(body, args.width, "").split("\n")]
            out.append("")
    return out


def md_path(s):
    """Section paths go in a code span: no escaping, no emphasis collisions."""
    return "`%s`" % s.replace("`", "")


if __name__ == "__main__":
    sys.exit(main())
