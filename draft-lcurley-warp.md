---
title: "Warp - Live Video Transport"
abbrev: WARP-BASE
docname: draft-lcurley-warp-base
date: {DATE}
category: info

ipr: trust200902
area: General
workgroup: Independent Submission
keyword: Internet-Draft

stand_alone: yes
smart_quotes: no
pi: [toc, sortrefs, symrefs]

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

  QUIC-RECOVERY:
    title: "QUIC Loss Detection and Congestion Control"
    date: 2021-05
    seriesinfo:
      RFC: 9002
      DOI: 10.17487/RFC9002
    author:
      -
        ins: J. Iyengar
        name: Jana Iyengar
        org: Fastly
        role: editor
      -
        ins: I. Swett
        name: Ian Swett
        org: Google
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
Latency is minimized achieved by prioritizing the delivery of important media during congestion.

--- middle

# Overview
Warp is a live video transport protocol that utilizes the {{QUIC}} network protocol.

The live stream is split into demuxed segments at IDR boundaries. These are fragmented fMP4 files as defined in {{ISOBMFF}}. Initialization segments contain track metadata and media segments contain the actual media samples.

Unidirectional QUIC streams are used to transfer messages and segments between endpoints. These streams are prioritized based on the contents, such that any available bandwidth is utilized by the highest priority streams. The prioritization scheme depends on the latency target.

Warp messages are used to control playback and carry any metadata about the stream contents.

## Terms and Definitions

{::boilerplate bcp14-tagged}

Commonly used terms in this document are described below.

TODO:

: TODO


# Segments
The live stream is split into segments before being transferred over the network. Segments are fragmented fMP4 files as defined by {{ISOBMFF}}.

There are two types of segments: initialization and media.

## Initialization Segments
Initialization segments contain track metadata but no sample data.

Initialization segments MUST consist of a File Type Box ('ftyp') followed by a Movie Box ('moov'). This Movie Box consists of Movie Header Boxes ('mvhd'), Track Header Boxes ('tkhd'), Track Boxes ('trak'), followed by a final Movie Extends Box ('mvex'). These boxes MUST NOT contain any samples and MUST have a duration of zero.

Note that a Common Media Application Format Header {{CMAF}} meets all these requirements.

## Media Segments
Media segments contain media samples for a single track.

Media segments MUST consist of a Segment Type Box ('styp') followed by at least one media fragments. Each media fragment consists of a Movie Fragment Box ('moof') followed by a Media Data Box ('mdat'). The Media Fragment Box MUST contain a Movie Fragment Header Box ('mfhd') and Track Box ('trak') with a Track ID ('track_ID') matching a Track Box in the initialization segment.

Note that a Common Media Application Format Segment {{CMAF}} meets all these requirements.

### Video
Media segments containing video data MUST start with an IDR frame. Media fragments SHOULD contain a single frame to minimize latency. Video frames MUST be in decode order.

### Audio
Media fragments SHOULD contain a single group of audio samples to minimize latency.


# Streams
Warp uses unidirectional QUIC streams to transfer messages and segments over the network. The establishment of the QUIC connection is outside the scope of this document.

Both endpoints CAN create any number of unidirectional streams. These streams contain any number of messages and segments appended together.

## Messages
Messages are used to carry metadata and control playback.

A Warp Box ('warp') is a top-level MP4 box as defined in {{ISOBMFF}}. The contents of this box is a warp message. See the Messages section for the encoding and available messages.

## Segments
Segments are transferred over streams along-side messages.

The sender SHOULD create a stream for each segment. The sender CAN send multiple segments over the same stream if there is an explicit dependency.

Each segment MUST be preceded by an 'init' or 'segment' message, indicating the type of segment.

## Prioritization
Warp utilizes a stream priority scheme rather than deadlines. This ensures that the most important content is delivered first during congestion.

The sender assigns a numeric priority to each stream. This is a strict prioritzation scheme, such that any available bandwidth is allocated to streams in descending priority order.

QUIC supports stream prioritization but does not standardize any mechanisms; see Section 2.3 in {{QUIC}}. Only the sender needs to implement prioritization.

The stream priority value depends on the type of content being served.

### Live Content
Live content is encoded and delivered in real-time. Media delivery is blocked on the encoder throughput, except during congestion.

Audio streams SHOULD be prioritized over video streams. This will skip video while audio continues uninterupted during congestion.
Newer video streams SHOULD be prioritized over older video streams. This will skip over older video content during congestion.

For example, this formula will prioritze audio segments up to 3s in the future:

~~~
  if is_audio:
    priority = timestamp + 3s
  else:
    priority = timestamp
~~~

### Recorded Content
Recorded content has already been encoded. Media delivery is blocked exclusively on network throughput.

Warp is primarily designed for live content, but can switch to head-of-line blocking by changing stream prioritization. This is also useful for content that should not be skipped over, such as advertisements.

To enable head-of-line blocking: older streams SHOULD be prioritized over newer streams.

For example, this formula will prioritize older segments:

~~~
  priority = -timestamp
~~~


## Starvation
During congestion, this strict prioritization will intentionally cause stream starvation for the lowest priority streams. This starvation will last until the network fully recovers, which may be indefinite.

The receiver SHOULD cancel a stream (STOP_SENDING) after it has been skipped to save bandwidth. The sender SHOULD reset the lowest priority stream when nearing resource limits.

## Retransmissions
STREAM frames may be lost over the network and require retransmision. The sender MAY choose to delay retransmitting these frames if a higher priority stream can be sent instead. This will not always be possible due to flow control limits.


# Messages
Warp endpoints communicate via messages contained in the top-level Warp Box (warp).

A warp message is JSON object, where the key defines the message type and the value depends on the message type. Unknown messages MUST be ignored.

## Ordering
An endpoint MUST send messages sequentially over a single stream when ordering is important.

Messages CAN be combined into a single JSON object, however this introduces ambiguous ordering.

## init
The `init` message indicates that the remainder of the stream contains an initialization segment.

* The `id` field is incremented by 1 for each unique initialization segment.

~~~
{
  init: {
    id: int
  }
}
~~~


## media
The `media` message indicates that the remainder of the stream contains a media segment.

* The `init` field is the id of the cooresponding initialization segment. A decoder MUST wait for the coorespending `init` message to arrive.
* The optional `timestamp` field indicates the desired presentation timestamp in milliseconds at the start of the segment. This field is used to support combining media streams without re-encoding timestamps. The player MUST correct the actual PTS/DTS within the media segment prior to decoding.

~~~
{
  segment: {
    init: int,
    timestamp*: int,
  }
}
~~~


## load
The `load` message is used to initialize a playback session. This message is application-specific. A `play` message is required to start transferring media.

* The `type` field is a string indicating the type of stream being loaded.
* The `value` field contents depend on the `type`.

~~~
{
  load: {
    type: string,
    value: any,
  }
}
~~~


## play
The `play` message instructs the sender to start or resume transferring media.

* The optional `latency` field is the desired latency in milliseconds (for starting playback). The server CAN use this value to determine which segments to transfer first.
* The optional `timestamp` field is the desired timestamp in milliseconds (for resuming playback). The server CAN use this value to determine which segments to transfer first.


~~~
{
  play: {
		latency*: int,
		timestamp*: int,
	}
}
~~~

## pause
The `pause` message instructs the sender to halt transferring media

~~~
{
  pause: {}
}
~~~


## priority
The `priority` message informs middleware about the intended priority of the current stream. The middleware CAN ignore this value if it has its own prioritization scheme.

* The `strict` field is an integer value, where larger values indicate higher priority. A higher priority stream will always use available bandwidth over a lower priority stream.

~~~
{
  priority: {
    strict: int,
  }
}
~~~


# Security Considerations

TODO Security


# IANA Considerations

This document has no IANA actions.



--- back

# Acknowledgments
{:numbered="false"}

TODO acknowledge.
