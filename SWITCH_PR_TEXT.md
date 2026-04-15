# SWITCH — PR Text

Complete text of all additions to `draft-ietf-moq-transport.md` by
this PR, in reading order.

---

## 1. Addition to Subscriber Interactions

*(Inserted after the paragraph on Joining FETCH and `Next Group Start`.)*

When a subscriber is already receiving one Track and intends to join another
Track that carries equivalent content (for example a higher or lower bitrate
variant), the subscriber can use a switching procedure. The subscriber
identifies the current Track and the target Track and requests a transition at
a suitable Group boundary.

#### Coordinated Track Switching for Adaptive Bitrate Streaming

Client-side Adaptive bitrate (ABR) streaming requires a subscriber to
transition between two Tracks that represent alternative formats of the same
content. The subscriber knows which Tracks are alternatives, based on
information such as catalog metadata or an out-of-band manifest.

To request a switch, the subscriber sends a SWITCH (see {{message-switch}})
identifying the Track it is currently receiving and the Track it intends to
receive next. The subscriber determines both Tracks locally and does not rely
on the Relay or publisher to infer ABR intent from subscription patterns. The
Relay responds by opening a PUBLISH for the To Track (see {{relay-switch}});
the subscriber need not pre-allocate any Request IDs for the SWITCH.

When a Relay receives a SWITCH message, it MUST NOT forward it upstream.
Instead, the Relay SHOULD perform the transition locally, preparing the
subscription for the new Track and determining the point at which to stop
forwarding objects from the old Track and begin forwarding objects from the
new one (see {{relay-switch}}).

---

## 2. New Section: Relay Processing of SWITCH

## Relay Processing of SWITCH {#relay-switch}

A Relay that receives SWITCH is responsible for carrying out the transition
locally and MUST NOT forward the SWITCH message upstream.

### Common Group Boundaries

For the purposes of SWITCH, a Group boundary is proven by evidence that Group g
exists for a Track. A Relay considers GroupID g to be available for a Track as
soon as it has received sufficient bytes to parse an Object header that
identifies GroupID g for that Track. The Relay does not need to receive the
entire Object payload. A GroupID g is a common Group boundary for two Tracks if
Group g is available for both Tracks as defined above.

### Processing Steps

Upon receiving a SWITCH message, the Relay MUST first validate that the From
Subscribe Request ID identifies an Established subscription. If no such
subscription exists, the Relay MUST NOT open a PUBLISH for the To Track and
MUST NOT modify any existing subscription state.

If the Relay receives a SWITCH that references a From Subscribe Request ID for
which it is already processing a prior SWITCH (i.e., it has not yet opened a
PUBLISH for the prior To Track), the Relay MUST reject the new SWITCH by opening
a PUBLISH for the To Track and immediately sending PUBLISH_DONE with Status Code
EXCESSIVE_LOAD. The Relay MAY include a non-zero Retry Interval to indicate when
the subscriber can retry.

When opening the PUBLISH for the To Track, the Relay MUST apply the parameters
carried in the SWITCH message as specified in {{message-switch}}. When
establishing or selecting any upstream subscriptions and/or FETCH requests needed
to satisfy the switch, the Relay MAY consider those parameters but is not required
to send identical parameters upstream.

While attempting to perform the SWITCH operation, the Relay MAY continue
forwarding Objects from the From subscription. The Relay MUST either (a)
identify G_switch and open a PUBLISH for the To Track, or (b) open a PUBLISH for
the To Track and immediately send PUBLISH_DONE with an appropriate Status Code,
within an implementation-specific timeout T_switch. If the Relay fails to do so
within T_switch, it MUST open a PUBLISH for the To Track and immediately send
PUBLISH_DONE with Status Code TIMEOUT, and MUST NOT alter the behavior of the
subscription associated with the From Subscribe Request ID.

The Relay selects a transition GroupID G_switch as the smallest GroupID g such
that:

* g is greater than or equal to the Minimum Switching Group ID; and
* g is a common Group boundary for the From Track and the To Track.

Note that G_switch MAY be smaller than the GroupID currently being forwarded on
the From subscription. This enables a subscriber to request replacement of
buffered content that has not been consumed by the application yet.

### Completing the SWITCH using PUBLISH Delivery

Once G_switch is identified, the Relay MUST open a PUBLISH stream for the To
Track (Required Request ID Delta = 0). The PUBLISH MUST include a
SWITCH_TRANSITION parameter (see {{switch-transition-param}}) carrying G_switch
as the Switching Group ID and the current live edge GroupID of the To Track as
the Live Edge Group ID.

If G_switch is less than the Live Edge Group ID, the Relay MUST immediately
follow the PUBLISH message on the relay-to-subscriber direction of the PUBLISH
bidi with a FETCH_HEADER (see {{fetch-header}}) carrying the From Subscribe
Request ID as the Request ID field. The Relay MUST then deliver Objects in
Groups [G_switch, Live Edge Group ID) in Group and Object order, inline on
the PUBLISH bidi. No FETCH request from the subscriber is required; the SWITCH
message acts as the implicit authorization for this catch-up delivery.

The subscriber correlates the inline catch-up delivery to a pending SWITCH by
matching the FETCH_HEADER Request ID against the From Subscribe Request ID of
a pending SWITCH whose target Track matches the PUBLISH. A subscriber MUST NOT
have more than one pending SWITCH for the same target Track simultaneously.

The Relay delivers live To Track Objects — those in Groups at or after the
Live Edge Group ID — via PUBLISH subgroup data streams. The Relay MUST NOT
deliver cached past Objects via PUBLISH subgroup data streams.

The subscriber MUST treat the receipt of the first Object at GroupID equal to
the Live Edge Group ID on a PUBLISH subgroup stream as the signal that catch-up
delivery is complete.

The Relay SHOULD assign higher transmission priority to the PUBLISH bidi than
to the PUBLISH subgroup streams for the same Track during catch-up, allowing
the subscriber to close the gap to the live edge quickly. Once the subscriber
has received the first Object at the Live Edge Group ID, the Relay SHOULD
restore normal transmission priority to subsequently opened subgroup streams.

If G_switch equals the Live Edge Group ID, no past Objects exist. The Relay
MUST NOT include a FETCH_HEADER on the PUBLISH bidi and MUST deliver live
Objects via PUBLISH subgroup streams immediately.

### Terminating the From subscription

Once the Relay begins delivering Objects for the To Track at or after G_switch,
it MUST NOT deliver any further Objects from the From Track to that subscriber.

If From-track Objects are already queued on QUIC streams, the Relay MUST ensure
they are not delivered; the Relay MAY use RESET_STREAM or RESET_STREAM_AT on
affected subgroup streams to enforce this.

After committing to the transition, the Relay MUST terminate the From
subscription by sending PUBLISH_DONE for the From Subscribe Request ID.

### Error Handling Guidance

If the Relay cannot perform the requested SWITCH operation, it MUST open a
PUBLISH for the To Track and immediately send PUBLISH_DONE with an appropriate
Status Code. The following Status Code mappings are RECOMMENDED:

* TIMEOUT: The Relay could not identify G_switch within T_switch.
* DOES_NOT_EXIST: The target Track is not available at the publisher.
* UNAUTHORIZED: Authorization for the target Track failed.
* NOT_SUPPORTED: The Relay does not support the SWITCH message.

While a SWITCH is pending, if the subscriber sends UNSUBSCRIBE for the From
Subscribe Request ID before the transition occurs, the Relay SHOULD abandon the
SWITCH attempt. If the Relay has already opened a PUBLISH for the To Track, it
MUST send PUBLISH_DONE for the To Track with Status Code SUBSCRIPTION_ENDED.

### Subscriber Considerations

Because a Relay may switch into a Group that the subscriber has partially
received on the From Track, a subscriber MUST be prepared to receive Objects for
the same (GroupID,ObjectID) from both Tracks and MUST process Objects from at
most one Track for a given (GroupID,ObjectID).

---

## 3. New Parameter: SWITCH_TRANSITION

*(Added to the Message Parameters section.)*

#### SWITCH_TRANSITION Parameter {#switch-transition-param}

The SWITCH_TRANSITION parameter (Parameter Type TBD) MUST appear in a PUBLISH
opened by a Relay in response to a SWITCH message (see {{relay-switch}}). It
MUST NOT appear in any other message. The parameter value contains two
variable-length integers: the Switching Group ID (G_switch) followed by the
Live Edge Group ID. Together, these inform the subscriber of the catch-up
range [G_switch, Live Edge Group ID) delivered inline on the PUBLISH bidi, and
identify the GroupID at which live Objects begin on PUBLISH subgroup streams
(see {{relay-switch}}).

If a PUBLISH contains a SWITCH_TRANSITION parameter but no pending SWITCH
exists for that target Track, the receiver MUST close the session with
PROTOCOL_VIOLATION.

---

## 4. New Message: SWITCH

*(Added to the Control Messages section. Message type 0x12.)*

## SWITCH {#message-switch}

A Subscriber sends a SWITCH message to request that a Relay transition delivery
from a Track it is currently receiving (the "From Track", identified by the From
Subscribe Request ID) to a target Track (the "To Track", identified by the Track
Namespace and Track Name fields). In response, the Relay opens a PUBLISH stream
for the To Track. If past content exists at the transition point, the Relay
delivers it inline on the PUBLISH bidi before live Objects begin on subgroup
streams (see {{relay-switch}}).

~~~
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
~~~

The fields of the SWITCH message are as follows:

* From Subscribe Request ID:
  Identifies the Established subscription that is the source of objects before
  the transition. If no such subscription exists, the receiver MUST NOT open a
  PUBLISH for the To Track and MUST NOT modify any existing subscription state.

* Track Namespace and Track Name:
  Identify the To Track and are encoded as in SUBSCRIBE.

* Minimum Switching Group ID:
  The earliest GroupID at which the subscriber permits the transition. The
  receiver MUST select G_switch such that G_switch is greater than or equal to
  Minimum Switching Group ID, and is a common Group boundary as defined in
  {{relay-switch}}.

* Parameters:
  Version-specific Message Parameters encoded as in SUBSCRIBE. The receiver MUST
  use the Parameters present in the SWITCH message as the complete parameter set
  for the To Track PUBLISH, and MUST NOT inherit Parameters from the
  subscription identified by the From Subscribe Request ID.

Upon receiving SWITCH, the receiver attempts to select a transition point and
perform the transition as described in {{relay-switch}}. If the receiver cannot
identify a suitable transition point within T_switch, it MUST open a PUBLISH for
the To Track and immediately send PUBLISH_DONE with an appropriate Status Code,
and MUST NOT alter the behavior of the subscription associated with the From
Subscribe Request ID.
