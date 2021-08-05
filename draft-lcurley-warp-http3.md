---
title: "Warp - Live Video Transport over HTTP/3"
abbrev: WARP-HTTP3
docname: draft-lcurley-warp-http3
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


# Security Considerations

TODO Security


# IANA Considerations

This document has no IANA actions.



--- back

# Acknowledgments
{:numbered="false"}

TODO acknowledge.
