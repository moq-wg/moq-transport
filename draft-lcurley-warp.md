---
title: "Warp - Segmented Live Media Transport"
abbrev: WARP
docname: draft-lcurley-warp-01
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
  QUIC-RECOVERY: RFC9002
  WebTransport: I-D.ietf-webtrans-http3

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

This document defines the core behavior for Warp, a segmented live media transport protocol.
Warp maps live media to QUIC streams based on the underlying media encoding.
Media is prioritized to reduce latency when encountering congestion.

--- middle

# Overview
Warp is a live media transport protocol that utilizes the QUIC network protocol {{QUIC}}.

{{connection}} covers how QUIC is used to transfer media. QUIC streams are created for each segment and prioritized such that the most important media is delivered during congestion.

{{segments}} covers how media is packaged into fragmented MP4 containers. Initialization segments contain track metadata while media segments contain audio and/or video samples.

{{messages}} covers how control messages are encoded. These are used sent alongside segments to carry necessary metadata and control playback.

{{configuration}} covers how to build an optimal live media stack. The application can configure Warp based on the desired user experience.

## Terms and Definitions

{::boilerplate bcp14-tagged}

Commonly used terms in this document are described below.

Congestion:

: Packet loss and queuing caused by degraded or overloaded networks.

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

Media player:

: A component responsible for presenting frames to a viewer based on the presentation timestamp.

Media encoder:

: A component responsible for creating a compressed media stream.

Media producer:

: A QUIC endpoint sending media over the network. This could be the media encoder or middleware.

Media consumer:

: A QUIC endpoint receiving media over the network. This could be the media player or middleware.

Middleware:

: A media consumer that forwards streams to one or more downstream media consumers.


# Connection
Warp uses the QUIC stream API to transfer media.

## Establishment
A connection is established using WebTransport over HTTP/3 {{WebTransport}}. This involves establishing a HTTP/3 connection, issuing a CONNECT request to establish the session, and exposing the underlying QUIC stream API while the session is active.

The application is responsible for authentication based on the CONNECT request.

The application is responsible for determining if an endpoint is a media producer, consumer, or both.

## Streams
Endpoints communicate over unidirectional QUIC streams. The application MAY use bidirectional QUIC streams for other purposes.

Both endpoints can create a new stream at any time. Each stream consists of byte data with an eventual final size. A stream is reliably delivered in order unless canceled early with an error code.

The delivery of each stream is independent. The sender MAY prioritize their delivery ({{prioritization}}); intentionally starving streams in favor of more important streams.

### Contents
Each stream consists of MP4 top-level boxes {{ISOBMFF}} concatenated together.

* Segments ({{segments}}) contain media samples and additional metadata. These are `ftyp`, `moov`, `styp`, `moof`, and `mdat` boxes.
* Messages ({{messages}}) control playback or carry metadata about segments. These are `warp` boxes.

Each `ftyp` box MUST be preceded by a `warp` box indicating that it is an initialization segment ({{message-init}}). Each `styp` box MUST be preceded by a `warp` box indicating that it is a media segment ({{message-segment}}).

A stream MUST start with a message and MAY contain multiple messages. A stream MUST NOT contain multiple segments.

### Prioritization
Warp utilizes precedence to deliver the most important content during congestion.

The media producer assigns a numeric precedence to each stream. This is a strict prioritization scheme, such that any available bandwidth is allocated to streams in descending order. QUIC supports stream prioritization but does not standardize any mechanisms; see Section 2.3 in {{QUIC}}.

The media producer MUST support sending prioritized streams using precedence. The media producer MAY choose to delay retransmitting lower priority streams when possible within QUIC flow control limits.

See {{configuration-prioritization}} for suggestions on how to prioritize streams based on the contents.

### Cancellation
During congestion, prioritization intentionally cause stream starvation for the lowest priority streams. Some form of starvation will last until the network fully recovers, which may be indefinite.

The media consumer SHOULD cancel a stream (via a QUIC `STOP_SENDING` frame) with application error code 0 when the segment is no longer desired. This can happen when the consumer decides to skip the remainder of a segment after some duration has elapsed. The media producer MUST NOT treat this as a fatal error.

The media producer SHOULD cancel the lowest priority stream (via QUIC `RESET_STREAM` frame) with application error code 0 when nearing resource limits. This can happen after sustained starvation and indicates that the consumer must skip over the remainer of a segment. The media consumer MUST NOT treat this as a fatal error.

Both of these actions will effectively drop the tail of the segment. The segment fragment size SHOULD be small to reduce data loss, ideally one fragment per frame.

## Middleware
Media may go through multiple hops and processing steps on the path from the broadcaster to player. The full effectiveness of warp as an end-to-end protocol depends on middleware support.

* Middleware SHOULD maintain stream idependence to avoid introducing head-of-line blocking.
* Middleware SHOULD maintain stream prioritization when traversing networks susceptible to congestion.
* Middleware MUST forward the `priority` message ({{message-priority}}) to downstream servers.

## Termination
The QUIC connection can be terminated at any point with an error code.

The media producer MAY terminate the QUIC connection with an error code of 0 to indicate the end of the media stream. Either endpoint MAY use any other error code to indicate a fatal error.

# Segments
The live stream is split into segments before being transferred over the network. Segments are fragmented MP4 files as defined by {{ISOBMFF}}.

There are two types of segments: initialization and media.

## Initialization
Initialization segments contain track metadata but no sample data.

Initialization segments MUST consist of a File Type Box (`ftyp`) followed by a Movie Box (`moov`). This Movie Box consists of Movie Header Boxes (`mvhd`), Track Header Boxes (`tkhd`), Track Boxes (`trak`), followed by a final Movie Extends Box (`mvex`). These boxes MUST NOT contain any samples and MUST have a duration of zero.

Note that a Common Media Application Format Header {{CMAF}} meets all these requirements.

## Media
Media segments contain media samples for a single track.

Media segments MUST consist of a Segment Type Box (`styp`) followed by at least one media fragment. Each media fragment consists of a Movie Fragment Box (`moof`) followed by a Media Data Box (`mdat`). The Media Fragment Box MUST contain a Movie Fragment Header Box (`mfhd`) and Track Box (`trak`) with a Track ID (`track_ID`) matching a Track Box in the initialization segment.

Note that a Common Media Application Format Segment {{CMAF}} meets all these requirements.

### Segmentation
Media is broken into segments at configurable boundaries. Each media segment MUST start with an I-frame so it can be decoded independently of other media segments. Each media segment SHOULD contain a single group of pictures (GOP).

### Fragmentation
Media segments are further broken into media fragments at configurable boundaries. See {{configuration-fragmentation}} for advice on when to fragment.


# Messages
Warp endpoints communicate via messages contained in a custom top-level {{ISOBMFF}} Box.

This Warp Box (`warp`) contains a single JSON object. Each key defines the message type and the value the contents. Unknown messages MUST be ignored.

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
The `priority` message informs middleware about the intended priority of the current stream. Middleware MUST foward this message but it is OPTIONAL to obey it.

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

Custom messages could control playback. For example: `x-pause` could halt the transfer of segments until followed by a `x-play`.

Custom messages SHOULD use a unique prefix to reduce collisions. For example: `x-twitch-load` would contain identification required to start playback of a Twitch stream.


# Configuration
Achieving both a high quality and low latency broadcast is difficult. Warp is a generic media transport and it is ultimately up to the application to choose the desired user experience.

## Playback Buffer
It is RECOMMENDED that a media player use a playback buffer to ensure smooth playback at the cost of higher latency. The buffer SHOULD be at last large enough to synchronize audio/video and to account for network/encoding jitter.

The size of the playback buffer MAY be increased by temporarily pausing playback or reducing playback speed. The playback buffer MAY be fragmented such that unreceived media can be skipped.

A larger playback buffer gives the application more time to recover from starvation without user impact. A media player MAY increase the size of the playback buffer when future starvation events are anticipated.

Middleware SHOULD NOT use a buffer, as it will increase latency for each hop.

## Congestion Control
Warp uses the underlying QUIC congestion control [QUIC-RECOVERY]. The default congestion control algorithm {{NewReno}} will work in many situations but can be improved.

This section outlines how a live media congestion control algorithm should perform, but does not recommend a specific algorithm.

### Transmission Delays
Live media is generated in real-time and played back at a constant rate. Transmission delays cause frame delays, necessitating a larger playback buffer. Additionally, the effectiveness of prioritizing streams is reduced by high transmission delays.

A live media congestion control algorithm SHOULD aim to minimize delay, possibly at the expense of throughput.

The default QUIC congestion controller is loss-based and suffers from bufferbloat. Large queues on intermediate routers cause high transmission delays prior to any packet loss.

#### Application Limited
Live media is often application-limited, as the encoder limits the amount of data available to be sent. This occurs more frequently with a smaller fragment duration, as individual frames might not be large enough to saturate the congestion window.

A live media congestion control algorithm SHOULD have some way of determining the network capabilities even when application-limited. Alternatively, the media producer CAN pad the network with QUIC PING frames to avoid being application limited at the expense of higher bandwidth usage.

The default QUIC congestion controller does not increase the congestion window when application-limited. See section 7.8 of {{QUIC-RECOVERY}}.

### Constant Delivery
Live media generates frames at regular intervals. Delaying the delivery of a frame relative to others necessitates a larger playback buffer

A live media congestion control algorithm SHOULD NOT introduce artificial starvation.

A counter-example is BBR {{BBR}}, as the `PROBE_RTT` state effectively prohibits sending packets for a short period of time for the sake of remeasuring `min_rtt`. The impact is reduced in future versions of BBR.

## Prioritization {#configuration-prioritization}
Media segments might be delivered out of order during starvation.

The media player determines how long to wait for a given segment (buffer size) before skipping ahead. The media consumer MAY cancel a skipped segment to save bandwidth, or leave it downloading in the background (ex. to support rewind).

Prioritization allows a single media producer to support multiple media consumers with different latency targets. For example, one consumer could have a 1s buffer to minimize latency, while another consumer could have a 5s buffer to improve quality, while a yet another consumer could have a 30s buffer to receive all media (ex. VOD recorder).

### Live Content
Live content is encoded and delivered in real-time. Media delivery is blocked on the encoder throughput, except during congestion causing limited network throughput. To best deliver live content:

* Audio streams SHOULD be prioritized over video streams. This allows the media consumer to skip video while audio continues uninterrupted during congestion.
* Newer video streams SHOULD be prioritized over older video streams. This allows the media consumer to skip older video content during congestion.

For example, this formula will prioritize audio segments, but only up to 3s in the future:

~~~
  if is_audio:
    precedence = timestamp + 3s
  else:
    precedence = timestamp
~~~

### Recorded Content
Recorded content has already been encoded. Media delivery is blocked exclusively on network throughput.

Warp is primarily designed for live content, but can switch to head-of-line blocking by changing stream prioritization. This is also useful for content that should not be skipped over, such as advertisements. To enable head-of-line blocking:

* Audio and video streams SHOULD be equally prioritized.
* Older streams SHOULD be prioritized over newer streams.

For example, this formula will prioritize older segments:

~~~
  precedence = -timestamp
~~~

## Bitrate Adjustment
The media producer SHOULD reduce the media bitrate in response to prolonged congestion. This can be done by adjusting the encoding bitrate and/or producing multiple renditions.

### Dynamic Bitrate
Live media is encoded in real-time and the bitrate can be adjusted on the fly. This is common in 1:1 media delivery.

A media producer MAY reduce the media bitrate in response to starvation. This can be detected via the estimated bitrate as reported by the congestion control algorithm. A less accurate indication of starvation is when the QUIC sender is actively prioritizing streams, as it means the congestion control window is full.

### Rendition Selection
Live media is can be encoded into multiple renditions, such that media consumers could receive different renditions based on network conditions. This is common in 1:n media delivery.

A media producer MAY switch between renditions at segment boundaries. The media producer MAY choose the rendition based on underlying network conditions and/or feedback from the media consumer via a custom message.

It is RECOMMENDED that rendition segments are aligned to avoid introducing gaps or overlapping media. A media decoder MUST be prepared to receive unaligned segments, skipping over excess or missing media.

## Fragmentation {#configuration-fragmentation}
Segments are encoded as fragmented MP4. Each fragment is a `moof` and `mdat` pair containing data for a number of samples. Using more fragments introduces more container overhead (higher bitrate), so it's up to the application to determine the fragment frequency.

For the highest latency: one fragment per segment. This means the entire segment must be received before any of the samples can be processed. This is optimal for content that is not intended to be decoded in real-time.

For the lowest latency: one fragment per frame. This means that each frame can be decoded when fully received. This is optimal for real-time decoding, however it introduces the largest overhead.

Fragments can be created with variable durations. However, the fragment duration SHOULD be relatively consistent to avoid introducing additional playback starvation. Likewise audio and video SHOULD be encoded using similar fragment durations.

## Encoding
Warp is primarily a network protocol and does enforce any encoding requirements. However, encoding has a significant impact on the user experience and should be taken into account.

B-frames MAY be used to improve compression efficiency, but they introduce jitter. This necessitates a larger playback buffer, increasing latency.

Audio and video MAY be encoded and transmitted independently. However, audio can be encoded without delay unlike video. Media players SHOULD be prepared to receive audio before video even without congestion.

# Security Considerations

## Resource Exhaustion
Live media requires significant bandwidth and resources. Failure to set limits will quickly cause resource exhaustion.

Warp uses QUIC flow control to impose resource limits at the network layer. Endpoints SHOULD set flow control limits based on the anticipated media bitrate.

The media producer prioritizes and transmits streams out of order. Streams might be starved indefinitely during congestion and SHOULD be cancelled ({{cancellation}}) after hitting some timeout or resource limit.

The media consumer might receive streams out of order. If stream data is buffered, for example to decode segments in order, then the media consumer SHOULD cancel a stream ({{cancellation}}) after hitting some timeout or resource limit.

# IANA Considerations

This document has no IANA actions.



--- back

# Contributors
{:numbered="false"}

* Michael Thornburgh
