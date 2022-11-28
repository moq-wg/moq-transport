---
title: "Media over QUIC - Terminology"
abbrev: MoQ
docname: draft-moq-terminology-latest
date: {DATE}
category: info

ipr: trust200902
area: General
submissionType: IETF
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

informative:
  MP4:
    title: "Information technology — Coding of audio-visual objects — Part 12: ISO Base Media File Format; ISO/IEC 14496-12:2015"
    date: 2015-12
    target: https://www.iso.org/standard/68960.html
  CMAF:
    title: "Information technology -- Multimedia application format (MPEG-A) -- Part 19: Common media application format (CMAF) for segmented media; ISO/IEC DIS 23000-19:2018"
    date: 2018-01
    target: https://www.iso.org/standard/71975.html
  DASH:
    title: "Information technology — Dynamic adaptive streaming over HTTP (DASH) — Part 1: Media presentation description and segment formats; ISO/IEC 23009-1:2019"
    date: 2019-08
    target: https://www.iso.org/standard/75485.html
  RTP: RFC3550
  RTP-SEMANTICS: RFC7656
  HLS: RFC8216
  RTMP:
    title: "Adobe’s Real Time Messaging Protocol"
    date: 2012-12
    target: https://rtmp.veriskope.com/docs/spec/
  TS:
    title: "Information technology — Generic coding of moving pictures and associated audio information: Systems — Part 1; ISO/IEC 13818-1:2007"
    date: 2007-10
    target: https://www.iso.org/standard/44169.html


--- abstract

This document defines the terminology behind Media over QUIC.


--- middle


# Introduction

# Pipeline
The flow that a single media stream follows from capture to consumption.

## Media Stream
A physical stimulus is captured into a media stream.
This media stram is usually compressed using a codec.

Known as:
* "encoded stream". {{RTP-SEMANTICS}}
* "coded representation" and "elementary stream". {{TS}}
* "encoded bitstream". {{HLS}}
* "track" and "CMAF track". {{MP4}}{{CMAF}}
* "media stream". {{DASH}}
* "message stream". {{RTMP}}

## Fragments
An encoded stream is split at boundaries into fragments, containing any number of samples.
These fragments can be transmitted independently, although they be dependent on other fragments.

Examples include:
* sample boundaries. {{RTP}}{{TS}}{{MP4}}
* GoP boundaries. {{HLS}}{{DASH}}
* arbitrary boundaries. {{RTMP}}

## Container
Fragments are placed into a container.
The container includes a timestamp, reassembly instructions, and other metadata.

Examples include:
* RTP Fixed Header. {{RTP}} (section 5.1)
* PES Packet. {{TS}} (section 2.4.3.6)
* RTMP Chunk. {{RTMP}} (setion 5.3)
* Fragment. {{CMAF}} (section 6.4.1)

## Transmission
Containers are futher split so they can be transmitted over IP.
These are sent over the network and may be lost.

Examples:
* RTP Packet. {{RTP}}
* TS Packet. {{TS}} (section 2.4.3.2)
* TCP Packet. {{RTMP}}{{HLS}}{{DASH}}

## Decoding
The peer reassembles IP packets into containers, then fragments, and finally the encoded bitstream.
This may not be a full reconstruction depending on the loss semantics of the protcol.
The reassembled encoded bitstream is decoded and rendered.


# Multiplexing
Multiple media streams may be transmitted over a single connection.

## Broadcast
A broadcast contains one or more media streams.
Not all of the media streams should be delivered, depending on codec support, sustained bitrate, preferred content, etc.

Known as:
* Presentation. {{HLS}}{{CMAF}}

## Renditions
TODO Decipher the difference between a rendition/representation.
I think one is typically a single track (audio OR video), while the other is a pair of tracks (audio AND video).

Known as:
* Adaption Set. {{DASH}}
* Switching Set. {{CMAF}}
* Alternative Rendition. {{HLS}} (section 4.3.4.2.1)

## Alignment
Media streams are aligned using timestamps.

Known as:
* Presentation Timestamp. (PTS)
* Program Date Time. {{HLS}} (section 4.3.2.6)


# Contributors
{:numbered="false"}
