---
title: "Warp - Segmented Live Video Transport"
abbrev: WARP
docname: draft-lcurley-warp-00
date: {DATE}
category: info

ipr: trust200902
area: General
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

normative:
  QUIC: RFC9000
  WebTransport: I-D.ietf-webtrans-http3

  ISOBMFF:
    title: "Information technology — Coding of audio-visual objects — Part 12: ISO Base Media File Format"
    date: 2015-12

informative:
  CMAF:
    title: "Information technology -- Multimedia application format (MPEG-A) -- Part 19: Common media application format (CMAF) for segmented media"
    date: 2020-03

--- abstract

This document defines the core behavior for Warp, a segmented live video transport protocol.
Warp maps live media to QUIC streams based on the underlying media encoding.
Media is prioritized to minimize latency during congestion.

--- middle

# Overview
Warp is a live video transport protocol that utilizes the QUIC network protocol {{QUIC}}.

QUIC streams ({{streams}}) are used to transfer segments and messages. These streams are prioritized based on the contents, such that the most important media is delivered during congestion.

Segments ({{segments}}) are fragmented MP4 containers {{ISOBMFF}}. Initialization segments contain track metadata while media segments contain media samples.

Messages ({{messages}}) are sent over streams alongside segments. These are used to carry necessary metadata about segments and control playback.

## Terms and Definitions

{::boilerplate bcp14-tagged}

Commonly used terms in this document are described below.

Frame:

: An video image or group of audio samples to be rendered at a specific point in time.

I-frame:

: A frame that does not depend on the contents of other frames.

Group of pictures (GOP):

: A I-frame followed by a sequential series of dependent frames.

Group of samples:

: A sequential series of audio samples starting at a given timestamp.

Segment:

: A sequence of video frames and/or audio samples serialized into a container.

Presentation Timestamp (PTS):

: A point in time when video/audio should be presented to the viewer.

Media producer:

: An endpoint sending media over the network.

Media consumer:

: An endpoint receiving media over the network.

Congestion:

: Packet loss and queuing caused by degraded or overloaded networks.


# Streams
Warp uses the QUIC stream API to transfer media.

Both endpoints MAY create unidirectional QUIC streams. An endpoint SHOULD discard any data received over a bidirectional stream.

Each stream consists of byte data with an eventual final size. A stream is reliably delivered in order unless cancelled early with an error code.

The delivery of each stream is independent. The sender can prioritize their delivery ({{prioritization}}); intentionally starving streams in favor of more important streams.

## Establishment
A connection is established using WebTransport over HTTP/3 {{WebTransport}}. This involves establishing a HTTP/3 connection, issuing a CONNECT request to establish a WebTransport session, and exposing the underlying QUIC stream API while the session is active.

The application is responsible for authentication based on the CONNECT request.

The application is responsible for determining if an endpoint is a media producer, consumer, or both. A media consumer does not send segments.

## Contents
Each stream consists of MP4 top-level boxes {{ISOBMFF}} concatenated together.

* Segments ({{segments}}) contain media samples and additional metadata. These are 'ftyp', 'moov', 'styp', 'moof', and 'mdat' boxes.
* Messages ({{messages}}) control playback or carry metadata about segments. These are 'warp' boxes.

Each 'ftyp' box MUST be preceded by a 'warp' box indicating that it is an initialization segment ({{message-init}}). Each 'styp' box MUST be preceded by a 'warp' box indicating that it is a media segment ({{message-segment}}).

A stream MUST start with a message and MAY contain multiple messages. A stream MUST NOT contain multiple segments.

## Prioritization
Warp utilizes precedence to deliver the most important content during congestion.

The media producer assigns a numeric presidence to each stream. This is a strict prioritzation scheme, such that any available bandwidth is allocated to streams in descending order. QUIC supports stream prioritization but does not standardize any mechanisms; see Section 2.3 in {{QUIC}}. The media producer MUST support sending priorized streams. The sender MAY choose to delay retransmitting lower priority streams when possible within QUIC flow control limits.

The media consumer determines how long to wait for a given segment (buffer size) before skipping ahead. The media consumer MAY cancel a skipped segment to save bandwidth, or leave it downloading in the background (ex. to support rewind).

Prioritization allows a single media producer to support multiple media consumers with different latency targets. For example, one consumer could have a 1s buffer to minimize latency, while another conssumer could have a 5s buffer to improve quality, while a yet another consumer could have a 30s buffer to receive all media (ex. VOD recorder).

### Live Content
Live content is encoded and delivered in real-time. Media delivery is blocked on the encoder throughput, except during congestion causing limited network throughput. To best deliver live content:

* Audio streams SHOULD be prioritized over video streams. This allows the media consumer to skip video while audio continues uninterupted during congestion.
* Newer video streams SHOULD be prioritized over older video streams. This allows the media consumer to skip older video content during congestion.

For example, this formula will prioritze audio segments, but only up to 3s in the future:

~~~
  if is_audio:
    precedence = timestamp + 3s
  else:
    precedence = timestamp
~~~

### Recorded Content
Recorded content has already been encoded. Media delivery is blocked exclusively on network throughput.

Warp is primarily designed for live content, but can switch to head-of-line blocking by changing stream prioritization. This is also useful for content that should not be skipped over, such as advertisements. To enable head-of-line blocking:

* Audio streams SHOULD be prioritized equally with video streams.
* Older streams SHOULD be prioritized over newer streams.

For example, this formula will prioritize older segments:

~~~
  precedence = -timestamp
~~~

## Cancellation
During congestion, prioritization intentionally cause stream starvation for the lowest priority streams. Some form of starvation will last until the network fully recovers, which may be indefinite.

The media consumer SHOULD cancel a stream (via a QUIC `STOP_SENDING` frame) after it has been skipped to save bandwidth. The media producer SHOULD reset the lowest priority stream (via QUIC `RESET_STREAM` frame) when nearing resource limits. Both of these actions will effectively drop the tail of the segment.

## Middleware
Media may go through multiple hops and processing steps on the path from the broadcaster to player. The full effectiveness of warp as an end-to-end protocol depends on middleware support.

* Middleware MUST maintain stream idependence to avoid introducing head-of-line blocking.
* Middleware SHOULD maintain stream prioritization when traversing networks susceptible to congestion.
* Middleware MUST forward the `priority` message ({{message-priority}}) for downstream servers.

# Segments
The live stream is split into segments before being transferred over the network. Segments are fragmented MP4 files as defined by {{ISOBMFF}}.

There are two types of segments: initialization and media.

## Initialization
Initialization segments contain track metadata but no sample data.

Initialization segments MUST consist of a File Type Box ('ftyp') followed by a Movie Box ('moov'). This Movie Box consists of Movie Header Boxes ('mvhd'), Track Header Boxes ('tkhd'), Track Boxes ('trak'), followed by a final Movie Extends Box ('mvex'). These boxes MUST NOT contain any samples and MUST have a duration of zero.

Note that a Common Media Application Format Header {{CMAF}} meets all these requirements.

## Media
Media segments contain media samples for a single track.

Media segments MUST consist of a Segment Type Box ('styp') followed by at least one media fragment. Each media fragment consists of a Movie Fragment Box ('moof') followed by a Media Data Box ('mdat'). The Media Fragment Box MUST contain a Movie Fragment Header Box ('mfhd') and Track Box ('trak') with a Track ID ('track_ID') matching a Track Box in the initialization segment.

Note that a Common Media Application Format Segment {{CMAF}} meets all these requirements.

### Fragmentation
Media is broken into segments at configurable boundaries. Each media segment MUST start with an I-frame so it can be decoded independently of other media segments. Each media segment SHOULD contain a single group of pictures (GOP).

Media segments are broken into media fragments at configurable boundaries. To minimize latency, each media fragment SHOULD contain a single frame.


# Messages
Warp endpoints communicate via messages contained in a custom top-level {{ISOBMFF}} Box.

This Warp Box ('warp') contains a single JSON object. Each key defines the message type and the value the contents. Unknown messages MUST be ignored.

Multiple messages with different types MAY be encoded in the same JSON object. Messages SHOULD be sent in separate boxes on the same stream when ordering is important.

## init {#message-init}
The `init` message indicates that the remainder of the stream contains an initialization segment.

~~~
{
  init: {
    id: int
  }
}
~~~

id:

: Incremented by 1 for each unique initialization segment.


## media {#message-segment}
The `segment` message contains metadata about the next media segment in the stream.

~~~
{
  segment: {
    init: int,
    timestamp: int,
    timescale: int, (optional)
  }
}
~~~

init:

: The id of the cooresponding initialization segment. A decoder MUST block until the cooresponding initialization segment has been fully processed.

timestamp:

: The presentation timestamp in `timescale` units for the first frame/sample in the next segment. This timestamp takes precedence over the timestamp in media container to support stream stitching.

timescale (optional):

: The number of units in second. This defaults to `1000` to signify milliseconds.


## priority {#message-priority}
The `priority` message informs middleware about the intended priority of the current stream. Middleware MAY obey this message but SHOULD forward it.

~~~
{
  priority: {
    precedence: int,
  }
}
~~~

precedence:

: An integer value, indicating that any available bandwidth SHOULD be allocated to streams in descending order.

## Extensions
Custom messages MUST start with `x-`. Unicode LATIN SMALL LETTER X (U+0078) followed by HYPHEN-MINUS (U+002D).

Custom messages MAY control playback. For example: `x-pause` could halt the transfer of segments until followed by a `x-play`.

Custom messages SHOULD use a unique prefix to reduce collisions. For example: `x-twitch-load` would contain identification required to start playback of a Twitch stream.


# Security Considerations

TODO


# IANA Considerations

This document has no IANA actions.



--- back

# Contributors
{:numbered="false"}

* Michael Thornburgh
