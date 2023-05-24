---
title: "Media over QUIC - Transport"
abbrev: moq-transport
docname: draft-lcurley-moq-transport-latest
date: {DATE}
category: info

ipr: trust200902
area: General
submissionType: IETF
workgroup: Independent Submission
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
  QUIC-RECOVERY: RFC9002
  WebTransport: I-D.ietf-webtrans-http3

informative:
  NewReno: RFC6582
  BBR: I-D.cardwell-iccrg-bbr-congestion-control-02

--- abstract

This document defines the core behavior for MoQTransport, a live media transport protocol over QUIC.
The application fragments a live stream into objects, including a header that describes the basic relationship between objects.
Objects are starved/dropped during congestion based on priorities in order to minimize latency.

--- middle


## Introduction
MoQTransport is a live media transport protocol that utilizes the QUIC network protocol {{QUIC}},
either directly or via WebTransport {{WebTransport}}.
It was originally developed for live media, but has been generalized for similar use-cases.

* {{motivation}} covers the background and rationale behind MoQ transport.
* {{objects}} covers how live content is fragmented into objects.
* {{transport-protocols}} covers aspects of setting up a MoQ transport session.
* {{stream-mapping}} covers how QUIC is used to transfer objects.
* {{priority-congestion}} covers protocol considerations on prioritization schemes and congestion response overall.
* {{relays-moq}} covers behavior at the relay entities.
* {{messages}} covers how messages are encoded on the wire.

### Motivation

#### Latency
In a perfect world, we could deliver live content at the same rate it is produced.
The end-to-end latency would be fixed and only subject to encoding and transmission delays.
Unfortunately, networks have variable throughput, primarily due to congestion.

Attempting to deliver content encoded at a higher bitrate than the network can support causes queuing.
This queuing can occur anywhere in the path between the producer and consumer.
For example: the application, the OS socket, a wifi router, within an ISP, or generally anywhere in transit.

If nothing is done, new data will be appended to the end of a growing queue and will take longer to arrive than their predecessors, increasing latency.
Our job is to minimize the growth of this queue, and if necessary, bypass the queue entirely by dropping content.

The speed at which protocol can detect and respond to queuing determines the latency.
TCP-based protocols are simple, but are slow to detect congestion and suffer from head-of-line blocking.
UDP-based protocols can avoid queuing, but the application is now responsible for fragmentation, congestion control, retransmissions, receiver feedback, reassembly, and more.

A goal of this draft is to get the best of both worlds: a simple protocol that can still rapidly detect and respond to congestion using QUIC streams.

#### Universal
The live media protocol ecosystem is fragmented; each protocol has it's own niche.
Specialization is often a good thing, but we believe there's enough overlap to warrant consolidation.

For example, a service might simultaneously ingest via WebRTC, SRT, RTMP, etc.
The same service might then simultaneously distribute via WebRTC, LL-HLS, HLS/DASH, etc.
Other similar live content would then be distributed other yet additional protocols: for example updates, chat, metadata, etc.

This draft attempts to build a unified base transport protocol for media and similar use-cases.
Any live content can be fragmented into objects and annotated to achieve the intended behavior.
The goal is not to reinvent how content is encoded, just delivered.

#### Relays
The prevailing belief is that UDP-based protocols are more expensive and don't "scale".
While it's true that UDP is more difficult to optimize than TCP, QUIC itself is proof that it is possible to reach performance parity.

The ability to scale a live content transport actually depends on relay support: proxies, caches, CDNs, SFUs, etc.
The success of HTTP-based protocols is due to the ability for a HTTP CDN to cache and deduplicate requests.

It's difficult to build a CDN for live protocols that were not designed with relays in mind.
This is the fatal flaw of many applications, as they relay on relays to perform bespoke parsing and decision making based on the contents.

A goal of this draft is to treat relays as first class citizens.
Any identification, reliability, ordering, prioritization, caching, etc is written to the wire in a header that is easy to parse.
This ensures that relays can easily route content and respond to congestion in a specified, deterministic manner.

#### Bandwidth Management and Congestion Response
TODO: Add motivation text regarding bw management techniques in response to congestion. Also refer to {{priority-congestion}} for further details.


## Terms and Definitions

{::boilerplate bcp14-tagged}

Commonly used terms in this document are described below.

Client:

: The party initiating a session.

Congestion:

: Packet loss and queuing caused by degraded or overloaded networks.

Consumer:

: A QUIC endpoint receiving media over the network. This could be a consumer or a relay.

Producer:

: A QUIC endpoint sending media over the network. This could be a producer or a relay.

Server:

: The party accepting an incoming session.

Track:

: An encoded bitstream, representing a single component that makes up the larger application.

Transport session:

: Either a native QUIC connection, or a WebTransport session used to transmit the data.


## Notational Conventions

This document uses the conventions detailed in Section 1.3 of {{!RFC9000}} when describing the binary encoding.

This document also defines an additional field type for binary data:

x (b):
: Indicates that x consists of a variable length integer, followed by that many bytes of binary data.


# Model

## Objects {#model-object}

The basic element of MoQTransport is an *object*.
An object is an addressable unit whose payload is a sequence of bytes.
All objects belong to a group, indicating ordering and potential dependencies. {{model-group}}
Objects carry associated metadata such as priority, TTL, or other information usable by a relay, but relays MUST treat the object payload as opaque.

The application is solely responsible for the contents of objects.
This includes the underlying encoding, compression, any end-to-end encryption, or authentication.
A relay MUST NOT combine, split, or otherwise modify object payloads.

## Groups {#model-group}
A *group* is collection of objects, part of a larger track ({{model-track}}).

A group behaves as a join point for subscriptions.
A new subscriber may not want to receive the entire track, and will instead opt to receive only the latest group(s).
The sender then selectively transmits objects based on their group membership.

The application is responsible for how objects are placed into groups.
In general, objects within a group SHOULD NOT depend on objects in other groups.


## Track {#model-track}

A *track* is a sequence of objects ({{model-object}}) organized into groups ({{model-group}}).
A subscriber can request individual tracks at group boundaries, including any new objects while the track is active.

### Track Naming and Scopes {#track-fn}

In MoQTransport, every track has a *track name* and a *track namespace* associated with it.
A track name identifies an individual track within the namespace.

A tuple of a track name and a track namespace together is known as *a full track name*:

~~~~~~~~~~~~~~~
Full Track Name = Track Namespace Track Name
~~~~~~~~~~~~~~~

A *MoQ scope* is a set of MoQ servers (as identified by their connection URIs) for which full track names are guaranteed to be unique.
This implies that within a single MoQ scope, subscribing to the same full track name would result in the subscriber receiving the data for the same track.
It is up to the application building on top of MoQ to define how broad or narrow the scope has to be.
An application that deals with connections between devices on a local network may limit the scope to a single connection;
by contrast, an application that uses multiple CDNs to serve media may require the scope to include all of those CDNs.

The full track name is the only piece of information that is used to identify the track within a given MoQ scope and is used as key for caching.
MoQTransport does not provide any in-band content negotiation methods similar to the ones defined by HTTP
({{?RFC9110, Section 10}}); if, at a given moment in time, two tracks within the same scope contain different data,
they have to have different full track names.

~~~
Example: 1
Track Namespace = videoconferencing.example.com/meetings/m123/participants/alice
Track Name = audio
Full Track Name = videoconferencing.example.com/meetings/m123/participants/alice/audio

Example: 2
Track Namespace = livestream.example.com
Track Name = uaCafDkl123/audio
Full Track Name = livestream.example.com/uaCafDkl123/audio

Example: 3
Track Namespace = security-camera.example.com/camera1
Track Name = hd-video
Full Track Name = security-camera.example.com/camera1/hd-video

~~~


### Connection URL

Each track MAY have one or more associated connection URLs specifying network hosts through which a track may be accessed. The syntax of the Connection URL and the associated connection setup procedures are specific to the underlying transport protocol usage {{transport-protocols}}.


## Session
A transport session is established for each track bundle.
The client issues a CONNECT request with a URL which the server uses for identification and authentication.
All control messages and prioritization occur within the context of a single transport session, which means a single track bundle.
When WebTransport is used, multiple transport sessions may be pooled over a single QUIC connection for efficiency.


# Objects
MoQTransport works by transferring objects over QUIC streams.
The application determines how live content is fragmented into tracks, groups, and objects.

## Order Priorities and Options

At the point of this writing, the working group has not reached consensus on the proper
way to meet several important goals, such as:

* Ensure that objects are delivered in the order intended by the emitter
* Allow nodes and relays to skip or delay some objects to deal with congestion
* Ensure that emitters can accurately predict the behavior of relays
* Ensure that when relay have to skip and delay objects belonging to different
  tracks they do it in a predictable way if tracks are explicitly coordinated
  and in a fair way if they are not.

The working group has been considering two alternatives: mark objects belonging to a track
with an explicit "send order"; and, define algorithms combining tracks, priorities and object
order within a group. The two proposals are listed in {{send-order}} and {{ordering-by-priorities}}.
We expect further work before a consensus is reached.

## Groups
TODO: Add text describing iteration of group and intra object priorities within a group and their relation to congestion response. Add how it refers to {{priority-congestion}}


# Supported Transport Protocols  {#transport-protocols}

This document defines a protocol that can be used interchangeably both over a QUIC connection directly [QUIC], and over WebTransport [WebTransport].
Both provide streams and datagrams with similar semantics (see {{?I-D.ietf-webtrans-overview, Section 4}});
thus, the main difference lies in how the servers are identified and how the connection is established.

## WebTransport

A MoQTransport server that is accessible via WebTransport can be identified using an HTTPS URI ({{!RFC9110, Section 4.2.2}}).
A MoQTransport session can be established by sending an extended CONNECT request to the host and the path indicated by the URI,
as described in {{WebTransport, Section 3}}.

## Native QUIC

A MoQTransport server that is accessible via native QUIC can be identified by a URI with a "moq" scheme.
The "moq" URI scheme is defined as follows, using definitions from {{!RFC3986}}:

~~~~~~~~~~~~~~~
moq-URI = "moq" "://" authority path-abempty [ "?" query ]
~~~~~~~~~~~~~~~

The `authority` portion MUST NOT contain a non-empty `userinfo` portion.
The `moq` URI scheme supports the `/.well-known/` path prefix defined in {{!RFC8615}}.

This protocol does not specify any semantics on the `path-abempty` and `query` portions of the URI.
The contents of those is left up to the application.

The client can establish a connection to a MoQ server identified by a given URI
by setting up a QUIC connection to the host and port identified by the `authority` section of the URI.
The `path-abempty` and `query` portions of the URI are communicated to the server using
the PATH parameter ({{path}}).
The ALPN value {{!RFC7301}} used by the protocol is `moq-00`.

# Stream Mapping  {#stream-mapping}

MoQTransport endpoints communicate over QUIC streams. Every stream is a sequence of messages, framed as described in {{messages}}.

The first stream opened is a client-initiated bidirectional stream where the peers exchange SETUP messages ({{message-setup}}). The subsequent streams MAY be either unidirectional and bidirectional. For exchanging content, an application would typically send a unidirectional stream containing a single OBJECT message ({{message-object}}).

Messages SHOULD be sent over the same stream if ordering is desired.


## Prioritization
MoQTransport utilizes stream prioritization to deliver the most important content during congestion.

TODO: Revisit the prioritization scheme and possibly move some of this to {{priority-congestion}}.

The producer may assign a numeric delivery order to each object ({{send-order}})

This is a strict prioritization scheme, such that any available bandwidth is allocated to streams in ascending priority order.

As explained in {{order-priorities-and-options}}, the working group has not reached consensus
on how the emitters mark objects so that relays can apply their preferences. This leads to at
least two possible implementations:

* if using the "send order" logic, the sender SHOULD prioritize streams based on the send order.

* if using the "priority" logic, the sender SHOULD send objects in streams corresponding to the object priority, and should mark these streams with the corresponding priority value.

If two streams have the same send order, they SHOULD receive equal bandwidth (round-robin).

QUIC supports stream prioritization but does not standardize any mechanisms; see Section 2.3 in {{QUIC}}.
In order to support prioritization, a QUIC library MUST expose a API to set the priority of each stream.
This is relatively easy to implement; the next QUIC packet should contain a STREAM frame for the next pending stream in priority order.

The sender MUST respect flow control even if means delivering streams out of send order.
It is OPTIONAL to prioritize retransmissions.


## Cancellation
A QUIC stream MAY be canceled at any point with an error code.
The producer does this via a `RESET_STREAM` frame while the consumer requests cancellation with a `STOP_SENDING` frame.

When using `order`, lower priority streams will be starved during congestion, perhaps indefinitely.
These streams will consume resources and flow control until they are canceled.
When nearing resource limits, an endpoint SHOULD cancel the lowest priority stream with error code 0.

The sender MAY cancel streams in response to congestion.
This can be useful when the sender does not support stream prioritization.

## Relays
MoQTransport encodes the delivery information for a stream via OBJECT headers ({{message-object}}).

A relay SHOULD prioritize streams ({{prioritization}}) based on the send order.

## Congestion Control
As covered in the motivation section ({{motivation}}), the ability to prioritize or cancel streams is a form of congestion response.
It's equally important to detect congestion via congestion control, which is handled in the QUIC layer {{QUIC-RECOVERY}}.

Bufferbloat occurs when routers queue packets for too long instead of dropping the packet, and can introduce significant latency.
This latency significantly reduces the ability for the application to prioritize or drop content in response to congestion.
Senders SHOULD use a congestion control algorithm that reduces this bufferbloat (ex. {{BBR}}).
It is NOT RECOMMENDED to use a loss-based algorithm (ex. {{NewReno}}) unless the network fully supports ECN.

Live content is typically application-limited, which means that the encoder is the limiting factor and not the network.
Most TCP congestion control algorithms will only increase the congestion window if it is full, limiting the upwards mobility when application-limited.
Senders SHOULD use a congestion control algorithm that is designed for application-limited flows (ex. GCC).
Senders MAY periodically pad the connection with QUIC PING frames to fill the congestion window.

TODO: update this section to refer to {{priority-congestion}}

## Termination
The transport session can be terminated at any point.
When native QUIC is used, the session is closed using the CONNECTION\_CLOSE frame ({{QUIC, Section 19.19}}).
When WebTransport is used, the session is closed using the CLOSE\_WEBTRANSPORT\_SESSION capsule ({{WebTransport, Section 5}}).

The application MAY use any error message and SHOULD use a relevant code, as defined below:

|------|--------------------|
| Code | Reason             |
|-----:|:-------------------|
| 0x0  | Session Terminated |
|------|--------------------|
| 0x1  | Generic Error      |
|------|--------------------|
| 0x2  | Unauthorized       |
|------|--------------------|
| 0x10 | GOAWAY             |
|------|--------------------|

* Session Terminated
No error occurred, however the endpoint wishes to terminate the session.

* Generic Error
An unclassified error occurred.

* Unauthorized:
The endpoint breached an agreement, which MAY have been pre-negotiated by the application.

* GOAWAY:
The endpoint successfully drained the session after a GOAWAY was initiated ({{message-goaway}}).

# Prioritization and Congestion Response Considerations {#priority-congestion}

TODO: This is a placeholder section to capture details on
how the Moq Transport protocol deals with prioritization and congestion overall. Having its own section helps reduce merge conflicts and allows us to reference it from other parts.

This section is expected to cover details on:

- Prioritization Schemes
- Congestion Algorithms and impacts
- Mapping considerations for one object per stream vs multiple objects per stream
- considerations for merging multiple streams across domains onto single connection and interactions with specific prioritization schemes

### Send Order
Media is produced with an intended order, both in terms of when media should be presented (PTS) and when media should be decoded (DTS).
As stated in motivation ({{latency}}), the network is unable to maintain this ordering during congestion without increasing latency.

The encoder determines how to behave during congestion by assigning each object a numeric send order.
The send order SHOULD be followed when possible to ensure that the most important media is delivered when throughput is limited.
Note that the contents within each object are still delivered in order; this send order only applies to the ordering between objects.

A sender MUST send each object over a dedicated QUIC stream.
The QUIC library should support prioritization ({{prioritization}}) such that streams are transmitted in send order.

A receiver MUST NOT assume that objects will be received in send order for a number of reasons:

* Newly encoded objects MAY have a smaller send order than outstanding objects.
* Packet loss or flow control MAY delay the send of individual streams.
* The sender might not support QUIC stream prioritization.

TODO: Refer to Congestion Response and Prioritization Section for further details on various proposals.

### Ordering by Priorities

Media is produced as a set of layers, such as for example low definition and high definition,
or low frame rate and high frame rate. Each object belonging to a track and a group has two attributes: the object-id, and the priority (or layer).

When nodes or relays have to choose which object to send next, they apply the following rules:

* within the same group, objects with a lower priority number (e.g. P1) are always sent
  before objects with a numerically greater priority number (e.g., P2)
* within the same group, and the same priority level, objects with a lower object-id are
  always sent before objects with a higher object-id.
* objects from later groups are normally always sent
  before objects of previous groups.

The latter rule is generally agreed as a way to ensure freshness, and to recover quickly
if queues and delays accumulate during a congestion period. However, there may be cases when
finishing the transmission of an ongoing group results in better user experience than strict
adherence to the freshness rule. We expect that that the working group will eventually reach
consensus and define meta data that control this behavior.

There have been proposals to allow emitters to coordinate the allocation of layer priorities
across multiple coordinated tracks. At this point, these proposals have not reached consensus.

# Relays {#relays-moq}

The Relays play an important role for enabling low latency delivery within the MoQ architecture. This specification allows for a delivery protocol based on a publish/subscribe metaphor where some endpoints, called publishers, publish objects and
some endpoints, called subscribers, consume those objects. Relays leverage this publish/subscribe metaphor to form an overlay delivery network similar/in-parallel to what CDN provides today.

Relays serves as policy enforcement points by validating subscribe
and publish requests to the tracks.

## Subscriber Interactions

Subscribers interact with the Relays by sending a "SUBSCRIBE REQUEST"  ({{message-subscribe-req}}) control message for the tracks of interest. Relays MUST ensure subscribers are authorized for the tracks. This is done by

- Verifying that the subscriber is authorized to access the content associated with the "Full Track Name". The authorization information can be part of subscriptions themselves or part of the encompassing session. Specifics of where the authorization happens, either at the relays or forwarded for further processing, depends on the way the relay is managed and is application specific (typically based on prior business agreement).

For successful subscriptions, relays proceed to save the subscription information by maintaining mapping from the track information to the list of subscribers. This will enable relays to forward matching publishes on the requested track. Subscriptions stay active until it is expired or the publisher of the track stops producing objects or other reasons that result in error (see {{message-subscribe-error}}).

In all the scenarios, the end-point making the subscribe request is notified of the result of the subscription, via "SUBSCRIBE OK" ({{message-subscribe-ok}}) or the "SUBSCRIBE ERROR" {{message-subscribe-error}} control message.

Relays MAY aggregate subscriptions for a given track when multiple subscribers request for the same track. Subscriptions aggregation allows relays to share the cache and forward only the unique subscriptions per track for further processing, say to setup routing for delivering objects, rather than forwarding all the subscriptions received. When the authorization information is carried in the subscribes, the relay MUST authorize the subscribe requests, in order to deduplicate and serve the subscriptions from the shared cache.


## Publisher Interactions

Publishing through the relay starts with publisher sending "ANNOUNCE" control message with a `Track Namespace` ({{model-track}}).

Relays MUST ensure that publishers are authorized by:

- Verifying that the publisher is authorized to publish the content associated with the set of tracks whose Track Namespace matches the announced namespace. Specifics of where the authorization happens, either at the relays or forwarded for further processing, depends on the way the relay is managed and is application specific (typically based on prior business agreement).

Relays respond with "ANNOUNCE OK" and/or "ANNOUNCE ERROR" control messages providing the results of announcement.

OBJECT message header carry short hop-by-hop Track Id that maps to the Full Track Name (see {{message-subscribe-ok}}). Relays use the Track ID of an incoming OBJECT message to identify its track and find the active subscribers for that track. Relays MUST NOT depend on OBJECT payload content for making forwarding decisions and MUST only depend on the fields, such as priority order and other metadata properties in the OBJECT message header. Unless determined by congestion response, Relays MUST forward the OBJECT message to the matching subscribers.

## Relay Discovery and Failover

TODO: This section shall cover aspects of relay failover and protocol interactions

## Restoring connections through relays

TODO: This section shall cover reconnect considerations for clients when moving between the Relays

## Congestion Response at Relays

TODO: Refer to {{priority-congestion}}. Add details describe
relays behavior when merging or splitting streams and interactions
with congestion response.

A relay MAY change the send order, in which case it SHOULD update the value on the wire for future hops.

A relay that reads from a stream and writes to stream in order will introduce head-of-line blocking.
Packet loss will cause stream data to be buffered in the QUIC library, awaiting in order delivery, which will increase latency over additional hops.
To mitigate this, a relay SHOULD read and write QUIC stream data out of order subject to flow control limits.
See section 2.2 in {{QUIC}}.

# Messages
Both unidirectional and bidirectional QUIC streams contain sequences of length-delimited messages.

~~~
MoQTransport Message {
  Message Type (i),
  Message Length (i),
  Message Payload (..),
}
~~~
{: #moq-transport-message-format title="MoQTransport Message"}

The Message Length field contains the length of the Message Payload field in bytes.
A length of 0 indicates the message is unbounded and continues until the end of the stream.

|------|----------------------------------------------|
| ID   | Messages                                     |
|-----:|:---------------------------------------------|
| 0x0  | OBJECT ({{message-object}})                  |
|------|----------------------------------------------|
| 0x1  | SETUP ({{message-setup}})                    |
|------|----------------------------------------------|
| 0x3  | SUBSCRIBE REQUEST ({{message-subscribe-req}})|
|------|----------------------------------------------|
| 0x4  | SUBSCRIBE OK ({{message-subscribe-ok}})      |
|------|----------------------------------------------|
| 0x5  | SUBSCRIBE ERROR ({{message-subscribe-error}})|
|------|----------------------------------------------|
| 0x6  | ANNOUNCE  ({{message-announce}})             |
|------|----------------------------------------------|
| 0x7  | ANNOUNCE OK ({{message-announce-ok}})        |
|------|----------------------------------------------|
| 0x8  | ANNOUNCE ERROR ({{message-announce-error}})  |
|------|----------------------------------------------|
| 0x10 | GOAWAY ({{message-goaway}})                  |
|------|----------------------------------------------|

## SETUP {#message-setup}

The `SETUP` message is the first message that is exchanged by the client and the server; it allows the peers to establish the mutually supported version and agree on the initial configuration. It is a sequence of key-value pairs called *SETUP parameters*; the semantics and the format of individual parameter values MAY depend on what party is sending it.

The wire format of the SETUP message is as follows:

~~~
SETUP Parameter {
  Parameter Key (i),
  Parameter Value Length (i),
  Parameter Value (..),
}

Client SETUP Message Payload {
  Number of Supported Versions (i),
  Supported Version (i) ...,
  SETUP Parameters (..) ...,
}

Server SETUP Message Payload {
  Selected Version (i),
  SETUP Parameters (..) ...,
}
~~~
{: #moq-transport-setup-format title="MoQTransport SETUP Message"}

The Parameter Value Length field indicates the length of the Parameter Value.

The client offers the list of the protocol versions it supports; the server MUST reply with one of the versions offered by the client. If the server does not support any of the versions offered by the client, or the client receives a server version that it did not offer, the corresponding peer MUST close the connection.

The SETUP parameters are described in the {{setup-parameters}} section.

### SETUP Parameters

The SETUP message ({{message-setup}}) allows the peers to exchange arbitrary parameters before any objects are exchanged. It is the main extensibility mechanism of MoQTransport. The peers MUST ignore unknown parameters. TODO: describe GREASE for those.

Every parameter MUST appear at most once within the SETUP message. The peers SHOULD verify that and close the connection if a parameter appears more than once.

The ROLE parameter is mandatory for the client. All of the other parameters are optional.

#### ROLE parameter {#role}

The ROLE parameter (key 0x00) allows the client to specify what roles it expects the parties to have in the MoQTransport connection. It has three possible values:

0x01:

: Only the client is expected to send objects on the connection. This is commonly referred to as *the ingestion case*.

0x02:

: Only the server is expected to send objects on the connection. This is commonly referred to as *the delivery case*.

0x03:

: Both the client and the server are expected to send objects.

The client MUST send a ROLE parameter with one of the three values specified above. The server MUST close the connection if the ROLE parameter is missing, is not one of the three above-specified values, or it is different from what the server expects based on the application in question.

#### PATH parameter {#path}

The PATH parameter (key 0x01) allows the client to specify the path of the MoQ URI when using native QUIC ({{native-quic}}).
It MUST NOT be used by the server, or when WebTransport is used.
If the peer receives a PATH parameter from the server, or when WebTransport is used, it MUST close the connection.

When connecting to a server using a URI with the "moq" scheme,
the client MUST set the PATH parameter to the `path-abempty` portion of the URI;
if `query` is present, the client MUST concatenate `?`, followed by the `query` portion of the URI to the parameter.


## OBJECT {#message-object}
A OBJECT message contains a range of contiguous bytes from from the specified track, as well as associated metadata required to deliver, cache, and forward it.

The format of the OBJECT message is as follows:

~~~
OBJECT Message {
  Track ID (i),
  Group Sequence (i),
  Object Sequence (i),
  Object Send Order (i),
  Object Payload (b),
}
~~~
{: #moq-transport-object-format title="MoQTransport OBJECT Message"}

* Track ID:
The track identifier obtained as part of subscription and/or publish control message exchanges.

* Group Sequence :
The object is a member of the indicated group {{model-group}} within the track.

* Object Sequence:
The order of the object within the group.
The sequence starts at 0, increasing sequentially for each object within the group.

* Object Send Order:
An integer indicating the object send order ({{send-order}}).

* Object Payload:
An opaque payload intended for the consumer and SHOULD NOT be processed by a relay.


## SUBSCRIBE REQUEST {#message-subscribe-req}

Entities that intend to receive content will do so via subscriptions to one or more tracks.

The format of SUBSCRIBE REQUEST is as follows:

~~~
Track Request Parameter {
  Track Request Parameter Key (i),
  Track Request Parameter Length (i),
  Track Request Parameter Value (..),
}

SUBSCRIBE REQUEST Message {
  Full Track Name Length(i),
  Full Track Name(...),
  Track Request Parameters (..) ...
}
~~~
{: #moq-transport-subscribe-format title="MoQTransport SUBSCRIBE REQUEST Message"}


* Full Track Name:
Identifies the track as defined in ({{track-fn}}).

* Track Request Parameters:
 As defined in {{track-req-params}}.

On successful subscription, the publisher SHOULD start delivering objects
from the group sequence and object sequence as defined in the `Track Request Parameters`.

## SUBSCRIBE OK {#message-subscribe-ok}

A `SUBSCRIBE OK` control message is sent for successful subscriptions.

~~~
SUBSCRIBE OK
{
  Full Track Name Length(i),
  Full Track Name(...),
  Track ID(i),
  Expires (i)
}
~~~
{: #moq-transport-subscribe-ok format title="MoQTransport SUBSCRIBE OK Message"}

* Full Track Name:
Identifies the track in the request message for which this
response is provided.

* Track ID:
Session specific identifier that maps the Full Track Name to the Track ID in OBJECT ({{message-object}}) message headers for the advertised track. Track IDs are generally shorter than Full Track Names and thus reduce the overhead in OBJECT messages.

* Expires:
Time in milliseconds after which the subscription is no longer valid. A value of 0 implies that the subscription stays active until its explicitly unsubscribed or the underlying transport is disconnected.

## SUBSCRIBE ERROR {#message-subscribe-error}

A `SUBSCRIBE ERROR` control message is sent for unsuccessful subscriptions.

~~~
SUBSCRIBE ERROR
{
  Full Track Name Length(i),
  Full Track Name(...),
  Error Code (i),
  Reason Phrase Length (i),
  Reason Phrase (...),
}
~~~
{: #moq-transport-subscribe-error format title="MoQTransport SUBSCRIBE ERROR Message"}

* Full Track Name:
Identifies the track in the request message for which this
response is provided.

* Error Code:
Identifies an integer error code for subscription failure.

* Reason Phrase:
Provides the reason for subscription error and `Reason Phrase Length` field carries its length.

## ANNOUNCE {#message-announce}

The publisher advertises the tracks via the `ANNOUNCE` control message. The `ANNOUNCE` message allows discovery of tracks being published by a publisher and verify publisher's authorization for all the tracks sharing the announced namespace.

~~~
ANNOUNCE Message {
  Track Namespace Length(i),
  Track Namespace,
  Track Request Parameters (..) ...,
}
~~~
{: #moq-transport-announce-format title="MoQTransport ANNOUNCE Message"}

* Track Namespace:
Identifies a track's namespace as defined in ({{track-fn}})

* Track Request Parameters:
As defined in {{track-req-params}}.

### Track Request Parameters {#track-req-params}

The Track Request Parameters identify properties of the track requested in either the ANNOUNCE or SUSBCRIBE REQUEST control messages. Every parameter MUST appear at most once. The peers MUST close the connection if there are duplicates. The Parameter Value Length field indicates the length of the Parameter Value.

#### GROUP SEQUENCE Parameter

The GROUP SEQUENCE parameter (key 0x00) identifies the group within the track to start delivering objects. The publisher MUST start delivering the objects from the most recent group, when this parameter is omitted. This parameter is applicable in SUBSCRIBE REQUEST message.

#### OBJECT SEQUENCE Parameter
The OBJECT SEQUENCE parameter (key 0x01) identifies the object with the track to start delivering objects. The `GROUP SEQUENCE` parameter MUST be set to identify the group under which to start delivery. The publisher MUST start delivering from the beginning of the selected group when this parameter is omitted. This parameter is applicable in SUBSCRIBE REQUEST message.

#### AUTHORIZATION INFO Parameter
AUTHORIZATION INFO parameter (key 0x02) identifies track's authorization information. This parameter is populated for cases where the authorization is required at the track level. This parameter is applicable in SUBSCRIBE REQUEST and ANNOUNCE messages.



## ANNOUNCE OK {#message-announce-ok}

`ANNOUNCE OK` control message is sent for announcements successfully authorized.

~~~
ANNOUNCE OK
{
  Track Namespace
}
~~~
{: #moq-transport-announce-ok format title="MoQTransport ANNOUNCE OK Message"}

* Track Namespace:
Identifies the track namespace in the ANNOUNCE message for which this response is provided.

## ANNOUNCE ERROR {#message-announce-error}

A `ANNOUNCE ERROR` control message is sent for the tracks that failed authorization.

~~~
ANNOUNCE ERROR
{
  Track Namespace Length(i),
  Track Namespace(...),
  Error Code (i),
  Reason Phrase Length (i),
  Reason Phrase (...),
}
~~~
{: #moq-transport-announce-error format title="MoQTransport ANNOUNCE ERROR Message"}

* Track Namespace:
Identifies the track namespace in the ANNOUNCE message for which this response is provided.

* Error Code:
Identifies an integer error code for announcement failure.

* Reason Phrase:
Provides the reason for announcement error and `Reason Phrase Length` field carries its length.


## GOAWAY {#message-goaway}
The `GOAWAY` message is sent by the server to force the client to reconnect.
This is useful for server maintenance or reassignments without severing the QUIC connection.
The server MAY be a producer or consumer.

The server:

* MAY initiate a graceful shutdown by sending a GOAWAY message.
* MUST close the QUIC connection after a timeout with the GOAWAY error code ({{termination}}).
* MAY close the QUIC connection with a different error code if there is a fatal error before shutdown.
* SHOULD wait until the `GOAWAY` message and any pending streams have been fully acknowledged, plus an extra delay to ensure they have been processed.

The client:

* MUST establish a new transport session to the provided URL upon receipt of a `GOAWAY` message.
* SHOULD establish the connection in parallel which MUST use different QUIC connection.
* SHOULD remain connected for two servers for a short period, processing objects from both in parallel.

# Security Considerations

## Resource Exhaustion
Live content requires significant bandwidth and resources.
Failure to set limits will quickly cause resource exhaustion.

MoQTransport uses QUIC flow control to impose resource limits at the network layer.
Endpoints SHOULD set flow control limits based on the anticipated bitrate.

The producer prioritizes and transmits streams out of order.
Streams might be starved indefinitely during congestion.
The producer and consumer MUST cancel a stream, preferably the lowest priority, after reaching a resource limit.

# IANA Considerations

TODO: fill out currently missing registries:
* MoQTransport version numbers
* SETUP parameters
* Track Request parameters
* Subscribe Error codes
* Announce Error codes
* Track format numbers
* Message types
* Object headers

TODO: register the URI scheme and the ALPN


# Contributors
{:numbered="false"}

- Alan Frindell
- Charles Krasic
- Cullen Jennings
- James Hurley
- Jordi Cenzano
- Mike English
- Will Law
- Ali Begen
