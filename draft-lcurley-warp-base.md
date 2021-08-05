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

  HTTP3:
    title: "Hypertext Transfer Protocol Version 3 (HTTP/3)"
    date: {DATE}
    seriesinfo:
      Internet-Draft: draft-ietf-quic-http-latest
    author:
      -
          ins: M. Bishop
          name: Mike Bishop
          org: Akamai Technologies
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

informative:
  HLS:
  RTP:
  RTMP:
  WebRTC:


--- abstract

This document defines the core behavior for Warp video transport protocol family: {{WARP-QUIC}} and {{WARP-HTTP3}}.
Warp is the method of mapping of live media to QUIC streams based on the underlying media encoding.
Latency is minimized achieved by prioritizing the delivery of specific streams during congestion.

--- middle

# Overview

Warp is a live video transport protocol that utilizes the {{QUIC}} network protocol. There are two Warp variants depending on product requirements:

* {{WARP-QUIC}} is an API on top of QUIC.
* {{WARP-HTTP3}} is an API on top of HTTP/3, primarily for distribution over CDNs.

This document covers the shared behavior for both variants.

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

TODO diagram

### Audio
Audio encoding works by producing samples at a specified frequency. These samples are grouped together based on the sample rate (also called frames). Unlike video, groups of audio samples do not depend on each other.

Some video transport protocols (like WebRTC) choose to prioritize audio over video for a few reasons:

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


# Streams
QUIC provides independent streams multiplexed over a connection. These streams are ordered and reliable, but can be closed early by either endpoint.

Media sent over a single QUIC stream would suffer from head-of-line blocking. Warp avoids this by utilizing multiple concurrent QUIC streams based on the media encoding.

For {{WARP-HTTP3}}, these concepts apply to the underlying bidirectional stream for each request.

## Prioritization
The sender assigns a priority to each QUIC stream. Warp uses a strict prioritzation scheme, such that any available bandwidth is allocated to streams in descending priority order.

During congestion, this prioritization will intentionally cause stream starvation for the lowest priority streams.

### Media Type
Audio and video are split into separate QUIC streams. The timestamp within the media container is used for synchronization.

Audio streams SHOULD be prioritized over video streams. This enables the receiver to skip video while audio continues uninterupted during congestion.

### Video Streams
Video is split into a separate QUIC streams that can be delivered and decoded independently. This is done by splitting at GoP boundaries, ideally one stream per GoP. A video stream is finalized when the next one begins.

For live content, newer video streams SHOULD be prioritized over older video streams. This enables the receiver to skip over older content during congestion.

QUIC streams are reliable and ordered, so frames are flushed to the application in decode order. This is ideal when the GoP structure is linear or unknown, as it prevents decode errors.

A future version of Warp could optimize for other GoP structures. For example, non-reference frames could be sent over a lower priority stream. This added complexity is situational and does not seem necessary at this time.

### Audio Streams
Audio samples are also split into separate QUIC streams. These boundaries are based on the frequency and sample rate. An audio stream is finalized when the next one begins.

For live content, newer audio streams CAN be prioritized over older audio streams. This enables the receiver to skip ahead after persistent congestion.

## Retransmissions
STREAM frames may be lost over the network and require retransmision. A Warp sender MAY choose to delay retransmitting these frames if a higher priority stream can be sent instead.

When this is done, stream prioritization MUST still obey QUIC flow control. STREAM frames counts towards flow control limits, even when lost, until the frame is acknowledged or the stream reset. A Warp sender SHOULD retransmit frames instead of prioritizing other streams when nearing connection flow control limits.

## Closure
Due to the strict prioritization, streams may be starved indefinitely. Both the sender and receiver SHOULD close the lowest priority stream when nearing resource limits.

The receiver CAN close a stream after it has been skipped to reduce network usage.

## Multiple Tracks
Sessions can support multiple tracks or renditions. These SHOULD be sent over separate QUIC streams and CAN be prioritized.

# Decoding

# Security Considerations

TODO Security


# IANA Considerations

This document has no IANA actions.



--- back

# Acknowledgments
{:numbered="false"}

TODO acknowledge.
