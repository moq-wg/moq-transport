---
title: "Warp - Live Video Transport"
abbrev: WARP
docname: draft-lcurley-warp-quic
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

informative:
  HLS:
  RTP:
  RTMP:
  WebRTC:


--- abstract

This document defines the Warp video transport protocol.
Warp utilizes {{QUIC}} to deliver live media streams over the network.
These streams are prioritized based on the underlying encoding to minimize latency.

--- middle

# Overview


# Conventions and Definitions

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


# Security Considerations

TODO Security


# IANA Considerations

This document has no IANA actions.



--- back

# Acknowledgments
{:numbered="false"}

TODO acknowledge.
