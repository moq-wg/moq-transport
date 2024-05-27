---
title: "Media over QUIC Transport"
abbrev: moq-transport
docname: draft-ietf-moq-transport-latest
date: {DATE}
category: std

ipr: trust200902
area: Applications and Real-Time
submissionType: IETF
workgroup: MOQ
keyword: Internet-Draft

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

MOQT is a generic protocol is designed to work in concert with multiple
MoQ Streaming Formats. These MoQ Streaming Formats define how content is
encoded, packaged, and mapped to MOQT objects, along with policies for
discovery and subscription.

* {{model}} describes the object model employed by MOQT.

* {{session}} covers aspects of setting up a MOQT session.

* {{priority-congestion}} covers protocol considerations on
  prioritization schemes and congestion response overall.

* {{relays-moq}} covers behavior at the relay entities.

* {{message}} covers how messages are encoded on the wire.


## Motivation

The development of MOQT is driven by goals in a number of areas -
specifically latency, the robustness of QUIC, workflow efficiency and
relay support.

### Latency

HTTP Adaptive Streaming (HAS) has been successful at achieving scale
although often at the cost of latency. Latency is necessary to correct
for variable network throughput. Ideally live content is consumed at the
same bitrate it is produced. End-to-end latency would be fixed and only
subject to encoding and transmission delays. Unfortunately, networks
have variable throughput, primarily due to congestion. Attempting to
deliver content encoded at a higher bitrate than the network can support
causes queuing along the path from producer to consumer. The speed at
which a protocol can detect and respond to queuing determines the
overall latency. TCP-based protocols are simple but are slow to detect
congestion and suffer from head-of-line blocking. Protocols utilizing
UDP directly can avoid queuing, but the application is then responsible
for the complexity of fragmentation, congestion control, retransmissions,
receiver feedback, reassembly, and more. One goal of MOQT is to achieve
the best of both these worlds: leverage the features of QUIC to create a
simple yet flexible low latency protocol that can rapidly detect and
respond to congestion.

### Leveraging QUIC

The parallel nature of QUIC streams can provide improvements in the face
of loss. A goal of MOQT is to design a streaming protocol to leverage
the transmission benefits afforded by parallel QUIC streams as well
exercising options for flexible loss recovery. Applying {{QUIC}} to HAS
via HTTP/3 has not yet yielded generalized improvements in
throughput. One reason for this is that sending segments down a single
QUIC stream still allows head-of-line blocking to occur.

### Universal

Internet delivered media today has protocols optimized for ingest and
separate protocols optimized for distribution. This protocol switch in
the distribution chain necessitates intermediary origins which
re-package the media content. While specialization can have its
benefits, there are gains in efficiency to be had in not having to
re-package content. A goal of MOQT is to develop a single protocol which
can be used for transmission from contribution to distribution. A
related goal is the ability to support existing encoding and packaging
schemas, both for backwards compatibility and for interoperability with
the established content preparation ecosystem.

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

: The party initiating a MoQ transport session.

Server:

: The party accepting an incoming transport session.

Endpoint:

: A Client or Server.

Producer:

: An endpoint sending media over the network.

Consumer:

: An endpoint receiving media over the network.

Transport session:

: A raw QUIC connection or a WebTransport session.

Congestion:

: Packet loss and queuing caused by degraded or overloaded networks.

Group:

: A temporal sequence of objects. A group represents a join point in a
  track. See ({{model-group}}).

Object:

: An object is an addressable unit whose payload is a sequence of
  bytes. Objects form the base element in the MOQT model. See
  ({{model-object}}).

Track:

: An encoded bitstream. Tracks contain a sequential series of one or
  more groups and are the subscribable entity with MOQT.


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

x (f):

: Indicates that x is a flag and is encoded as a single byte with the
  value 0 or 1. A value of 0 indicates the flag is false or off, while a
  value of 1 indicates the flag is true or on. Any other value is a
  protocol error and SHOULD terminate the session with a Protocol
  Violation ({{session-termination}}).


To reduce unnecessary use of bandwidth, variable length integers SHOULD
be encoded using the least number of bytes possible to represent the
required value.


# Object Model {#model}

MOQT has a hierarchical object model for data, comprised of objects,
groups and tracks.

## Objects {#model-object}

The basic data element of MOQT is an object.  An object is an
addressable unit whose payload is a sequence of bytes.  All objects
belong to a group, indicating ordering and potential
dependencies. {{model-group}}  An object is uniquely identified by
its track namespace, track name, group ID, and object ID, and must be an
identical sequence of bytes regardless of how or where it is retrieved.
An Object can become unavailable, but it's contents MUST NOT change over
time.

Objects are comprised of two parts: metadata and a payload.
The metadata is never encrypted and is always
visible to relays. The payload portion may be encrypted, in which case
it is only visible to the producer and consumer. The application is
solely responsible for the content of the object payload. This includes
the underlying encoding, compression, any end-to-end encryption, or
authentication. A relay MUST NOT combine, split, or otherwise modify
object payloads.

## Groups {#model-group}

A group is a collection of objects and is a sub-unit of a track
({{model-track}}).  Objects within a group SHOULD NOT depend on objects
in other groups.  A group behaves as a join point for subscriptions.
A new subscriber might not want to receive the entire track, and may
instead opt to receive only the latest group(s).  The sender then
selectively transmits objects based on their group membership.

## Track {#model-track}

A track is a sequence of groups ({{model-group}}). It is the entity
against which a consumer issues a subscription request.  A subscriber
can request to receive individual tracks starting at a group boundary,
including any new objects pushed by the producer while the track is
active.

### Track Naming and Scopes {#track-name}

In MOQT, every track has a track name and a track namespace associated
with it.  A track name identifies an individual track within the
namespace.

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

In this specification, both the Track Namespace and the Track Name are
not constrained to a specific encoding. They carry a sequence of
bytes and comparison between two Track Namespaces or Track Names is
done by exact comparison of the bytes. Specifications that use MoQ Transport
may constrain the information in these fields, for example by restricting
them to UTF-8. Any specification that does needs to specify the
canonicalization into the bytes in the Track Namespace or Track Name
such that exact comparison works.

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
URI with a "moq" scheme.  The "moq" URI scheme is defined as follows,
using definitions from {{!RFC3986}}:

~~~~~~~~~~~~~~~
moq-URI = "moqt" "://" authority path-abempty [ "?" query ]
~~~~~~~~~~~~~~~

The `authority` portion MUST NOT contain a non-empty `host` portion.
The `moq` URI scheme supports the `/.well-known/` path prefix defined in
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
the peers exchange Setup messages ({{message-setup}}).  All messages defined in
this draft except OBJECT and OBJECT_WITH_LENGTH are sent on the control stream
after the Setup message. Control messages MUST NOT be sent on any other stream,
and a peer receiving a control message on a different stream closes the session
as a 'Protocol Violation'. Objects MUST NOT be sent on the control stream, and a
peer receiving an Object on the control stream closes the session as a 'Protocol
Violation'.

This draft only specifies a single use of bidirectional streams. Objects are
sent on unidirectional streams.  Because there are no other uses of
bidirectional streams, a peer MAY currently close the session as a
'Protocol Violation' if it receives a second bidirectional stream.

The control stream MUST NOT be abruptly closed at the underlying transport
layer.  Doing so results in the session being closed as a 'Protocol Violation'.

## Stream Cancellation

Streams aside from the control stream MAY be canceled due to congestion
or other reasons by either the sender or receiver. Early termination of a
stream does not affect the MoQ application state, and therefore has no
effect on outstanding subscriptions.

## Termination  {#session-termination}

The transport session can be terminated at any point.  When native QUIC
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

* GOAWAY Timeout: The session was closed because the client took too long to
  close the session in response to a GOAWAY ({{message-goaway}}) message.
  See session migration ({{session-migration}}).

## Migration {#session-migration}

MoqTransport requires a long-lived and stateful session. However, a service
provider needs the ability to shutdown/restart a server without waiting for all
sessions to drain naturally, as that can take days for long-form media.
MoqTransport avoids this via the GOAWAY message ({{message-goaway}}).

The server sends a GOAWAY message, signaling that the client should establish a
new session and migrate any active subscriptions. The GOAWAY message may contain
a new URI for the new session, otherwise the current URI is reused. The server
SHOULD terminate the session with 'GOAWAY Timeout' after a sufficient timeout if
there are still open subscriptions on a connection.

The GOAWAY message does not immediately impact subscription state. A subscriber
SHOULD individually UNSUBSCRIBE for each existing subscription, while a
publisher MAY reject new SUBSCRIBEs while in the draining state. When the server
is a subscriber, it SHOULD send a GOAWAY message prior to any UNSUBSCRIBE
messages.

After the client receives a GOAWAY, it's RECOMMENDED that the client waits until
there are no more active subscriptions before closing the session with NO_ERROR.
Ideally this is transparent to the application using MOQT, which involves
establishing a new session in the background and migrating active subscriptions
and announcements. The client can choose to delay closing the session if it
expects more OBJECTs to be delivered. The server closes the session with a
'GOAWAY Timeout' if the client doesn't close the session quickly enough.


# Prioritization and Congestion Response {#priority-congestion}

TODO: This is a placeholder section to capture details on how the MOQT
protocol deals with prioritization and congestion overall.

This section is expected to cover details on:

- Prioritization Schemes.
- Congestion Algorithms and impacts.
- Mapping considerations for one object per stream vs multiple objects
  per stream.
- Considerations for merging multiple streams across domains onto single
  connection and interactions with specific prioritization schemes.

## Order Priorities and Options

At the point of this writing, the working group has not reached
consensus on several important goals, such as:

* Ensuring that objects are delivered in the order intended by the
  emitter
* Allowing nodes and relays to skip or delay some objects to deal with
  congestion
* Ensuring that emitters can accurately predict the behavior of relays
* Ensuring that when relays have to skip and delay objects belonging to
  different tracks that they do it in a predictable way if tracks are
  explicitly coordinated and in a fair way if they are not.

The working group has been considering two alternatives: marking objects
belonging to a track with an explicit "send order"; and, defining
algorithms combining tracks, priorities and object order within a
group. The two proposals are listed in {{send-order}} and
{{ordering-by-priorities}}.  We expect further work before a consensus
is reached.

### Proposal - Send Order {#send-order}

Media is produced with an intended order, both in terms of when media
should be presented (PTS) and when media should be decoded (DTS).  As
stated in the introduction, the network is unable to maintain this
ordering during congestion without increasing latency.

The encoder determines how to behave during congestion by assigning each
object a numeric send order.  The send order SHOULD be followed when
possible, to ensure that the most important media is delivered when
throughput is limited.  Note that the contents within each object are
still delivered in order; this send order only applies to the ordering
between objects.

A sender MUST send each object over a dedicated stream.  The library
should support prioritization ({{priority-congestion}}) such that
streams are transmitted in send order.

A receiver MUST NOT assume that objects will be received in send order,
for the following reasons:

* Newly encoded objects can have a smaller send order than outstanding
  objects.
* Packet loss or flow control can delay the send of individual streams.
* The sender might not support stream prioritization.

TODO: Refer to Congestion Response and Prioritization Section for
further details on various proposals.

### Proposal - Ordering by Priorities {#ordering-by-priorities}

Media is produced as a set of layers, such as for example low definition
and high definition, or low frame rate and high frame rate. Each object
belonging to a track and a group has two attributes: the object-id, and
the priority (or layer).

When nodes or relays have to choose which object to send next, they
apply the following rules:

* within the same group, objects with a lower priority number (e.g. P1)
  are always sent before objects with a numerically greater priority
  number (e.g., P2)
* within the same group, and the same priority level, objects with a
  lower object-id are always sent before objects with a higher
  object-id.
* objects from later groups are normally always sent before objects of
  previous groups.

The latter rule is generally agreed as a way to ensure freshness, and to
recover quickly if queues and delays accumulate during a congestion
period. However, there may be cases when finishing the transmission of
an ongoing group results in better user experience than strict adherence
to the freshness rule. We expect that that the working group will
eventually reach consensus and define meta data that controls this
behavior.

There have been proposals to allow emitters to coordinate the allocation
of layer priorities across multiple coordinated tracks. At this point,
these proposals have not reached consensus.


# Relays {#relays-moq}

Relays are leveraged to enable distribution scale in the MoQ
architecture. Relays can be used to form an overlay delivery network,
similar in functionality to Content Delivery Networks
(CDNs). Additionally, relays serve as policy enforcement points by
validating subscribe and publish requests at the edge of a network.

## Subscriber Interactions

Subscribers interact with the Relays by sending a SUBSCRIBE
({{message-subscribe-req}}) control message for the tracks of
interest. Relays MUST ensure subscribers are authorized to access the
content associated with the track. The authorization
information can be part of subscription request itself or part of the
encompassing session. The specifics of how a relay authorizes a user are
outside the scope of this specification.

The subscriber making the subscribe request is notified of the result of
the subscription, via SUBSCRIBE_OK ({{message-subscribe-ok}}) or the
SUBSCRIBE_ERROR {{message-subscribe-error}} control message.
The entity receiving the SUBSCRIBE MUST send only a single response to
a given SUBSCRIBE of either SUBSCRIBE_OK or SUBSCRIBE_ERROR.

For successful subscriptions, the publisher maintains a list of
subscribers for each track. Each new OBJECT belonging to the
track within the subscription range is forwarded to each active
subscriber, dependent on the congestion response. A subscription
remains active until the publisher of the track terminates the
track with a SUBSCRIBE_DONE (see {{message-subscribe-done}}).

Objects MUST NOT be sent for unsuccessful subscriptions, and if a subscriber
receives a SUBSCRIBE_ERROR after receiving objects, it MUST close the session
with a 'Protocol Violation'.

A relay MUST not reorder or drop objects received on a multi-object stream when
forwarding to subscribers, unless it has application specific information.

Relays MAY aggregate authorized subscriptions for a given track when
multiple subscribers request the same track. Subscription aggregation
allows relays to make only a single forward subscription for the
track. The published content received from the forward subscription
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

## Publisher Interactions

Publishing through the relay starts with publisher sending ANNOUNCE
control message with a `Track Namespace` ({{model-track}}).

Relays MUST ensure that publishers are authorized by:

- Verifying that the publisher is authorized to publish the content
  associated with the set of tracks whose Track Namespace matches the
  announced namespace. Specifics of where the authorization happens,
  either at the relays or forwarded for further processing, depends on
  the way the relay is managed and is application specific (typically
  based on prior business agreement).

Relays respond with an ANNOUNCE_OK or ANNOUNCE_ERROR control message
providing the result of announcement. The entity receiving the
ANNOUNCE MUST send only a single response to a given ANNOUNCE of
either ANNOUNCE_OK or ANNOUNCE_ERROR.  When a publisher wants to stop
new subscriptions for an announced namespace it sends an UNANNOUNCE.
A subscriber indicates it will no longer route subscriptions for a
namespace it previously responded ANNOUNCE_OK to by sending an
ANNOUNCE_CANCEL.

A relay manages sessions from multiple publishers and subscribers,
connecting them based on the track namespace. This MUST use an exact
match on track namespace unless otherwise negotiated by the application.
For example, a SUBSCRIBE namespace=foobar message will be forwarded to
the session that sent ANNOUNCE namespace=foobar.

OBJECT message headers carry a short hop-by-hop `Track Alias` that maps to
the Full Track Name (see {{message-subscribe-ok}}). Relays use the
`Track Alias` of an incoming OBJECT message to identify its track and find
the active subscribers for that track. Relays MUST NOT depend on OBJECT
payload content for making forwarding decisions and MUST only depend on the
fields, such as priority order and other metadata properties in the
OBJECT message header. Unless determined by congestion response, Relays
MUST forward the OBJECT message to the matching subscribers.

## Congestion Response at Relays

TODO: Refer to {{priority-congestion}}. Add details to describe relay
behavior when merging or splitting streams and interactions with
congestion response.

## Relay Object Handling

MOQT encodes the delivery information for a stream via OBJECT headers
({{message-object}}).  A relay MUST NOT modify Object properties when
forwarding.

A relay MUST treat the object payload as opaque.  A relay MUST NOT
combine, split, or otherwise modify object payloads.  A relay SHOULD
prioritize streams ({{priority-congestion}}) based on the send
order/priority.

A sender SHOULD begin sending incomplete objects when available to
avoid incurring additional latency.

A relay that reads from a stream and writes to stream in order will
introduce head-of-line blocking.  Packet loss will cause stream data to
be buffered in the library, awaiting in order delivery, which will
increase latency over additional hops.  To mitigate this, a relay SHOULD
read and write stream data out of order subject to flow control
limits.  See section 2.2 in {{QUIC}}.

# Messages {#message}

Unidirectional streams and datagrams contain Objects and all other
messages are sent on a bidirectional stream.

An endpoint that receives an unknown message type MUST close the session.

~~~
MOQT Message {
  Message Type (i),
  Message Payload (..),
}
~~~
{: #moq-transport-message-format title="MOQT Message"}

|-------|-----------------------------------------------------|
| ID    | Messages                                            |
|------:|:----------------------------------------------------|
| 0x0   | OBJECT_STREAM ({{object-message-formats}})          |
|-------|-----------------------------------------------------|
| 0x1   | OBJECT_DATAGRAM ({{object-message-formats}}) |
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
| 0x40  | CLIENT_SETUP ({{message-setup}})                    |
|-------|-----------------------------------------------------|
| 0x41  | SERVER_SETUP ({{message-setup}})                    |
|-------|-----------------------------------------------------|
| 0x50  | STREAM_HEADER_TRACK ({{multi-object-streams}})      |
|-------|-----------------------------------------------------|
| 0x51  | STREAM_HEADER_GROUP ({{multi-object-streams}})      |
|-------|-----------------------------------------------------|

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
implied by that type does not match the Parameter Length field, the receiver MUST
terminate the session with error code 'Parameter Length Mismatch'.

### Version Specific Parameters {#version-specific-params}

Each version-specific parameter definition indicates the message types in which
it can appear. If it appears in some other type of message, it MUST be ignored.
Note that since Setup parameters use a separate namespace, it is impossible for
these parameters to appear in Setup messages.

#### AUTHORIZATION INFO Parameter {#authorization-info}

AUTHORIZATION INFO parameter (key 0x02) identifies a track's authorization
information in a SUBSCRIBE or ANNOUNCE message. This parameter is populated for
cases where the authorization is required at the track level. The value is an
ASCII string.

## CLIENT_SETUP and SERVER_SETUP {#message-setup}

The `CLIENT_SETUP` and `SERVER_SETUP` messages are the first messages exchanged
by the client and the server; they allows the peers to establish the mutually
supported version and agree on the initial configuration before any objects are
exchanged. It is a sequence of key-value pairs called Setup parameters; the
semantics and format of which can vary based on whether the client or server is
sending.  To ensure future extensibility of MOQT, the peers MUST ignore unknown
setup parameters. TODO: describe GREASE for those.

The wire format of the Setup messages are as follows:

~~~
CLIENT_SETUP Message Payload {
  Number of Supported Versions (i),
  Supported Version (i) ...,
  Number of Parameters (i) ...,
  Setup Parameters (..) ...,
}

SERVER_SETUP Message Payload {
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

#### ROLE parameter {#role}

The ROLE parameter (key 0x00) allows each endpoint to independently specify what
functionality they support for the session. It has three possible values,
which are of type varint:

0x01: Publisher

: The endpoint can process subscriptions and send objects, but not subscribe.
  The endpoint MUST NOT send a SUBSCRIBE message and an ANNOUNCE MUST NOT be
  sent to it.

0x02: Subscriber

: The endpoint can send subscriptions and receive objects, but not publish.
  The endpoint MUST NOT send an ANNOUNCE message and a SUBSCRIBE MUST NOT be
  sent to it.

0x03: PubSub

: The endpoint can act as a publisher or subscriber, and can send or process
  any message type.

Both endpoints MUST send a ROLE parameter with one of the three values
specified above. Both endpoints MUST close the session if the ROLE
parameter is missing or is not one of the three above-specified values.

#### PATH parameter {#path}

The PATH parameter (key 0x01) allows the client to specify the path of
the MoQ URI when using native QUIC ({{QUIC}}).  It MUST NOT be used by
the server, or when WebTransport is used.  If the peer receives a PATH
parameter from the server, or when WebTransport is used, it MUST close
the connection. It follows the URI formatting rules {{!RFC3986}}.

When connecting to a server using a URI with the "moq" scheme, the
client MUST set the PATH parameter to the `path-abempty` portion of the
URI; if `query` is present, the client MUST concatenate `?`, followed by
the `query` portion of the URI to the parameter.

## GOAWAY {#message-goaway}
The server sends a `GOAWAY` message to initiate session migration
({{session-migration}}) with an optional URI.

The server MUST terminate the session with a Protocol Violation
({{session-termination}}) if it receives a GOAWAY message. The client MUST
terminate the session with a Protocol Violation ({{session-termination}}) if it
receives multiple GOAWAY messages.

~~~
GOAWAY Message {
  New Session URI (b)
}
~~~
{: #moq-transport-goaway-format title="MOQT GOAWAY Message"}

* New Session URI: The client MUST use this URI for the new session if provided.
  If the URI is zero bytes long, the current URI is reused instead. The new
  session URI SHOULD use the same scheme as the current URL to ensure
  compatibility.



## SUBSCRIBE {#message-subscribe-req}

### Filter Types {#sub-filter}

The subscriber specifies a filter on the subscription to allow
the publisher to identify which objects need to be delivered.

There are 4 types of filters:

Latest Group (0x1) : Specifies an open-ended subscription with objects
from the beginning of the current group.

Latest Object (0x2): Specifies an open-ended subscription beginning from
the current object of the current group.

AbsoluteStart (0x3):  Specifies an open-ended subscription beginning
from the object identified in the StartGroup and StartObject fields.

AbsoluteRange (0x4):  Specifies a closed subscription starting at StartObject
in StartGroup and ending at EndObject in EndGroup.  The start and end of the
range are inclusive.  EndGroup and EndObject MUST specify the same or a later
object than StartGroup and StartObject.

A filter type other than the above MUST be treated as error.


### SUBSCRIBE Format
A receiver issues a SUBSCRIBE to a publisher to request a track.

The format of SUBSCRIBE is as follows:

~~~
SUBSCRIBE Message {
  Subscribe ID (i),
  Track Alias (i),
  Track Namespace (b),
  Track Name (b),
  Filter Type (i),
  [StartGroup (i),
   StartObject (i)],
  [EndGroup (i),
   EndObject (i)],
  Number of Parameters (i),
  Track Request Parameters (..) ...
}
~~~
{: #moq-transport-subscribe-format title="MOQT SUBSCRIBE Message"}

* Subscribe ID: The subscription identifier that is unique within the session.
`Subscribe ID` is a monotonically increasing variable length integer which
MUST not be reused within a session. `Subscribe ID` is used by subscribers and
the publishers to identify a given subscription. Subscribers specify the
`Subscribe ID` and it is included in the corresponding SUBSCRIBE_OK or
SUBSCRIBE_ERROR messages.

* Track Alias: A session specific identifier for the track.
Messages that reference a track, such as OBJECT ({{message-object}}),
reference this Track Alias instead of the Track Name and Track Namespace to
reduce overhead. If the Track Alias is already in use, the publisher MUST
close the session with a Duplicate Track Alias error ({{session-termination}}).

* Track Namespace: Identifies the namespace of the track as defined in
({{track-name}}).

* Track Name: Identifies the track name as defined in ({{track-name}}).

* Filter Type: Identifies the type of filter, which also indicates whether
the StartGroup/StartObject and EndGroup/EndObject fields will be present.
See ({{sub-filter}}).

* StartGroup: The start Group ID. Only present for "AbsoluteStart" and
"AbsoluteRange" filter types.

* StartObject: The start Object ID, plus 1. A value of 0 means the entire group is
requested. Only present for "AbsoluteStart" and "AbsoluteRange" filter types.

* EndGroup: The end Group ID. Only present for the "AbsoluteRange" filter type.

* EndObject: The end Object ID, plus 1. A value of 0 means the entire group is
requested. Only present for the "AbsoluteRange" filter type.

* Track Request Parameters: The parameters are defined in
{{version-specific-params}}

On successful subscription, the publisher MUST reply with a SUBSCRIBE_OK,
allowing the subscriber to determine the start group/object when not explicitly
specified and the publisher SHOULD start delivering objects.

If a publisher cannot satisfy the requested start or end for the subscription it
MAY send a SUBSCRIBE_ERROR with code 'Invalid Range'. A publisher MUST NOT send
objects from outside the requested start and end.

## SUBSCRIBE_UPDATE {#message-subscribe-update-req}

A receiver issues a SUBSCRIBE_UPDATE to a publisher to request a change to
a prior subscription.  Subscriptions can only become more narrower, not wider,
because an attempt to widen a subscription could fail.  If Objects before the
start or after the end of the current subscription are needed, a separate
subscription can be made. The start Object MUST NOT decrease and when it increases,
there is no guarantee that a publisher will not have already sent Objects before
the new start Object.  The end Object MUST NOT increase and when it decreases,
there is no guarantee that a publisher will not have already sent Objects after
the new end Object.

Unlike a new subscription, SUBSCRIBE_UPDATE can not cause an Object to be
delivered multiple times.  Like SUBSCRIBE, EndGroup and EndObject MUST specify the
same or a later object than StartGroup and StartObject.

The format of SUBSCRIBE_UPDATE is as follows:

~~~
SUBSCRIBE_UPDATE Message {
  Subscribe ID (i),
  StartGroup (i),
  StartObject (i),
  EndGroup (i),
  EndObject (i),
  Number of Parameters (i),
  Track Request Parameters (..) ...
}
~~~
{: #moq-transport-subscribe-update-format title="MOQT SUBSCRIBE_UPDATE Message"}

* Subscribe ID: The subscription identifier that is unique within the session.
This MUST match an existing Subscribe ID.

* StartGroup: The start Group ID.

* StartObject: The start Object ID, plus 1. A value of 0 means the entire group
is requested.

* EndGroup: The end Group ID, plus 1.  A value of 0 means the subscription is
open-ended.

* EndObject: The end Object ID, plus 1. A value of 0 means the entire group is
requested.

* Track Request Parameters: The parameters are defined in
{{version-specific-params}}

## UNSUBSCRIBE {#message-unsubscribe}

A subscriber issues a `UNSUBSCRIBE` message to a publisher indicating it is no
longer interested in receiving media for the specified track and Objects
should stop being sent as soon as possible.  The publisher sends a
SUBSCRIBE_DONE to acknowledge the unsubscribe was successful and indicate
the final Object.

The format of `UNSUBSCRIBE` is as follows:

~~~
UNSUBSCRIBE Message {
  Subscribe ID (i)
}
~~~
{: #moq-transport-unsubscribe-format title="MOQT UNSUBSCRIBE Message"}

* Subscribe ID: Subscription Identifier as defined in {{message-subscribe-req}}.

## ANNOUNCE_OK {#message-announce-ok}

The subscriber sends an ANNOUNCE_OK control message to acknowledge the
successful authorization and acceptance of an ANNOUNCE message.

~~~
ANNOUNCE_OK
{
  Track Namespace (b),
}
~~~
{: #moq-transport-announce-ok format title="MOQT ANNOUNCE_OK Message"}

* Track Namespace: Identifies the track namespace in the ANNOUNCE
message for which this response is provided.

## ANNOUNCE_ERROR {#message-announce-error}

The subscriber sends an ANNOUNCE_ERROR control message for tracks that
failed authorization.

~~~
ANNOUNCE_ERROR
{
  Track Namespace (b),
  Error Code (i),
  Reason Phrase (b),
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
  Track Namespace (b),
}
~~~
{: #moq-transport-announce-cancel-format title="MOQT ANNOUNCE_CANCEL Message"}

* Track Namespace: Identifies a track's namespace as defined in
({{track-name}}).

## TRACK_STATUS_REQUEST {#message-track-status-req}

A potential subscriber sends a 'TRACK_STATUS_REQUEST' message on the control
stream to obtain information about the current status of a given track.

A TRACK_STATUS message MUST be sent in response to each TRACK_STATUS_REQUEST.

~~~
TRACK_STATUS_REQUEST Message {
  Track Namespace (b),
  Track Name (b),
}
~~~
{: #moq-track-status-request-format title="MOQT TRACK_STATUS_REQUEST Message"}



## OBJECT {#message-object}

An OBJECT message contains a range of contiguous bytes from from the
specified track, as well as associated metadata required to deliver,
cache, and forward it.  Objects are sent by publishers.

### Canonical Object Fields

A canonical MoQ Object has the following information:

* Track Namespace and Track Name: The track this object belongs to.

* Group ID: The object is a member of the indicated group ID
{{model-group}} within the track.

* Object ID: The order of the object within the group.  The
IDs starts at 0, increasing sequentially for each object within the
group.

* Object Send Order: An integer indicating the object send order
{{send-order}} or priority {{ordering-by-priorities}} value.

* Object Forwarding Preference: An enumeration indicating how a sender sends an
object. The preferences are Track, Group, Object and Datagram.  An Object MUST
be sent according to its `Object Forwarding Preference`, described below.

* Object Status: As enumeration used to indicate missing
objects or mark the end of a group or track. See {{object-status}} below.

* Object Payload: An opaque payload intended for the consumer and SHOULD
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

* 0x2 := Indicates Group does not exist. Indicates that objects with
         this GroupID do not exist at any publisher and they will not be
         published in the future. This SHOULD be cached.

* 0x3 := Indicates end of Group. ObjectId is one greater that the
         largest object produced in the group identified by the
         GroupID. This is sent right after the last object in the
         group. This SHOULD be cached.

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

In most cases, messages with a non zero status code are sent on the same
stream that an object with that GroupID would have been sent on. The
exception to this is when that stream has been reset; in that case they
are sent on a new stream. This is to avoid the status message being lost
in cases such as a relay dropping a group and reseting the stream the
group is being sent on.

### Object Message Formats

Every Track has a single 'Object Forwarding Preference' and publishers
MUST NOT mix different forwarding preferences within a single track.
If a subscriber receives different forwarding preferences for a track, it
SHOULD close the session with an error of 'Protocol Violation'.

**Object Stream Message**

An `OBJECT_STREAM` message carries a single object on a stream.  There is no
explicit length of the payload; it is determined by the end of the stream.  An
`OBJECT_STREAM` message MUST be the first and only message on a unidirectional
stream.

An Object received in an `OBJECT_STREAM` message has an `Object Forwarding
Preference` = `Object`.

To send an Object with `Object Forwarding Preference` = `Object`, open a stream,
serialize object fields below, and terminate the stream.

~~~
OBJECT_STREAM Message {
  Subscribe ID (i),
  Track Alias (i),
  Group ID (i),
  Object ID (i),
  Object Send Order (i),
  Object Status (i),
  Object Payload (..),
}
~~~
{: #moq-transport-object-stream-format title="MOQT OBJECT_STREAM Message"}

* Subscribe ID: Subscription Identifier as defined in {{message-subscribe-req}}.

* Track Alias: Identifies the Track Namespace and Track Name as defined in
{{message-subscribe-req}}.

If the Track Namespace and Track Name identified by the Track Alias are
different from those specified in the subscription identified by Subscribe ID,
the receiver MUST close the session with a Protocol Violation.

* Other fields: As described in {{canonical-object-fields}}.

**Object Datagram Message**

An `OBJECT_DATAGRAM` message carries a single object in a datagram.
There is no explicit length of the payload; it is determined by the
length of the datagram.

An Object received in an `OBJECT_DATAGRAM` message has an `Object
Forwarding Preference` = `Datagram`. To send an Object with `Object
Forwarding Preference` = `Datagram`, determine the length of the fields and
payload and send the Object as datagram. In certain scenarios where the object
size can be larger than maximum datagram size for the session, the Object
will be dropped.

~~~
OBJECT_DATAGRAM Message {
  Subscribe ID (i),
  Track Alias (i),
  Group ID (i),
  Object ID (i),
  Object Send Order (i),
  Object Status (i),
  Object Payload (..),
}
~~~
{: #object-datagram-format title="MOQT OBJECT_DATAGRAM Message"}

### Multi-Object Streams

When multiple objects are sent on a stream, the stream begins with a stream
header message and is followed by one or more sets of serialized object fields.
If a stream ends gracefully in the middle of a serialized Object, terminate the
session with a Protocol Violation.

A sender SHOULD NOT open more than one multi-object stream at a time with the
same stream header message type and fields.


TODO: figure out how a relay closes these streams

**Stream Header Track**

When a stream begins with `STREAM_HEADER_TRACK`, all objects on the stream
belong to the track requested in the Subscribe message identified by `Subscribe
ID`.  All objects on the stream have the `Object Send Order` specified in the
stream header.


~~~
STREAM_HEADER_TRACK Message {
  Subscribe ID (i)
  Track Alias (i),
  Object Send Order (i),
}
~~~
{: #stream-header-track-format title="MOQT STREAM_HEADER_TRACK Message"}

All Objects received on a stream opened with STREAM_HEADER_TRACK have an `Object
Forwarding Preference` = `Track`.

To send an Object with `Object Forwarding Preference` = `Track`, find the open
stream that is associated with the subscription, or open a new one and send the
`STREAM_HEADER_TRACK` if needed, then serialize the following object fields.
The Object Status field is only sent if the Object Payload Length is zero.

~~~
{
  Group ID (i),
  Object ID (i),
  Object Payload Length (i),
  [Object Status (i)],
  Object Payload (..),
}
~~~
{: #object-track-format title="MOQT Track Stream Object Fields"}

**Stream Header Group**

A sender MUST NOT send an Object on a stream if its Group ID is less than a
previously sent Group ID on that stream, or if its Object ID is less than or
equal to a previously sent Object ID within a given group on that stream.

When a stream begins with `STREAM_HEADER_GROUP`, all objects on the stream
belong to the track requested in the Subscribe message identified by `Subscribe
ID` and the group indicated by `Group ID`.  All objects on the stream
have the `Object Send Order` specified in the stream header.

~~~
STREAM_HEADER_GROUP Message {
  Subscribe ID (i),
  Track Alias (i),
  Group ID (i)
  Object Send Order (i)
}
~~~
{: #stream-header-group-format title="MOQT STREAM_HEADER_GROUP Message"}

All Objects received on a stream opened with `STREAM_HEADER_GROUP` have an
`Object Forwarding Preference` = `Group`.

To send an Object with `Object Forwarding Preference` = `Group`, find the open
stream that is associated with the subscription, `Group ID` and `Object
Send Order`, or open a new one and send the `STREAM_HEADER_GROUP` if needed,
then serialize the following fields.
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

A sender MUST NOT send an Object on a stream if its Object ID is less than a
previously sent Object ID within a given group in that stream.

### Examples:

Sending a track on one stream:

~~~
STREAM_HEADER_TRACK {
  Subscribe ID = 1
  Track Alias = 1
  Object Send Order = 0
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

Sending a group on one stream, with a unordered object in the group appearing
on its own stream.

~~~
Stream = 2

STREAM_HEADER_GROUP {
  Subscribe ID = 2
  Track Alias = 2
  Group ID = 0
  Object Send Order = 0
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

Stream = 6

OBJECT_STREAM {
  Subscribe ID = 2
  Track Alias = 2
  Group ID = 0
  Object ID = 1
  Payload = "moqrocks"
}
~~~


## SUBSCRIBE_OK {#message-subscribe-ok}

A publisher sends a SUBSCRIBE_OK control message for successful
subscriptions.

~~~
SUBSCRIBE_OK
{
  Subscribe ID (i),
  Expires (i),
  ContentExists (f),
  [Largest Group ID (i)],
  [Largest Object ID (i)],
  Number of Subscription Parameters (i),
  Subscription Parameters (..) ...
}
~~~
{: #moq-transport-subscribe-ok format title="MOQT SUBSCRIBE_OK Message"}

* Subscribe ID: Subscription Identifier as defined in {{message-subscribe-req}}.

* Expires: Time in milliseconds after which the subscription is no
longer valid. A value of 0 indicates that the subscription does not expire
or expires at an unknown time.  Expires is advisory and a subscription can
end prior to the expiry time or last longer.

* ContentExists: 1 if an object has been published on this track, 0 if not.
If 0, then the Largest Group ID and Largest Object ID fields will not be
present.

* Largest Group ID: the largest Group ID available for this track. This field
is only present if ContentExists has a value of 1.

* Largest Object ID: the largest Object ID available within the largest Group ID
for this track. This field is only present if ContentExists has a value of 1.

* Subscription Parameters: optional key-value pairs formatted as described in {{params}}.

### Subscription Paramteres  {#subscription-parameters}

SUBSCRIBE_OK may contain zero or more parameters describing either the
properties of the track, or the properties of an individual subscription.

The following properties are defined in this document:

* AVAILABILITY_LIMIT_ABSOLUTE: an integer expressing an absolute time in the
  number of seconds since 1970-01-01T00:00Z in UTC.  If present, the relay MUST
  NOT start forwarding any objects received through this subscription after the
  time point specified by this parameter is in the past.
* AVAILABILITY_LIMIT_RELATIVE: an integer expressing a number of seconds.  If
  present, the relay MUST NOT start forwarding any individual object received
  through this subscription after the specified number of seconds has elapsed
  since the object in question has been fully received.

If both AVAILABILITY_LIMIT_ABSOLUTE and AVAILABILITY_LIMIT_RELATIVE are
specified, both of those limitations apply.

## SUBSCRIBE_ERROR {#message-subscribe-error}

A publisher sends a SUBSCRIBE_ERROR control message in response to a
failed SUBSCRIBE.

~~~
SUBSCRIBE_ERROR
{
  Subscribe ID (i),
  Error Code (i),
  Reason Phrase (b),
  Track Alias (i),
}
~~~
{: #moq-transport-subscribe-error format title="MOQT SUBSCRIBE_ERROR Message"}

* Subscribe ID: Subscription Identifier as defined in {{message-subscribe-req}}.

* Error Code: Identifies an integer error code for subscription failure.

* Reason Phrase: Provides the reason for subscription error.

* Track Alias: When Error Code is 'Retry Track Alias', the subscriber SHOULD re-issue the
  SUBSCRIBE with this Track Alias instead. If this Track Alias is already in use,
  the receiver MUST close the connection with a Duplicate Track Alias error
  ({{session-termination}}).


## SUBSCRIBE_DONE {#message-subscribe-done}

A publisher sends a `SUBSCRIBE_DONE` message to indicate it is done publishing
Objects for that subscription.  The Status Code indicates why the subscription ended,
and whether it was an error.

The format of `SUBSCRIBE_DONE` is as follows:

~~~
SUBSCRIBE_DONE Message {
  Subscribe ID (i),
  Status Code (i),
  Reason Phrase (b),
  ContentExists (f),
  [Final Group (i)],
  [Final Object (i)],
}
~~~
{: #moq-transport-subscribe-fin-format title="MOQT SUBSCRIBE_DONE Message"}

* Subscribe ID: Subscription identifier as defined in {{message-subscribe-req}}.

* Status Code: An integer status code indicating why the subscription ended.

* Reason Phrase: Provides the reason for subscription error.

* ContentExists: 1 if an object has been published for this subscription, 0 if
not. If 0, then the Final Group and Final Object fields will not be present.

* Final Group: The largest Group ID sent by the publisher in an OBJECT
message in this track.

* Final Object: The largest Object ID sent by the publisher in an OBJECT
message in the `Final Group` for this track.

## ANNOUNCE {#message-announce}

The publisher sends the ANNOUNCE control message to advertise where the
receiver can route SUBSCRIBEs for tracks within the announced
Track Namespace. The receiver verifies the publisher is authorized to
publish tracks under this namespace.

~~~
ANNOUNCE Message {
  Track Namespace (b),
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
  Track Namespace (b),
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
  Track Namespace (b),
  Track Name (b),
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

0x04: The sender is a relay that cannot obtain the current track status from
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

The producer prioritizes and transmits streams out of order.  Streams
might be starved indefinitely during congestion.  The producer and
consumer MUST cancel a stream, preferably the lowest priority, after
reaching a resource limit.


# IANA Considerations {#iana}

TODO: fill out currently missing registries:

* MOQT version numbers
* Setup parameters
* Track Request parameters
* Subscribe Error codes
* Announce Error codes
* Track format numbers
* Message types
* Object headers

TODO: register the URI scheme and the ALPN

TODO: the MOQT spec should establish the IANA registration table for MoQ
Streaming Formats. Each MoQ streaming format can then register its type
in that table. The MoQ Streaming Format type MUST be carried as the
leading varint in catalog track objects.


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
