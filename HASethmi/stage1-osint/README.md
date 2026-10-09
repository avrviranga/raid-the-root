# Stage 1 — The First Trace (OSINT / Reconnaissance)

**Owner:** IT24103666 (Challenge Design A)
**Flag:** `RTR{first-trace_RJewantha}`

## Artefacts

| File | Role |
|---|---|
| `artefacts/staff_directory_archive.html` | Archived public staff page — names, usernames, staff IDs, departments, and the email convention |
| `artefacts/paste_excerpt.txt` | Third-party conference breach dump — mostly unrelated organisations |
| `artefacts/helpdesk_ticket_4471.csv` | Service desk export — references staff by **ID only**, never by name |

Upload all three to the Stage 1 challenge in CTFd. No container required.

## How the puzzle works

No single artefact identifies the compromised account. The staff ID is the
pivot: the helpdesk export deliberately never prints a name, so the solver has
to map `NXB-2291` back through the directory. The email convention
(`first-initial.surname@nexorabank.com`) is published on the directory page,
which is what lets the leaked addresses be matched to staff IDs.

Three-way intersection:

```
directory  ∩  leaked credentials  ∩  credential-category ticket
```

| Candidate | Directory | In paste | Credential ticket | Outcome |
|---|---|---|---|---|
| `AFernando` (NXB-1104) | yes | yes | no — his ticket is a software issue | eliminated |
| `SPerera` (NXB-3310) | yes | no | yes — but routine 90-day expiry, in person | eliminated |
| `p.wickrama` | **no** — former staff | yes | no | eliminated |
| **`RJewantha` (NXB-2291)** | yes | yes | yes — lockout after 14 failed logins, 02:11 AM, phone reset | **answer** |

Verified programmatically: the intersection has exactly one member.

## Decoys and why each is there

- **`p.wickrama@nexorabank.com`** — leaked but absent from the directory. The
  page states leavers are removed at month end, so this is a former employee.
  Catches solvers who stop at "which nexorabank address is in the dump".
- **`SPerera` ticket 4465** — a credential ticket, but a routine scheduled
  expiry acknowledged in person. Contrast with 4469: unrecognised client,
  14 failed attempts, 02:11 AM, reset given over the phone on a verbal check.
  Teaches reading the ticket rather than filtering on the category column.
- **`AFernando`** — in the directory *and* the dump, so two of three match.
  Only the absence of a credential event rules him out. This is the decoy that
  makes the third artefact necessary rather than optional.
- **`HBandara` / `LJayasuriya`** — on extended leave, in Treasury Operations
  like the answer. Plausible-looking but appear in neither other source.
- **Non-bank domains** in the paste — volume, so the solver has to filter.

## Narrative payoff

Ticket 4469 is dated **2026-09-14**, weeks before the 03:47 AM transfer. This
is the "compromised weeks ago" detail that Stage 6's final evidence resolves
back to. The phone-based reset with only a verbal identity check is the
plausible mechanism by which Ghost obtained the account.

## Expected solution path

1. Open the directory; note usernames, staff IDs, and the email convention.
2. Filter the paste for `@nexorabank.com` — three addresses, one not in the
   directory.
3. Open the helpdesk CSV; it names nobody, only staff IDs.
4. Find the credential event that reads as a compromise rather than routine
   maintenance, and precedes the incident.
5. Map `NXB-2291` back through the directory → `RJewantha`.
6. Submit `RTR{first-trace_RJewantha}`.

## Dependency

The username is consumed twice downstream:

- **Stage 2** — the carrier image must be named `RJewantha_backup.png`
- **Stage 4** — the decryption key derives from this username

Changing the answer means regenerating both.

## Reset

Static artefacts. Re-upload the three files from this repository to the CTFd
challenge entry. They are versioned here, so the original state is exact.
