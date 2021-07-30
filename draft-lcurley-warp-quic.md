---
title: "Warp - Low-Latency Video Transport over QUIC"
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


# Background

## Congestion
Congestion occurs when a network is oversaturated and is unable to deliver packets in a timely manner.
{{QUIC-RECOVERY}} outlines how QUIC limits the transmission rate in response to congestion.

During periods of congestion, the encoder bitrate can exceed the network bitrate.
To remediate the situation, media must be queued or dropped until the sufficiently network recovers.

## Latency
The latency of a video transport protocol depends on how timely it can respond to congestion.
A low-latency video transport protocol will deliver newly generated media at the expense of older media.
This means dropping older media, which can have side-effects depending on the encoding.

## Video
Video encoding works by computing deltas between frames. Each frame can depend on 0, 1, or multiple frames in the past, or somtimes future.

There are a few common frame types:
* I frames are effectively a static image, so they are relatively large
* P frames depend on previous I or P frames.
* B frames depend on future P or B frames, and possibly previous I or P frames,

It's important to take video encoding into account when delivering low-latency media over a network.
The decision to drop a frame at the network level can cause video decoding errors impacting other frames.

TODO diagram

## Audio
Audio encoding works by producing groups of samples at a specified frequency.

Audio samples do not depend on each other and can be more freely dropped at the network level.
However, some video protocols like WebRTC choose to prioritize audio over video for a few reasons:

* Audio is more important for some applications (ex. teleconferencing)
* Audio gaps are far more noticable.
* Audio uses a fraction of the bandwidth.


# Conventions and Definitions

{::boilerplate bcp14-tagged}


# Security Considerations

TODO Security


# IANA Considerations

This document has no IANA actions.



--- back

# Acknowledgments
{:numbered="false"}

TODO acknowledge.
