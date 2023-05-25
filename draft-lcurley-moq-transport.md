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

This document defines the core behavior for MoQTransport, a media transport protocol over QUIC.  MoQTransport allows a producer of media to publish data and have it consumed via subscription by a multiplicity of endpoints. It supports intermediate content distribution networks and is designed for high scale and low latency distribution. The core subscribable entities are tracks, consisting of a sequence of objects organized into groups. MoQTransport is a generic protocol, designed to work in concert with multiple MoQ Streaming Formats, each of which define alternate schemes for carrying media content over MoQT.

--- middle


## Introduction
MoQTransport (MoQT) is a transport protocol that utilizes QUIC Transport {{QUIC}}, either directly or via WebTransport {{WebTransport}}, for the dissemination of media. MoQT utilizes a publish/subscribe workflow in which producers of media publish data in response to subscription requests from a multiplicity of endpoints. MoQT supports live, as well as near-live and Video on Demand (VOD) use-cases. MoQT supports delivery over intermediate content distribution networks and is architected for high scale and low latency distribution. In live mode, MoQT facilitates a broad spectrum of latency regimes, from real-time, to interactive and non-interactive.

MoQTransport is a generic protocol is designed to work in concert with multiple MoQ Streaming Formats. These MoQ Streaming Formats define how content is encoded, packaged, and mapped to MoQT objects, along with policies for discovery, subscription and congestion response.

* {{model}} describes the object model employed by MoQT
* {{session}} covers aspects of setting up a MoQT session.
* {{priority-congestion}} covers protocol considerations on prioritization schemes and congestion response overall.
* {{relays-moq}} covers behavior at the relay entities.
* {{message}} covers how messages are encoded on the wire.

### Motivation
The development of MoQT is driven by goals in a number of areas - specifically latency, the robustness of QUIC, workflow efficiency and relay support.

#### Latency
HTTP Adaptive Streaming (HAS) has been successful at achieving scale although often at the cost of latency. Latency is necessary to correct for variable network throughput. Ideally live content is consumed at the same rate it is produced. End-to-end latency would be fixed and only subject to encoding and transmission delays. Unfortunately, networks have variable throughput, primarily due to congestion. Attempting to deliver content encoded at a higher bitrate than the network can support causes queuing along the path from producer to consumer. The speed at which a protocol can detect and respond to queuing determines the overall latency. TCP-based protocols are simple but are slow to detect congestion and suffer from head-of-line blocking. UDP-based protocols can avoid queuing, but the application is now responsible for the complexity of fragmentation, congestion control, retransmissions, receiver feedback, reassembly, and more. One goal of MoQTransport is to achieve the best of both these worlds: leverage the features of QUIC to create a simple yet flexible low latency protocol that can rapidly detect and respond to congestion.

#### Leveraging QUIC
Applying {{QUIC}} to HAS via HTTP/3 does not yield generalized improvements in throughput. One reason for this is that sending segments down a single QUIC stream still allows head-of-line blocking to occur. Only by leveraging the parallel nature of QUIC streams can improved throughput be achieved in the face of loss. A goal of MoQT is to design a streaming protocol to leverage the transmission benefits afforded by parallel  QUIC streams as well exercising options for flexible loss recovery.

#### Workflow efficiency
Internet delivered media today has protocols optimized for ingest and separate protocols optimized for distribution. This protocol switch in the distribution chain necessitates intermediary origins which re-package the media content. While specialization can have its benefits, there are gains in efficiency to be had in not having to re-package content. A goal of MoQT is to develop a single protocol which can be used for transmission from contribution to distribution. A related goal is the ability to support existing encoding and packaging schemas, both for backwards compatibility and for interoperability with the established content preparation ecosystem.

#### Relays
An integral feature of a protocol being successful is its ability to deliver media at scale. Greatest scale is achieved when third-party networks, independent of both the publisher and subscriber, can be leveraged to relay the content. These relays must cache content for distribution efficiency while simultaneously routing content and deterministically responding to congestion in a multi-tenant network. A goal of MoQT is to treat relays as first-class citizens of the protocol and ensure that objects are structured such that information necessary for distribution is available to relays while the media content itself remains opaque and private.


## Terms and Definitions

{::boilerplate bcp14-tagged}

Commonly used terms in this document are described below.

Client:

: The party initiating a transport session.

Congestion:

: Packet loss and queuing caused by degraded or overloaded networks.

Consumer:

: A QUIC endpoint receiving media over the network. This could be an endpoint or a relay.

Endpoint:

: The original producer or the final consumer in a transmission chain. TODO - does this apply to the hop or the complete transmission chain? 

Group:

: A temporal sequence of one or more objects. A group represents a subscription point in a track. 

Object:

: An object is an addressable unit whose payload is a sequence of bytes. Objects form the base element in the MoQTransport data model {{model-object}}.

Producer:

: A QUIC endpoint sending media over the network. This could be an endpoint or a relay.

Server:

: The party accepting an incoming transport session.

Track:

: An encoded bitstream. Tracks contain a sequential series of one or more groups and are the subscribable entity with MoQT.

Transport session:

: A native QUIC connection, or a WebTransport session.


## Notational Conventions

This document uses the conventions detailed in Section 1.3 of {{!RFC9000}} when describing the binary encoding.

This document also defines an additional field type for binary data:

x (b):
: Indicates that x consists of a variable length integer, followed by that many bytes of binary data.


# Object Model {#model}

MoQT is a transport that moves entitites called messages {{message}}. Messages are divided into two classes: control messages and objects. Control messages are used to setup connections, announce content, issues subscriptions etc. All media data is carried inside object messages. MoQT has a hierarchical object model for data, comprised of objects, groups and tracks.

## Objects {#model-object}

The basic data element of MoQTransport is an *object*.
An object is an addressable unit whose payload is a sequence of bytes.
All objects belong to a group, indicating ordering and potential dependencies. {{model-group}}
Objects are comprised of two parts: metadata and a payload.  The metadata is never encrypted and is always visible to relays. The payload portion may be encrypted, in which case it is only visible to the producer and consumer. The application is solely responsible for the content of the object payload. This includes the underlying encoding, compression, any end-to-end encryption, or authentication. A relay MUST NOT combine, split, or otherwise modify object payloads.

## Groups {#model-group}
A *group* is a collection of objects and is a sub-unit of a track ({{model-track}}).
Objects within a group SHOULD NOT depend on objects in other groups.
A group behaves as a join point for subscriptions. 
A new subscriber might not want to receive the entire track, and can instead opt to receive only the latest group(s).
The sender then selectively transmits objects based on their group membership.


## Track {#model-track}

A *track* is a sequence of groups ({{model-group}}). It is the entity against which a consumer issues a subscription request. 
A subscriber can request to receive individual tracks starting at a group boundary, including any new objects pushed by the producer while the track is active.

### Track Naming and Scopes {#track-name}

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

The full track name is the only piece of information that is used to identify the track within a given MoQ scope and that is used as a key for caching.
MoQTransport does not provide any in-band content negotiation methods similar to the ones defined by HTTP
({{?RFC9110, Section 10}}); if, at a given moment in time, two tracks within the same scope contain different data,
they have to have different full track names.

~~~
Example: 1
Track Namespace = videoconferencing.example.com/meetings/m123/participants/alice/
Track Name = audio
Full Track Name = videoconferencing.example.com/meetings/m123/participants/alice/audio

Example: 2
Track Namespace = livestream.example.com
Track Name = /uaCafDkl123/audio
Full Track Name = livestream.example.com/uaCafDkl123/audio

Example: 3
Track Namespace = security-camera.example.com/camera1/
Track Name = hd-video
Full Track Name = security-camera.example.com/camera1/hd-video

~~~

### Track Connection URL
Each track MAY have one or more associated connection URLs specifying network hosts through which a track may be accessed. The syntax of the Connection URL and the associated connection setup procedures are specific to the underlying transport protocol usage {{session}}.

# Sessions {#session}

## Session establishment {#session-establishment}

This document defines a protocol that can be used interchangeably both over a QUIC connection directly [QUIC], and over WebTransport [WebTransport].
Both provide streams and datagrams with similar semantics (see {{?I-D.ietf-webtrans-overview, Section 4}});
thus, the main difference lies in how the servers are identified and how the connection is established.

### WebTransport

A MoQTransport server that is accessible via WebTransport can be identified using an HTTPS URI ({{!RFC9110, Section 4.2.2}}).
A MoQTransport session can be established by sending an extended CONNECT request to the host and the path indicated by the URI,
as described in {{WebTransport, Section 3}}.

### QUIC

A MoQTransport server that is accessible via native QUIC can be identified by a URI with a "moq" scheme.
The "moq" URI scheme is defined as follows, using definitions from {{!RFC3986}}:

~~~~~~~~~~~~~~~
moq-URI = "moq" "://" authority path-abempty [ "?" query ]
~~~~~~~~~~~~~~~

The `authority` portion MUST NOT contain a non-empty `host` portion.
The `moq` URI scheme supports the `/.well-known/` path prefix defined in {{!RFC8615}}.

This protocol does not specify any semantics on the `path-abempty` and `query` portions of the URI.
The contents of those are left up to the application.

The client can establish a connection to a MoQ server identified by a given URI
by setting up a QUIC connection to the host and port identified by the `authority` section of the URI.
The `path-abempty` and `query` portions of the URI are communicated to the server using
the PATH parameter ({{path}}) which is sent in the SETUP message at the start of the session. 
The ALPN value {{!RFC7301}} used by the protocol is `moq-00`.

## Session initialization {#session-init}

The first stream opened is a client-initiated bidirectional stream where the peers exchange SETUP messages ({{message-setup}}). The subsequent streams MAY be either unidirectional or bidirectional. For exchanging content, an application would typically send a unidirectional stream containing a single OBJECT message ({{message-object}}), as putting more than one object into one stream may create head-of-line blocking delays.  However, if one object has a hard dependency on another object, putting them on the same stream could be a valid choice.

## Cancellation {#session-cancellation}
A QUIC stream MAY be canceled at any point with an error code.
The producer does this via a `RESET_STREAM` frame while the consumer requests cancellation with a `STOP_SENDING` frame.

When using `order`, lower priority streams will be starved during congestion, perhaps indefinitely.
These streams will consume resources and flow control until they are canceled.
When nearing resource limits, an endpoint SHOULD cancel the lowest priority stream with error code 0.

The sender MAY cancel streams in response to congestion.
This can be useful when the sender does not support stream prioritization.

TODO: this section actually describes stream cancellation, not session cancellation. Is this section required, or can it be deleted, or added to a new "workflow" section?


## Termination {#session-termination}
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
No error occurred; however the endpoint wishes to terminate the session.

* Generic Error
An unclassified error occurred.

* Unauthorized:
The endpoint breached an agreement, which MAY have been pre-negotiated by the application.

* GOAWAY:
The endpoint successfully drained the session after a GOAWAY was initiated ({{message-goaway}}).

# Prioritization and Congestion Response {#priority-congestion}

TODO: This is a placeholder section to capture details on how the MoQTransport protocol deals with prioritization and congestion overall.

This section is expected to cover details on:

- Prioritization Schemes.
- Congestion Algorithms and impacts.
- Mapping considerations for one object per stream vs multiple objects per stream.
- Considerations for merging multiple streams across domains onto single connection and interactions with specific prioritization schemes.

## Order Priorities and Options

At the point of this writing, the working group has not reached consensus on several important goals, such as:

* Ensuring that objects are delivered in the order intended by the emitter
* Allowing nodes and relays to skip or delay some objects to deal with congestion
* Ensuring that emitters can accurately predict the behavior of relays
* Ensuring that when relays have to skip and delay objects belonging to different
  tracks that they do it in a predictable way if tracks are explicitly coordinated
  and in a fair way if they are not.

The working group has been considering two alternatives: marking objects belonging to a track
with an explicit "send order"; and, defining algorithms combining tracks, priorities and object
order within a group. The two proposals are listed in {{send-order}} and {{ordering-by-priorities}}.
We expect further work before a consensus is reached.

### Proposal - Send Order {#send-order}
Media is produced with an intended order, both in terms of when media should be presented (PTS) and when media should be decoded (DTS).
As stated in the introduction, the network is unable to maintain this ordering during congestion without increasing latency.

The encoder determines how to behave during congestion by assigning each object a numeric send order.
The send order SHOULD be followed when possible, to ensure that the most important media is delivered when throughput is limited.
Note that the contents within each object are still delivered in order; this send order only applies to the ordering between objects.

A sender MUST send each object over a dedicated QUIC stream.
The QUIC library SHOULD support prioritization ({{priority-congestion}}) such that streams are transmitted in send order.

A receiver MUST NOT assume that objects will be received in send order, for the following reasons:

* Newly encoded objects can have a smaller send order than outstanding objects.
* Packet loss or flow control can delay the send of individual streams.
* The sender might not support QUIC stream prioritization.

### Proposal - Order by Priorities {#ordering-by-priorities}

Media is produced as a set of layers, such as for example low definition and high definition,
or low frame rate and high frame rate. Each object belonging to a track and a group has two attributes: the object-id, and the priority (or layer).

When nodes or relays have to choose which object to send next, they apply the following rules:

* Within the same group, objects with a lower priority number (e.g. P1) are always sent
  before objects with a numerically greater priority number (e.g., P2)
* Within the same group, and the same priority level, objects with a lower object-id are
  always sent before objects with a higher object-id.
* Objects from later groups are normally always sent
  before objects of previous groups.

The latter rule is generally agreed as a way to ensure freshness, and to recover quickly
if queues and delays accumulate during a congestion period. However, there may be cases when
finishing the transmission of an ongoing group results in better user experience than strict
adherence to the freshness rule. We expect that that the working group will eventually reach
consensus and define meta data that controls this behavior.

There have been proposals to allow emitters to coordinate the allocation of layer priorities
across multiple coordinated tracks. At this point, these proposals have not reached consensus.

# Relays {#relays-moq}

Relays are leveraged to enable distribution scale in the MoQ architecture. Relays can be used to form an overlay delivery network, similar in functionality to  Content Delivery Networks (CDNs). Additionally, relays serve as policy enforcement points by validating subscribe and publish requests at the edge of a network.

## Subscriber Interactions

Subscribers interact with the Relays by sending a "SUBSCRIBE REQUEST"  ({{message-subscribe-req}}) control message for the tracks of interest. Relays MUST ensure subscribers are authorized to subscribe to the requested tracks. This is done by verifying that the subscriber is authorized to access the content associated with the "Full Track Name". The authorization information can be part of subscription request itself or part of the encompassing session. The specifics of how a relay authorizes a user are outside the scope of this specification.

The endpoint making the subscribe request is notified of the result of the subscription, via "SUBSCRIBE OK" ({{message-subscribe-ok}}) or the "SUBSCRIBE ERROR" {{message-subscribe-error}} control message.

For successful subscriptions, the sender maintains a list of subscribers for each full track name. Each new OBJECT belonging to the track MUST be forwarded to each active subscriber, unless determined by congestion response. A subscription remains active until it expires, or until the publisher of the track stops producing objects or there is a subscription error (see {{message-subscribe-error}}).

Relays MAY aggregate authorized subscriptions for a given track when multiple subscribers request the same track. Subscription aggregation allows relays to make only a single forward subscription for the track. The published content received from the forward subscription request is cached and shared among the pending subscribers.


## Publisher Interactions

Publishing through the relay starts with publisher sending "ANNOUNCE" control message with a `Track Namespace` ({{model-track}}).

Relays MUST ensure that publishers are authorized by:

- Verifying that the publisher is authorized to publish the content associated with the set of tracks whose Track Namespace matches the announced namespace. Specifics of where the authorization happens, either at the relays or forwarded for further processing, depends on the way the relay is managed and is application specific (typically based on prior business agreement).

Relays respond with "ANNOUNCE OK" and/or "ANNOUNCE ERROR" control messages providing the results of announcement.

OBJECT message header carry short hop-by-hop Track Id that maps to the Full Track Name (see {{message-subscribe-ok}}). Relays use the Track ID of an incoming OBJECT message to identify its track and find the active subscribers for that track. Relays MUST NOT depend on OBJECT payload content for making forwarding decisions and MUST only depend on the fields, such as priority order and other metadata properties in the OBJECT message header. Unless determined by congestion response, Relays MUST forward the OBJECT message to the matching subscribers.

## Relay Discovery and Failover

TODO: This section shall cover aspects of relay failover and protocol interactions.

## Restoring connections through relays

TODO: This section shall cover reconnect considerations for clients when moving between the Relays.

## Congestion Response at Relays

TODO: Refer to {{priority-congestion}}. Add details to describe relay behavior when merging or splitting streams and interactions
with congestion response.

## Relay Object Handling
MoQTransport encodes the delivery information for a stream via OBJECT headers ({{message-object}}).

A relay MUST treat the object payload as opaque. 
A relay MUST NOT combine, split, or otherwise modify object payloads.
A relay SHOULD prioritize streams ({{priority-congestion}}) based on the send order/priority.
A relay MAY change the send order/priority, in which case it SHOULD update the value on the wire for future hops.

A relay that reads from a stream and writes to stream in order will introduce head-of-line blocking.
Packet loss will cause stream data to be buffered in the QUIC library, awaiting in order delivery, which will increase latency over additional hops.
To mitigate this, a relay SHOULD read and write QUIC stream data out of order subject to flow control limits.
See section 2.2 in {{QUIC}}.

# Messages {#message}
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

The `SETUP` message is the first message that is exchanged by the client and the server; it allows the peers to establish the mutually supported version and agree on the initial configuration before any objects are exchanged. It is a sequence of key-value pairs called *SETUP parameters*; the semantics and format of which can vary based on whether the client or server is sending. To ensure future extensibility of MoQTransport, the peers MUST ignore unknown setup parameters. TODO: describe GREASE for those.

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

### SETUP Parameters {#setup-parameters}

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

The client MUST send a ROLE parameter with one of the three values specified above. The server MUST close the connection if the ROLE parameter is missing, is not one of the three above-specified values, or it is different from what the server expects based on the application.

#### PATH parameter {#path}

The PATH parameter (key 0x01) allows the client to specify the path of the MoQ URI when using native QUIC {{QUIC}}.
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
An integer indicating the object Send Order {{send-order} or Priority {{ordering-by-priorities}} value.

* Object Payload:
An opaque payload intended for the consumer and SHOULD NOT be processed by a relay.


## SUBSCRIBE REQUEST {#message-subscribe-req}

A receiver issues a SUBSCRIBE REQUEST to a publisher to request a track.

The format of SUBSCRIBE REQUEST is as follows:

~~~
Track Request Parameter {
  Track Request Parameter Key (i),
  Track Request Parameter Length (i),
  Track Request Parameter Value (..),
}

SUBSCRIBE REQUEST Message {
  Full Track Name Length (i),
  Full Track Name (...),
  Track Request Parameters (..) ...
}
~~~
{: #moq-transport-subscribe-format title="MoQTransport SUBSCRIBE REQUEST Message"}


* Full Track Name:
Identifies the track as defined in ({{track-name}}).

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
Identifies the track for which this response is provided.

* Track ID:
Session specific identifier that is used as an alias for the Full Track Name in the Track ID field of the OBJECT ({{message-object}}) message headers of the requested track. Track IDs are generally shorter than Full Track Names and thus reduce the overhead in OBJECT messages.

* Expires:
Time in milliseconds after which the subscription is no longer valid. A value of 0 indicates that the subscription stays active until it is explicitly unsubscribed.

## SUBSCRIBE ERROR {#message-subscribe-error}

A publisher sends a SUBSCRIBE ERROR control message in response to a failed SUBSCRIBE REQUEST.

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

The publisher sends the ANNOUNCE control message to advertise where the receiver can route SUBSCRIBE REQUESTs for tracks within the announced Track Namespace. The receiver verifies the publisher is authorized to publish tracks under this namespace.

~~~
ANNOUNCE Message {
  Track Namespace Length(i),
  Track Namespace,
  Track Request Parameters (..) ...,
}
~~~
{: #moq-transport-announce-format title="MoQTransport ANNOUNCE Message"}

* Track Namespace:
Identifies a track's namespace as defined in ({{track-name}})

* Track Request Parameters:
The parameters are defined in {{track-req-params}}.

### Track Request Parameters {#track-req-params}

The Track Request Parameters identify properties of the track requested in either the ANNOUNCE or SUSBCRIBE REQUEST control messages. The peers MUST close the connection if there are duplicates. The Parameter Value Length field indicates the length of the Parameter Value.

#### GROUP SEQUENCE Parameter

The GROUP SEQUENCE parameter (key 0x00) identifies the group within the track to start delivering objects. The publisher MUST start delivering the objects from the most recent group, when this parameter is omitted. This parameter is applicable in SUBSCRIBE REQUEST message.

#### OBJECT SEQUENCE Parameter
The OBJECT SEQUENCE parameter (key 0x01) identifies the object with the track to start delivering objects. The `GROUP SEQUENCE` parameter MUST be set to identify the group under which to start delivery. The publisher MUST start delivering from the beginning of the selected group when this parameter is omitted. This parameter is applicable in SUBSCRIBE REQUEST message.

#### AUTHORIZATION INFO Parameter
AUTHORIZATION INFO parameter (key 0x02) identifies track's authorization information. This parameter is populated for cases where the authorization is required at the track level. This parameter is applicable in SUBSCRIBE REQUEST and ANNOUNCE messages.


## ANNOUNCE OK {#message-announce-ok}

The receiver sends an `ANNOUNCE OK` control message to acknowledge the successful authorization and acceptance of an ANNOUNCE message.

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

The receiver sends an  `ANNOUNCE ERROR` control message for tracks that failed authorization.

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

* Reason Phrase Length:
The length in bytes of the reason phrase.

* Reason Phrase:
Provides the reason for the announcement error.


## GOAWAY {#message-goaway}
The server sends a `GOAWAY` message to force the client to reconnect.
This is useful for server maintenance or reassignments without severing the QUIC connection.
The server can be a producer or a consumer.

The server:

* MAY initiate a graceful shutdown by sending a GOAWAY message.
* MUST close the QUIC connection after a timeout with the GOAWAY error code ({{session-termination}}).
* MAY close the QUIC connection with a different error code if there is a fatal error before shutdown.
* SHOULD wait until the `GOAWAY` message and any pending streams have been fully acknowledged, plus an extra delay to ensure they have been processed.

The client:

* MUST establish a new transport session upon receipt of a `GOAWAY` message, assuming it wants to continue operation. 
* SHOULD establish the new transport session using a different QUIC connection to that on which it received the GOAWAY message.
* SHOULD remain connected on both connections for a short period, processing objects from both in parallel.

# Security Considerations
TODO: Expand this section. 

## Resource Exhaustion
Live content requires significant bandwidth and resources.
Failure to set limits will quickly cause resource exhaustion.

MoQTransport uses QUIC flow control to impose resource limits at the network layer.
Endpoints SHOULD set flow control limits based on the anticipated bitrate.

Endpoints MAY impose a MAX STREAM count limit which would restrict the number of concurrent streams which a MoQTransport Streaming Format could have in flight.

The producer prioritizes and transmits streams out of order. Streams might be starved indefinitely during congestion. The producer and consumer MUST cancel a stream, preferably the lowest priority, after reaching a resource limit.

# IANA Considerations {#iana}

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

TODO: the MoQTransport spec should establish the IANA registration table for MoQtransport Streaming Formats. Each MoQTransport streaming format can then register its type in that table. The MoQT Streaming Format type MUST be carried as the leading varint in catalog track objects.


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
