# RAID — Research and Information Department (NLCI)

This is background knowledge about the real-world department RAIDsystem
serves — not the software itself (see the codebase and Guide for that),
but who RAID is, what the department actually does, and how it operates.

## What RAID is

RAID is **not** a disk-storage acronym here — it's the **Research And
Information Department** of **NLCI (New Life Computer Institute)**. NLCI
is the parent organization; RAID is one department within it.

RAID documents under-resourced and endangered languages through field
survey work, and produces the reports that inform Bible translation
priorities. The department has two sides:

- **Research** — the field survey and linguistic documentation work itself.
- **Information** — technical/systems side (this app, data management,
  internal tooling).

## Org structure

- **Nidhin Joseph** — Department Manager. Approves leave, WFH, and IOU
  requests for the team.
- **Praison Cherian** — IT Head.
- **Jancy CB** — Data.
- **Jacob Thomas** — On-call developer.
- **Jayakumar Siva** — Advisor.
- Reporting/escalation runs through this chain for RAID-wide decisions.

## Office roster (attendance-tracked)

Eight people are tracked on the department's official office attendance
roster: Nidhin Joseph, Praison Cherian, Aaron A, Soumya R M, Anas Abraham,
Martin T Mathew, Abhijeet Singh, Babu Tanti.

This is a separate view from the reporting hierarchy above — some people
(Jancy, Jacob, Jayakumar) are in the reporting chain but work
remotely/advisory and aren't on the office attendance roster; others are
on the roster but not in the formal reporting chain. Both are accurate,
just answering different questions ("who reports to whom" vs. "who's
physically in the office").

There's also an external tester, **Jeremiah Johnson** (castanet.in), who
tests RAIDsystem but isn't part of the nlife.in staff roster.

## The field survey process

RAID's actual research work — documenting a language or dialect — follows
an 8-stage process from proposal through to fieldwork and finally report
submission. The real instruments used in that fieldwork include:

- **LUAV** — a survey instrument.
- **Wordlist / .cogx** — structured vocabulary comparison data.
- **Dialect Mapping** — mapping how a language varies across a region.
- **SIR / Paint Brush** — additional survey/documentation tools.

(This is generic knowledge about what these tools are for — actual survey
data collected with them, including any respondent information, is
separate and not part of this knowledge base.)

## Working days and hours

- **Monday–Friday** are full working days.
- **The last Saturday of every month** is also a working day (half-day).
- Every other Saturday, and all Sundays, are non-working.
- Standard working hours: **9:00 AM to 5:30 PM**.

## Leave policy (per-year eligibility)

- **AL (Annual/Earned Leave):** 21 days
- **CL (Casual Leave):** 10 days
- **SL (Sick Leave):** 10 days

Leave and WFH requests go through RAIDsystem's own approval workflow (see
`/attendance` to request, `/dashboard/raid-manager-dash` for a manager to
approve) — Nidhin Joseph is the real-world approver for leave, WFH, and
IOU requests.

## Where RAID's real data lives

Day-to-day department data (survey reports, language data, department
documents) lives on a Google Shared Drive named "Research And Information
Department(NLCI)" — separate from RAIDsystem's own local SQLite databases,
which hold the app's own operational data (users, attendance, library
loans, blog posts, chat).
