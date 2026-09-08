# Sentence diff: `draft-ietf-moq-transport-20` → `draft-21-retro`

Regenerate with:

    tools/sentence-diff.py draft-ietf-moq-transport-20 draft-21-retro \
        --skip-section 'Change Log' --format md > review/draft-21-sentence-diff.md

Sentences appearing in both revisions cancel out regardless of where they moved
to, so a section that was relocated but not edited produces no findings. The
Change Log is skipped: the draft-21 release notes summarize this diff, so
including them would just restate it.

#1887, #1888 and #1892 each bundled editorial clarifications with their move
upstream. Those clarifications were reverted on this branch, so the findings
below should be moves, cross-references, and the #1878 removals only — anything
else is worth a second look.

| | |
|---|---:|
| old units | 2030 |
| new units | 2046 |
| unchanged | 1995 (97.5% of new) |
| modified | 20 |
| added | 31 |
| removed | 15 |
| **total findings** | **66** |

_Section references and anchors are normalized to `§`, so retargeting a reference is not reported. Pass `--keep-refs` to include them._

## Modified (20)

`Error Handling > Session Termination Codes` ← `Sessions > Termination` · 98% similar · L4775

> When terminating the ~~Session,~~ **Session (§),** the application MAY use any error
> message and SHOULD use a relevant code, as defined below:

`Error Handling > Request Error Codes` ← `Control Messages > REQUEST_ERROR > REQUEST_ERROR Message Format` · 98% similar · L4857

> The application SHOULD use a relevant error code in ~~REQUEST_ERROR,~~ **REQUEST_ERROR
> (§),** as defined below and assigned in §.

`Error Handling > Publish Done Codes` ← `Control Messages > PUBLISH_DONE` · 98% similar · L4953

> The application SHOULD use a relevant status code in ~~PUBLISH_DONE,~~ **PUBLISH_DONE
> (§),** as defined below:

`Publishing and Receiving Tracks > Filtering Tracks and Objects > Location Filters` ← `Publishing and Retrieving Tracks > Subscriptions > Location Filters` · 97% similar · L727

> Some Location filters are defined to be relative to the Largest ~~Object.~~ **Object
> (§).**

`Notational Conventions and Common Structures > Authorization Token Compression` ← `Control Messages > Message Parameters > AUTHORIZATION TOKEN Parameter` · 94% similar · L2274

> The ~~parameter~~ value is a Token structure containing an optional Session-specific
> Alias.

`Publishing and Receiving Tracks > Filtering Tracks and Objects > Location Filters` ← `Publishing and Retrieving Tracks > Subscriptions > Location Filters` · 93% similar · L723

> Fetch requests without a filter include all Locations from {0, 0} up to Largest Object
> ~~(defined below).~~ **(§).**

`Notational Conventions and Common Structures > Authorization Token Compression` ← `Control Messages > Message Parameters > AUTHORIZATION TOKEN Parameter` · 93% similar · L2335

> The receiver of a message carrying an ~~AUTHORIZATION TOKEN~~ **Authorization Token**
> with Alias Type REGISTER that does not result in a Session error MUST register the Token
> Alias in the token cache, even if the message fails for other reasons, including
> Unauthorized.

`Object Data Model > Track > Track Naming` · 90% similar · L443

> Track Namespace is an ordered set of between 0 and 32 Track Namespace Fields, encoded as
> ~~follows:~~ **described in §.**

`Notational Conventions and Common Structures > Authorization Token Compression` ← `Control Messages > Message Parameters > AUTHORIZATION TOKEN Parameter` · 89% similar · L2331

> The receiver of a message containing a well-formed Token structure ~~but~~ **that is**
> otherwise invalid ~~AUTHORIZATION TOKEN parameter~~ MUST reject that message with an
> MALFORMED_AUTH_TOKEN error.

`Publishing and Receiving Tracks > Filtering Tracks and Objects > Range Filters` ← `Publishing and Retrieving Tracks > Subscriptions > Range Filters` · 87% similar · L750

> There are five Range Filter parameter types, ~~0x25-0x29, as shown below.~~
> **0x25-0x29.**

`Notational Conventions and Common Structures > Authorization Token Compression` ← `Control Messages > Message Parameters > AUTHORIZATION TOKEN Parameter` · 86% similar · L2372

> ~~The AUTHORIZATION TOKEN parameter~~ **An Authorization Token** MAY be repeated within
> a message as long as the combination of Token Type and Token Value are unique after
> resolving any aliases.

`Control Messages > Control Message Parameters > LOCATION FILTER Parameter` ← `Control Messages > Message Parameters > LOCATION FILTER Parameter` · 82% similar · L3649

> ~~It~~ **The LOCATION_FILTER parameter (Parameter Type 0x21)** MAY appear in a FETCH,
> SUBSCRIBE, PUBLISH, REQUEST_UPDATE (for a subscription) or PUBLISH_STATE_NOTIFY message.

`Notational Conventions and Common Structures > Authorization Token Compression` ← `Control Messages > Message Parameters > AUTHORIZATION TOKEN Parameter` · 74% similar · L2376

> Messages carrying ~~the AUTHORIZATION TOKEN parameter~~ **an Authorization Token** can
> appear on different control streams.

`Control Messages > Control Message Parameters > SUBGROUP FILTER Parameter` ← `Control Messages > FETCH_OK` · 67% similar · L3706

> See **§ and** §.

`Control Messages > Control Message Parameters > OBJECTID FILTER Parameter` ← `Data Streams and Datagrams` · 67% similar · L3720

> See **§ and** §.

`Control Messages > Control Message Parameters > PRIORITY FILTER Parameter` ← `Data Streams and Datagrams > Objects > Object Header` · 67% similar · L3734

> See **§ and** §.

`Control Messages > Control Message Parameters > OBJECT PROPERTY FILTER Parameter` ← `Data Streams and Datagrams > Objects > Object Header > Object Properties` · 67% similar · L3752

> See **§ and** §.

`Control Messages > Control Message Parameters > TRACK PROPERTY FILTER Parameter` ← `MOQT Properties > DEFAULT PUBLISHER PRIORITY` · 67% similar · L3771

> See **§ and** §.

`Publishing and Receiving Tracks > Filtering Tracks and Objects > Location Filters` ← `Publishing and Retrieving Tracks > Subscriptions > Location Filters` · 67% similar · L733

> Note that due to network reordering or prioritization, relays can receive Objects with
> Locations smaller than Largest Object after the ~~SUBSCRIBE~~ **filter** is processed,
> but these Objects do not pass ~~this filter.~~ **a filter that starts at the Next
> Object.**

`Control Messages > Control Message Parameters > LOCATION FILTER Parameter` ← `Publishing and Retrieving Tracks > Subscriptions > Location Filters` · 63% similar · L3680

> If only StartGroup and StartObject are present and both 0, the start Location is the
> Next Object ~~which is {Largest Object.Group, Largest Object.Object + 1}, or {0, 0} if
> no content has been delivered yet.~~ **(see §).**

## Added (31)

`Introduction > Document Structure` · L90

> **This document describes the MOQT protocol and is structured as follows:**

`Introduction > Document Structure` · L92

> **The core concepts and functionality are described first**

`Introduction > Document Structure` · L93

> **Section 2 § Object Data Model describes how Objects, Tracks and Namespaces relate**

`Introduction > Document Structure` · L94

> **Section 3 § Describes how Objects in Tracks are Published and Retrieved.**

`Introduction > Document Structure` · L95

> **Section 4 § Describes mechanisms for discovering Namespaces and Tracks**

`Introduction > Document Structure` · L97

> **Next, the document describes how Objects are transmitted and MOQT Sessions**

`Introduction > Document Structure` · L98

> **Section 5 § Describes ways MOTQ allows a subscriber to influence Object transmission
> order**

`Introduction > Document Structure` · L99

> **Section 6 § Describes how to initiate a session and key properties of a session, such
> as extensibility.**

`Introduction > Document Structure` · L100

> **Section 7 § Describes key properties and requirements of MOQT relays**

`Introduction > Document Structure` · L102

> **Then the document describes how Control Messages and Objects are serialized and sent**

`Introduction > Document Structure` · L103

> **Section 8 § Notational Conventions and Common Structures details structures used by
> subsequent sections**

`Introduction > Document Structure` · L104

> **Section 9 § Control Messages details how Control Messages are sent, including their
> wire encoding**

`Introduction > Document Structure` · L105

> **Section 10 § MOQT Properties describes Track and Object properties defined in the core
> protocol**

`Introduction > Document Structure` · L106

> **Section 11 § Data streams describes the mapping and serialization of Objects onto
> streams and datagrams**

`Introduction > Document Structure` · L108

> **Finally, the document discusses deployment related considerations**

`Introduction > Document Structure` · L109

> **Section 12 § Discusses MOQT errors and how to best handle them**

`Introduction > Document Structure` · L110

> **Section 13 § Describes how to utilize unspecified codepoints to prevent protocol
> ossification.**

`Introduction > Document Structure` · L111

> **Section 14 § Discusses transport related considerations, including congestion
> control**

`Introduction > Document Structure` · L112

> **Section 15 § Discusses security considerations, including denial-of-service and
> authentication**

`Publishing and Receiving Tracks > Subscriptions > Largest Object` · L681

> **The Next Object is the Location immediately following Largest Object, which is
> {Largest Object.Group, Largest Object.Object + 1}, or {0, 0} if no content has been
> delivered yet.**

`Publishing and Receiving Tracks > Filtering Tracks and Objects > Location Filters` · L715

> **A Location filter is encoded as specified in §.**

`Publishing and Receiving Tracks > Filtering Tracks and Objects > Range Filters` · L750

> **They share the encoding specified in §.**

`Sessions > Termination` · L1639

> **The error codes used when terminating a Session are defined in §.**

`Notational Conventions and Common Structures > Range Filter Structure` · L2146

> **Each Range Filter parameter (see §) carries a sequence of Ranges, encoded as
> follows:**

`Notational Conventions and Common Structures > Track Namespace Structure` · L2171

> **Track Namespace (§) is encoded as follows:**

`Notational Conventions and Common Structures > Authorization Token Compression` · L2269

> **Authorization tokens are carried in the AUTHORIZATION TOKEN message parameter (see §)
> and the AUTHORIZATION TOKEN Setup Option (see §).**

`Notational Conventions and Common Structures > Authorization Token Compression` · L2269

> **Both use the wire format and semantics defined in this section.**

`Control Messages > SETUP > AUTHORIZATION TOKEN` · L2557

> **The option value is a Token structure, whose wire format and semantics are defined in
> §.**

`Control Messages > REQUEST_ERROR > REQUEST_ERROR Message Format` · L2783

> **The error codes used in REQUEST_ERROR are defined in §.**

`Control Messages > PUBLISH_DONE` · L3063

> **The status codes used in PUBLISH_DONE are defined in §.**

`Control Messages > Control Message Parameters > AUTHORIZATION TOKEN Parameter` · L3545

> **The parameter value is a Token structure, whose wire format and semantics are defined
> in §.**

## Removed (15)

`Introduction` · L88

> ~~§ describes the data model employed by MOQT.~~

`Introduction` · L90

> ~~§ covers aspects of setting up an MOQT session.~~

`Introduction` · L92

> ~~§ covers mechanisms for prioritizing subscriptions.~~

`Introduction` · L94

> ~~§ covers behavior at the relay entities.~~

`Introduction` · L96

> ~~§ covers how control messages are encoded on the wire.~~

`Introduction` · L98

> ~~§ covers how data messages are encoded on the wire.~~

`Sessions > Session establishment > Connection URL` · L988

> ~~Each track MAY have one or more associated connection URLs specifying network hosts
> through which a track may be accessed.~~

`Sessions > Session establishment > Connection URL` · L988

> ~~The syntax of the Connection URL and the associated connection setup procedures are
> specific to the underlying transport protocol usage (see §).~~

`Publishing and Retrieving Tracks > Subscriptions > Location Filters` · L1546

> ~~Objects delivered via a fill fetch stream (see §) are fill-delivered.~~

`Control Messages > Message Parameters > LOCATION FILTER Parameter` · L2849

> ~~The LOCATION_FILTER parameter (Parameter Type 0x21) uses length-prefixed encoding.~~

`Data Streams and Datagrams > Streams > Stream Cancellation` · L4415

> ~~Streams aside from the control streams MAY be canceled due to congestion or other
> reasons by either the publisher or subscriber.~~

`Data Streams and Datagrams > Streams > Stream Cancellation` · L4415

> ~~Early termination of a unidirectional stream does not affect the MOQT application
> state, and therefore has no effect on outstanding subscriptions.~~

`Data Streams and Datagrams > Streams > Stream Cancellation` · L4415

> ~~Closing a bidirectional request stream is governed by §.~~

`Data Streams and Datagrams > Examples` · L4795

> ~~Sending a subgroup on one stream:~~

`Data Streams and Datagrams > Examples` · L4819

> ~~Sending a group on one stream, with the first object containing two Properties.~~
