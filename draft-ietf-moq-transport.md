---
title: "Media over QUIC Transport"
abbrev: moq-transport
docname: draft-ietf-moq-transport-latest
date: {DATE}
category: std

ipr: trust200902
area:  "Web and Internet Transport"
submissionType: IETF
workgroup: "Media Over QUIC"
keyword:
 - media over quic
venue:
  group: "Media Over QUIC"
  type: "Working Group"
  mail: "moq@ietf.org"
  arch: "https://mailarchive.ietf.org/arch/browse/moq/"
  github: "moq-wg/moq-transport"
  latest: "https://moq-wg.github.io/moq-transport/draft-ietf-moq-transport.html"

stand_alone: yes
smart_quotes: no
pi: [toc, sortrefs, symrefs, docmapping]

author:
  -
    ins: L. Curley
    name: Luke Curley
    organization: Discord
    email: kixelated@gmail.com

  -
    ins: K. Pugin
    name: Kirill Pugin
    organization: Meta
    email: ikir@meta.com

  -
    ins: S. Nandakumar
    name: Suhas Nandakumar
    organization: Cisco
    email: snandaku@cisco.com

  -
    ins: V. Vasiliev
    name: Victor Vasiliev
    organization: Google
    email: vasilvv@google.com

  -
    ins: I. Swett
    name: Ian Swett
    organization: Google
    email: ianswett@google.com
    role: editor

normative:
  QUIC: RFC9000
  WebTransport: I-D.ietf-webtrans-http3

informative:

--- abstract

This document defines the core behavior for Media over QUIC Transport
(MOQT), a media transport protocol designed to operate over QUIC and
WebTransport, which have similar functionality. MOQT allows a producer of
media to publish data and have it consumed via subscription by a
multiplicity of endpoints. It supports intermediate content distribution
networks and is designed for high scale and low latency distribution.

--- middle


# Introduction

Media Over QUIC Transport (MOQT) is a protocol that is optimized
for the QUIC protocol {{QUIC}}, either directly or via WebTransport
{{WebTransport}}, for the dissemination of media. MOQT utilizes a
publish/subscribe workflow in which producers of media publish data in
response to subscription requests from a multiplicity of endpoints. MOQT
supports wide range of use-cases with different resiliency and latency
(live, interactive) needs without compromising the scalability and cost
effectiveness associated with content delivery networks.

MOQT is a generic protocol designed to work in concert with multiple
MoQ Streaming Formats. These MoQ Streaming Formats define how content is
encoded, packaged, and mapped to MOQT objects, along with policies for
discovery and subscription.

* {{model}} describes the object model employed by MOQT.

* {{session}} covers aspects of setting up a MOQT session.

* {{priorities}} covers mechanisms for prioritizing subscriptions.

* {{relays-moq}} covers behavior at the relay entities.

* {{message}} covers how control messages are encoded on the wire.

* {{data-streams}} covers how data messages are encoded on the wire.


## Motivation

The development of MOQT is driven by goals in a number of areas -
specifically latency, the robust feature set of QUIC and relay
support.

### Latency

Latency is necessary to correct for variable network throughput. Ideally live
content is consumed at the same bitrate it is produced. End-to-end latency would
be fixed and only subject to encoding and transmission delays. Unfortunately,
networks have variable throughput, primarily due to congestion. Attempting to
deliver content encoded at a higher bitrate than the network can support causes
queuing along the path from producer to consumer. The speed at which a protocol
can detect and respond to congestion determines the overall latency. TCP-based
protocols are simple but are slow to detect congestion and suffer from
head-of-line blocking. Protocols utilizing UDP directly can avoid queuing, but
the application is then responsible for the complexity of fragmentation,
congestion control, retransmissions, receiver feedback, reassembly, and
more. One goal of MOQT is to achieve the best of both these worlds: leverage the
features of QUIC to create a simple yet flexible low latency protocol that can
rapidly detect and respond to congestion.

### Leveraging QUIC

The parallel nature of QUIC streams can provide improvements in the face
of loss. A goal of MOQT is to design a streaming protocol to leverage
the transmission benefits afforded by parallel QUIC streams as well
exercising options for flexible loss recovery.

### Convergence

Some live media architectures today have separate protocols for ingest and
distribution, for example RTMP and HTTP based HLS or DASH. Switching protocols
necessitates intermediary origins which re-package the
media content. While specialization can have its benefits, there are efficiency
gains to be had in not having to re-package content. A goal of MOQT is to
develop a single protocol which can be used for transmission from contribution
to distribution. A related goal is the ability to support existing encoding and
packaging schemas, both for backwards compatibility and for interoperability
with the established content preparation ecosystem.

### Relays

An integral feature of a protocol being successful is its ability to
deliver media at scale. Greatest scale is achieved when third-party
networks, independent of both the publisher and subscriber, can be
leveraged to relay the content. These relays must cache content for
distribution efficiency while simultaneously routing content and
deterministically responding to congestion in a multi-tenant network. A
goal of MOQT is to treat relays as first-class citizens of the protocol
and ensure that objects are structured such that information necessary
for distribution is available to relays while the media content itself
remains opaque and private.

## Terms and Definitions

{::boilerplate bcp14-tagged}

Client:

: The party initiating a Transport Session.

Server:

: The party accepting an incoming Transport Session.

Endpoint:

: A Client or Server.

Peer:

: The other endpoint than the one being described

Publisher:

: An endpoint that handles subscriptions by sending requested Objects from the requested track.

Subscriber:

: An endpoint that subscribes to and receives tracks.

Original Publisher:

: The initial publisher of a given track.

End Subscriber:

: A subscriber that initiates a subscription and does not send the data on to other subscribers.

Relay:

: An entity that is both a Publisher and a Subscriber, but not the Original
Publisher or End Subscriber.

Upstream:

: In the direction of the Original Publisher

Downstream:

: In the direction of the End Subscriber(s)

Transport Session:

: A raw QUIC connection or a WebTransport session.

Congestion:

: Packet loss and queuing caused by degraded or overloaded networks.

Group:

: A temporal sequence of objects. A group represents a join point in a
  track. See ({{model-group}}).

Object:

: An object is an addressable unit whose payload is a sequence of
  bytes. Objects form the base element in the MOQT data model. See
  ({{model-object}}).

Track:

: An encoded bitstream. Tracks contain a sequential series of one or
  more groups and are the subscribable entity with MOQT.
  See ({{model-track}}).


## Notational Conventions

This document uses the conventions detailed in ({{?RFC9000, Section 1.3}})
when describing the binary encoding.

As a quick reference, the following list provides a non normative summary
of the parts of RFC9000 field syntax that are used in this specification.

x (L):

: Indicates that x is L bits long

x (i):

: Indicates that x holds an integer value using the variable-length
  encoding as described in ({{?RFC9000, Section 16}})

x (..):

: Indicates that x can be any length including zero bits long.  Values
 in this format always end on a byte boundary.

[x (L)]:

: Indicates that x is optional and has a length of L

x (L) ...:

: Indicates that x is repeated zero or more times and that each instance
  has a length of L

This document extends the RFC9000 syntax and with the additional field types:

x (b):

: Indicates that x consists of a variable length integer encoding as
  described in ({{?RFC9000, Section 16}}), followed by that many bytes
  of binary data

x (tuple):

: Indicates that x is a tuple, consisting of a variable length integer encoded
  as described in ({{?RFC9000, Section 16}}), followed by that many variable
  length tuple fields, each of which are encoded as (b) above.


To reduce unnecessary use of bandwidth, variable length integers SHOULD
be encoded using the least number of bytes possible to represent the
required value.


# Object Data Model {#model}

MOQT has a hierarchical data model, comprised of tracks which contain
groups, and groups that contain objects. Inside of a group, the objects
can be organized into subgroups.

To give an example of how an application might use this data model,
consider an application sending high and low resolution video using a
codec with temporal scalability. Each resolution is sent as a separate
track to allow the subscriber to pick the appropriate resolution given
the display environment and available bandwidth. Each "group of pictures"
in a video is sent as a group because the first frame is needed to
decode later frames. This allows the client to join at the logical points
where they can get the information to start decoding the stream.
The temporal layers are sent as separate sub groups to allow the
priority mechanism to favour the base layer when there is not enough
bandwidth to send both the base and enhancement layers. Each frame of
video on a given layer is sent as a single object.

## Objects {#model-object}

The basic data element of MOQT is an object.  An object is an
addressable unit whose payload is a sequence of bytes.  All objects
belong to a group, indicating ordering and potential
dependencies. {{model-group}}  An object is uniquely identified by
its track namespace, track name, group ID, and object ID, and must be an
identical sequence of bytes regardless of how or where it is retrieved.
An Object can become unavailable, but its contents MUST NOT change over
time.

Objects are comprised of two parts: metadata and a payload.  The metadata is
never encrypted and is always visible to relays (see {{relays-moq}}). The
payload portion may be encrypted, in which case it is only visible to the
Original Publisher and End Subscribers. The Original Publisher is solely
responsible for the content of the object payload. This includes the
underlying encoding, compression, any end-to-end encryption, or
authentication. A relay MUST NOT combine, split, or otherwise modify object
payloads.

Objects within a group are ordered numerically by their Object ID.

## Subgroups {#model-subgroup}

A subgroup is a sequence of one or more objects from the same group
({{model-group}}) in ascending order by Object ID. Objects in a subgroup
have a dependency and priority relationship consistent with sharing a QUIC
stream. In some cases, a Group will be most effectively delivered using more
than one QUIC stream.

When a Track's forwarding preference (see {{object-fields}}) is "Track" or
"Datagram", Objects are not sent in Subgroups, no Subgroup IDs are assigned, and the
description in the remainder of this section does not apply.

QUIC streams offer in-order reliable delivery and the ability to cancel sending
and retransmission of data. Furthermore, many implementations offer the ability
to control the relative priority of streams, which allows control over the
scheduling of sending data on active streams.

Every object within a Group belongs to exactly one Subgroup.

Objects from two subgroups cannot be sent on the same QUIC stream. Objects from the
same Subgroup MUST NOT be sent on different QUIC streams, unless one of the streams
was reset prematurely, or upstream conditions have forced objects from a Subgroup
to be sent out of Object ID order.

Original publishers assign each Subgroup a Subgroup ID, and do so as they see fit.  The
scope of a Subgroup ID is a Group, so Subgroups from different Groups MAY share a Subgroup
ID without implying any relationship between them. In general, publishers assign
objects to subgroups in order to leverage the features of QUIC streams as described
above.

An example strategy for using QUIC stream properties follows. If object B is
dependent on object A, then delivery of B can follow A, i.e. A and B can be
usefully delivered over a single QUIC stream. Furthermore, in this example:

- If an object is dependent on all previous objects in a Subgroup, it is added to
that Subgroup.

- If an object is not dependent on all of the objects in a Subgroup, it goes in
a different Subgroup.

- There are often many ways to compose Subgroups that meet these criteria. Where
possible, choose the composition that results in the fewest Subgroups in a group
to minimize the number of QUIC streams used.


## Groups {#model-group}

A group is a collection of objects and is a sub-unit of a track ({{model-track}}).
Groups SHOULD be indendepently useful, so objects within a group SHOULD NOT depend
on objects in other groups. A group provides a join point for subscriptions, so a
subscriber that does not want to receive the entire track can opt to receive only
the latest group(s).  The publisher then selectively transmits objects based on
their group membership.  Groups can contain any number of objects.

Groups are ordered numerically by their Group ID.

## Track {#model-track}

A track is a sequence of groups ({{model-group}}). It is the entity
against which a subscriber issues a subscription request.  A subscriber
can request to receive individual tracks starting at a group boundary,
including any new objects pushed by the publisher while the track is
active.

### Track Naming and Scopes {#track-name}

In MOQT, every track has a track name and a track namespace associated
with it.  A track name identifies an individual track within the
namespace.

Track namespace is an ordered N-tuple of bytes where N can be between 1 and 32.
The structured nature of Track Namespace allows relays and applications to
manipulate prefixes of a namespace. Track name is a sequence of bytes.
If an endpoint receives a Track Namespace tuple with an N of 0 or more
than 32, it MUST close the session with a Protocol Violation.

In this specification, both the Track Namespace tuple fields and the Track Name
are not constrained to a specific encoding. They carry a sequence of bytes and
comparison between two Track Namespace tuple fields or Track Names is done by
exact comparison of the bytes. Specifications that use MoQ Transport may
constrain the information in these fields, for example by restricting them to
UTF-8. Any specification that does needs to specify the canonicalization into
the bytes in the Track Namespace or Track Name such that exact comparison works.

### Scope {#track-scope}

A MOQT scope is a set of servers (as identified by their connection
URIs) for which the tuple of Track Name and Track Namespace are
guaranteed to be unique and identify a specific track. It is up to
the application using MOQT to define how broad or narrow the scope is.
An application that deals with connections between devices
on a local network may limit the scope to a single connection; by
contrast, an application that uses multiple CDNs to serve media may
require the scope to include all of those CDNs.

Because the tuple of Track Namespace and Track Name are unique within an
MOQT scope, they can be used as a cache key.
MOQT does not provide any in-band content negotiation methods similar to
the ones defined by HTTP ({{?RFC9110, Section 10}}); if, at a given
moment in time, two tracks within the same scope contain different data,
they have to have different names and/or namespaces.

### Connection URL

Each track MAY have one or more associated connection URLs specifying
network hosts through which a track may be accessed. The syntax of the
Connection URL and the associated connection setup procedures are
specific to the underlying transport protocol usage {{session}}.


# Sessions {#session}

## Session establishment {#session-establishment}

This document defines a protocol that can be used interchangeably both
over a QUIC connection directly [QUIC], and over WebTransport
[WebTransport].  Both provide streams and datagrams with similar
semantics (see {{?I-D.ietf-webtrans-overview, Section 4}}); thus, the
main difference lies in how the servers are identified and how the
connection is established.  When using QUIC, datagrams MUST be
supported via the [QUIC-DATAGRAM] extension, which is already a
requirement for WebTransport over HTTP/3.

There is no definition of the protocol over other transports,
such as TCP, and applications using MoQ might need to fallback to
another protocol when QUIC or WebTransport aren't available.

### WebTransport

A MOQT server that is accessible via WebTransport can be identified
using an HTTPS URI ({{!RFC9110, Section 4.2.2}}).  A MOQT session can be
established by sending an extended CONNECT request to the host and the
path indicated by the URI, as described in {{WebTransport, Section 3}}.

### QUIC

A MOQT server that is accessible via native QUIC can be identified by a
URI with a "moqt" scheme.  The "moqt" URI scheme is defined as follows,
using definitions from {{!RFC3986}}:

~~~~~~~~~~~~~~~
moqt-URI = "moqt" "://" authority path-abempty [ "?" query ]
~~~~~~~~~~~~~~~

The `authority` portion MUST NOT contain an empty `host` portion.
The `moqt` URI scheme supports the `/.well-known/` path prefix defined in
{{!RFC8615}}.

This protocol does not specify any semantics on the `path-abempty` and
`query` portions of the URI.  The contents of those are left up to the
application.

The client can establish a connection to a MoQ server identified by a
given URI by setting up a QUIC connection to the host and port
identified by the `authority` section of the URI.  The `path-abempty`
and `query` portions of the URI are communicated to the server using the
PATH parameter ({{path}}) which is sent in the CLIENT_SETUP message at the
start of the session.  The ALPN value {{!RFC7301}} used by the protocol
is `moq-00`.

## Version and Extension Negotiation {#version-negotiation}

Endpoints use the exchange of Setup messages to negotiate the MOQT version and
any extensions to use.

The client indicates the MOQT versions it supports in the CLIENT_SETUP message
(see {{message-setup}}). It also includes the union of all Setup Parameters
{{setup-params}} required for a handshake by any of those versions.

Within any MOQT version, clients request the use of extensions by adding Setup
parameters corresponding to that extension. No extensions are defined in this
document.

The server replies with a SERVER_SETUP message that indicates the chosen
version, includes all parameters required for a handshake in that version, and
parameters for every extension requested by the client that it supports.

New versions of MOQT MUST specify which existing extensions can be used with
that version. New extensions MUST specify the existing versions with which they
can be used.

If a given parameter carries the same information in multiple versions,
but might have different optimal values in those versions, there SHOULD be
separate Setup parameters for that information in each version.

## Session initialization {#session-init}

The first stream opened is a client-initiated bidirectional control stream where
the endpoints exchange Setup messages ({{message-setup}}).  All messages defined
in this draft except OBJECT and OBJECT_WITH_LENGTH are sent on the control
stream after the Setup message. Control messages MUST NOT be sent on any other
stream, and a peer receiving a control message on a different stream closes the
session as a 'Protocol Violation'. Objects MUST NOT be sent on the control
stream, and a peer receiving an Object on the control stream closes the session
as a 'Protocol Violation'.

This draft only specifies a single use of bidirectional streams. Objects are
sent on unidirectional streams.  Because there are no other uses of
bidirectional streams, a peer MAY currently close the session as a
'Protocol Violation' if it receives a second bidirectional stream.

The control stream MUST NOT be closed at the underlying transport layer while the
session is active.  Doing so results in the session being closed as a
'Protocol Violation'.

## Stream Cancellation

Streams aside from the control stream MAY be canceled due to congestion
or other reasons by either the publisher or subscriber. Early termination of a
stream does not affect the MoQ application state, and therefore has no
effect on outstanding subscriptions.

## Termination  {#session-termination}

The Transport Session can be terminated at any point.  When native QUIC
is used, the session is closed using the CONNECTION\_CLOSE frame
({{QUIC, Section 19.19}}).  When WebTransport is used, the session is
closed using the CLOSE\_WEBTRANSPORT\_SESSION capsule ({{WebTransport,
Section 5}}).

The application MAY use any error message and SHOULD use a relevant
code, as defined below:

|------|---------------------------|
| Code | Reason                    |
|-----:|:--------------------------|
| 0x0  | No Error                  |
|------|---------------------------|
| 0x1  | Internal Error            |
|------|---------------------------|
| 0x2  | Unauthorized              |
|------|---------------------------|
| 0x3  | Protocol Violation        |
|------|---------------------------|
| 0x4  | Duplicate Track Alias     |
|------|---------------------------|
| 0x5  | Parameter Length Mismatch |
|------|---------------------------|
| 0x6  | Too Many Subscribes       |
|------|---------------------------|
| 0x10 | GOAWAY Timeout            |
|------|---------------------------|

* No Error: The session is being terminated without an error.

* Internal Error: An implementation specific error occurred.

* Unauthorized: The endpoint breached an agreement, which MAY have been
 pre-negotiated by the application.

* Protocol Violation: The remote endpoint performed an action that was
  disallowed by the specification.

* Duplicate Track Alias: The endpoint attempted to use a Track Alias
  that was already in use.

* Too Many Subscribes: The session was closed because the subscriber used
  a Subscribe ID equal or larger than the current Maximum Subscribe ID.

* GOAWAY Timeout: The session was closed because the peer took too long to
  close the session in response to a GOAWAY ({{message-goaway}}) message.
  See session migration ({{session-migration}}).

## Migration {#session-migration}

MOQT requires a long-lived and stateful session. However, a service
provider needs the ability to shutdown/restart a server without waiting for all
sessions to drain naturally, as that can take days for long-form media.
MOQT enables proactively draining sessions via the GOAWAY message ({{message-goaway}}).

The server sends a GOAWAY message, signaling the client to establish a new
session and migrate any active subscriptions. The GOAWAY message optionally
contains a new URI for the new session, otherwise the current URI is
reused. The server SHOULD terminate the session with 'GOAWAY Timeout' after a
sufficient timeout if there are still open subscriptions or fetches on a
connection.

When the server is a subscriber, it SHOULD send a GOAWAY message to downstream
subscribers prior to any UNSUBSCRIBE messages to upstream publishers.

After the client receives a GOAWAY, it's RECOMMENDED that the client waits until
there are no more active subscriptions before closing the session with NO_ERROR.
Ideally this is transparent to the application using MOQT, which involves
establishing a new session in the background and migrating active subscriptions
and announcements. The client can choose to delay closing the session if it
expects more OBJECTs to be delivered. The server closes the session with a
'GOAWAY Timeout' if the client doesn't close the session quickly enough.


# Priorities {#priorities}

MoQ priorities allow a subscriber and original publisher to influence
the transmission order of Objects within a session in the presence of
congestion.

## Definitions

MoQT maintains priorities between different _schedulable objects_.
A schedulable object in MoQT is either:

1. An object that belongs to a subgroup where that object would be the next
   object to be sent in that subgroup.
1. An object that belongs to a track with delivery preference Datagram.

Since a single subgroup or datagram has a single publisher priority, it can be
useful to conceptualize this process as scheduling subgroups or datagrams
instead of individual objects on them.

A _priority number_ is an unsigned integer with a value between 0 and 255.
A lower priority number indicates higher priority; the highest priority is 0.

_Subscriber Priority_ is a priority number associated with an individual
subscription.  It is specified in the SUBSCRIBE message, and can be updated via
SUBSCRIBE_UPDATE message.  The subscriber priority of an individual schedulable
object is the subscriber priority of the subscription that caused that object
to be sent. When subscriber priority is changed, a best effort SHOULD be made
to change the apply that to all objects that have not been sent, but it is
implementation dependent what happens to objects that have already been
received and possibly scheduled.

_Publisher Priority_ is a priority number associated with an individual
schedulable object.  It is specified in the header of the respective subgroup or
datagram, and is the same for all objects in a single subgroup.

_Group Order_ is a property of an invidual subscription.  It can be either
'Ascending' (groups with lower group ID are sent first), or 'Descending'
(groups with higher group ID are sent first).  The publisher communicates its
group order in the SUBSCRIBE_OK message; the subscriber can override it in its
SUBSCRIBE message.  The group order of an existing subscription cannot be
changed.

## Scheduling Algorithm

When an MoQT publisher has multiple schedulable objects it can choose between,
the objects SHOULD be selected as follows:

1. If two objects have a different subscriber priority associated with them,
   the one with **the highest subscriber priority** is sent first.
1. If two objects have the same subscriber priority, but a different publisher
   priority, the one with **the highest publisher priority** is sent first.
1. If two objects have the same subscriber and publisher priority, but belong
   to two different groups of the same track received through the same
   subscription, **the group order** of the associated subscription is used to
   decide the one that is sent first.
1. If two objects belong to the same group of the same track received through
   the same subscription, the one with **the lowest Subgroup ID** (for tracks
   with delivery preference Subgroup), or **the lowest Object ID** (for tracks
   with delivery preference Datagram) is sent first.

This algorithm does not provide a well-defined ordering for objects that belong
to different subscriptions, but have the same subscriber and publisher
priority.  The ordering in those cases is implementation-defined, though the
expectation is that all subscriptions will be able to send some data.

Given the critical nature of control messages and their relatively
small size, the control stream SHOULD be prioritized higher than all
subscribed Objects.

## Considerations for Setting Priorities

Relays SHOULD respect the subscriber and original publisher's priorities.
Relays SHOULD NOT directly use Subscriber Priority or Group Order
from incoming subscriptions for upstream subscriptions. Relays use of
Subscriber Priority for upstream subscriptions can be based on
factors specific to it, such as the popularity of the
content or policy, or relays can specify the same value for all
upstream subscriptions.

MoQ Sessions can span multiple namespaces, and priorities might not
be coordinated across namespaces.  The subscriber's priority is
considered first, so there is a mechanism for a subscriber to fix
incompatibilities between different namespaces prioritization schemes.
Additionally, it is anticipated that when multiple namespaces
are present within a session, the namespaces could be coordinating,
possibly part of the same application.  In cases when pooling among
namespaces is expected to cause issues, multiple MoQ sessions, either
within a single connection or on multiple connections can be used.

Implementations that have a default priority SHOULD set it to a value in
the middle of the range (eg: 128) to allow non-default priorities to be
set either higher or lower.

# Relays {#relays-moq}

Relays are leveraged to enable distribution scale in the MoQ
architecture. Relays can be used to form an overlay delivery network,
similar in functionality to Content Delivery Networks
(CDNs). Additionally, relays serve as policy enforcement points by
validating subscribe and publish requests at the edge of a network.

Relays are endpoints, which means they terminate Transport Sessions in order to
have visibility of MoQ Object metadata.

Relays MAY cache Objects, but are not required to.

## Subscriber Interactions

Subscribers interact with the Relays by sending a SUBSCRIBE
({{message-subscribe-req}}) control message for the tracks of
interest. Relays MUST ensure subscribers are authorized to access the
content associated with the track. The authorization
information can be part of subscription request itself or part of the
encompassing session. The specifics of how a relay authorizes a user are
outside the scope of this specification. The subscriber is notified
of the result of the subscription via a
SUBSCRIBE_OK ({{message-subscribe-ok}}) or SUBSCRIBE_ERROR
{{message-subscribe-error}} control message. The entity receiving the
SUBSCRIBE MUST send only a single response to a given SUBSCRIBE of
either SUBSCRIBE_OK or SUBSCRIBE_ERROR.

If a relay does not already have a subscription for the track,
or if the subscription does not cover all the requested Objects, it
will need to make an upstream subscription.  The relay SHOULD NOT
return a SUBCRIBE_OK until at least one SUBSCRIBE_OK has been
received for the track, to ensure the Group Order is correct.

For successful subscriptions, the publisher maintains a list of
subscribers for each track. Each new OBJECT belonging to the
track within the subscription range is forwarded to each active
subscriber, dependent on the congestion response. A subscription
remains active until soon after the publisher of the track terminates the
subscription with a SUBSCRIBE_DONE (see {{message-subscribe-done}}).

A caching relay saves Objects to its cache identified by the Object's
Full Track Name, Group ID and Object ID. Relays MUST be able to
process objects for the same Full Track Name from multiple
publishers and forward objects to active matching subscriptions.
If multiple objects are received with the same Full Track Name,
Group ID and Object ID, Relays MAY ignore subsequently received Objects
or MAY use them to update the cache. Implementations that update the
cache need to be protect against cache poisoning.

Objects MUST NOT be sent for unsuccessful subscriptions, and if a subscriber
receives a SUBSCRIBE_ERROR after receiving objects, it MUST close the session
with a 'Protocol Violation'.

A relay MUST NOT reorder or drop objects received on a multi-object stream when
forwarding to subscribers, unless it has application specific information.

Relays MAY aggregate authorized subscriptions for a given track when
multiple subscribers request the same track. Subscription aggregation
allows relays to make only a single upstream subscription for the
track. The published content received from the upstream subscription
request is cached and shared among the pending subscribers.

The application SHOULD use a relevant error code in SUBSCRIBE_ERROR,
as defined below:

|------|---------------------------|
| Code | Reason                    |
|-----:|:--------------------------|
| 0x0  | Internal Error            |
|------|---------------------------|
| 0x1  | Invalid Range             |
|------|---------------------------|
| 0x2  | Retry Track Alias         |
|------|---------------------------|
| 0x3  | Track Does Not Exist      |
|------|---------------------------|
| 0x4  | Unauthorized              |
|------|---------------------------|
| 0x5  | Timeout                   |
|------|---------------------------|

The application SHOULD use a relevant status code in
SUBSCRIBE_DONE, as defined below:

|------|---------------------------|
| Code | Reason                    |
|-----:|:--------------------------|
| 0x0  | Unsubscribed              |
|------|---------------------------|
| 0x1  | Internal Error            |
|------|---------------------------|
| 0x2  | Unauthorized              |
|------|---------------------------|
| 0x3  | Track Ended               |
|------|---------------------------|
| 0x4  | Subscription Ended        |
|------|---------------------------|
| 0x5  | Going Away                |
|------|---------------------------|
| 0x6  | Expired                   |
|------|---------------------------|
| 0x7  | Too Far Behind            |
|------|---------------------------|

### Graceful Publisher Relay Switchover

This section describes behavior a subscriber MAY implement
to allow for a better user experience when a relay sends a GOAWAY.

When a subscriber receives the GOAWAY message, it starts the process
of connecting to a new relay and sending the SUBSCRIBE requests for
all active subscriptions to the new relay. The new relay will send a
response to the subscribes and if they are successful, the subscriptions
to the old relay can be stopped with an UNSUBSCRIBE.


## Publisher Interactions

Publishing through the relay starts with publisher sending ANNOUNCE
control message with a `Track Namespace` ({{model-track}}).
The announce enables the relay to know which publisher to forward a
SUBSCRIBE to.

Relays MUST ensure that publishers are authorized by:

- Verifying that the publisher is authorized to publish the content
  associated with the set of tracks whose Track Namespace matches the
  announced namespace. Where the authorization and identification of
  the publisher occurs depends on the way the relay is managed and
  is application specific.

Relays respond with an ANNOUNCE_OK or ANNOUNCE_ERROR control message
providing the result of announcement. The entity receiving the
ANNOUNCE MUST send only a single response to a given ANNOUNCE of
either ANNOUNCE_OK or ANNOUNCE_ERROR.

A Relay can receive announcements from multiple publishers for the same
Track Namespace and it SHOULD respond with the same response to each of the
publishers, as though it was responding to an ANNOUNCE
from a single publisher for a given tracknamespace.

When a publisher wants to stop
new subscriptions for an announced namespace it sends an UNANNOUNCE.
A subscriber indicates it will no longer route subscriptions for a
namespace it previously responded ANNOUNCE_OK to by sending an
ANNOUNCE_CANCEL.

A relay manages sessions from multiple publishers and subscribers,
connecting them based on the track namespace. This MUST use an exact
match on track namespace unless otherwise negotiated by the application.
For example, a SUBSCRIBE namespace=foobar message will be forwarded to
the session that sent ANNOUNCE namespace=foobar.

When a relay receives an incoming SUBSCRIBE request that triggers an
upstream subscription, it SHOULD send a SUBSCRIBE request to each
publisher that has announced the subscription's namespace, unless it
already has an active subscription for the Objects requested by the
incoming SUBSCRIBE request from all available publishers.

When a relay receives an incoming ANNOUCE for a given namespace, for
each active upstream subscription that matches that namespace, it SHOULD send a
SUBSCRIBE to the publisher that sent the ANNOUNCE.

OBJECT message headers carry a short hop-by-hop `Track Alias` that maps to
the Full Track Name (see {{message-subscribe-ok}}). Relays use the
`Track Alias` of an incoming OBJECT message to identify its track and find
the active subscribers for that track. Relays MUST forward OBJECT messages to
matching subscribers in accordance to each subscription's priority, group order,
and delivery timeout.

### Graceful Publisher Network Switchover

This section describes behavior that a publisher MAY
choose to implement to allow for a better users experience when
switching between networks, such as WiFi to Cellular or vice versa.

If the original publisher detects it is likely to need to switch networks,
for example because the WiFi signal is getting weaker, and it does not
have QUIC connection migration available, it establishes a new session
over the new interface and sends an ANNOUCE. The relay will forward
matching subscribes and the publisher publishes objects on both sessions.
Once the subscriptions have migrated over to session on the new network,
the publisher can stop publishing objects on the old network. The relay
will drop duplicate objects received on both subscriptions.
Ideally, the subscriptions downstream from the relay do no observe this
change, and keep receiving the objects on the same subscription.

### Graceful Publisher Relay Switchover

This section describes behavior that a publisher MAY choose to implement
to allow for a better user experience when a relay sends them a GOAWAY.

When a publisher receives a GOAWAY, it starts the process of
connecting to a new relay and sends announces, but it does not immediately
stop publishing objects to the old relay. The new relay will send
subscribes and the publisher can start sending new objects to the new relay
instead of the old relay. Once objects are going to the new relay,
the announcement and subscription to the old relay can be stopped.

## Relay Object Handling

MOQT encodes the delivery information for a stream via OBJECT headers
({{message-object}}).  A relay MUST NOT modify Object properties when
forwarding.

A relay MUST treat the object payload as opaque.  A relay MUST NOT
combine, split, or otherwise modify object payloads.  A relay SHOULD
prioritize sending Objects based on {{priorities}}.

A publisher SHOULD begin sending incomplete objects when available to
avoid incurring additional latency.

A relay that reads from one stream and writes to another in order can
introduce head-of-line blocking.  Packet loss will cause stream data to
be buffered in the library, awaiting in-order delivery, which could
increase latency over additional hops.  To mitigate this, a relay MAY
read and write stream data out of order subject to flow control
limits.  See section 2.2 in {{QUIC}}.

# Control Messages {#message}

MOQT uses a single bidirectional stream to exchange control messages, as
defined in {{session-init}}.  Every single message on the control stream is
formatted as follows:

~~~
MOQT Control Message {
  Message Type (i),
  Message Length (i),
  Message Payload (..),
}
~~~
{: #moq-transport-message-format title="MOQT Message"}

|-------|-----------------------------------------------------|
| ID    | Messages                                            |
|------:|:----------------------------------------------------|
| 0x2   | SUBSCRIBE_UPDATE ({{message-subscribe-update-req}})|
|-------|-----------------------------------------------------|
| 0x3   | SUBSCRIBE ({{message-subscribe-req}})               |
|-------|-----------------------------------------------------|
| 0x4   | SUBSCRIBE_OK ({{message-subscribe-ok}})             |
|-------|-----------------------------------------------------|
| 0x5   | SUBSCRIBE_ERROR ({{message-subscribe-error}})       |
|-------|-----------------------------------------------------|
| 0x6   | ANNOUNCE  ({{message-announce}})                    |
|-------|-----------------------------------------------------|
| 0x7   | ANNOUNCE_OK ({{message-announce-ok}})               |
|-------|-----------------------------------------------------|
| 0x8   | ANNOUNCE_ERROR ({{message-announce-error}})         |
|-------|-----------------------------------------------------|
| 0x9   | UNANNOUNCE  ({{message-unannounce}})                |
|-------|-----------------------------------------------------|
| 0xA   | UNSUBSCRIBE ({{message-unsubscribe}})               |
|-------|-----------------------------------------------------|
| 0xB   | SUBSCRIBE_DONE ({{message-subscribe-done}})         |
|-------|-----------------------------------------------------|
| 0xC   | ANNOUNCE_CANCEL ({{message-announce-cancel}})       |
|-------|-----------------------------------------------------|
| 0xD   | TRACK_STATUS_REQUEST ({{message-track-status-req}}) |
|-------|-----------------------------------------------------|
| 0xE   | TRACK_STATUS ({{message-track-status}})             |
|-------|-----------------------------------------------------|
| 0x10  | GOAWAY ({{message-goaway}})                         |
|-------|-----------------------------------------------------|
| 0x11  | SUBSCRIBE_ANNOUNCES ({{message-subscribe-ns}})      |
|-------|-----------------------------------------------------|
| 0x12  | SUBSCRIBE_ANNOUNCES_OK ({{message-sub-ann-ok}})     |
|-------|-----------------------------------------------------|
| 0x13  | SUBSCRIBE_ANNOUNCES_ERROR ({{message-sub-ann-error}}|
|-------|-----------------------------------------------------|
| 0x14  | UNSUBSCRIBE_ANNOUNCES ({{message-unsub-ann}})       |
|-------|-----------------------------------------------------|
| 0x15  | MAX_SUBSCRIBE_ID ({{message-max-subscribe-id}})     |
|-------|-----------------------------------------------------|
| 0x1A  | SUBSCRIBES_BLOCKED ({{message-subscribes-blocked}}) |
|-------|-----------------------------------------------------|
| 0x16  | FETCH ({{message-fetch}})                           |
|-------|-----------------------------------------------------|
| 0x17  | FETCH_CANCEL ({{message-fetch-cancel}})             |
|-------|-----------------------------------------------------|
| 0x18  | FETCH_OK ({{message-fetch-ok}})                     |
|-------|-----------------------------------------------------|
| 0x19  | FETCH_ERROR ({{message-fetch-error}})               |
|-------|-----------------------------------------------------|
| 0x40  | CLIENT_SETUP ({{message-setup}})                    |
|-------|-----------------------------------------------------|
| 0x41  | SERVER_SETUP ({{message-setup}})                    |
|-------|-----------------------------------------------------|

An endpoint that receives an unknown message type MUST close the session.
Control messages have a length to make parsing easier, but no control
messages are intended to be ignored. If the length does not match the
length of the message content, the receiver MUST close the session.

## Parameters {#params}

Some messages include a Parameters field that encode optional message
elements. They contain a type, length, and value.

Senders MUST NOT repeat the same parameter type in a message. Receivers
SHOULD check that there are no duplicate parameters and close the session
as a 'Protocol Violation' if found.

Receivers ignore unrecognized parameters.

The format of Parameters is as follows:

~~~
Parameter {
  Parameter Type (i),
  Parameter Length (i),
  Parameter Value (..),
}
~~~
{: #moq-param format title="MOQT Parameter"}

Parameter Type is an integer that indicates the semantic meaning of the
parameter. Setup message parameters use a namespace that is constant across all
MoQ Transport versions. All other messages use a version-specific namespace. For
example, the integer '1' can refer to different parameters for Setup messages
and for all other message types.

SETUP message parameter types are defined in {{setup-params}}. Version-
specific parameter types are defined in {{version-specific-params}}.

The Parameter Length field of the String Parameter encodes the length
of the Parameter Value field in bytes.

Each parameter description will indicate the data type in the Parameter Value
field. If a receiver understands a parameter type, and the parameter length
implied by that type does not match the Parameter Length field, the receiver
MUST terminate the session with error code 'Parameter Length Mismatch'.

### Version Specific Parameters {#version-specific-params}

Each version-specific parameter definition indicates the message types in which
it can appear. If it appears in some other type of message, it MUST be ignored.
Note that since Setup parameters use a separate namespace, it is impossible for
these parameters to appear in Setup messages.

#### AUTHORIZATION INFO {#authorization-info}

AUTHORIZATION INFO parameter (Parameter Type 0x02) identifies a track's
authorization information in a SUBSCRIBE, SUBSCRIBE_ANNOUNCES, ANNOUNCE
or FETCH message. This parameter is populated for cases where the authorization
is required at the track level. The value is an ASCII string.

#### DELIVERY TIMEOUT Parameter {#delivery-timeout}

The DELIVERY TIMEOUT parameter (Parameter Type 0x03) MAY appear in a
SUBSCRIBE, SUBSCRIBE_OK, or a SUBSCRIBE_UDPATE message.  It is the duration in
milliseconds the relay SHOULD continue to attempt forwarding Objects after
they have been received.  The start time for the timeout is based on when the
beginning of the Object is received, and does not depend upon the forwarding
preference. There is no explicit signal that an Object was not sent because
the delivery timeout was exceeded.

If both the subscriber and publisher specify the parameter, they use the min of the
two values for the subscription.  The publisher SHOULD always specify the value
received from an upstream subscription when there is one, and nothing otherwise.
If an earlier Object arrives later than subsequent Objects, relays can consider
the receipt time as that of the next later Object, with the assumption that the
Object's data was reordered.

If neither the subscriber or publisher specify DELIVERY TIMEOUT, all Objects
in the track matching the subscription filter are delivered as indicated by
their Group Order and Priority.  If a subscriber exceeds the publisher's
resource limits by failing to consume objects at a sufficient rate, the
publisher MAY terminate the subscription with error 'Too Far Behind'.

If an object in a subgroup exceeds the delivery timeout, the publisher MUST
reset the underlying transport stream (see {{closing-subgroup-streams}}).

When sent by a subscriber, this parameter is intended to be specific to a
subscription, so it SHOULD NOT be forwarded upstream by a relay that intends
to serve multiple subscriptions for the same track.

Publishers SHOULD consider whether the entire Object is likely to be delivered
before sending any data for that Object, taking into account priorities,
congestion control, and any other relevant information.

#### MAX CACHE DURATION Parameter {#max-cache-duration}

MAX_CACHE_DURATION (Parameter Type 0x04): An integer expressing a number of
milliseconds. If present, the relay MUST NOT start forwarding any individual
Object received through this subscription after the specified number of
milliseconds has elapsed since the beginning of the Object was received.  This
means Objects earlier in a multi-object stream will expire earlier than Objects
later in the stream. Once Objects have expired, their state becomes unknown, and
a relay that handles a subscription that includes those Objects re-requests them.

## CLIENT_SETUP and SERVER_SETUP {#message-setup}

The `CLIENT_SETUP` and `SERVER_SETUP` messages are the first messages exchanged
by the client and the server; they allow the endpoints to establish the mutually
supported version and agree on the initial configuration before any objects are
exchanged. It is a sequence of key-value pairs called Setup parameters; the
semantics and format of which can vary based on whether the client or server is
sending.  To ensure future extensibility of MOQT, endpoints MUST ignore unknown
setup parameters. TODO: describe GREASE for those.

The wire format of the Setup messages are as follows:

~~~
CLIENT_SETUP Message {
  Type (i) = 0x40,
  Length (i),
  Number of Supported Versions (i),
  Supported Version (i) ...,
  Number of Parameters (i) ...,
  Setup Parameters (..) ...,
}

SERVER_SETUP Message {
  Type (i) = 0x41,
  Length (i),
  Selected Version (i),
  Number of Parameters (i) ...,
  Setup Parameters (..) ...,
}
~~~
{: #moq-transport-setup-format title="MOQT Setup Messages"}

The available versions and Setup parameters are detailed in the next sections.

### Versions {#setup-versions}

MoQ Transport versions are a 32-bit unsigned integer, encoded as a varint.
This version of the specification is identified by the number 0x00000001.
Versions with the most significant 16 bits of the version number cleared are
reserved for use in future IETF consensus documents.

The client offers the list of the protocol versions it supports; the
server MUST reply with one of the versions offered by the client. If the
server does not support any of the versions offered by the client, or
the client receives a server version that it did not offer, the
corresponding peer MUST close the session.

\[\[RFC editor: please remove the remainder of this section before
publication.]]

The version number for the final version of this specification (0x00000001), is
reserved for the version of the protocol that is published as an RFC.
Version numbers used to identify IETF drafts are created by adding the draft
number to 0xff000000. For example, draft-ietf-moq-transport-13 would be
identified as 0xff00000D.

### Setup Parameters {#setup-params}

#### PATH {#path}

The PATH parameter (Parameter Type 0x01) allows the client to specify the path
of the MoQ URI when using native QUIC ({{QUIC}}).  It MUST NOT be used by
the server, or when WebTransport is used.  If the peer receives a PATH
parameter from the server, or when WebTransport is used, it MUST close
the connection. It follows the URI formatting rules {{!RFC3986}}.

When connecting to a server using a URI with the "moqt" scheme, the
client MUST set the PATH parameter to the `path-abempty` portion of the
URI; if `query` is present, the client MUST concatenate `?`, followed by
the `query` portion of the URI to the parameter.

#### MAX_SUBSCRIBE_ID {#max-subscribe-id}

The MAX_SUBSCRIBE_ID parameter (Parameter Type 0x02) communicates an initial value for the Maximum Subscribe ID to the receiving subscriber. The default value is 0, so if not specified, the peer MUST NOT create subscriptions.

## GOAWAY {#message-goaway}

An endpoint sends a `GOAWAY` message to inform the peer it intends to close
the session soon.  Servers can use GOAWAY to initiate session migration
({{session-migration}}) with an optional URI.

The GOAWAY message does not impact subscription state. A subscriber
SHOULD individually UNSUBSCRIBE for each existing subscription, while a
publisher MAY reject new requests while in the draining state.

Upon receiving a GOAWAY, an endpoint SHOULD NOT initiate new requests to
the peer including SUBSCRIBE, FETCH, ANNOUNCE and SUBSCRIBE_ANNOUNCE.

The endpoint MUST terminate the session with a Protocol Violation
({{session-termination}}) if it receives multiple GOAWAY messages.

~~~
GOAWAY Message {
  Type (i) = 0x10,
  Length (i),
  New Session URI Length (i),
  New Session URI (..),
}
~~~
{: #moq-transport-goaway-format title="MOQT GOAWAY Message"}

* New Session URI: When received by a client, indicates where the client can
  connect to continue this session.  The client MUST use this URI for the new
  session if provided. If the URI is zero bytes long, the client can reuse the
  current URI is reused instead. The new session URI SHOULD use the same scheme
  as the current URL to ensure compatibility.

  If a server receives a GOAWAY with a non-zero New Session URI Length it MUST
  terminate the session with a Protocol Violation.


## SUBSCRIBE {#message-subscribe-req}

A subscription causes the publisher to send newly published objects for a track.
A subscriber MUST NOT make multiple active subscriptions for a track within a
single session and publishers SHOULD treat this as a protocol violation.
The only objects prior to the current object that can be requested are those
in the current group.

**Filter Types**

The subscriber specifies a filter on the subscription to allow
the publisher to identify which objects need to be delivered.

There are 4 types of filters:

Latest Group (0x1) : Specifies an open-ended subscription with objects
from the beginning of the current group.  If no content has been delivered yet,
the subscription starts with the first published or received group.

Latest Object (0x2): Specifies an open-ended subscription beginning from
the current object of the current group.  If no content has been delivered yet,
the subscription starts with the first published or received group.

AbsoluteStart (0x3):  Specifies an open-ended subscription beginning
from the object identified in the StartGroup and StartObject fields. If the
StartGroup is prior to the current group, the publisher MUST reply with a
SUBSCRIBE_ERROR with code 'Invalid Range'.

AbsoluteRange (0x4):  Specifies a closed subscription starting at StartObject
in StartGroup and ending at EndObject in EndGroup.  The start and end of the
range are inclusive.  EndGroup MUST specify the same or a later group than
StartGroup. If the StartGroup is prior to the current group, the publisher MUST
reply with a SUBSCRIBE_ERROR with code 'Invalid Range'.

A filter type other than the above MUST be treated as error.

If a subscriber wants to subscribe to Objects both before and after
the Latest Object, it can send a SUBSCRIBE for the Latest Object
followed by a FETCH. Depending upon the application, one might want to send
both messages at the same time or wait for the first to return before sending
the second.

The format of SUBSCRIBE is as follows:

~~~
SUBSCRIBE Message {
  Type (i) = 0x3,
  Length (i),
  Subscribe ID (i),
  Track Alias (i),
  Track Namespace (tuple),
  Track Name Length (i),
  Track Name (..),
  Subscriber Priority (8),
  Group Order (8),
  Filter Type (i),
  [StartGroup (i),
   StartObject (i)],
  [EndGroup (i)],
  Number of Parameters (i),
  Subscribe Parameters (..) ...
}
~~~
{: #moq-transport-subscribe-format title="MOQT SUBSCRIBE Message"}

* Subscribe ID: The subscriber specified identifier used to manage a
subscription. `Subscribe ID` is a variable length integer that MUST be
unique and monotonically increasing within a session and MUST be less
than the session's Maximum Subscribe ID.

* Track Alias: A session specific identifier for the track.
Messages that reference a track, such as OBJECT ({{message-object}}),
reference this Track Alias instead of the Track Name and Track Namespace to
reduce overhead. If the Track Alias is already being used for a different
track, the publisher MUST close the session with a Duplicate Track Alias
error ({{session-termination}}).

* Track Namespace: Identifies the namespace of the track as defined in
({{track-name}}).

* Track Name: Identifies the track name as defined in ({{track-name}}).

* Subscriber Priority: Specifies the priority of a subscription relative to
other subscriptions in the same session. Lower numbers get higher priority.
See {{priorities}}.

* Group Order: Allows the subscriber to request Objects be delivered in
Ascending (0x1) or Descending (0x2) order by group. See {{priorities}}.
A value of 0x0 indicates the original publisher's Group Order SHOULD be
used. Values larger than 0x2 are a protocol error.

* Filter Type: Identifies the type of filter, which also indicates whether
the StartGroup/StartObject and EndGroup/EndObject fields will be present.

* StartGroup: The start Group ID. Only present for "AbsoluteStart" and
"AbsoluteRange" filter types.

* StartObject: The start Object ID. Only present for "AbsoluteStart" and
"AbsoluteRange" filter types.

* EndGroup: The end Group ID, inclusive. Only present for the "AbsoluteRange"
filter type.

* Subscribe Parameters: The parameters are defined in {{version-specific-params}}.

On successful subscription, the publisher MUST reply with a SUBSCRIBE_OK,
allowing the subscriber to determine the start group/object when not explicitly
specified and the publisher SHOULD start delivering objects.

If a publisher cannot satisfy the requested start or end or if the end has
already been published it SHOULD send a SUBSCRIBE_ERROR with code 'Invalid Range'.
A publisher MUST NOT send objects from outside the requested start and end.

## SUBSCRIBE_UPDATE {#message-subscribe-update-req}

A subscriber issues a SUBSCRIBE_UPDATE to a publisher to request a change to
a prior subscription.  Subscriptions can only become more narrower, not wider,
because an attempt to widen a subscription could fail.  If Objects before the
start or after the end of the current subscription are needed, a separate
subscription can be made. The start Object MUST NOT decrease and when it increases,
there is no guarantee that a publisher will not have already sent Objects before
the new start Object.  The end Object MUST NOT increase and when it decreases,
there is no guarantee that a publisher will not have already sent Objects after
the new end Object. A publisher SHOULD close the Session as a 'Protocol Violation'
if the SUBSCRIBE_UPDATE violates either rule or if the subscriber specifies a
Subscribe ID that does not exist within the Session.

Unlike a new subscription, SUBSCRIBE_UPDATE can not cause an Object to be
delivered multiple times.  Like SUBSCRIBE, EndGroup and EndObject MUST specify the
same or a later object than StartGroup and StartObject.

The format of SUBSCRIBE_UPDATE is as follows:

~~~
SUBSCRIBE_UPDATE Message {
  Type (i) = 0x2,
  Length (i),
  Subscribe ID (i),
  StartGroup (i),
  StartObject (i),
  EndGroup (i),
  Subscriber Priority (8),
  Number of Parameters (i),
  Subscribe Parameters (..) ...
}
~~~
{: #moq-transport-subscribe-update-format title="MOQT SUBSCRIBE_UPDATE Message"}

* Subscribe ID: The subscription identifier that is unique within the session.
This MUST match an existing Subscribe ID.

* StartGroup: The start Group ID.

* StartObject: The start Object ID.

* EndGroup: The end Group ID, plus 1. A value of 0 means the subscription is
open-ended.

* Subscriber Priority: Specifies the priority of a subscription relative to
other subscriptions in the same session. Lower numbers get higher priority.
See {{priorities}}.

* Subscribe Parameters: The parameters are defined in {{version-specific-params}}.

## UNSUBSCRIBE {#message-unsubscribe}

A subscriber issues a `UNSUBSCRIBE` message to a publisher indicating it is no
longer interested in receiving media for the specified track and Objects
should stop being sent as soon as possible.  The publisher sends a
SUBSCRIBE_DONE to acknowledge the unsubscribe was successful.

The format of `UNSUBSCRIBE` is as follows:

~~~
UNSUBSCRIBE Message {
  Type (i) = 0xA,
  Length (i),
  Subscribe ID (i)
}
~~~
{: #moq-transport-unsubscribe-format title="MOQT UNSUBSCRIBE Message"}

* Subscribe ID: Subscription Identifier as defined in {{message-subscribe-req}}.


## FETCH {#message-fetch}

A subscriber issues a FETCH to a publisher to request a range of already published
objects within a track. The publisher responding to a FETCH is responsible for retrieving
all available Objects. If there are gaps between Objects, the publisher omits them from the
fetch response. All omitted objects have status Object Not Available.

**Fetch Types**

There are two types of Fetch messages:

Standalone Fetch (0x1) : A Fetch of Objects performed independently of any Subscribe.

Joining Fetch (0x2) : A Fetch joined together with a Subscribe. A Joining Fetch
shares the same Subscribe ID as an already-sent Subscribe. A publisher receiving a Joining
Fetch should use properties of the associated Subscribe to determine the Track Namespace,
Track, StartGroup, StartObject, EndGroup, and EndObject for the Joining Fetch such that it is
contiguous with the associated Subscribe and begins Preceding Group Offset prior.

A Fetch Type other than the above MUST be treated as an error.

A publisher responds to a FETCH request with either a FETCH_OK or a FETCH_ERROR
message.  If it responds with FETCH_OK, the publisher creates a new unidirectional
stream that is used to send the Objects.  A relay MAY start sending objects immediately
in response to a FETCH, even if sending the FETCH_OK takes longer because it requires
going upstream to populate the latest object.

The Object Forwarding Preference does not apply to fetches.

Fetch specifies an inclusive range of Objects starting at StartObject
in StartGroup and ending at EndObject in EndGroup. EndGroup and EndObject MUST
specify the same or a later object than StartGroup and StartObject.

The format of FETCH is as follows:

~~~
FETCH Message {
  Type (i) = 0x16,
  Length (i),
  Subscribe ID (i),
  Subscriber Priority (8),
  Fetch Type (i),
  [Track Namespace (tuple),
   Track Name Length (i),
   Track Name (..),
   Group Order (8),
   StartGroup (i),
   StartObject (i),
   EndGroup (i),
   EndObject (i),]
  [Preceding Group Offset (i),]
  Number of Parameters (i),
  Parameters (..) ...
}
~~~
{: #moq-transport-fetch-format title="MOQT FETCH Message"}

Fields common to all Fetch Types:

* Subscribe ID: The Subscribe ID identifies a given fetch request. Subscribe ID
is a variable length integer that MUST be unique and monotonically increasing
within a session. For a Standalone Fetch a new Subscribe ID MUST be used. For
a Joining Fetch, the Subscribe ID MUST correspond to a Subscribe which has already
been sent. If a publisher receives a Joining Fetch with a Subscribe ID that does
not correspond to an existing Subscribe, it MUST respond with a Fetch Error.

* Subscriber Priority: Specifies the priority of a fetch request relative to
other subscriptions or fetches in the same session. Lower numbers get higher
priority. See {{priorities}}.

* Fetch Type: Identifies the type of Fetch, whether joining or standalone.

* Parameters: The parameters are defined in {{version-specific-params}}.

Fields present only for Standalone Fetch (0x1):

* Track Namespace: Identifies the namespace of the track as defined in
({{track-name}}).

* Track Name: Identifies the track name as defined in ({{track-name}}).

* Group Order: Allows the subscriber to request Objects be delivered in
Ascending (0x1) or Descending (0x2) order by group. See {{priorities}}.
A value of 0x0 indicates the original publisher's Group Order SHOULD be
used. Values larger than 0x2 are a protocol error.

* StartGroup: The start Group ID.

* StartObject: The start Object ID.

* EndGroup: The end Group ID.

* EndObject: The end Object ID, plus 1. A value of 0 means the entire group is
requested.

Field present only for Joining Fetch (0x2):

* Preceding Group Offset: The group offset for the Fetch prior and relative to the StartGroup of the corresponding Subscribe

Objects that are not yet published will not be retrieved by a FETCH.
The latest available Object is indicated in the FETCH_OK, and is the last
Object a fetch will return if the EndGroup and EndObject have not yet been
published.

A publisher MUST send fetched groups in the determined group order, either
ascending or descending. Within each group, objects are sent in Object ID order;
subgroup ID is not used for ordering.

If StartGroup/StartObject is greater than the latest published Object group,
the publisher MUST return FETCH_ERROR with error code 'No Objects'.

A publisher MUST send fetched groups in group order, either ascending or
descending. Within each group, objects are sent in Object ID order;
subgroup ID is not used for ordering.

### Calculating the Range of a Joining Fetch

A publisher which receives a Fetch message with a Fetch Type of 0x2 must treat it as a Fetch
with a range dynamically determined by the Preceding Group Offset (PGO) field and values derived
from to the corresponding Subscribe message (hereafter "the Subscribe").

The following values are used:

* Resolved Subscribe Start Group:
  * For Subscribes with Filter Type LatestObject or LatestGroup, this is equal to Largest Group ID.
  * For Subscribes with Filter Type AbsoluteStart or AbsoluteRange, this is equal to the StartGroup field of the Subscribe message
* Resolved Subscribe Start Object:
  * For Subscribes with Filter Type LatestObject, this is equal to Largest Object ID.
  * For Subscribes with Filter Type LatestGroup, this is 0
  * For Subscribes with Filter Type AbsoluteStart or AbsoluteRange, this is equal to the StartObject field of the Subscribe message
* Preceding Group Offset: A field in the Joining Fetch message indicating the relative offset from the start of the Subscribe

Note: If a relay does not yet have LatestGroup and LatestObject for a given track, it can choose to either forward both the Subscribe and
the Joining Fetch upstream or to wait until the Joining Fetch can be resolved locally. In either case, the Resolved Subscribe Start values
for a Joining Fetch MUST correspond to the Subscribe within the same session so the Fetch and Subscribe can be contiguous and non-overlapping.

Using that information and the following algorithm, these values are computed:

* Fetch Start Group: The StartGroup for the Fetch
* Fetch Start Object: The StartObject for the Fetch (always 0)
* Fetch End Group: The EndGroup for the Fetch
* Fetch End Object: The EndObject for the Fetch (represented as 1 more than the end Object ID
  or a value of 0 indicating that the entire group is requested)

The publisher receiving a Joining Fetch computes the fetch range as follows:

* Fetch Start Group: Resolved Subscribe Start Group - Preceding Group Offset
* Fetch Start Object: 0

If Resolved Subscribe Start Object is 0:
* Fetch End Group: Resolved Subscribe Start Group - 1
* Fetch End Object: 0 (all objects in the group)

Else, if Resolved Subscribe Start Object is 1 or more:
* Fetch End Group: Resolved Subscribe Start Group
* Fetch End Object: Resolved Subscribe Start Object

If Fetch End Group < Fetch Start Group respond with a Fetch Error.

A Joining Fetch MUST be sent in ascending group order.

## FETCH_CANCEL {#message-fetch-cancel}

A subscriber issues a `FETCH_CANCEL` message to a publisher indicating it is no
longer interested in receiving Objects for the fetch specified by 'Subscribe ID'.
The publisher SHOULD close the unidirectional stream as soon as possible.

The format of `FETCH_CANCEL` is as follows:

~~~
FETCH_CANCEL Message {
  Type (i) = 0x17,
  Length (i),
  Subscribe ID (i)
}
~~~
{: #moq-transport-fetch-cancel title="MOQT FETCH_CANCEL Message"}

* Subscribe ID: Subscription Identifier as defined in {{message-fetch}}.


## ANNOUNCE_OK {#message-announce-ok}

The subscriber sends an ANNOUNCE_OK control message to acknowledge the
successful authorization and acceptance of an ANNOUNCE message.

~~~
ANNOUNCE_OK Message
{
  Type (i) = 0x7,
  Length (i),
  Track Namespace (tuple),
}
~~~
{: #moq-transport-announce-ok format title="MOQT ANNOUNCE_OK Message"}

* Track Namespace: Identifies the track namespace in the ANNOUNCE
message for which this response is provided.

## ANNOUNCE_ERROR {#message-announce-error}

The subscriber sends an ANNOUNCE_ERROR control message for tracks that
failed authorization.

~~~
ANNOUNCE_ERROR Message
{
  Type (i) = 0x8,
  Length (i),
  Track Namespace (tuple),
  Error Code (i),
  Reason Phrase Length (i),
  Reason Phrase (..),
}
~~~
{: #moq-transport-announce-error format title="MOQT ANNOUNCE_ERROR Message"}

* Track Namespace: Identifies the track namespace in the ANNOUNCE
message for which this response is provided.

* Error Code: Identifies an integer error code for announcement failure.

* Reason Phrase: Provides the reason for announcement error.

## ANNOUNCE_CANCEL {#message-announce-cancel}

The subscriber sends an `ANNOUNCE_CANCEL` control message to
indicate it will stop sending new subscriptions for tracks
within the provided Track Namespace.

If a publisher receives new subscriptions for that namespace after
receiving an ANNOUNCE_CANCEL, it SHOULD close the session as a
'Protocol Violation'.

~~~
ANNOUNCE_CANCEL Message {
  Type (i) = 0xC,
  Length (i),
  Track Namespace (tuple),
  Error Code (i),
  Reason Phrase Length (i),
  Reason Phrase Length (..),
}
~~~
{: #moq-transport-announce-cancel-format title="MOQT ANNOUNCE_CANCEL Message"}

* Track Namespace: Identifies a track's namespace as defined in
({{track-name}}).

* Error Code: Identifies an integer error code for canceling the announcement.

* Reason Phrase: Provides the reason for announcement cancelation.


## TRACK_STATUS_REQUEST {#message-track-status-req}

A potential subscriber sends a 'TRACK_STATUS_REQUEST' message on the control
stream to obtain information about the current status of a given track.

A TRACK_STATUS message MUST be sent in response to each TRACK_STATUS_REQUEST.

~~~
TRACK_STATUS_REQUEST Message {
  Type (i) = 0xD,
  Length (i),
  Track Namespace (tuple),
  Track Name Length (i),
  Track Name (..),
}
~~~
{: #moq-track-status-request-format title="MOQT TRACK_STATUS_REQUEST Message"}

## SUBSCRIBE_ANNOUNCES {#message-subscribe-ns}

The subscriber sends the SUBSCRIBE_ANNOUNCES control message to a publisher
to request the current set of matching announcements, as well as future updates
to the set.

~~~
SUBSCRIBE_ANNOUNCES Message {
  Type (i) = 0x11,
  Length (i),
  Track Namespace Prefix (tuple),
  Number of Parameters (i),
  Parameters (..) ...,
}
~~~
{: #moq-transport-subscribe-ns-format title="MOQT SUBSCRIBE_ANNOUNCES Message"}

* Track Namespace Prefix: An ordered N-Tuple of byte fields which are matched
against track namespaces known to the publisher.  For example, if the publisher
is a relay that has received ANNOUNCE messages for namespaces ("example.com",
"meeting=123", "participant=100") and ("example.com", "meeting=123",
"participant=200"), a SUBSCRIBE_ANNOUNCES for ("example.com", "meeting=123")
would match both.  If an endpoint receives a Track Namespace Prefix tuple with
an N of 0 or more than 32, it MUST close the session with a Protocol
Violation.

* Parameters: The parameters are defined in {{version-specific-params}}.

The publisher will respond with SUBSCRIBE_ANNOUNCES_OK or
SUBSCRIBE_ANNOUNCES_ERROR.  If the SUBSCRIBE_ANNOUNCES is successful,
the publisher will forward any matching ANNOUNCE messages to the subscriber
that it has not yet sent.  If the set of matching ANNOUNCE messages changes, the
publisher sends the corresponding ANNOUNCE or UNANNOUNCE message.

A subscriber cannot make overlapping namespace subscriptions on a single
session.  Within a session, if a publisher receives a SUBSCRIBE_ANNOUNCES
with a Track Namespace Prefix that is a prefix of an earlier
SUBSCRIBE_ANNOUNCES or vice versa, it MUST respond with
SUBSCRIBE_ANNOUNCES_ERROR, with error code SUBSCRIBE_ANNOUNCES_OVERLAP.

The publisher MUST ensure the subscriber is authorized to perform this
namespace subscription.

SUBSCRIBE_ANNOUNCES is not required for a publisher to send ANNOUNCE and
UNANNOUNCE messages to a subscriber.  It is useful in applications or relays
where subscribers are only interested in or authorized to access a subset of
available announcements.

## UNSUBSCRIBE_ANNOUNCES {#message-unsub-ann}

A subscriber issues a `UNSUBSCRIBE_ANNOUNCES` message to a publisher
indicating it is no longer interested in ANNOUNCE and UNANNOUNCE messages for
the specified track namespace prefix.

The format of `UNSUBSCRIBE_ANNOUNCES` is as follows:

~~~
UNSUBSCRIBE_ANNOUNCES Message {
  Type (i) = 0x14,
  Length (i),
  Track Namespace Prefix (tuple)
}
~~~
{: #moq-transport-unsub-ann-format title="MOQT UNSUBSCRIBE Message"}

* Track Namespace Prefix: As defined in {{message-subscribe-ns}}.

## SUBSCRIBE_OK {#message-subscribe-ok}

A publisher sends a SUBSCRIBE_OK control message for successful
subscriptions.

~~~
SUBSCRIBE_OK
{
  Type (i) = 0x4,
  Length (i),
  Subscribe ID (i),
  Expires (i),
  Group Order (8),
  ContentExists (8),
  [Largest Group ID (i)],
  [Largest Object ID (i)],
  Number of Parameters (i),
  Subscribe Parameters (..) ...
}
~~~
{: #moq-transport-subscribe-ok format title="MOQT SUBSCRIBE_OK Message"}

* Subscribe ID: Subscription Identifier as defined in {{message-subscribe-req}}.

* Expires: Time in milliseconds after which the subscription is no
longer valid. A value of 0 indicates that the subscription does not expire
or expires at an unknown time.  Expires is advisory and a subscription can
end prior to the expiry time or last longer.

* Group Order: Indicates the subscription will be delivered in
Ascending (0x1) or Descending (0x2) order by group. See {{priorities}}.
Values of 0x0 and those larger than 0x2 are a protocol error.

* ContentExists: 1 if an object has been published on this track, 0 if not.
If 0, then the Largest Group ID and Largest Object ID fields will not be
present. Any other value is a protocol error and MUST terminate the
session with a Protocol Violation ({{session-termination}}).

* Largest Group ID: The largest Group ID available for this track. This field
is only present if ContentExists has a value of 1.

* Largest Object ID: The largest Object ID available within the largest Group ID
for this track. This field is only present if ContentExists has a value of 1.

* Subscribe Parameters: The parameters are defined in {{version-specific-params}}.

## SUBSCRIBE_ERROR {#message-subscribe-error}

A publisher sends a SUBSCRIBE_ERROR control message in response to a
failed SUBSCRIBE.

~~~
SUBSCRIBE_ERROR
{
  Type (i) = 0x5,
  Length (i),
  Subscribe ID (i),
  Error Code (i),
  Reason Phrase Length (i),
  Reason Phrase (..),
  Track Alias (i),
}
~~~
{: #moq-transport-subscribe-error format title="MOQT SUBSCRIBE_ERROR Message"}

* Subscribe ID: Subscription Identifier as defined in {{message-subscribe-req}}.

* Error Code: Identifies an integer error code for subscription failure.

* Reason Phrase: Provides the reason for subscription error.

* Track Alias: When Error Code is 'Retry Track Alias', the subscriber SHOULD re-issue the
  SUBSCRIBE with this Track Alias instead. If this Track Alias is already in use,
  the subscriber MUST close the connection with a Duplicate Track Alias error
  ({{session-termination}}).


## FETCH_OK {#message-fetch-ok}

A publisher sends a FETCH_OK control message in response to successful fetches.
A publisher MAY send Objects in response to a FETCH before the FETCH_OK message is sent,
but the FETCH_OK MUST NOT be sent until the latest group and object are known.

~~~
FETCH_OK
{
  Type (i) = 0x18,
  Length (i),
  Subscribe ID (i),
  Group Order (8),
  End Of Track (8),
  Largest Group ID (i),
  Largest Object ID (i),
  Number of Parameters (i),
  Subscribe Parameters (..) ...
}
~~~
{: #moq-transport-fetch-ok format title="MOQT FETCH_OK Message"}

* Subscribe ID: Fetch Identifier as defined in {{message-fetch}}.

* Group Order: Indicates the fetch will be delivered in
Ascending (0x1) or Descending (0x2) order by group. See {{priorities}}.
Values of 0x0 and those larger than 0x2 are a protocol error.

* End Of Track: 1 if all objects have been published on this track, so
the Largest Group ID and Object Id indicate the last Object in the track,
0 if not.

* Largest Group ID: The largest Group ID available for this track. This field
is only present if ContentExists has a value of 1.

* Largest Object ID: The largest Object ID available within the largest Group ID
for this track. This field is only present if ContentExists has a value of 1.

* Subscribe Parameters: The parameters are defined in {{version-specific-params}}.

## FETCH_ERROR {#message-fetch-error}

A publisher sends a FETCH_ERROR control message in response to a
failed FETCH.

~~~
FETCH_ERROR
{
  Type (i) = 0x19,
  Length (i),
  Subscribe ID (i),
  Error Code (i),
  Reason Phrase Length (i),
  Reason Phrase (..),
}
~~~
{: #moq-transport-fetch-error format title="MOQT FETCH_ERROR Message"}

* Subscribe ID: Subscription Identifier as defined in {{message-subscribe-req}}.

* Error Code: Identifies an integer error code for fetch failure.

* Reason Phrase: Provides the reason for fetch error.


## SUBSCRIBE_DONE {#message-subscribe-done}

A publisher sends a `SUBSCRIBE_DONE` message to indicate it is done publishing
Objects for that subscription.  The Status Code indicates why the subscription
ended, and whether it was an error. Because SUBSCRIBE_DONE is sent on the
control stream, it is likely to arrive at the receiver before late-arriving
objects, and often even late-opening streams. However, the receiver uses it
as an indication that it should receive any late-opening streams in a relatively
short time.

Note that some objects in the subscribed track might never be delivered,
because a stream was reset, or never opened in the first place, due to the
delivery timeout.

A sender MUST NOT send SUBSCRIBE_DONE until it has closed all streams it will
ever open, and has no further datagrams to send, for a subscription. After
sending SUBSCRIBE_DONE, the sender can immediately destroy subscription state,
although stream state can persist until delivery completes. The sender might
persist subscription state to enforce the delivery timeout by resetting streams
on which it has already sent FIN, only deleting it when all such streams have
received ACK of the FIN.

A sender MUST NOT destroy subscription state until it sends SUBSCRIBE_DONE,
though it can choose to stop sending objects (and thus send SUBSCRIBE_DONE) for
any reason.

A subscriber that receives SUBSCRIBE_DONE SHOULD set a timer of at least its
delivery timeout in case some objects are still inbound due to prioritization
or packet loss. The subscriber MAY dispense with a timer if it sent UNSUBSCRIBE
or is otherwise no longer interested in objects from the track. Once the timer
has expired, the receiver destroys subscription state once all open streams for
the subscription have closed. A subscriber MAY discard subscription state
earlier, at the cost of potentially not delivering some late objects to the
application. The subscriber SHOULD send STOP_SENDING on all streams related to
the subscription when it deletes subscription state.

The format of `SUBSCRIBE_DONE` is as follows:

~~~
SUBSCRIBE_DONE Message {
  Type (i) = 0xB,
  Length (i),
  Subscribe ID (i),
  Status Code (i),
  Stream Count (i),
  Reason Phrase Length (i),
  Reason Phrase (..),
}
~~~
{: #moq-transport-subscribe-fin-format title="MOQT SUBSCRIBE_DONE Message"}

* Subscribe ID: Subscription identifier as defined in {{message-subscribe-req}}.

* Status Code: An integer status code indicating why the subscription ended.

* Stream Count: An integer indicating the number of data streams the publisher
opened for this subscription.  The subscriber can remove all subscription state
once the same number of streams have been processed.

* Reason Phrase: Provides the reason for subscription error.

## MAX_SUBSCRIBE_ID {#message-max-subscribe-id}

A publisher sends a MAX_SUBSCRIBE_ID message to increase the number of
subscriptions a subscriber can create within a session.

The Maximum Subscribe Id MUST only increase within a session, and
receipt of a MAX_SUBSCRIBE_ID message with an equal or smaller Subscribe ID
value is a 'Protocol Violation'.

~~~
MAX_SUBSCRIBE_ID
{
  Type (i) = 0x15,
  Length (i),
  Subscribe ID (i),
}
~~~
{: #moq-transport-max-subscribe-id format title="MOQT MAX_SUBSCRIBE_ID Message"}

* Subscribe ID: The new Maximum Subscribe ID for the session. If a Subscribe ID
{{message-subscribe-req}} equal or larger than this is received by the publisher
that sent the MAX_SUBSCRIBE_ID, the publisher MUST close the session with an
error of 'Too Many Subscribes'.

## SUBSCRIBES_BLOCKED {#message-subscribes-blocked}

The SUBSCRIBES_BLOCKED message is sent when a subscriber would like to begin
a new subscription, but cannot because the Subscribe ID would exceed the
Maximum Subscribe ID value sent by the peer.  The subscriber SHOULD send only
one SUBSCRIBES_BLOCKED for a given Maximum Subscribe ID.

A publisher MAY send a MAX_SUBSCRIBE_ID upon receipt of SUBSCRIBES_BLOCKED,
but it MUST NOT rely on SUBSCRIBES_BLOCKED to trigger sending a
MAX_SUBSCRIBE_ID, because sending SUBSCRIBES_BLOCKED is not required.

~~~
SUBSCRIBES_BLOCKED
{
  Type (i) = 0x1A,
  Length (i),
  Maximum Subscribe ID (i),
}
~~~
{: #moq-transport-subscribes-blocked format title="MOQT SUBSCRIBES_BLOCKED Message"}

* Maximum Subscribe ID: The Maximum Subscribe ID for the session on which the subscriber
is blocked. More on Subscribe ID in {{message-subscribe-req}}.


## ANNOUNCE {#message-announce}

The publisher sends the ANNOUNCE control message to advertise where the
receiver can route SUBSCRIBEs for tracks within the announced
Track Namespace. The receiver verifies the publisher is authorized to
publish tracks under this namespace.

~~~
ANNOUNCE Message {
  Type (i) = 0x6,
  Length (i),
  Track Namespace (tuple),
  Number of Parameters (i),
  Parameters (..) ...,
}
~~~
{: #moq-transport-announce-format title="MOQT ANNOUNCE Message"}

* Track Namespace: Identifies a track's namespace as defined in
({{track-name}})

* Parameters: The parameters are defined in {{version-specific-params}}.


## UNANNOUNCE {#message-unannounce}

The publisher sends the `UNANNOUNCE` control message to indicate
its intent to stop serving new subscriptions for tracks
within the provided Track Namespace.

~~~
UNANNOUNCE Message {
  Type (i) = 0x9,
  Length (i),
  Track Namespace (tuple),
}
~~~
{: #moq-transport-unannounce-format title="MOQT UNANNOUNCE Message"}

* Track Namespace: Identifies a track's namespace as defined in
({{track-name}}).


## TRACK_STATUS {#message-track-status}

A publisher sends a 'TRACK_STATUS' message on the control stream in response
to a TRACK_STATUS_REQUEST message.

~~~
TRACK_STATUS Message {
  Type (i) = 0xE,
  Length (i),
  Track Namespace (tuple),
  Track Name Length(i),
  Track Name (..),
  Status Code (i),
  Last Group ID (i),
  Last Object ID (i),
}
~~~
{: #moq-track-status-format title="MOQT TRACK_STATUS Message"}

The 'Status Code' field provides additional information about the status of the
track. It MUST hold one of the following values. Any other value is a malformed
message.

0x00: The track is in progress, and subsequent fields contain the highest group
and object ID for that track.

0x01: The track does not exist. Subsequent fields MUST be zero, and any other
value is a malformed message.

0x02: The track has not yet begun. Subsequent fields MUST be zero. Any other
value is a malformed message.

0x03: The track has finished, so there is no "live edge." Subsequent fields
contain the highest Group and object ID known.

0x04: The publisher is a relay that cannot obtain the current track status from
upstream. Subsequent fields contain the largest group and object ID known.

Any other value in the Status Code field is a malformed message.

When a relay is subscribed to a track, it can simply return the highest group
and object ID it has observed, whether or not that object was cached or
completely delivered. If not subscribed, a relay SHOULD send a
TRACK_STATUS_REQUEST upstream to obtain updated information.

Alternatively, the relay MAY subscribe to the track to obtain the same
information.

If a relay cannot or will not do either, it should return its best available
information with status code 0x04.

The receiver of multiple TRACK_STATUS messages for a track uses the information
from the latest arriving message, as they are delivered in order on a single
stream.

## SUBSCRIBE_ANNOUNCES_OK {#message-sub-ann-ok}

A publisher sends a SUBSCRIBE_ANNOUNCES_OK control message for successful
namespace subscriptions.

~~~
SUBSCRIBE_ANNOUNCES_OK
{
  Type (i) = 0x12,
  Length (i),
  Track Namespace Prefix (tuple),
}
~~~
{: #moq-transport-sub-ann-ok format title="MOQT SUBSCRIBE_ANNOUNCES_OK
Message"}

* Track Namespace Prefix: As defined in {{message-subscribe-ns}}.

## SUBSCRIBE_ANNOUNCES_ERROR {#message-sub-ann-error}

A publisher sends a SUBSCRIBE_ANNOUNCES_ERROR control message in response to
a failed SUBSCRIBE_ANNOUNCES.

~~~
SUBSCRIBE_ANNOUNCES_ERROR
{
  Type (i) = 0x13,
  Length (i),
  Track Namespace Prefix (tuple),
  Error Code (i),
  Reason Phrase Length (i),
  Reason Phrase (..),
}
~~~
{: #moq-transport-sub-ann-error format
title="MOQT SUBSCRIBE_ANNOUNCES_ERROR Message"}

* Track Namespace Prefix: As defined in {{message-subscribe-ns}}.

* Error Code: Identifies an integer error code for the namespace subscription
failure.

* Reason Phrase: Provides the reason for the namespace subscription error.



# Data Streams {#data-streams}

A publisher sends Objects matching a subscription on Data Streams.

All unidirectional MOQT streams start with a variable-length integer indicating
the type of the stream in question.

|-------|-------------------------------------------------------|
| ID    | Type                                                  |
|------:|:------------------------------------------------------|
| 0x4   | STREAM_HEADER_SUBGROUP  ({{stream-header-subgroup}})  |
|-------|-------------------------------------------------------|
| 0x5   | FETCH_HEADER  ({{fetch-header}})                      |
|-------|-------------------------------------------------------|

All MOQT datagrams start with a variable-length integer indicating the type of
the datagram.

|-------|-------------------------------------------------------|
| ID    | Type                                                  |
|------:|:------------------------------------------------------|
| 0x1   | OBJECT_DATAGRAM ({{object-datagram}})                 |
|-------|-------------------------------------------------------|
| 0x2   | OBJECT_DATAGRAM_STATUS ({{object-datagram}})          |
|-------|-------------------------------------------------------|

An endpoint that receives an unknown stream or datagram type MUST close the
session.

Every Track has a single 'Object Forwarding Preference' and the Original
Publisher MUST NOT mix different forwarding preferences within a single track.
If a subscriber receives different forwarding preferences for a track, it
SHOULD close the session with an error of 'Protocol Violation'.

## Object Headers {#message-object}

An OBJECT message contains a range of contiguous bytes from from the
specified track, as well as associated metadata required to deliver,
cache, and forward it.  Objects are sent by publishers.

### Canonical Object Fields {#object-fields}

A canonical MoQ Object has the following information:

* Track Namespace and Track Name: The track this object belongs to.

* Group ID: The object is a member of the indicated group ID
{{model-group}} within the track.

* Object ID: The order of the object within the group.  The
IDs starts at 0, increasing sequentially for each object within the
group.

* Publisher Priority: An 8 bit integer indicating the publisher's priority for
the Object {{priorities}}.

* Object Forwarding Preference: An enumeration indicating how a publisher sends
an object. The preferences are Track, Subgroup, and Datagram.  An Object
MUST be sent according to its `Object Forwarding Preference`, described below.

* Subgroup ID: The object is a member of the indicated subgroup ID ({{model-subgroup}})
within the group. This field is omitted if the Object Forwarding Preference is
Track or Datagram.

* Object Status: As enumeration used to indicate missing
objects or mark the end of a group or track. See {{object-status}} below.

* Object Payload: An opaque payload intended for an End Subscriber and SHOULD
NOT be processed by a relay. Only present when 'Object Status' is Normal (0x0).

#### Object Status {#object-status}

The Object Status informs subscribers what objects will not be received
because they were never produced, are no longer available, or because they
are beyond the end of a group or track.

`Status` can have following values:

* 0x0 := Normal object. The payload is array of bytes and can be empty.

* 0x1 := Indicates Object does not exist. Indicates that this object
         does not exist at any publisher and it will not be published in
         the future. This SHOULD be cached.

* 0x3 := Indicates end of Group. ObjectId is one greater that the
         largest object produced in the group identified by the
         GroupID. This is sent right after the last object in the
         group. If the ObjectID is 0, it indicates there are no Objects
         in this Group. This SHOULD be cached. A publisher MAY use an end of
         Group object to signal the end of all open Subgroups in a Group.

* 0x4 := Indicates end of Track and Group. GroupID is one greater than
         the largest group produced in this track and the ObjectId is
         one greater than the largest object produced in that
         group. This is sent right after the last object in the
         track. This SHOULD be cached.

Any other value SHOULD be treated as a protocol error and terminate the
session with a Protocol Violation ({{session-termination}}).
Any object with a status code other than zero MUST have an empty payload.

Though some status information could be inferred from QUIC stream state,
that information is not reliable and cacheable.

## Object Datagram Message {#object-datagram}

An `OBJECT_DATAGRAM` message carries a single object in a datagram.

An Object received in an `OBJECT_DATAGRAM` message has an `Object
Forwarding Preference` = `Datagram`. To send an Object with `Object
Forwarding Preference` = `Datagram`, determine the length of the header and
payload and send the Object as datagram. In certain scenarios where the object
size can be larger than maximum datagram size for the session, the Object
will be dropped.

~~~
OBJECT_DATAGRAM Message {
  Track Alias (i),
  Group ID (i),
  Object ID (i),
  Publisher Priority (8),
  Object Payload (..),
}
~~~
{: #object-datagram-format title="MOQT OBJECT_DATAGRAM Message"}

There is no explicit length field.  The entirety of the transport datagram
following Publisher Priority contains the Object Payload.

## Object Datagram Status Message {#object-datagram-status}

An `OBJECT_DATAGRAM_STATUS` message is similar to OBEJCT_DATAGRAM except it
conveys an Object Status and has no payload.

~~~
OBJECT_DATAGRAM_STATUS Message {
  Track Alias (i),
  Group ID (i),
  Object ID (i),
  Publisher Priority (8),
  Object Status (i),
}
~~~
{: #object-datagram-status-format title="MOQT OBJECT_DATAGRAM_STATUS Message"}

## Streams

When objects are sent on streams, the stream begins with a stream header
message and is followed by one or more sets of serialized object fields.
If a stream ends gracefully in the middle of a serialized Object, terminate the
session with a Protocol Violation.

A publisher SHOULD NOT open more than one stream at a time with the same stream
header message type and fields.


TODO: figure out how a relay closes these streams


### Stream Header Subgroup

When a stream begins with `STREAM_HEADER_SUBGROUP`, all objects on the stream
belong to the track requested in the Subscribe message identified by `Track Alias`
and the subgroup indicated by 'Group ID' and `Subgroup ID`.

~~~
STREAM_HEADER_SUBGROUP Message {
  Track Alias (i),
  Group ID (i),
  Subgroup ID (i),
  Publisher Priority (8),
}
~~~
{: #stream-header-subgroup-format title="MOQT STREAM_HEADER_SUBGROUP Message"}

All Objects received on a stream opened with `STREAM_HEADER_SUBGROUP` have an
`Object Forwarding Preference` = `Subgroup`.

To send an Object with `Object Forwarding Preference` = `Subgroup`, find the open
stream that is associated with the subscription, `Group ID` and `Subgroup ID`,
or open a new one and send the `STREAM_HEADER_SUBGROUP`. Then serialize the
following fields.

The Object Status field is only sent if the Object Payload Length is zero.

~~~
{
  Object ID (i),
  Object Payload Length (i),
  [Object Status (i)],
  Object Payload (..),
}
~~~
{: #object-group-format title="MOQT Group Stream Object Fields"}

A publisher MUST NOT send an Object on a stream if its Object ID is less than a
previously sent Object ID within a given group in that stream.

### Closing Subgroup Streams

Subscribers will often need to know if they have received all objects in a
Subgroup, particularly if they serve as a relay or cache. QUIC and Webtransport
streams provide signals that can be used for this purpose. Closing Subgroups
promptly frees system resources and often unlocks flow control credit to open
more streams.

If a sender has delivered all objects in a Subgroup to the QUIC stream, except
any objects before the beginning of a subscription, it MUST close the
stream with a FIN.

If a sender closes the stream before delivering all such objects to the QUIC
stream, it MUST use a RESET_STREAM or RESET_STREAM_AT
{{!I-D.draft-ietf-quic-reliable-stream-reset}} frame. This includes an open
Subgroup exceeding its Delivery Timeout, early termination of subscription due to
an UNSUBSCRIBE message, a publisher's decision to end the subscription early, or a
SUBSCRIBE_UPDATE moving the end of the subscription to before the current Group
or the start after the current Group.  When RESET_STREAM_AT is used, the
reliable_size SHOULD include the stream header so the receiver can identify the
corresponding subscription and accurately account for reset data streams when
handling SUBSCRIBE_DONE (see {{message-subscribe-done}}).  Publishers that reset
data streams without using RESET_STREAM_AT with an appropriate reliable_size can
cause subscribers to hold on to subscription state until a timeout expires.

A sender might send all objects in a Subgroup and the FIN on a QUIC stream,
and then reset the stream. In this case, the receiving application would receive
the FIN if and only if all objects were received. If the application receives
all data on the stream and the FIN, it can ignore any RESET_STREAM it receives.

If a sender will not deliver any objects from a Subgroup, it MAY send
a STREAM_HEADER_SUBGROUP on a new stream, with no objects, and
then send RESET_STREAM_AT with a reliable_size equal to the length of the
stream header. This explicitly tells the receiver there is an unsent Subgroup.

Since SUBSCRIBEs always end on a group boundary, an ending subscription can
always cleanly close all its subgroups. A sender that terminates a stream
early for any other reason (e.g., to handoff to a different sender) MUST
use RESET_STREAM or RESET_STREAM_AT. Senders SHOULD terminate a stream on
Group boundaries to avoid doing so.

An MoQT implementation that processes a stream FIN is assured it has received
all objects in a subgroup from the start of the subscription. If a relay, it
can forward stream FINs to its own subscribers once those objects have been
sent. A relay MAY treat receipt of EndOfGroup, GroupDoesNotExist, or
EndOfTrack objects as a signal to close corresponding streams even if the FIN
has not arrived, as further objects on the stream would be a protocol violation.

Similarly, an EndOfGroup message indicates the maximum Object ID in the
Group, so if all Objects in the Group have been received, a FIN can be sent on
any stream where the entire subgroup has been sent. This might be complex to
implement.

Processing a RESET_STREAM or RESET_STREAM_AT means that there might be other
objects in the Subgroup beyond the last one received. A relay might immediately
reset the corresponding downstream stream, or it might attempt to recover the
missing Objects in an effort send all the objects in the subgroups and the FIN. It also
might send RESET_STREAM_AT with reliable_size set to the last object it has, so
as to reliably deliver the objects it has while signaling that other objects
might exist.

A subscriber MAY send a QUIC STOP_SENDING frame for a subgroup stream if the Group
or Subgroup is no longer of interest to it. The publisher SHOULD respond with
RESET_STREAM or RESET_STREAM_AT. If RESET_STREAM_AT is sent, note that the receiver
has indicated no interest in the objects, so setting a reliable_size beyond the
stream header is of questionable utility.

RESET_STREAM and STOP_SENDING on SUBSCRIBE data streams have no impact on other
Subgroups in the Group or the subscription, although applications might cancel all
Subgroups in a Group at once.

### Fetch Header {#fetch-header}

When a stream begins with `FETCH_HEADER`, all objects on the stream belong to the
track requested in the Fetch message identified by `Subscribe ID`.

~~~
FETCH_HEADER Message {
  Subscribe ID (i),
}
~~~
{: #fetch-header-format title="MOQT FETCH_HEADER Message"}


Each object sent on a fetch stream after the FETCH_HEADER has the following format:

~~~
{
  Group ID (i),
  Subgroup ID (i),
  Object ID (i),
  Publisher Priority (8),
  Object Payload Length (i),
  [Object Status (i)],
  Object Payload (..),
}
~~~
{: #object-fetch-format title="MOQT Fetch Object Fields"}

The Object Status field is only sent if the Object Payload Length is zero.

The Subgroup ID field of an object with a Forwarding Preference of "Datagram"
(see {{object-fields}}) is set to the Object ID.

## Examples

Sending a track on one stream:

~~~
STREAM_HEADER_TRACK {
  Track Alias = 1
  Publisher Priority = 0
}
{
  Group ID = 0
  Object ID = 0
  Object Payload Length = 4
  Payload = "abcd"
}
{
  Group ID = 1
  Object ID = 0
  Object Payload Length = 4
  Payload = "efgh"
}
~~~

Sending a subgroup on one stream:

~~~
Stream = 2

STREAM_HEADER_SUBGROUP {
  Track Alias = 2
  Group ID = 0
  Subgroup ID = 0
  Publisher Priority = 0
}
{
  Object ID = 0
  Object Payload Length = 4
  Payload = "abcd"
}
{
  Object ID = 1
  Object Payload Length = 4
  Payload = "efgh"
}
~~~



# Security Considerations {#security}

TODO: Expand this section, including subscriptions.

## Resource Exhaustion

Live content requires significant bandwidth and resources.  Failure to
set limits will quickly cause resource exhaustion.

MOQT uses stream limits and flow control to impose resource limits at
the network layer.  Endpoints SHOULD set flow control limits based on the
anticipated bitrate.

Endpoints MAY impose a MAX STREAM count limit which would restrict the
number of concurrent streams which a MOQT Streaming Format could have in
flight.

The publisher prioritizes and transmits streams out of order.  Streams
might be starved indefinitely during congestion.  The publisher and
subscriber MUST cancel a stream, preferably the lowest priority, after
reaching a resource limit.


# IANA Considerations {#iana}

TODO: fill out currently missing registries:

* MOQT version numbers
* Setup parameters
* Subscribe parameters
* Subscribe Error codes
* Subscribe Namespace Error codes
* Announce Error codes
* Announce Cancel Reason codes
* Message types

TODO: register the URI scheme and the ALPN

# Contributors
{:numbered="false"}

- Alan Frindell
- Ali Begen
- Charles Krasic
- Christian Huitema
- Cullen Jennings
- James Hurley
- Jordi Cenzano
- Mike English
- Mo Zanaty
- Will Law
