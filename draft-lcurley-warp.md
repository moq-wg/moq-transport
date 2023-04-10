---
title: "Warp - Live Transport over QUIC"
abbrev: WARP
docname: draft-lcurley-warp-transport-latest
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

This document defines a transport to deliver media and similar streamable formats over QUIC.
The payload is fragmented (based on the encoding) such that fragments can be dropped or delayed in the event of congestion.
A simple set of instructions is written on the wire such that relays will exhibit the same behavior regardless of the hop.

--- middle


## Introduction
Warp is a live transport protocol that utilizes the QUIC network protocol {{QUIC}}.

* {{model}} is an overview of how the high level concept interact.
* {{quic}} covers how QUIC is used to transfer data.
* {{messages}} covers how messages are encoded on the wire.


## Terms and Definitions

{::boilerplate bcp14-tagged}

Commonly used terms in this document are described below.

Client:

: The party initiating a Warp session.

Congestion:

: Packet loss and queuing caused by degraded or overloaded networks.

Consumer:

: A QUIC endpoint receiving media over the network. This could be the media decoder or middleware.

Producer:

: A QUIC endpoint sending media over the network. This could be the media encoder or middleware.

Server:

: The party accepting an incoming Warp session.

Track:

: An encoded bitstream, representing a single media component (ex. audio, video, subtitles) that makes up the larger broadcast.


## Notational Conventions

This document uses the conventions detailed in Section 1.3 of {{!RFC9000}} when describing the binary encoding.

This document also defines an additional field type for binary data:

x (b):
: Indicates that x consists of a variable length integer, followed by that many bytes of binary data.


# Model

## Objects

The basic element of Warp is an *object*. An object is a single addressable
cacheable unit whose payload is a sequence of bytes.  An object MAY depend on other 
objects to be decoded. An object MUST belong to a group {{groups}}. Objects carry 
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

## Groups

An object group is a sequence of media objects. Beginning of an object group can be used as a point at which the receiver can start consuming a track without having any other object groups available. Object groups have an ID that identifies them uniquely within a track.

DISCUSS: We need to determine what are the exact requirements we need to impose on how the media objects depend on each other. Such requirements would need to address the use case (a join point), while being flexible enough to accomodate scenarios like B-frames and temporal scaling.

## Track
A track in Warp is a combination of *an init object* and a sequence of object groups. An init object is a format-specific self-contained description of the track that is required to decode any object contained within the track, but can also be used as the metadata for track selection.

## Track Bundle
A track bundle is a collection of tracks intended to be delivered together.
Objects within a track bundle may be prioritized relative to each other via the delivery order property.
This allows objects to be prioritized within a track (ex. newer > older) and between tracks (ex. audio > video).
The track bundle contains a catalog indicating the available tracks.

## Session
A WebTransport session is established for each track bundle.
The client issues a CONNECT request with a URL which the server uses for identification and authentication.
All control messages and prioritization occur within the context of a single WebTransport session, which means a single track bundle.
Multiple WebTransport sessions may be pooled over a single QUIC connection for efficiency.

## Example
As an example, consider a scenario where `example.org` hosts a simple live stream that anyone can subscribe to.
That live stream would be a single track bundle, accessible via the WebTransport URL: `https://example.org/livestream`.
In a simple scenario, the track bundle would contain only two media tracks, one with audio and one with video.
In a more complicated scenario, the track bundle could multiple tracks with different formats, encodings, bitrates, and quality levels, possibly for the same content.
The receiver learns about each available track within the bundle via the catalog, and can choose to subscribe to a subset.


# QUIC

## Establishment
A connection is established using WebTransport {{WebTransport}}.

To summarize:
The client issues a HTTP CONNECT request to a URL.
The server returns an "200 OK" response to establish the WebTransport session, or an error status code otherwise.

A WebTransport session exposes the basic QUIC service abstractions.
Specifically, either endpoint may create independent streams which are reliably delivered in order until canceled.

WebTransport can currently operate via HTTP/3 and HTTP/2, using QUIC or TCP under the hood respectively.
TCP introduces head-of-line blocking and will result in a worse experience.
It is RECOMMENDED to use WebTransport over HTTP/3.

### CONNECT
The server uses the HTTP CONNECT request for identification and authorization of a track bundle.
The specific mechanism is left up to the application.
For example, an identifier and authentication token could be included in the path.

The server MAY return an error status code for any reason, for example a 403 when the client is forbidden.
Otherwise the server MUST respond with a "200 OK" to establish the WebTransport session.

## Streams
Warp endpoints communicate over QUIC streams. Every stream is a sequence of messages, framed as described in {{messages}}.

The first stream opened is a client-initiated bidirectional stream where the peers exchange SETUP messages ({{message-setup}}). The subsequent streams MAY be either unidirectional and bidirectional. For exchanging media, an application would typically send a unidirectional stream containing a single OBJECT message ({{message-object}}).

Messages SHOULD be sent over the same stream if ordering is desired.


## Prioritization
Warp utilizes stream prioritization to deliver the most important content during congestion.

The producer may assign a numeric delivery order to each object.
This is a strict prioritization scheme, such that any available bandwidth is allocated to streams in ascending priority order.
The sender SHOULD prioritize streams based on the delivery order.
If two streams have the same delivery order, they SHOULD receive equal bandwidth (round-robin).

QUIC supports stream prioritization but does not standardize any mechanisms; see Section 2.3 in {{QUIC}}.
In order to support prioritization, a QUIC library MUST expose a API to set the priority of each stream.
This is relatively easy to implement; the next QUIC packet should contain a STREAM frame for the next pending stream in priority order.

The sender MUST respect flow control even if means delivering streams out of delivery order.
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

A relay SHOULD prioritize streams ({{prioritization}}) based on the delivery order.
A relay MAY change the delivery order, in which case it SHOULD update the value on the wire for future hops.

A relay that reads from a stream and writes to stream in order will introduce head-of-line blocking.
Packet loss will cause stream data to be buffered in the QUIC library, awaiting in order delivery, which will increase latency over additional hops.
To mitigate this, a relay SHOULD read and write QUIC stream data out of order subject to flow control limits.
See section 2.2 in {{QUIC}}.

## Congestion Control
The ability to prioritize or cancel streams is a form of congestion response.
It's equally important to detect congestion via congestion control, which is handled in the QUIC layer {{QUIC-RECOVERY}}.

Bufferbloat is caused by routers queueing packets for an indefinite amount of time rather than drop them.
This latency significantly reduces the ability for the application to prioritize or drop media in response to congestion.
Senders SHOULD use a congestion control algorithm that reduces this bufferbloat (ex. {{BBR}}).
It is NOT RECOMMENDED to use a loss-based algorithm (ex. {{NewReno}}) unless the network fully supports ECN.

Live media is application-limited, which means that the encoder determines the max bitrate rather than the network.
Most TCP congestion control algorithms will only increase the congestion window if it is full, limiting the upwards mobility when application-limited.
Senders SHOULD use a congestion control algorithm that is designed for application-limited flows (ex. GCC).
Senders MAY periodically pad the connection with QUIC PING frames to fill the congestion window.

## Termination
The WebTransport session can be terminated at any point with CLOSE\_WEBTRANSPORT\_SESSION capsule, consisting of an integer code and string message.

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

|------|-----------------------------------|
| ID   | Messages                          |
|-----:|:----------------------------------|
| 0x0  | OBJECT ({{message-object}})       |
|------|-----------------------------------|
| 0x1  | SETUP ({{message-setup}})         |
|------|-----------------------------------|
| 0x3  | SUBSCRIBE ({{message-subscribe}}) |
|------|-----------------------------------|
| 0x10 | GOAWAY ({{message-goaway}})       |
|------|-----------------------------------|

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
  Object Delivery Order (i),
  Object Payload (b),
}
~~~
{: #warp-object-format title="Warp OBJECT Message"}

* Track ID:
The track identifier.

* Group Sequence :
An integer always starts at 0 and increases sequentially at the original media publisher.
Group sequences are scoped under a Track.

* Object Sequence:
An integer always starts at 0 with in a Group and increases sequentially.
Object Sequences are scoped to a Group.

* Object Delivery Order:
An integer indicating the object delivery order.

* Object Payload:
This is a media bitstream intended for the decoder and SHOULD NOT be processed by a relay.

## SUBSCRIBE {#message-subscribe}
The receiver sends a SUBSCRIBE message to indicate that it wishes to receive the indicated tracks.

The format of SUBSCRIBE is as follows:

~~~
SUBSCRIBE Message {
  Track Count (i),
  Track IDs (..),
}
~~~
{: #warp-subscribe-format title="Warp SUBSCRIBE Message"}

* Track Count:
The number of track IDs that follow.
This MAY be zero to unsubscribe to all tracks.

* Track IDs:
A list of varint track IDs.


Only the most recent SUBSCRIBE message is active.
SUBSCRIBE messages MUST be sent on the same QUIC stream to preserve ordering.


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

* MUST establish a new WebTransport session to the provided URL upon receipt of a `GOAWAY` message.
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
* Track format numbers
* Message types
* Object headers


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
