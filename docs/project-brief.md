# Project Brief — Yard Sign Request to Delivery

**Client:** Jessica Rushing, candidate for the Massachusetts Plymouth 6th District
**Course:** MLD-371, Artificial Intelligence and Civil Society (HKS)
**Workflow diagram:** [yard-sign-workflow.pdf](yard-sign-workflow.pdf)

## The ask

Jessica needs help managing campaign yard sign requests and delivery. Today the
campaign runs on a Google Form that feeds a Google Sheet: the form captures the
request, but everything after it — verification, assignment, delivery
confirmation, and follow-up — is manual and untracked.

We proposed leveraging AI and automation to add the functionality the current
setup lacks, chiefly request tracking and the elimination of redundant
hand-offs, so campaign staff spend their time on judgment calls rather than
transcription.

## Current workflow

1. Upon request, provide a QR code that directs constituents to a Google Form.
2. Constituent completes the form.
3. Data from the form is stored in a Google Sheet.
4. Campaign staff review each request and pass it to the respective town captain
   for delivery.
5. Delivery is completed.
6. Within 48 hours after the election, all signs must be picked up.

**Where it breaks down.** Steps 4 and 5 carry no status of their own. Once a row
leaves the sheet for a town captain, the campaign has no record of whether the
sign was delivered, and the supporter has no way to check. Step 6 has no list to
work from, because nothing recorded where the signs ended up.

## Proposed workflow

A supporter requests a yard sign through an intake form and instantly receives a
confirmation email with a status tracking link. Automation validates and
geocodes the address, assigns it to a town, and logs it to the database as
**New**.

Campaign staff work through a review queue to verify the address, set the sign
count, and approve the request. A live dashboard shows approved, pending, and
delivered signs by town.

Each night, the system groups approved requests by town, builds an optimized
route, and emails each town captain a route list with map pins and **Delivered**
buttons. The captain picks up signs at the town drop point, delivers them along
the route, and taps **Delivered** at each stop, which timestamps the delivery
and updates the sheet and dashboard automatically.

The supporter then receives a thank-you email — including a photo of the
installed sign — with an ask to volunteer or donate.

### By lane

| Lane | Steps |
| --- | --- |
| **Supporter** | Submits request → gets confirmation email + tracking link → gets thank-you email with photo and volunteer/donate ask |
| **Automation** | Validate + geocode address, auto-assign town, log as New → nightly batch: group approved requests by town, build optimized route → dispatch route email to town captain → update sheet + dashboard, timestamp delivery |
| **Campaign staff** | Review queue: verify address, set sign count, approve → live dashboard: approved, pending, and delivered by town |
| **Town captain** | Pick up signs at town drop point → deliver along route, tap Delivered at each stop |

### What this changes

- Every request carries a status (New → Approved → Delivered) that both staff and
  the supporter can see, replacing the current blind hand-off.
- Route building and captain dispatch become a nightly batch rather than a staff
  task repeated per request.
- Delivery confirmation is captured at the point of delivery by the person doing
  it, so the sheet and dashboard stay current without anyone transcribing.
- Each delivery becomes a volunteer/donate touchpoint at the moment goodwill is
  highest.

## Open questions

1. **Intake platform.** The diagram shows a Google Form; we are considering
   alternatives that support validation and a tracking link natively. Staying on
   Google Forms keeps the QR codes and staff habits intact, so the trade-off is
   worth deciding explicitly and early.
2. **Post-election retrieval.** The current workflow requires all signs to be
   picked up within 48 hours of the election, but the proposed workflow has no
   counterpart step. The delivery records we capture are exactly the pickup list
   that step needs — this looks like a gap to close rather than a scope cut.
3. **Sign inventory.** The workflow assumes signs are available at the town drop
   point. Whether the system should track stock per town, and warn when approved
   requests exceed it, is undecided.
