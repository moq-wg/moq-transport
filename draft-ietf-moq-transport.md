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
    organization: Twitch
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

This document also defines an additional field type for binary data:

x (b):
: Indicates that x consists of a variable length integer, followed by
  that many bytes of binary data.


# Object Model {#model}

MOQT has a hierarchical object model for data, comprised of objects,
groups and tracks.

## Objects {#model-object}

The basic data element of MOQT is an object.  An object is an
addressable unit whose payload is a sequence of bytes.  All objects
belong to a group, indicating ordering and potential
dependencies. {{model-group}} Objects are comprised of two parts:
metadata and a payload.  The metadata is never encrypted and is always
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

A tuple of a track name and a track namespace together is known as a
full track name:

~~~~~~~~~~~~~~~
Full Track Name = Track Namespace Track Name
~~~~~~~~~~~~~~~

A MOQT scope is a set of servers (as identified by their connection
URIs) for which full track names are guaranteed to be unique.  This
implies that within a single MOQT scope, subscribing to the same full
track name would result in the subscriber receiving the data for the
same track.  It is up to the application using MOQT to define how broad
or narrow the scope has to be.  An application that deals with
connections between devices on a local network may limit the scope to a
single connection; by contrast, an application that uses multiple CDNs
to serve media may require the scope to include all of those CDNs.

The full track name is the only piece of information that is used to
identify the track within a given MOQT scope and is used as cache key.
MOQT does not provide any in-band content negotiation methods similar to
the ones defined by HTTP ({{?RFC9110, Section 10}}); if, at a given
moment in time, two tracks within the same scope contain different data,
they have to have different full track names.

~~~
Example: 1
Track Namespace = live.example.com/meeting/123/member/alice/
Track Name = audio
Full Track Name = live.example.com/meeting/123/member/alice/audio

Example: 2
Track Namespace = live.example.com/
Track Name = uaCafDkl123/audio
Full Track Name = live.example.com/uaCafDkl123/audio

Example: 3
Track Namespace = security-camera.example.com/camera1/
Track Name = hd-video
Full Track Name = security-camera.example.com/camera1/hd-video

~~~


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
connection is established.  There is no definition of the protocol
over other transports, such as TCP, and applicaitons using MoQ might
need to fallback to another protocol when QUIC or WebTransport aren't
available.

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
moq-URI = "moq" "://" authority path-abempty [ "?" query ]
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

Endpoints use the exchange of SETUP messages to negotiate the MOQT version and
any extensions to use.

The client indicates the MOQT versions it supports in the CLIENT_SETUP message
(see {{message-setup}}). It also includes the union of all Setup Parameters
{{setup-params}} required for a handshake by any of those versions.

Within any MOQT version, clients request the use of extensions by adding SETUP
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
separate SETUP parameters for that information in each version.

## Session initialization {#session-init}

The first stream opened is a client-initiated bidirectional control stream
where the peers exchange SETUP messages ({{message-setup}}).  All messages
defined in this draft are sent on the control stream after the SETUP message.
Control messages MUST NOT be sent on any other stream, and a peer receiving
a control message on a different stream closes the session as a
'Protocol Violation'. Objects MUST NOT be sent on the control stream, and a
peer receiving an Object on the control stream closes the session as a
'Protocol Violation'.

This draft only specifies a single use of bidirectional streams. Objects are
sent on unidirectional streams.  Because there are no other uses of
bidirectional streams, a peer MAY currently close the connection if it
receives a second bidirectional stream.

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

|------|--------------------|
| Code | Reason             |
|-----:|:-------------------|
| 0x0  | No Error           |
|------|--------------------|
| 0x1  | Generic Error      |
|------|--------------------|
| 0x2  | Unauthorized       |
|------|--------------------|
| 0x3  | Protocol Violation |
|------|--------------------|
| 0x10 | GOAWAY Timeout     |
|------|--------------------|

* No Error: The session is being terminated without an error.

* Generic Error: An unclassified error occurred.

* Unauthorized: The endpoint breached an agreement, which MAY have been
pre-negotiated by the application.

* Protocol Violation: The remote endpoint performed an action that was
  disallowed by the specification.

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
content associated with the Full Track Name. The authorization
information can be part of subscription request itself or part of the
encompassing session. The specifics of how a relay authorizes a user are
outside the scope of this specification.

The subscriber making the subscribe request is notified of the result of
the subscription, via SUBSCRIBE_OK ({{message-subscribe-ok}}) or the
SUBSCRIBE_ERROR {{message-subscribe-error}} control message.
The entity receiving the SUBSCRIBE MUST send only a single response to
a given SUBSCRIBE of either SUBSCRIBE_OK or SUBSCRIBE_ERROR.

For successful subscriptions, the publisher maintains a list of
subscribers for each full track name. Each new OBJECT belonging to the
track is forwarded to each active subscriber, dependent on the
congestion response. A subscription remains active until it expires,
until the publisher of the track terminates the track with a SUBSCRIBE_FIN
(see {{message-subscribe-fin}}) or a SUBSCRIBE_RST
(see {{message-subscribe-rst}}).

Relays MAY aggregate authorized subscriptions for a given track when
multiple subscribers request the same track. Subscription aggregation
allows relays to make only a single forward subscription for the
track. The published content received from the forward subscription
request is cached and shared among the pending subscribers.


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
either ANNOUNCE_OK or ANNOUNCE_ERROR.

OBJECT message header carry short hop-by-hop Track Id that maps to the
Full Track Name (see {{message-subscribe-ok}}). Relays use the Track ID
of an incoming OBJECT message to identify its track and find the active
subscribers for that track. Relays MUST NOT depend on OBJECT payload
content for making forwarding decisions and MUST only depend on the
fields, such as priority order and other metadata properties in the
OBJECT message header. Unless determined by congestion response, Relays
MUST forward the OBJECT message to the matching subscribers.

## Relay Discovery and Failover

TODO: This section shall cover aspects of relay failover and protocol
interactions.

## Restoring connections through relays

TODO: This section shall cover reconnect considerations for clients when
moving between the Relays.

## Congestion Response at Relays

TODO: Refer to {{priority-congestion}}. Add details to describe relay
behavior when merging or splitting streams and interactions with
congestion response.

## Relay Object Handling

MOQT encodes the delivery information for a stream via OBJECT headers
({{message-object}}).

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

Both unidirectional and bidirectional streams contain sequences of
length-delimited messages.

An endpoint that receives an unknown message type MUST close the connection.

~~~
MOQT Message {
  Message Type (i),
  Message Payload (..),
}
~~~
{: #moq-transport-message-format title="MOQT Message"}

|-------|----------------------------------------------------|
| ID    | Messages                                           |
|------:|:---------------------------------------------------|
| 0x0   | OBJECT with payload length ({{message-object}})    |
|-------|----------------------------------------------------|
| 0x2   | OBJECT without payload length ({{message-object}}) |
|-------|----------------------------------------------------|
| 0x3   | SUBSCRIBE ({{message-subscribe-req}})      |
|-------|----------------------------------------------------|
| 0x4   | SUBSCRIBE_OK ({{message-subscribe-ok}})            |
|-------|----------------------------------------------------|
| 0x5   | SUBSCRIBE_ERROR ({{message-subscribe-error}})      |
|-------|----------------------------------------------------|
| 0x6   | ANNOUNCE  ({{message-announce}})                   |
|-------|----------------------------------------------------|
| 0x7   | ANNOUNCE_OK ({{message-announce-ok}})              |
|-------|----------------------------------------------------|
| 0x8   | ANNOUNCE_ERROR ({{message-announce-error}})        |
|-------|----------------------------------------------------|
| 0x9   | UNANNOUNCE  ({{message-unannounce}})               |
|-------|----------------------------------------------------|
| 0xA   | UNSUBSCRIBE ({{message-unsubscribe}})              |
|-------|----------------------------------------------------|
| 0xB   | SUBSCRIBE_FIN ({{message-subscribe-fin}})          |
|-------|----------------------------------------------------|
| 0xC   | SUBSCRIBE_RST ({{message-subscribe-rst}})          |
|-------|----------------------------------------------------|
| 0x10  | GOAWAY ({{message-goaway}})                        |
|-------|----------------------------------------------------|
| 0x40  | CLIENT_SETUP ({{message-setup}})                   |
|-------|----------------------------------------------------|
| 0x41  | SERVER_SETUP ({{message-setup}})                   |
|-------|----------------------------------------------------|

## Parameters {#params}

Some messages include a Parameters field that encode optional message
elements. They contain a type, length, and value.

Senders MUST NOT repeat the same parameter type in a message. Receivers
SHOULD check that there are no duplicate parameters and close the connection
if found.

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
parameter. SETUP message parameters use a namespace that is constant across all
MoQ Transport versions. All other messages use a version-specific namespace. For
example, the integer '1' can refer to different parameters for SETUP messages
and for all other message types.

SETUP message parameter types are defined in {{setup-params}}. Version-
specific parameter types are defined in {{version-specific-params}}.

The Parameter Length field of the String Parameter encodes the length
of the Parameter Value field in bytes.

Each parameter description will indicate the data type in the Parameter Value
field. If the parameter value is a varint, but the self-encoded length of that
varint does not match the Parameter Length field, the receiver MUST ignore the
parameter using the value in the Parameter Length field.

### Version Specific Parameters {#version-specific-params}

Each version-specific parameter definition indicates the message types in which
it can appear. If it appears in some other type of message, it MUST be ignored.
Note that since SETUP parameters use a separate namespace, it is impossible for
these parameters to appear in SETUP messages.

#### AUTHORIZATION INFO Parameter {#authorization-info}

AUTHORIZATION INFO parameter (key 0x02) identifies a track's authorization
information in a SUBSCRIBE or ANNOUNCE message. This parameter is populated for
cases where the authorization is required at the track level. The value is an
ASCII string.

## CLIENT_SETUP and SERVER_SETUP {#message-setup}

The `CLIENT_SETUP` and `SERVER_SETUP` messages are the first messages exchanged
by the client and the server; they allows the peers to establish the mutually
supported version and agree on the initial configuration before any objects are
exchanged. It is a sequence of key-value pairs called SETUP parameters; the
semantics and format of which can vary based on whether the client or server is
sending.  To ensure future extensibility of MOQT, the peers MUST ignore unknown
setup parameters. TODO: describe GREASE for those.

The wire format of the SETUP messages is as follows:

~~~
CLIENT_SETUP Message Payload {
  Number of Supported Versions (i),
  Supported Version (i) ...,
  Number of Parameters (i) ...,
  SETUP Parameters (..) ...,
}

SERVER_SETUP Message Payload {
  Selected Version (i),
  Number of Parameters (i) ...,
  SETUP Parameters (..) ...,
}
~~~
{: #moq-transport-setup-format title="MOQT SETUP Messages"}

The available versions and SETUP parameters are detailed in the next sections.

### Versions {#setup-versions}

MoQ Transport versions are a 32-bit unsigned integer, encoded as a varint.
This version of the specification is identified by the number 0x00000001.
Versions with the most significant 16 bits of the version number cleared are
reserved for use in future IETF consensus documents.

The client offers the list of the protocol versions it supports; the
server MUST reply with one of the versions offered by the client. If the
server does not support any of the versions offered by the client, or
the client receives a server version that it did not offer, the
corresponding peer MUST close the connection.

\[\[RFC editor: please remove the remainder of this section before
publication.]]

The version number for the final version of this specification (0x00000001), is
reserved for the version of the protocol that is published as an RFC.
Version numbers used to identify IETF drafts are created by adding the draft
number to 0xff000000. For example, draft-ietf-moq-transport-13 would be
identified as 0xff00000D.

### SETUP Parameters {#setup-params}

#### ROLE parameter {#role}

The ROLE parameter (key 0x00) allows the client to specify what roles it
expects the parties to have in the MOQT connection. It has three
possible values, which are of type varint:

0x01:

: Only the client is expected to send objects on the connection. This is
  commonly referred to as the ingestion case.

0x02:

: Only the server is expected to send objects on the connection. This is
  commonly referred to as the delivery case.

0x03:

: Both the client and the server are expected to send objects.

The client MUST send a ROLE parameter with one of the three values
specified above. The server MUST close the connection if the ROLE
parameter is missing, is not one of the three above-specified values, or
it is different from what the server expects based on the application.

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

## OBJECT {#message-object}

A OBJECT message contains a range of contiguous bytes from from the
specified track, as well as associated metadata required to deliver,
cache, and forward it. There are two subtypes of this message. When the
message type is 0x00, the optional Object Payload Length field is
present. When the message type ix 0x02, the field is not present.

The format of the OBJECT message is as follows:

~~~
OBJECT Message {
  Track ID (i),
  Group Sequence (i),
  Object Sequence (i),
  Object Send Order (i),
  [Object Payload Length (i),]
  Object Payload (b),
}
~~~
{: #moq-transport-object-format title="MOQT OBJECT Message"}

* Track ID: The track identifier obtained as part of subscription and/or
publish control message exchanges.

* Group Sequence : The object is a member of the indicated group
{{model-group}} within the track.

* Object Sequence: The order of the object within the group.  The
sequence starts at 0, increasing sequentially for each object within the
group.

* Object Send Order: An integer indicating the object send order
{{send-order}} or priority {{ordering-by-priorities}} value.

* Object Payload Length: The length of the following Object Payload. If this
field is absent, the object payload continues to the end of the stream.

* Object Payload: An opaque payload intended for the consumer and SHOULD
NOT be processed by a relay.


## SUBSCRIBE {#message-subscribe-req}

A receiver issues a SUBSCRIBE to a publisher to request a track.

### Subscribe Locations {#subscribe-locations}

The receiver specifies a start and optional end `Location` for the subscription.
A location value may be an absolute group or object sequence, or it may be a
delta relative to the largest group or the largest object in a group.

~~~
Location {
  Mode (i),
  [Value (i)]
}
~~~

There are 4 modes:

None (0x0): The Location is unspecified, Value is not present

Absolute (0x1): Value is an absolute sequence

RelativePrevious (0x2): Value is a delta from the largest sequence.  0 is the
largest sequence, 1 is the largest sequence - 1, and so on.

RelativeNext (0x3): Value is a delta from the largest sequence.  0 is the largest
sequence + 1, 1 is the largest sequence + 2, and so on.

The following table shows an example of how the RelativePrevious and RelativeNext
values are used to determine the absolute sequence.

~~~
Sequence:                0    1    2    3    4   [5]  [6] ...
                                             ^
                                      Largest Sequence
RelativePrevious Value:  4    3    2    1    0
RelativeNext Value:                               0    1  ...
~~~
{: title="Relative Indexing"}


### SUBSCRIBE REQUEST Format

The format of SUBSCRIBE REQUEST is as follows:

~~~
SUBSCRIBE REQUEST Message {
  Full Track Name Length (i),
  Full Track Name (...),
  StartGroup (Location),
  StartObject (Location),
  EndGroup (Location),
  EndObject (Location),
  Track Request Parameters (..) ...
}
~~~
{: #moq-transport-subscribe-format title="MOQT SUBSCRIBE Message"}

* Track Namespace: Identifies the namespace of the track as defined in
({{track-name}}).

* Track Name: Identifies the track name as defined in ({{track-name}}).

* StartGroup: The Location of the requested group.  StartGroup's Mode MUST NOT be
None.

* StartObject: The Location of the requested object.  StartObject's Mode MUST NOT
be None.

* EndGroup: The last Group requested in the subscription, inclusive.  EndGroup's
Mode is None for an open-ended subscription.

* EndObject: The last Object requested in the subscription, exclusive.
EndObject's Mode MUST be None if EndGroup's Mode is None.  EndObject's Mode MUST
NOT be None if EndGroup's Mode is not None.

* Track Request Parameters: The parameters are defined in
{{version-specific-params}}

On successful subscription, the publisher SHOULD start delivering
objects from the group sequence and object sequence described above.

If a publisher cannot satisfy the requested start or end for the subscription it
MAY send a SUBSCRIBE_ERROR with code TBD. A publisher MUST NOT send objects
from outside the requested start and end.

### Examples

~~~
1. Now

Start Group: Mode=RelativePrevious, Value=0
Start Object: Mode=RelateiveNext, Value=0
End Group: Mode=None
End Object: Mode=None

StartGroup=Largest Group
StartObject=Largest Object + 1

2. Current

Start Group: Mode=RelativePrevious, Value=0
Start Object: Mode=Absolute, Value=0
End Group: Mode=None
End Object: Mode=None

StartGroup=Largest Group
StartObject=0

3. Previous

Start Group: Mode=RelativePrevious, Value=1
Start Object: Mode=Absolute, Value=0
End Group: Mode=None
End Object: Mode=None

StartGroup=Largest Group - 1
StartObject=0

4. Next

Start Group: Mode=RelativeNext, Value=0
Start Object: Mode=Absolute, Value=0
End Group: Mode=None
End Object: Mode=None

StartGroup=Largest Group + 1
StartObject=0

5. Range, All of group 3

Start Group: Mode=Absolute, Value=3
Start Object: Mode=Absolute, Value=0
End Group: Mode=Absolute, Value=4
End Object: Mode=Absolute, Value=0

Start = Group 3, Object 0
End = Group 3, Object <last>
~~~


## SUBSCRIBE_OK {#message-subscribe-ok}

A SUBSCRIBE_OK control message is sent for successful subscriptions.

~~~
SUBSCRIBE_OK
{
  Track Namespace (b),
  Track Name (b),
  Track ID (i),
  Expires (i)
}
~~~
{: #moq-transport-subscribe-ok format title="MOQT SUBSCRIBE_OK Message"}

* Track Namespace: Identifies the namespace of the track as defined in
({{track-name}}).

* Track Name: Identifies the track name as defined in ({{track-name}}).

* Track ID: Session specific identifier that is used as an alias for the
Full Track Name in the Track ID field of the OBJECT ({{message-object}})
message headers of the requested track. Track IDs are generally shorter
than Full Track Names and thus reduce the overhead in OBJECT messages.

* Expires: Time in milliseconds after which the subscription is no
longer valid. A value of 0 indicates that the subscription stays active
until it is explicitly unsubscribed.


## SUBSCRIBE_ERROR {#message-subscribe-error}

A publisher sends a SUBSCRIBE_ERROR control message in response to a
failed SUBSCRIBE.

~~~
SUBSCRIBE_ERROR
{
  Track Namespace (b),
  Track Name (b),
  Error Code (i),
  Reason Phrase (b),
}
~~~
{: #moq-transport-subscribe-error format title="MOQT SUBSCRIBE_ERROR Message"}

* Track Namespace: Identifies the namespace of the track as defined in
({{track-name}}).

* Track Name: Identifies the track name as defined in ({{track-name}}).

* Error Code: Identifies an integer error code for subscription failure.

* Reason Phrase Length: The length in bytes of the reason phrase.

* Reason Phrase: Provides the reason for subscription error.


## UNSUBSCRIBE {#message-unsubscribe}

A subscriber issues a `UNSUBSCRIBE` message to a publisher indicating it is no
longer interested in receiving media for the specified track.

The format of `UNSUBSCRIBE` is as follows:

~~~
UNSUBSCRIBE Message {
  Track Namespace (b),
  Track Name (b),
}
~~~
{: #moq-transport-unsubscribe-format title="MOQT UNSUBSCRIBE Message"}

* Track Namespace: Identifies the namespace of the track as defined in
({{track-name}}).

* Track Name: Identifies the track name as defined in ({{track-name}}).

## SUBSCRIBE_FIN {#message-subscribe-fin}

A publisher issues a `SUBSCRIBE_FIN` message to all subscribers indicating it
is done publishing objects on the subscribed track.

The format of `SUBSCRIBE_FIN` is as follows:

~~~
SUBSCRIBE_FIN Message {
  Track Namespace (b),
  Track Name (b),
  Final Group (i),
  Final Object (i),
}
~~~
{: #moq-transport-subscribe-fin-format title="MOQT SUBSCRIBE_FIN Message"}

* Track Namespace: Identifies the namespace of the track as defined in
({{track-name}}).

* Track Name: Identifies the track name as defined in ({{track-name}}).

* Final Group: The largest Group Sequence sent by the publisher in an OBJECT
message in this track.

* Final Object: The largest Object Sequence sent by the publisher in an OBJECT
message in the `Final Group` for this track.

## SUBSCRIBE_RST {#message-subscribe-rst}

A publisher issues a `SUBSCRIBE_RST` message to all subscribers indicating there
wan an error publishing to the given track and subscription is terminated.

The format of `SUBSCRIBE_RST` is as follows:

~~~
SUBSCRIBE_RST Message {
  Track Namespace (b),
  Track Name (b),
  Error Code (i),
  Reason Phrase (b),
  Final Group (i),
  Final Object (i),
}
~~~
{: #moq-transport-subscribe-rst format title="MOQT SUBSCRIBE RST Message"}

* Track Namespace: Identifies the namespace of the track as defined in
({{track-name}}).

* Track Name: Identifies the track name as defined in ({{track-name}}).

* Error Code: Identifies an integer error code for subscription failure.

* Reason Phrase: Provides the reason for subscription error.

* Final Group: The largest Group Sequence sent by the publisher in an OBJECT
message in this track.

* Final Object: The largest Object Sequence sent by the publisher in an OBJECT
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

## ANNOUNCE_OK {#message-announce-ok}

The receiver sends an ANNOUNCE_OK control message to acknowledge the
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

The receiver sends an ANNOUNCE_ERROR control message for tracks that
failed authorization.

~~~
ANNOUNCE_ERROR
{
  Track Namespace(b),
  Error Code (i),
  Reason Phrase (b),
}
~~~
{: #moq-transport-announce-error format title="MOQT ANNOUNCE_ERROR Message"}

* Track Namespace: Identifies the track namespace in the ANNOUNCE
message for which this response is provided.

* Error Code: Identifies an integer error code for announcement failure.

* Reason Phrase: Provides the reason for announcement error.


## UNANNOUNCE {#message-unannounce}

The publisher sends the `UNANNOUNCE` control message to indicate
its intent to stop serving new subscriptions for tracks
within the provided Track Namespace.

~~~
UNANNOUNCE Message {
  Track Namespace(b),
}
~~~
{: #moq-transport-unannounce-format title="MOQT UNANNOUNCE Message"}

* Track Namespace: Identifies a track's namespace as defined in
({{track-name}}).


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

* New Session URI: The client MUST use this URI for the new session if provded.
  If the URI is zero bytes long, the current URI is reused instead. The new
  session URI SHOULD use the same scheme as the current URL to ensure
  compatibility.


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
* SETUP parameters
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
