---
title: "Warp - Live Video Transport"
abbrev: WARP
docname: draft-lcurley-warp
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
    email: lcurley@twitch.tv

normative:
  QUIC:
    title: "QUIC: A UDP-Based Multiplexed and Secure Transport"
    date: 2021-05
    seriesinfo:
      RFC: 9000
      DOI: 10.17487/RFC9000
    author:
      -
        ins: J. Iyengar
        name: Jana Iyengar
        org: Fastly
        role: editor
      -
        ins: M. Thomson
        name: Martin Thomson
        org: Mozilla
        role: editor

  ISOBMFF:
    title: "Information technology — Coding of audio-visual objects — Part 12: ISO Base Media File Format"
    date: 2015-12

informative:
  BBR:
  Copa:
  CMAF:
    title: "Information technology -- Multimedia application format (MPEG-A) -- Part 19: Common media application format (CMAF) for segmented media"
    date: 2020-03

--- abstract

This document defines the core behavior for Warp video transport protocol.
Warp maps live media to QUIC streams based on the underlying media encoding.
Media is prioritized to minimize latency during congestion.

--- middle

# Overview
Warp is a live video transport protocol that utilizes the {{QUIC}} network protocol.

The live stream is split into segments ({{segments}}) at I-frame boundaries. These are fragmented MP4 files as defined in {{ISOBMFF}}. Initialization segments contain track metadata while media segments contain either video or audio samples.

QUIC streams ({{streams}}) are used to transfer messages and segments between endpoints. These streams are prioritized based on the contents, such that the most important media is delivered during congestion.

Messages ({{messages}}) are sent over streams alongside segments. These are used to carry necessary metadata and control messages.

## Terms and Definitions

{::boilerplate bcp14-tagged}

Commonly used terms in this document are described below.

Frame:

: An image to be rendered at a specific point in time.

I-frame:

: A frame that does not depend on the contents of other frames.

Group of pictures (GOP):

: A I-frame followed by a sequential series of dependent frames.

Group of samples:

: A sequential series of audio samples starting at a given timestamp.

Segment:

: One or more group of pictures serialized into a container.

Presentation Timestamp (PTS):

: A point in time when video/audio should be presented to the viewer.

Media producer:

: An endpoint sending media over the network.

Media consumer:

: An endpoint receiving media over the network.

Congestion:

: Packet loss and queuing caused by degraded or overloaded networks.


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

### Video
Media segments containing video data MUST start with an I-frame. Media fragments MAY contain a single frame, minimizing latency at the cost of a small increase in segment size. Video frames MUST be in decode order.

### Audio
Media fragments MAY contain a single group of audio samples, minimizing latency at the cost of a small increase in segment size.


# Streams
Warp uses unidirectional QUIC streams to transfer messages and segments over the network. The establishment of the QUIC connection is outside the scope of this document.

An endpoints MAY both send media (producer) and receive media (consumer). This is accomplished by sending messages and segments over unidirectional streams. Streams contain any number of messages and segments concatenated together.

## Messages {#streams-messages}
Messages are used to control playback or carry metadata about upcoming segments.

A Warp Box ('warp') is a top-level MP4 box as defined in {{ISOBMFF}}. The contents of this box is a warp message. See the messages section ({{messages}}) for the encoding and types available.

## Segments
Segments are transferred over streams alongside messages. Each segment MUST be preceded by an `init` ({{message-init}}) or `media` ({{message-media}}) message, indicating the type of segment and providing additional metadata.

The media producer SHOULD send each segment as a unique stream to avoid head-of-line blocking. The media producer CAN send multiple segments over a single stream, for simplicity, when head-of-line blocking is desired.

A segment is the smallest unit of delivery, as the tail of a segment can be safely delayed/dropped without decode errors. A future version of Warp will support layered coding (additional QUIC streams) to enable dropping or downscalling frames in the middle of a segment.

## Prioritization
Warp utilizes a stream priority scheme to deliver the most important content during congestion.

The media producer assigns a numeric presidence to each stream. This is a strict prioritzation scheme, such that any available bandwidth is allocated to streams in descending order. QUIC supports stream prioritization but does not standardize any mechanisms; see Section 2.3 in {{QUIC}}. The media producer MUST support sending priorized streams. The media producer MAY choose to delay retransmitting lower priority streams when possible within QUIC flow control limits.

The media consumer determines how long to wait for a given segment (buffer size) before skipping ahead. The media consumer CAN cancel a skipped segment to save bandwidth, or leave it downloading in the background (ex. to support rewind).

Prioritization allows a single media producer to support multiple media consumers with different latency targets. For example, one viewer could have a 1s buffer to minimize latency, another viewer could have a 5s buffer to improve quality, while a VOD worker could have a 30s buffer to receive all media.

### Live Content
Live content is encoded and delivered in real-time. Media delivery is blocked on the encoder throughput, except during congestion causing limited network throughput. To best deliver live content:

* Audio streams SHOULD be prioritized over video streams. This allows the media consumer to skip video while audio continues uninterupted during congestion.
* Newer video streams SHOULD be prioritized over older video streams. This allows the media consumer to skip older video content during congestion.

For example, this formula will prioritze audio segments, but only up to 3s in the future:

~~~
  if is_audio:
    priority = timestamp + 3s
  else:
    priority = timestamp
~~~

### Recorded Content
Recorded content has already been encoded. Media delivery is blocked exclusively on network throughput.

Warp is primarily designed for live content, but can switch to head-of-line blocking by changing stream prioritization. This is also useful for content that should not be skipped over, such as advertisements. To enable head-of-line blocking:

* Older streams SHOULD be prioritized over newer streams.

For example, this formula will prioritize older segments:

~~~
  priority = -timestamp
~~~

## Cancellation
During congestion, this strict prioritization will intentionally cause stream starvation for the lowest priority streams. This starvation will last until the network fully recovers, which may be indefinite.

The media consumer SHOULD cancel a stream (via STOP_SENDING frame) after it has been skipped to save bandwidth. The media producer SHOULD reset the lowest priority stream (via RESET_STREAM frame) when nearing resource limits. Both of these actions will effectively drop the tail of the segment.

## Middleware
Media may go through multiple hops and processing steps on the path from the broadcaster to player. The full effectiveness of warp as an end-to-end protocol depends on middleware support.

* Middleware MUST maintain stream idependence to avoid introducing head-of-line blocking.
* Middleware SHOULD maintain stream prioritization when traversing networks susceptible to congestion.
* Middleware MUST forward the `priority` message ({{message-priority}}) for downstream servers.

# Messages
Warp endpoints communicate via messages contained in the top-level Warp Box (warp).

A warp message is JSON object, where the key defines the message type and the value depends on the message type. Unknown messages MUST be ignored.

An endpoint MUST send messages sequentially over a single stream when ordering is required. Messages MAY be combined into a single JSON object when ordering is not required.

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

: Incremented by 1 for each initialization segment.


## media {#message-media}
The `media` message indicates that the remainder of the stream contains a media segment.

~~~
{
  segment: {
    init: int,
    timestamp: int,
  }
}
~~~

init:

: The id of the cooresponding initialization segment. A decoder MUST block until the coorespending `init` message to arrive.

timestamp:

: The presentation timestamp in milliseconds for the first frame/sample in the segment. This timestamp MUST be used when it does not match the timestamp in the media container.


## priority {#message-priority}
The `priority` message informs middleware about the intended priority of the current stream. Any middleware MAY ignore this value but SHOULD forward it.

~~~
{
  priority: {
    strict: int,
  }
}
~~~

strict:

: An integer value, where higher values take precedence over smaller values. The highest priority stream with pending data MUST be transmitted first as allowed by flow control and congestion control limits.


## Extensions
Custom messages MUST start with `x-`. Unicode LATIN SMALL LETTER X (U+0078) followed by HYPHEN-MINUS (U+002D).

Custom messages SHOULD use a unique prefix to reduce collisions. For example: `x-twitch-load` would contain identification required to start playback of a Twitch stream.


# Security Considerations

TODO


# IANA Considerations

This document has no IANA actions.



--- back

# Acknowledgments
{:numbered="false"}

TODO
