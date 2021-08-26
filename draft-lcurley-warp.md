---
title: "Warp - Live Video Transport"
abbrev: WARP-BASE
docname: draft-lcurley-warp-base
date: {DATE}
category: info

ipr: trust200902
area: General
workgroup: TODO Working Group
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

--- abstract

This document defines the core behavior for Warp video transport protocol.
Warp maps live media to QUIC streams based on the underlying media encoding.
Latency is minimized achieved by prioritizing the delivery of important media during congestion.

--- middle

# Overview
Warp is a live video transport protocol that utilizes the {{QUIC}} network protocol.

TODO Summarize each section.

## Terms and Definitions

TODO terms

{::boilerplate bcp14-tagged}

# Media

## Segments
Media is split into multiple segments before being transferred over the network. Each media segment MUST be:

* Independent; there is no dependency on data contained in other media segments.
* Streamable; individual frames and samples can be decoded as they arrive.

Audio and video are split into separate media segments that can be delivered separately.

## Video
Each video segment contains a complete group of pictures. A video segment MUST start with an IDR frame, although it CAN contain multiple IDR frames.

The encoder SHOULD insert an IDR at least every 4 seconds. This allows the decoder to skip ahead to the next segment during periods of congestion.

Video frames MUST be fragmented, such that they can be decoded individually. Video frames MUST be in decode order.

## Audio
Each audio segment contains blocks of samples. The duration of these blocks depends on the codec and sample rate.

The boundary of audio segments SHOULD align with that of video segments, within the margin of error caused by different frame and block durations.

## Container
Media segments are encoded using {{ISOBMFF}}. This is compatible with fragmented MP4, but more generic.

Each media segment consists of a segment type box (styp), followed by a single movie fragment box (moof), followed by one or more media data boxes (mdat).

TODO is this sufficient for initialization data?


# QUIC

## Establishment
The establishment of the QUIC connection and any authentication is currently outside the scope of this document.

## Streams
Warp creates a unidirectional QUIC stream for each media segment. These media streams are finalized when the media segment has been fully written.

Media segments are encoded using {{ISOBMFF}}. This document defines a new top-level box (warp) that MAY be intermixed with the media segment. See the API section for further details.

## Prioritization
Warp utilizes a stream priority scheme rather than deadlines. This ensures that the most important content is delivered first during congestion.

The Warp sender assigns a priority to each media stream. This is a strict prioritzation scheme, such that any available bandwidth is allocated to streams in descending priority order.

QUIC supports stream prioritization but does not standardize any mechanisms; see Section 2.3 in {{QUIC}}. An implementation must support stream prioritization to send media streams, but it is not required to receive media streams.

The stream priority value depends on the type of content being served. The next sections outline a recommendation for live content and recorded content.

### Live Content
Live content is encoded and delivered in real-time. Media delivery is blocked on the encoder throughput, except during congestion.

Audio streams SHOULD be prioritized over video streams. This will skip video while audio continues uninterupted during congestion.
Newer video streams SHOULD be prioritized over older video streams. This will skip over older video content during congestion.

A simple prioritization formula: `priority = 2 * sequence + 3 * is_audio`

### Recorded Content
Recorded content has already been encoded. Media delivery is blocked exclusively on network throughput.

Warp is primarily designed for live content, but can switch to head-of-line blocking by changing stream prioritization. This is also useful for content that should not be skipped over, such as advertisements.

To enable head-of-line blocking: older streams SHOULD be prioritized over newer streams.

A simple formula formula: `priority = -sequence`

## Starvation
During congestion, this strict prioritization will intentionally cause stream starvation for the lowest priority streams. This starvation will last until the network fully recovers, which may be indefinite.

The receiver SHOULD cancel a stream (STOP_SENDING) after it has been skipped to save bandwidth. The sender SHOULD reset the lowest priority stream when nearing resource limits.

## Retransmissions
STREAM frames may be lost over the network and require retransmision. The Warp sender MAY choose to delay retransmitting these frames if a higher priority stream can be sent instead. This will not always be possible due to flow control limits.


# Latency
This section covers a few latency requirements and suggestions.

## Variable Latency
Warp works via prioritization rather than deadlines so it can offer variable latency. It is up to the decoder to determine how long to block playback while waiting for a media segment.

Variable latency is especially useful when there are multiple recipients. For example, a viewer might skip video content after 2s while an archive worker might wait for up to 30s. Warp can serve both of these use-cases using the same media segments and prioritization scheme.

The sender SHOULD defer to the receiver to cancel streams (via STOP_SENDING) while resource limits allow. The sender SHOULD NOT impose tight stream deadlines.

## Middleware
Warp senders and receivers can be combined to form middleware. For example, intermediate servers that perform caching within a video distribution system.

Middleware SHOULD maintain the same stream priority within the scope of a session. Middleware CAN implement its own prioritization scheme.

Middleware MUST NOT combine segments or otherwise introduce dependencies.

## Congestion Control
Live video is produced and delivered at a consistent rate, so excess queuing on intermediate routers will introduce latency.

Warp implementations SHOULD use a delay-based congestion control algorithm (ex. BBR or Copa) to counter bufferbloat.

## Decoder
The decoder SHOULD maintain a buffer, sized based on the desired amount of latency. The decoder CAN pause playback to increase the size of the buffer during persistent congestion.

The decoder SHOULD skip the tail of video segments during congestion, resulting in dropped frames. The decoder CAN show video frames late if they arrive after being skipped.

The decoder CAN skip tail of audio segments during congestion, resulting in missing audio.


# API
The contents of each QUIC stream are encoded using {{ISOBMFF}}. The stream consists of multiple top-level boxes appended together.

## warp
The `warp` top-level box is parent for the new boxes as defined below. This box MAY be intermixed with media segment boxes.

TODO figure out tracks
TODO MP4 instead of JSON
TODO ingest specific APIs

### segm
The `segm` box contains metadata about the media segment.

```
{
  sequence: int,
  priority: int,
  continuity: int,
}
```

### load
The `load` box is used to initialize a playback session. It must be followed by a `play` box to begin media transfer.

```
{
  type: string,
  payload: any,
}
```

### play
The `play` box instructs the sender to start or resume transferring media.

```
{
  sequence: int,
  latency: duration,
}
```

### paus
The `paus` box instructs the sender to pause transferring media

```
{}
```


# Security Considerations

TODO Security


# IANA Considerations

This document has no IANA actions.



--- back

# Acknowledgments
{:numbered="false"}

TODO acknowledge.
