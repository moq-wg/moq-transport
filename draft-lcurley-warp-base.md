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
  WARP-QUIC:
    title: "Warp - Live Video Transport over QUIC"
    date: {DATE}
    seriesinfo:
      Internet-Draft: draft-lcurley-warp-quic
    author:
      -
        ins: L. Curley
        name: Luke Curley
        organization: Twitch
        email: lcurley@twitch.tv

  WARP-HTTP3:
    title: "Warp - Live Video Transport over HTTP/3"
    date: {DATE}
    seriesinfo:
      Internet-Draft: draft-lcurley-warp-http3
    author:
      -
        ins: L. Curley
        name: Luke Curley
        organization: Twitch
        email: lcurley@twitch.tv

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


--- abstract

This document defines the core behavior for Warp video transport protocol family: {{WARP-QUIC}} and {{WARP-HTTP3}}.
Warp is the method of mapping of live media to QUIC streams based on the underlying media encoding.
Latency is minimized achieved by prioritizing the delivery of specific streams during congestion.

--- middle

# Overview
Warp is a live video transport protocol that utilizes the {{QUIC}} network protocol.

TODO Summarize each section.

## Variants
There are two Warp variants depending on product requirements:

* {{WARP-QUIC}} is an bidirectional API on top of QUIC.
* {{WARP-HTTP3}} is an unidirectional API on top of HTTP/3, primarily for distribution over CDNs.

This document covers the shared concepts and functionality for both variants.

## Terms and Definitions

{::boilerplate bcp14-tagged}


# Background

## Encoding
In order to optimize media delivery over a network, it's important to have a basic understanding of how media is encoded.

### Video
Video encoding works by computing deltas between frames. Each frame can depend on 0, 1, or multiple frames in the past, or sometimes future.

There are a few common frame types:

- I frames are effectively a static image, so they are relatively large
- P frames depend on previous I or P frames.
- B frames depend on future P or B frames, and possibly previous I or P frames,

The encoder effectively creates a dependency graph based on which frames are used as references.

TODO diagram

### Audio
Audio encoding works by producing samples at a specified frequency. These samples are grouped together based on the sample rate (also called frames). Unlike video, groups of audio samples do not depend on each other.

Live video transport protocols (ex. WebRTC) typically choose to prioritize audio over video for a few reasons:

- Audio is more important for some applications (ex. teleconferencing)
- Audio gaps are far more noticable.
- Audio uses a fraction of the bandwidth.

## Latency
The latency of a video protocol depends on how long media frames are queued. Media can be queued for a number of different reasons, such as to improve the compression ratio by using more reference frames.

For a video transport protocol, the vast majority of queuing (and thus latency) is caused by network congestion.

## Congestion
Congestion occurs when a network is oversaturated and is unable to deliver packets in a timely manner.

During periods of congestion, intermediate routers will queue and eventually drop packets. Excessive queuing causes bufferbloat, increasing latency and eating into any buffer maintained by the receiver.

{{QUIC-RECOVERY}} outlines how QUIC limits the transmission rate in response to congestion. When this happens, encoder bitrate can exceed that of the transmission bitrate and results in queuing. The ability to rapidly respond to this situation determines the latency of a video transport protocol.

### Encoder Backpressure
The simplest response to network congestion is to reduce the encoder bitrate. The encoder can be reconfigured relatively quickly, while any queued media is delivered or reencoded.

However, tweaking the encoder bitrate has ramifications when there are multiple recipients. Network congestion for one receipient will cause degraded video quality for other participants.

### Media Dropping
As mentioned in the encoding section, video frames and audio samples only sometimes depend on each other. It is possible to deliver certain frames out-of-order or drop them entirely.

The effective media bitrate can be reduced by dropping frames at the network layer. The specific frames dropped have an impact on media decoding, so it's important that the network layer takes this into account.


# API
Warp runs on top of a standard QUIC connection. It utilizes multiple concurrent QUIC streams to transmit media in a prioritized manner.

## Streams
QUIC streams are is independent and multiplexed over a connection. These streams are ordered and reliable, but can be closed early by either endpoint.

If all media was sent over a single QUIC stream, the protocol suffers from head-of-line blocking (like TCP). Warp avoids this by utilizing multiple concurrent QUIC streams based on the media encoding.

For {{WARP-HTTP3}}, these concepts apply to the underlying bidirectional stream for each request.

## Media Container
Stream payloads start with a warp-specific header indicating the content. The remainder of the stream consists of a FMP4 or TS media container, depending on the configuration.

## Media Type
Audio and video are split into separate QUIC streams. The timestamp within the media container is used for synchronization.

### Video Streams
Video is split into a separate QUIC streams that can be delivered and decoded independently. This is done by splitting at GoP boundaries, preferably one stream per GoP. A video stream is finalized when the next one begins.

QUIC streams are reliable and ordered, so frames are flushed to the application in decode order. This is ideal when the GoP structure is linear or unknown, as it prevents decode errors.

### Audio Streams
Audio samples are also split into separate QUIC streams. An audio stream is finalized when the next one begins.

Audio streams should be aligned with video streams, which are split based on the GoP. This allows an endpoint to drop the same amount of audio and video if desired.

## Multiple Tracks
Sessions can support multiple tracks or renditions sent over separate QUIC streams.

# Prioritization
Warp utilizes a stream priority scheme rather than deadlines. This ensures that the most important content is delivered first without constant coordination between endpoints.

## Streams
The sender assigns a priority to each QUIC stream. Warp uses a strict prioritzation scheme, such that any available bandwidth is allocated to streams in descending priority order.

QUIC supports stream prioritization but does not standardize any mechanisms; see Section 2.3 in {{QUIC}}. The sender need to add support in their QUIC implementation.

### Live Content
Live content is encoded and delivered in real-time. The video transport protocol is typically blocked on the encoder throughput rather than the network, except during congestion.

Audio streams SHOULD be prioritized over video streams. This will skip video while audio continues uninterupted during congestion.

Newer video streams SHOULD be prioritized over older video streams. This will skip over older video content during congestion.

### Recorded Content
Recorded content has already been encoded and can be delivered at line speed. The video transport protocol is only blocked on the network throughput.

Warp is primarily designed for live content, but can switch to head-of-line blocking by changing stream prioritization. This is also useful for content that should not be skipped over, such as advertisements.

To enable head-of-line blocking: older streams SHOULD be prioritized over newer streams.

## Retransmissions
STREAM frames may be lost over the network and require retransmision. A Warp sender MAY choose to delay retransmitting these frames if a higher priority stream can be sent instead.

When this is done, stream prioritization MUST still obey QUIC flow control. STREAM frames counts towards flow control limits, even when lost, until the frame is acknowledged or the stream reset. A Warp sender SHOULD retransmit frames instead of prioritizing other streams when nearing connection flow control limits.

## Starvation
During congestion, this prioritization scheme will intentionally cause stream starvation for the lowest priority streams. This starvation will last until the network fully recovers, which may be indefinite.

When nearing resource limits, an endpoint SHOULD close the lowest priority stream. The receiver CAN close a stream after it has been skipped to reduce network usage.

# Endpoints
This section covers a few requirements and suggestions depending on the endpoint.

## Encoder
The encoder SHOULD insert a keyframe at least every 4 seconds. This allows the receiver to skip ahead to the next GoP during periods of congestion.

The encoder SHOULD reduce the media bitrate during periods of sustained congestion. This allows the receiver to recover catch up and reduces the amount of media skipped.

A low-latency encoder configuration is recommended.

## Sender
The sender is the network component responsible for sending Warp streams.

The sender SHOULD use a delay-based congestion control algorithm to counter bufferbloat. Live video is produced and delivered at a consistent rate, so any queuing on intermediate routers will introduce latency.

The sender SHOULD NOT be responsible for imposing latency deadlines, and instead SHOULD defer to the receiver to cancel streams (ie. STOP_SENDING).

## Receiver
The receiver is the network component responsible for receiver Warp streams.

The receiver SHOULD cancel a stream (ex. STOP_SENDING) once its contents have been fully skipped to save bandwidth. 

## Middleware
Warp senders and receivers can be combined to form middleware. For example, intermediate servers that perform caching within a video distribution system.

The middleware SHOULD maintain the same stream priority, within the scope of a session. The middleware CAN implement its own prioritization scheme when congestion is unlikely.

The middleware MUST NOT introduce any head-of-line blocking. This means the middleware MUST NOT combine streams or otherwise introduce dependencies.

## Decoder
The decoder MUST maintain a separate audio and video buffer. The initial and maximum size of this buffer depends on the application. The decoder CAN pause playback to increase the size of the buffer during persistent congestion.

The decoder SHOULD maintain a constant playback rate. The decoder SHOULD temporarily desynchronize audio and video when one of the buffers is missing data.

The decoder CAN drop audio samples if there is a gap in the audio buffer. This may introduce a noticable blip.

The decoder SHOULD drop video frames if there is a gap in the video buffer. The decoder CAN show late video frames. This will result in video that is missing or late compared to audio.

# Security Considerations

TODO Security


# IANA Considerations

This document has no IANA actions.



--- back

# Acknowledgments
{:numbered="false"}

TODO acknowledge.
