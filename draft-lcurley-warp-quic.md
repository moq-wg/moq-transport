---
title: "Warp - Live Video Transport over QUIC"
abbrev: WARP-QUIC
docname: draft-lcurley-warp-quic
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
  WARP-BASE:
		title: "Warp - Live Video Transport"
		date: {DATE}
		seriesinfo:
			Internet-Draft: draft-lcurley-warp-base
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

This document defines the Warp video transport protocol when using QUIC directly.
Warp maps live media to QUIC streams based on the underlying media encoding.
Latency is minimized achieved by prioritizing the delivery of specific streams during congestion.

--- middle

# Overview
Warp is a strategy to deliver live video using QUIC. The core concepts and shared functionality are defined in the {{WARP-BASE}} draft. This draft defines a wire protocol for using Warp directly on top of QUIC.

Warp over QUIC is a bidirectional live vieo transport. A QUIC connection is established and unidirectional streams are used to transfer messages. Any media data is prioritized and sent over the remainder of the stream.

# Conventions and Definitions

{::boilerplate bcp14-tagged}

# API

## Establishment
Warp over QUIC runs on top of a standard QUIC connection. The establishment of this connection, and any other session establishment, is out of scope of this document.

## Streams
{{WARP-BASE}} defines how media is split into multiple streams. An endpoint attempting to send media MUST support the outlined stream prioritization scheme.

Warp over QUIC exclusively uses unidirectional streams, initiated by both the client and server.

## Frames
A stream consists of one or more frames appended together. Streams can be finalized or reset with an error code.

Frames that depend on strict ordering MUST use the same stream. Frames with no ordering requirements SHOULD use separate streams to avoid head-of-line blocking.

## Frame
Each frame consists of the payload size in bytes followed by the payload itself. The payload size is encoded as a uint32 with little endian encoding, utilizing 4 bytes.

A payload size of zero indicates that the payload is unbounded and continues until the end of the stream. This is used exclusively to transfer media data.

A non-zero payload size indicates that it is a message. These messages are used to issue commands or transfer metadata.

## Messages
Warp uses JSON-encoded messages for simplicity. A future draft may define a binary encoding once the goals of the API have been determined.

Each message consists of a JSON object with a single key-value pair. The key identifies the message type and the value depends on the type. The common message types are defined in the next section.

```
{
	type: value
}
```

An implemenation MUST ignore any unknown message types. This enables backwards compatibility and custom message types. Any custom message types SHOULD use a unique prefix to avoid collisions.

### media
The `media` message is used to carry metadata about the current media chunk. The next frame MUST have a zero payload size and will contain the media in its specified container.

* `track` is used to distinguish between multiple tracks.
* `sequence` is incremented by one for each media chunk within the current track.
* `continuity` is incremented by one each time there is a discontinuity, requiring a decoder reset.

```
{
  type: 'video'|'audio',
  track: int,
  sequence: int,
  continuity: int
}
```

### load
The `load` message specifies stream to load. The format and payload are application specific. This must be followed by a `play` message to actually begin playback.

* `format` is the format of the payload.
* `payload` depents on the format.

The only defined format is `"url"`. The payload is a fully qualified URL including the schema, for example: `rtmp://host.com/path`.

```
{
	format: string,
  payload: *
}
```


### play
The `play` message starts/resumes playback the current track, sequence, and/or target latency. Any of these fields can be omitted to maintain the current settings.

* `track` is the desired track index, or 0 for auto.
* `sequence` is the desired sequence number for seeking forwards or backwards.
* `latency` is the target latency in seconds.

```
{
  track: int*,
  sequence: int*,
  latency: float*
}
```

### pause
The `pause` message halts playback until the next `play` message. This not does cancel any QUIC streams in flight; only prevents the creation of new ones.


### time
The `time` message is used for simple clock synchronization. It includes the sender's current unix epoch and the estimated transmission delay. An endpoint MUST prioritize the delivery of this message to avoid queuing.

* `epoch` is the sender's current unix timestamp in seconds.
* `delay` is the transmission delay in seconds, computed as half of the {{QUIC-RECOVERY}} RTT estimation.

```
{
  epoch: float,
  delay: float
}
```

### end
The `end` message is used to signal the end of a media stream.

* `track` is the track identifier.
* `sequence` is the last valid sequence number.
* `error` is an optional error message

```
{
  track: ``,
  sequence: ``,
  error: string*
}
```



# Security Considerations

TODO Security


# IANA Considerations

This document has no IANA actions.



--- back

# Acknowledgments
{:numbered="false"}

TODO acknowledge.
