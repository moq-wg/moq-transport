---
title: "Warp - Live Media Transport over QUIC"
abbrev: WARP
docname: draft-lcurley-warp-latest
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
  URI: RFC3986

  ISOBMFF:
    title: "Information technology — Coding of audio-visual objects — Part 12: ISO Base Media File Format"
    date: 2015-12

informative:
  CMAF:
    title: "Information technology -- Multimedia application format (MPEG-A) -- Part 19: Common media application format (CMAF) for segmented media"
    date: 2020-03
  NewReno: RFC6582
  BBR: I-D.cardwell-iccrg-bbr-congestion-control-02

--- abstract

This document defines the core behavior for Warp, a live media transport protocol over QUIC.
Media is split into objects based on the underlying media encoding and transmitted independently over QUIC streams.
QUIC streams are prioritized based on the send order, allowing less important objects to be starved or dropped during congestion.

--- middle


## Introduction
Warp is a live media transport protocol that utilizes the QUIC network protocol {{QUIC}},
either directly or via WebTransport {{WebTransport}}.

* {{motivation}} covers the background and rationale behind Warp.
* {{objects}} covers how media is fragmented into objects.
* {{transport-protocols}} covers aspects of setting up a MoQ transport session.
* {{stream-mapping}} covers how QUIC is used to transfer media.
* {{priority-congestion}} covers protocol considerations on prioritization schemes and congestion response overall.
* {{relays-moq}} covers behavior at the relay entities.
* {{messages}} covers how messages are encoded on the wire.
* {{containers}} covers how media tracks are packaged.


## Terms and Definitions

{::boilerplate bcp14-tagged}

Commonly used terms in this document are described below.

Bitstream:

: A continunous series of bytes.

Client:

: The party initiating a Warp session.

Codec:

: A compression algorithm for audio or video.

Congestion:

: Packet loss and queuing caused by degraded or overloaded networks.

Consumer:

: A QUIC endpoint receiving media over the network. This could be the media player or middleware.

Container:

: A file format containing timestamps and the codec bitstream

Decoder:

: A endpoint responsible for a deflating a compressed media stream into raw frames.

Decode Timestamp (DTS):

: A timestamp indicating the order that frames/samples should be fed to the decoder.

Encoder:

: A component responsible for creating a compressed media stream out of raw frames.

Frame:

: An video image or group of audio samples to be rendered at a specific point in time.

I-frame:

: A frame that does not depend on the contents of other frames; effectively an image.

Group of pictures (GoP):

: A I-frame followed by a sequential series of dependent frames.

Group of samples:

: A sequential series of audio samples starting at a given timestamp.

Player:

: A component responsible for presenting frames to a viewer based on the presentation timestamp.

Presentation Timestamp (PTS):

: A timestamp indicating when a frames/samples should be presented to the viewer.

Producer:

: A QUIC endpoint sending media over the network. This could be the media encoder or middleware.

Server:

: The party accepting an incoming Warp session.

Slice:

: A section of a video frame. There may be multiple slices per frame.

Track:

: An encoded bitstream, representing a single media component (ex. audio, video, subtitles) that makes up the larger broadcast.

Transport session:

: Either a native QUIC connection, or a WebTransport session used to transmit the data.

Variant:

: A track with the same content but different encoding as another track. For example, a different bitrate, codec, language, etc.

## Notational Conventions

This document uses the conventions detailed in Section 1.3 of {{!RFC9000}} when describing the binary encoding.

This document also defines an additional field type for binary data:

x (b):
: Indicates that x consists of a variable length integer, followed by that many bytes of binary data.


# Model

## Objects {#model-object}

The basic element of Warp is an *object*. An object is a single addressable
cacheable unit whose payload is a sequence of bytes.  An object MAY depend on other 
objects to be decoded. All objects belong to a group {{model-group}}. Objects carry 
associated metadata such as priority, TTL or other information usable by a relay, 
but relays MUST treat object payloads as opaque.

DISCUSS: Can an object be partially decodable by an endpoint?

Authors agree that an object is always partially *forwardable* by a relay but
disagree on whether a partial object can be used by a receiving endpoint.

Option 1: A receiver MAY start decoding an object before it has been completely received

Example: sending an entire GOP as a single object.  A receiver can decode the
GOP from the beginning without having the entire object present, and the object's
tail could be dropped.  Sending a GOP as a group of not-partially-decodable
objects might incur additional overhead on the wire and/or additional processing of 
video segments at a sender to find object boundaries.

Partial decodability could be another property of an object.

Option 2: A receiver MUST NOT start decoding an object before it has completely arrived

Objects could be end-to-end encrypted and the receiver might not be able to
decrypt or authenticate an object until it is fully present.  Allowing Objects
to span more than one useable unit may create more than one viable application
mapping from media to wire format, which could be confusing for protocol users.

## Groups {#model-group}
A *group* is sequence of objects.
Each group is independent and behaves as a join point for new subscribers.

An object MUST be decodable after the delivery of all prior objects within the same group.
This implies that the first object within a group MUST NOT depend on other objects.
The application MAY use the sequence number to perform ordering and detect gaps within a group.

A sender SHOULD selectively transmit objects based on group membership.
For example, the sender could transmit only the newest group to new subscriber, as the objects are then guaranteed to be decodable.
However, the sender MUST still transmit objects based on the priority {{send-order}}, not based on the group sequence number.

A decoder MAY use objects from prior groups when using a self-correcting encoding scheme.
For example, an audio decoder should not be reinitialized at group boundaries, otherwise it causes a noticeable blip.
Likewise, an video decoder may temporarily reference a prior group when using intra-refresh encoding.


## Track {#model-track}

A Track is the central concept within the MoQ Transport protocol for delivering media and is made up of sequence of objects ({{model-object}}) organized in the form of groups ({{model-group}}).

A track is a transform of a uncompressed media or metadata using a specific encoding process, a set of parameters for that encoding, and possibly an encryption process. The MoQ Transport protocol is designed to transport tracks.

### Full Track Name {#track-fn}

Tracks are identified by a globally unique identifier, called "Full Track Name" and defined as shown below:

~~~~~~~~~~~~~~~
Full Track Name = Track Namespace  "/"  Track Name
~~~~~~~~~~~~~~~

This document does not define the exact mechanism of naming Track Namespaces. Applications building on top of MoQ MUST ensure that the mechanism used guarantees global uniqueness; for instance, an application could use domain names as track namespaces. Track Namespace is followed by the application context specific Track Name, encoded as an opaque string. 

~~~
Example: 1
Track Namespace = videoconferencing.example.com
Track Name = meeting123/audio
Full Track Name = videoconferencing.example.com/meeting123/audio

Example: 2
Track Namespace = livestream.example
Track Name = uaCafDkl123/audio
Full Track Name = livestream.example/uaCafDkl123/audio
~~~

### Connection URL

Each track MAY have one or more associated connection URLs specifying network hosts through which a track may be accessed. The syntax of the Connection URL and the associated connection setup procedures are specific to the underlying transport protocol usage {{transport-protocols}}.


## Session
A transport session is established for each track bundle.
The client issues a CONNECT request with a URL which the server uses for identification and authentication.
All control messages and prioritization occur within the context of a single transport session, which means a single track bundle.
When WebTransport is used, multiple transport sessions may be pooled over a single QUIC connection for efficiency.

## Example
As an example, consider a scenario where `example.org` hosts a simple live stream that anyone can subscribe to.
That live stream would be a single track bundle, accessible via the WebTransport URL: `https://example.org/livestream`.
In a simple scenario, the track bundle would contain only two media tracks, one with audio and one with video.
In a more complicated scenario, the track bundle could multiple tracks with different formats, encodings, bitrates, and quality levels, possibly for the same content.
The receiver learns about each available track within the bundle via the catalog, and can choose to subscribe to a subset.


# Motivation

## Latency
In a perfect world, we could deliver live media at the same rate it is produced.
The end-to-end latency of a broadcast would be fixed and only subject to encoding and transmission delays.
Unfortunately, networks have variable throughput, primarily due to congestion.

Attempting to deliver media encoded at a higher bitrate than the network can support causes queuing.
This queuing can occur anywhere in the path between the encoder and decoder.
For example: the application, the OS socket, a wifi router, within an ISP, or generally anywhere in transit.

If nothing is done, new frames will be appended to the end of a growing queue and will take longer to arrive than their predecessors, increasing latency.
Our job is to minimize the growth of this queue, and if necessary, bypass the queue entirely by dropping content.

The speed at which a media protocol can detect and respond to queuing determines the latency.
We can generally classify existing media protocols into two categories based on the underlying network protocol:

* TCP-based media protocols (ex. RTMP, HLS, DASH) are popular due to their simplicity.
Media is served/consumed in decode order while any networking is handled by the TCP layer.
However, these protocols primarily see usage at higher latency targets due to their relatively slow detection and response to queuing.

* UDP-based media protocols (ex. RTP, WebRTC, SRT) can side-step the issues with TCP and provide lower latency with better queue management.
However the media protocol is now responsible for fragmentation, congestion control, retransmissions, receiver feedback, reassembly, and more.
This added complexity significantly raises the implementation difficulty and hurts interoperability.

A goal of this draft is to get the best of both worlds: a simple protocol that can still rapidly detect and respond to congestion.
This is possible with the emergence of QUIC, designed to fix the shortcomings of TCP.

## Universal
The media protocol ecosystem is fragmented; each protocol has it's own niche.
Specialization is often a good thing, but we believe there's enough overlap to warrant consolidation.

For example, a service might simultaneously ingest via WebRTC, SRT, RTMP, and/or a custom UDP protocol depending on the broadcaster.
The same service might then simultaneously distribute via WebRTC, LL-HLS, HLS, (or the DASH variants) and/or a custom UDP protocol depending on the viewer.

These media protocols are often radically different and not interoperable; requiring transcoding or transmuxing.
This cost is further increased by the need to maintain separate stacks with different expertise requirements.

A goal of this draft is to cover a large spectrum of use-cases. Specifically:

* Consolidated contribution and distribution.
The primary difference between the two is the ability to fanout.
How does a CDN know how to forward media to N consumers and how does it reduce the encoded bitrate during congestion?
A single protocol can cover both use-cases provided relays are informed on how to forward and drop media.

* A configurable latency versus quality trade-off.
The producer (broadcaster) chooses how to encode and transmit media based on the desired user experience.
Each consumer (viewer) chooses how long to wait for media based on their desired user experience and network.
We want an experience that can vary from real-time and lossy for one viewer, to delayed and loss-less for another viewer, without separate encodings or protocols.

A related goal is to not reinvent how media is encoded.
The same codec bitstream and container should be usable between different protocols.

## Relays
The prevailing belief is that UDP-based protocols are more expensive and don't "scale".
While it's true that UDP is more difficult to optimize than TCP, QUIC itself is proof that it is possible to reach performance parity.
In fact even some TCP-based protocols (ex. RTMP) don't "scale" either and are exclusively used for contribution as a result.

The ability to scale a media protocol actually depends on relay support: proxies, caches, CDNs, SFUs, etc.
The success of HTTP-based media protocols is due to the ability to leverage traditional HTTP CDNs.

It's difficult to build a CDN for media protocols that were not designed with relays in mind.
For example, an relay has to parse the underlying codec to determine which RTP packets should be dropped first, and the decision is not deterministic or consistent for each hop.
This is the fatal flaw of many UDP-based protocols.

A goal of this draft is to treat relays as first class citizens.
Any identification, reliability, ordering, prioritization, caching, etc is written to the wire in a header that is easy to parse.
This ensures that relays can easily route/fanout media to the final destination.
This also ensures that congestion response is consistent at every hop based on the preferences of the media producer.

## Bandwidth Management and Congestion Response
TODO: Add motivation text regarding bw management techniques in
response to congestion. Also refer to {{priority-congestion}} for
further details.

# Objects
Warp works by splitting media into objects that can be transferred over QUIC streams.

* The encoder determines how to fragment the encoded bitstream into objects ({{media}}).
* Objects are assigned an intended send order that should be obeyed during congestion ({{send-order}})
* The decoder receives each objects and skips any objects that do not arrive in time ({{decoder}}).

## Media
An encoder produces one or more codec bitstreams for each track.
The decoder processes the codec bitstreams in the same order they were produced, with some possible exceptions based on the encoding.
See the appendix for an overview of media encoding ({{appendix.encoding}}).

Warp works by fragmenting the bitstream into objects that can be transmitted somewhat independently.
Depending on how the objects are fragmented, the decoder has the ability to safely drop media during congestion.
See the appendix for fragmentation examples ({{appendix.examples}})

A media object:

* MUST contain a single track.
* MUST be in decode order. This means an increasing DTS.
* MAY contain any number of frames/samples.
* MAY have gaps between frames/samples.
* MAY overlap with other objects. This means timestamps may be interleaved between objects.

Media objects are encoded using a specified container ({{containers}}).

## Send Order
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

TODO: Refer to Congestion Response and Priorirization Section for further details on various proposals.

## Groups
TODO: Add text describing interation of group and intra object priorities within a group and their relation to congestion response. Add how it refers to {{priority-congestion}}

## Decoder
The decoder will receive multiple objects in parallel and out of order.

Objects arrive in send order, but media usually needs to be processed in decode order.
The decoder SHOULD use a buffer to reassmble objects into decode order and it SHOULD skip objects after a configurable duration.
The amount of time the decoder is willing to wait for an object (buffer duration) is what ultimately determines the end-to-end latency.

Objects MUST synchronize frames within and between tracks using presentation timestamps within the container.
Objects are NOT REQUIRED to be aligned and the decoder MUST be prepared to skip over any gaps.


# Supported Transport Protocols  {#transport-protocols}

This document defines a protocol that can be used interchangeably both over a QUIC connection directly [QUIC], and over WebTransport [WebTransport].
Both provide streams and datagrams with similar semantics (see {{?I-D.ietf-webtrans-overview, Section 4}});
thus, the main difference lies in how the servers are identified and how the connection is established.

## WebTransport

A Warp server that is accessible via WebTransport can be identified using an HTTPS URI ({{!RFC9110, Section 4.2.2}}).
A Warp transport session can be established by sending an extended CONNECT request to the host and the path indicated by the URI,
as described in {{WebTransport, Section 3}}.

## Native QUIC

A Warp server that is accessible via native QUIC can be identified by a URI with a "moq" scheme.
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

Warp endpoints communicate over QUIC streams. Every stream is a sequence of messages, framed as described in {{messages}}.

The first stream opened is a client-initiated bidirectional stream where the peers exchange SETUP messages ({{message-setup}}). The subsequent streams MAY be either unidirectional and bidirectional. For exchanging media, an application would typically send a unidirectional stream containing a single OBJECT message ({{message-object}}).

Messages SHOULD be sent over the same stream if ordering is desired.


## Prioritization
Warp utilizes stream prioritization to deliver the most important content during congestion.

TODO: Revisit the prioritization scheme and possibly move some of this to {{priority-congestion}}.

The producer may assign a numeric delivery order to each object ({{send-order}})

This is a strict prioritization scheme, such that any available bandwidth is allocated to streams in ascending priority order.
The sender SHOULD prioritize streams based on the send order.
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
Warp encodes the delivery information for a stream via OBJECT headers ({{message-object}}).

A relay SHOULD prioritize streams ({{prioritization}}) based on the send order.
A relay MAY change the send order, in which case it SHOULD update the value on the wire for future hops.

A relay that reads from a stream and writes to stream in order will introduce head-of-line blocking.
Packet loss will cause stream data to be buffered in the QUIC library, awaiting in order delivery, which will increase latency over additional hops.
To mitigate this, a relay SHOULD read and write QUIC stream data out of order subject to flow control limits.
See section 2.2 in {{QUIC}}.

## Congestion Control
As covered in the motivation section ({{motivation}}), the ability to prioritize or cancel streams is a form of congestion response.
It's equally important to detect congestion via congestion control, which is handled in the QUIC layer {{QUIC-RECOVERY}}.

Bufferbloat is caused by routers queueing packets for an indefinite amount of time rather than drop them.
This latency significantly reduces the ability for the application to prioritize or drop media in response to congestion.
Senders SHOULD use a congestion control algorithm that reduces this bufferbloat (ex. {{BBR}}).
It is NOT RECOMMENDED to use a loss-based algorithm (ex. {{NewReno}}) unless the network fully supports ECN.

Live media is application-limited, which means that the encoder determines the max bitrate rather than the network.
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
No error occured, however the endpoint no longer desires to send or receive media.

* Generic Error
An unclassified error occured.

* Unauthorized:
The endpoint breached an agreement, which MAY have been pre-negotiated by the application.

* GOAWAY:
The endpoint successfully drained the session after a GOAWAY was initiated ({{message-goaway}}).

# Prioritization and Congestion Response Considerations {#priority-congestion}

TODO: This is a placeholder section to capture details on
how the Moq Transport protocol deals with prioritization and congestion overall. Having its own section helps reduce merge conflicts and allows us to reference it from other parts.

This section is expected to cover detailson:

- Prioritization Schemes
- Congestion Algorithms and impacts 
- Mapping considerations for one object per stream vs multiple objects per stream
- considerations for merging multiple streams across domans onto single connection and interactions with specific prioritization schemes

# Relays {#relays-moq}

The Relays play an important role for enabling low latency media delivery within the MoQ architecture. This specification allows for a delivery protocol based on a publish/subscribe metaphor where some endpoints, called publishers, publish media objects and
some endpoints, called subscribers, consume those media objects. Relays leverage this publish/subscribe metaphor to form an overlay delivery network similar/in-parallel to what CDN provides today.

Relays serves as policy enforcement points by validating subscribe
and publish requests to the tracks.

## Subscriber Interactions
TODO: This section shall cover relay handling of subscriptions.

## Publisher Interactions
TODO: This section shall cover relay handling of publishes.

## Relay Discovery and Failover
TODO: This section shall cover aspects of relay failover and protocol interactions

## Restoring connections through relays
TODO: This section shall cover reconnect considerations for clients when moving between the Relays

## Congestion Response at Relays
TODO: Refer to {{priority-congestion}}. Add details describe 
relays behavior when merging or splitting streams and interactions
with congestion response.

# Messages
Both unidirectional and bidirectional Warp streams are sequences of length-deliminated messages.

~~~
Warp Message {
  Message Type (i),
  Message Length (i),
  Message Payload (..),
}
~~~
{: #warp-message-format title="Warp Message"}

The Message Length field contains the length of the Message Payload field in bytes.
A length of 0 indicates the message is unbounded and continues until the end of the stream.

|------|----------------------------------------------|
| ID   | Messages                                     |
|-----:|:---------------------------------------------|
| 0x0  | OBJECT ({{message-object}})                  |
|------|----------------------------------------------|
| 0x1  | SETUP ({{message-setup}})                    |
|------|----------------------------------------------|
| 0x2  | CATALOG ({{message-catalog}})                |
|------|----------------------------------------------|
| 0x3  | SUBSCRIBE REQUEST ({{message-subscribe-req}})|
|------|----------------------------------------------|
| 0x4  | SUBSCRIBE OK ({{message-subscribe-ok}})      |
|------|----------------------------------------------|
| 0x5  | SUBSCRIBE ERROR ({{message-subscribe-error}})|
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
{: #warp-setup-format title="Warp SETUP Message"}

The Parameter Value Length field indicates the length of the Parameter Value.

The client offers the list of the protocol versions it supports; the server MUST reply with one of the versions offered by the client. If the server does not support any of the versions offered by the client, or the client receives a server version that it did not offer, the corresponding peer MUST close the connection.

The SETUP parameters are described in the {{setup-parameters}} section.


## OBJECT {#message-object}
A OBJECT message contains a single media object associated with a specified track, as well as associated metadata required to deliver, cache, and forward it.

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
{: #warp-object-format title="Warp OBJECT Message"}

* Track ID:
The track identifier obtained as part of subscription and/or publish control message exchanges.

* Group Sequence :
The object is a member of the indicated group {{model-group}} within the track.
The sequence starts at 0, increasing sequentially for each group within the track.

* Object Sequence:
The order of the object within the group.
The sequence starts at 0, increasing sequentially for each object within the group.

* Object Send Order:
An integer indicating the object send order ({{send-order}}).

* Object Payload:
The format depends on the track container ({{containers}}).
This is a media bitstream intended for the decoder and SHOULD NOT be processed by a relay.


## CATALOG {#message-catalog}
The sender advertises tracks via the CATALOG message.
The receiver can then SUBSCRIBE to the indiciated tracks by ID.

The format of the CATALOG message is as follows:

~~~
CATALOG Message {
  Track Count (i),
  Track Descriptors (..)
}
~~~
{: #warp-catalog-format title="Warp CATALOG Message"}

* Track Count:
The number of tracks within the catalog.


For each track, there is a track descriptor with the format:

~~~
Track Descriptor {
  Track ID (i),
  Container Format (i),
  Container Init Payload (b)
}
~~~
{: #warp-track-descriptor title="Warp Track Descriptor"}

* Track ID:
A unique identifier for the track within the track bundle.

* Container Format:
The container format as defined in {{containers}}.

* Container Init Payload:
A container-specific payload as defined in {{containers}}.
This contains base information required to decode OBJECT messages, such as codec parameters.


An endpoint MUST NOT send multiple CATALOG messages.
A future draft will add the ability to add/remove/update tracks.

## SUBSCRIBE REQUEST {#message-subscribe-req}

Entities that intend to receive media will do so via subscriptions to one or more tracks. The information for the tracks can be obtained via catalog or from incoming SUBSCRIBE REQUEST messages.

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
{: #warp-subscribe-format title="Warp SUBSCRIBE REQUEST Message"}


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
{: #warp-subscribe-ok format title="Warp SUBSCRIBE OK Message"}

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
{: #warp-subscribe-error format title="Warp SUBSCRIBE ERROR Message"}

* Full Track Name:
Identifies the track in the request message for which this
response is provided.

* Error Code:
Identifies an integer error code for subscription failure.

* Reason Phrase:
Provides the reason for subscription error and `Reason Phrase Length` field carries its length.


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

# SETUP Parameters

The SETUP message ({{message-setup}}) allows the peers to exchange arbitrary parameters before any media is exchanged. It is the main extensibility mechanism of Warp. The peers MUST ignore unknown parameters. TODO: describe GREASE for those.

Every parameter MUST appear at most once within the SETUP message. The peers SHOULD verify that and close the connection if a parameter appears more than once.

The ROLE parameter is mandatory for the client. All of the other parameters are optional.

## ROLE parameter {#role}

The ROLE parameter (key 0x00) allows the client to specify what roles it expects the parties to have in the Warp connection. It has three possible values:

0x01:

: Only the client is expected to send media on the connection. This is commonly referred to as *the ingestion case*.

0x02:

: Only the server is expected to send media on the connection. This is commonly referred to as *the delivery case*.

0x03:

: Both the client and the server are expected to send media.

The client MUST send a ROLE parameter with one of the three values specified above. The server MUST close the connection if the ROLE parameter is missing, is not one of the three above-specified values, or it is different from what the server expects based on the application in question.

## PATH parameter {#path}

The PATH parameter (key 0x01) allows the client to specify the path of the MoQ URI when using native QUIC ({{native-quic}}).
It MUST NOT be used by the server, or when WebTransport is used.
If the peer receives a PATH parameter from the server, or when WebTransport is used, it MUST close the connection.

When connecting to a server using a URI with the "moq" scheme,
the client MUST set the PATH parameter to the `path-abempty` portion of the URI;
if `query` is present, the client MUST concatenate `?`, followed by the `query` portion of the URI to the parameter.

# Track Request Parameters {#track-req-params}

The Track Request Parameters identify properties of the track requested in either the PUBLISH REQUEST or SUSBCRIBE REQUEST control messages. Every parameter MUST appear at most once. The peers MUST close the connection if there are duplicates. The Parameter Value Length field indicates the length of the Parameter Value.

### GROUP SEQUENCE Parameter

The GROUP SEQUENCE parameter (key 0x00) identifies the group within the track to start delivering the objects. The publisher MUST start delivering the objects from the most recent group, when this parameter is omitted.

### OBJECT SEQUENCE Parameter
The OBJECT SEQUENCE parameter (key 0x01) identifies the object with the track to start delivering the media. The `GROUP SEQUENCE` parameter MUST be set to identify the group under which to start the media delivery. The publisher MUST start delivering from the beginning of the selected group when this parameter is omitted.

### AUTHORIZATION INFO Parameter
AUTHORIZATION INFO parameter (key 0x02) identifies track's authorization information. This parameter is populated for cases where the authorization is required at the track level.

# Containers
The container format describes how the underlying codec bitstream is encoded.
This includes timestamps, metadata, and generally anything required to decode and display the media.

This draft currently specifies only a single container format.
Future drafts and extensions may specifiy additional formats.

|------|------------------|
| ID   | Container Format |
|-----:|:-----------------|
| 0x0  | fMP4 ({{fmp4}})  |
|------|------------------|

## fMP4
A fragmented MP4 container  {{ISOBMFF}}.

The "Container Init Payload" in a CATALOG message ({{message-catalog}}) MUST consist of a File Type Box (ftyp) followed by a Movie Box (moov).
This Movie Box (moov) consists of Movie Header Boxes (mvhd), Track Header Boxes (tkhd), Track Boxes (trak), followed by a final Movie Extends Box (mvex).
These boxes MUST NOT contain any samples and MUST have a duration of zero.
A Common Media Application Format Header {{CMAF}} meets all these requirements.

The "Object Payload" in an OBJECT message ({{message-object}}) MUST consist of a Segment Type Box (styp) followed by any number of media fragments.
Each media fragment consists of a Movie Fragment Box (moof) followed by a Media Data Box (mdat).
The Media Fragment Box (moof) MUST contain a Movie Fragment Header Box (mfhd) and Track Box (trak) with a Track ID (`track_ID`) matching a Track Box in the initialization fragment.
A Common Media Application Format Segment {{CMAF}} meets all these requirements.

Media fragments can be packaged at any frequency, causing a trade-off between overhead and latency.
It is RECOMMENDED that a media fragment consists of a single frame to minimize latency.


# Security Considerations

## Resource Exhaustion
Live media requires significant bandwidth and resources.
Failure to set limits will quickly cause resource exhaustion.

Warp uses QUIC flow control to impose resource limits at the network layer.
Endpoints SHOULD set flow control limits based on the anticipated media bitrate.

The media producer prioritizes and transmits streams out of order.
Streams might be starved indefinitely during congestion.
The producer and consumer MUST cancel a stream, preferably the lowest priority, after reaching a resource limit.

# IANA Considerations

TODO: fill out currently missing registries:
* Warp version numbers
* SETUP parameters
* Track Request parameters
* Subscribe Error codes
* Track format numbers
* Message types
* Object headers

TODO: register the URI scheme and the ALPN

# Appendix A. Video Encoding {#appendix.encoding}
In order to transport media, we first need to know how media is encoded.
This section is an overview of media encoding.

## Tracks
A broadcast consists of one or more tracks.
Each track has a type (audio, video, caption, etc) and uses a corresponding codec.
There may be multiple tracks, including of the same type for a number of reasons.

For example:

* A track for each codec.
* A track for each resolution and bitrate.
* A track for each language.
* A track for each camera feed.

Tracks can be muxed together into a single container or stream.
The goal of Warp is to independently deliver tracks, and even parts of a track, so this is not allowed.
Each Warp object MUST contain a single track.

## Init {#appendix.init}
Media codecs have a wide array of configuration options.
For example, the resolution, the color space, the features enabled, etc.

Before playback can begin, the decoder needs to know the configuration.
This is done via a short payload at the very start of the media file.
The initialization payload MAY be cached and reused between objects with the same configuration.

## Video {#appendix.video}
Video is a sequence of pictures (frames) with a presentation timestamp (PTS).

An I-frame is a frame with no dependencies and is effectively an image file.
These frames are usually inserted at a frequent interval to support seeking or joining a live stream.
However they can also improve compression when used at scene boundaries.

A P-frame is a frame that references on one or more earlier frames.
These frames are delta-encoded, such that they only encode the changes (motion).
This result in a massive file size reduction for most content outside of few notorious cases (ex. confetti).

A common encoding structure is to only reference the previous frame, as it is simple and minimizes latency:

~~~
 I <- P <- P <- P   I <- P <- P <- P   I <- P ...
~~~

There is no such thing as an optimal encoding structure.
Encoders tuned for the best quality will produce a tangled spaghetti of references.
Encoders tuned for the lowest latency can avoid reference frames to allow more to be dropped.

### B-Frames {#appendix.b-frame}
The goal of video codecs is to maximize compression.
One of the improvements is to allow a frame to reference later frames.

A B-frame is a frame that can reference one or more frames in the future, and any number of frames in the past.
These frames are more difficult to encode/decode as they require buffering and reordering.

A common encoding structure is to use B-frames in a fixed pattern.
Such a fixed pattern is not optimal, but it's simpler for hardware encoding:

~~~
    B     B         B     B         B
   / \   / \       / \   / \       / \
  v   v v   v     v   v v   v     v   v
 I <-- P <-- P   I <-- P <-- P   I <-- P ...
~~~

### Timestamps
Each frame is assigned a presentation timestamp (PTS), indicating when it should be shown relative to other frames.

The encoder outputs the bitstream in decode order, which means that each frame is output after its references.
This makes it easier for the decoder as all references are earlier in the bitstream and can be decoded immediately.

However, this causes problems with B-frames because they depend on a future frame, and some reordering has to occur.
In order to keep track of this, frames have a decode timestamp (DTS) in addition to a presentation timestamp (PTS).
A B-frame will have higher DTS value that its dependencies, while PTS and DTS will be the same for other frame types.

For the example above, this would look like:

~~~
     0 1 2 3 4 5 6 7 8 9 10
PTS: I B P B P I B P B P B
DTS: I   PB  PBI   PB  PB
~~~

B-frames add latency because of this reordering so they are usually not used for conversational latency.

### Group of Pictures {#appendix.gop}
A group of pictures (GoP) is an I-frame followed by any number of frames until the next I-frame.
All frames MUST reference, either directly or indirectly, only the most recent I-frame.

~~~
        GoP               GoP            GoP
+-----------------+-----------------+---------------
|     B     B     |     B     B     |     B
|    / \   / \    |    / \   / \    |    / \
|   v   v v   v   |   v   v v   v   |   v   v
|  I <-- P <-- P  |  I <-- P <-- P  |  I <-- P ...
+-----------------+-----------------+--------------
~~~

This is a useful abstraction because GoPs can always be decoded independently.

### Scalable Video Coding {#appendix.svc}
Some codecs support scalable video coding (SVC), in which the encoder produces multiple bitstreams in a hierarchy.
This layered coding means that dropping the top layer degrades the user experience in a configured way.
Examples include reducing the resolution, picture quality, and/or frame rate.

Here is an example SVC encoding with 3 resolutions:

~~~
      +-------------------------+------------------
   4k |  P <- P <- P <- P <- P  |  P <- P <- P ...
      |  |    |    |    |    |  |  |    |    |
      |  v    v    v    v    v  |  v    v    v
      +-------------------------+------------------
1080p |  P <- P <- P <- P <- P  |  P <- P <- P ...
      |  |    |    |    |    |  |  |    |    |
      |  v    v    v    v    v  |  v    v    v
      +-------------------------+------------------
 360p |  I <- P <- P <- P <- P  |  I <- P <- P ...
      +-------------------------+------------------
~~~

## Audio {#appendix.audio}
Audio is dramatically simpler than video as it is not typically delta encoded.
Audio samples are grouped together (group of samples) at a configured rate, also called a "frame".

The encoder spits out a continuous stream of samples (S):

~~~
S S S S S S S S S S S S S ...
~~~


# Appendix B. Object Examples {#appendix.examples}
Warp offers a large degree of flexibility on how objects are fragmented and prioritized.
There is no best solution; it depends on the desired complexity and user experience.

This section provides a summary of some options available.

## Video

### Group of Pictures
A group of pictures (GoP) is consists of an I-frame and all frames that directly or indirectly reference it ({{appendix.gop}}).
The tail of a GoP can be dropped without causing decode errors, even if the encoding is otherwise unknown, making this the safest option.

It is RECOMMENDED that each object consist of a single GoP.
For example:

~~~
     object 1        object 2     object 3
+---------------+---------------+---------
| I  P  B  P  B | I  P  B  P  B | I  P  B
+---------------+---------------+---------
~~~

Depending on the video encoding, this approach may introduce unnecessary ordering and dependencies.
A better option may be available below.

### Scalable Video Coding
Some codecs support scalable video coding (SVC), in which the encoder produces multiple bitstreams in a hierarchy ({{appendix.svc}}).

When SVC is used, it is RECOMMENDED that each object consist of a single layer and GoP.
For example:

~~~
                object 3              object 6
      +-------------------------+---------------
   4k |  P <- P <- P <- P <- P  |  P <- P <- P
      |  |    |    |    |    |  |  |    |    |
      |  v    v    v    v    v  |  v    v    v
      +-------------------------+--------------

                object 2              object 5
      +-------------------------+---------------
1080p |  P <- P <- P <- P <- P  |  P <- P <- P
      |  |    |    |    |    |  |  |    |    |
      |  v    v    v    v    v  |  v    v    v
      +-------------------------+--------------

                object 1              object 4
      +-------------------------+---------------
 360p |  I <- P <- P <- P <- P  |  I <- P <- P
      +-------------------------+---------------
~~~


### Frames
With full knowledge of the encoding, the encoder MAY can split a GoP into multiple objects based on the frame.
However, this is highly dependent on the encoding, and the additional complexity might not improve the user experience.

For example, we could split our example B-frame structure ({{appendix.b-frame}}) into 13 objects:

~~~
      2     4           7     9           12
+--------+--------+--------+--------+-----------+
|     B  |  B     |     B  |  B     |     B     |
|-----+--+--+-----+-----+--+--+-----+-----+-----+
|  I  |  P  |  P  |  I  |  P  |  P  |  I  |  P  |
+-----+-----+-----+-----+-----+-----+-----+-----+
   1     3     5     6     8     10    11    13
~~~

Objects can be merged with their dependency to reduce the total number of objects.
QUIC streams will deliver each object in order so the QUIC library performs the reordering.

The same GoP structure can be represented using eight objects:

~~~
      2     3           5     6           8
+--------+--------+-----------------+------------
|     B  |  B     |     B  |  B     |     B     |
+--------+--------+--------+--------+-----------+
|  I     P     P  |  I     P     P  |  I     P
+-----------------+-----------------+------------
         1                 4              7
~~~

We can further reduce the number of objects by combining frames that don't depend on each other.
The only restriction is that frames can only reference frames earlier in the object.
For example, non-reference frames can have their own object so they can be prioritized or dropped separate from reference frames.

The same GoP structure can also be represented using six objects, although we've removed the ability to drop individual B-frames:

~~~
    object 2      object 4    object 6
+-------------+-------------+---------
|    B   B    |    B   B    |    B
+-------------+-------------+---------
|  I   P   P  |  I   P   P  |  I   P
+-------------+-------------+---------
    object 1      object 3    object 5
~~~

### Init
Initialization data ({{appendix.init}}) is required to initialize the decoder.
Each object MAY start with initialization data although this adds overhead.

Instead, it is RECOMMENDED to create a init object.
Each media object can then depend on the init object to avoid the redundant overhead.
For example:

~~~
     object 2        object 3     object 5
+---------------+---------------+---------
| I  P  B  P  B | I  P  B  P  B | I  P  B
+---------------+---------------+---------
|              init             |  init
+-------------------------------+---------
              object 1            object 4
~~~


## Audio
Audio ({{appendix.audio}}) is much simpler than video so there's fewer options.

The simplest configuration is to use a single object for each audio track.
This may seem inefficient given the ease of dropping audio samples.
However, the audio bitrate is low and gaps cause quite a poor user experience, when compared to video.

~~~
          object 1
+---------------------------
| S S S S S S S S S S S S S
+---------------------------
~~~

An improvement is to periodically split audio samples into separate objects.
This gives the consumer the ability to skip ahead during severe congestion or temporary connectivity loss.

~~~
     object 1        object 2     object 3
+---------------+---------------+---------
| S  S  S  S  S | S  S  S  S  S | S  S  S
+---------------+---------------+---------
~~~

This frequency of audio objects is configurable, at the cost of additional overhead.
It's NOT RECOMMENDED to create a object for each audio frame because of this overhead.

Since video can only recover from severe congestion with an I-frame, so there's not much point recovering audio at a separate interval.
It is RECOMMENDED to create a new audio object at each video I-frame.

~~~
     object 1        object 3     object 5
+---------------+---------------+---------
| S  S  S  S  S | S  S  S  S  S | S  S  S
+---------------+---------------+---------
| I  P  B  P  B | I  P  B  P  B | I  P  B
+---------------+---------------+---------
     object 2        object 4     object 6
~~~

## Send Order {#appendix.send-order}
The send order ({{send-order}} depends on the desired user experience during congestion:

* if media should be skipped: send order = PTS
* if media should not be skipped: send order = -PTS
* if video should be skipped before audio: audio send order < video send order

The send order may be changed if the content changes.
For example, switching from a live stream (skippable) to an advertisement (unskippable).

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
