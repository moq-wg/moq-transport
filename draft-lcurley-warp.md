---
title: "Warp - Layered Live Media Transport"
abbrev: WARP
docname: draft-lcurley-warp-latest
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

  -
    ins: K. Pugin
    name: Kirill Pugin
    organization: Meta
    email: ikir@meta.com

  -
    ins: S. Nandakumar
    name: Suhas Nandakumar
    organization: Cisco
    email: snandaku@cisco.com


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

This document defines the core behavior for Warp, a layered live media transport protocol.
Media is split into layers based on the underlying media encoding.
Each layer is transmitted independently over a QUIC stream.
QUIC streams are prioritized, allowing less important layers to be starved or dropped during congestion.

--- middle


## Introduction
Warp is a live media transport protocol that utilizes the QUIC network protocol {{QUIC}}.

{{motivation}} covers the background and rationale behind Warp.
{{layers}} covers how media is encoded and split into layers.
{{quic}} covers how QUIC is used to transfer media.
{{messages}} covers how messages are encoded on the wire.


## Terms and Definitions

{::boilerplate bcp14-tagged}

Commonly used terms in this document are described below.

TODO definitions


# Motivation

## Latency
In a perfect world, we could deliver live media at the same rate it is produced.
The end-to-end latency of a broadcast would be fixed and only subject to encoding and transmission delays.
Unfortunately, networks have variable throughput, primarily due to congestion.

Attempting to deliver media larger than this variable network bitrate causes queuing.
This queuing can occur anywhere in the path between the encoder and decoder.
For example: the application, the OS socket, a wifi router, within an ISP, or generally anywhere in transit.

If nothing is done, new frames will be appended to the end of a growing queue and will take longer to arrive than their predecessors, increasing latency.
Our job is to minimize the growth of this queue, and failing that, skip the queue when possible.

Thus speed at which a media protocol can detect and respond to queuing determines the latency.
We can generally classify existing media protocols into two categories based on the underlying network protocol:

* TCP-based media protocols (ex. RTMP, HLS, DASH) are popular due to their simplicity.
Media is served/consumed in decode order while any networking is handled by the TCP layer.
However, these protocols primarily see use at higher latency targets due to their relatively slow detection and response to queuing.

* UDP-based media protocols (ex. RTP, WebRTC, SRT) can side-step the issues with TCP and provide lower latency with better queue management.
However the media protocol is now responsible for fragmentation, congestion control, retransmissions, receiver feedback, reassembly, and more.
This added complexity significantly raises the implementation difficulty and hurts interoperability.

A goal of this draft is to get the best of both worlds: a simple protocol that can still rapidly detect and respond to congestion.
This is possible emergence of QUIC, designed to fix the shortcomings of TCP.
This draft relies on QUIC streams to deliver media layers in priority order during congestion.

## Universal
The media protocol ecosystem is fragmented; each protocol has it's own niche.
Specialization is often a good thing, but we believe there's enough overlap to warrant consolidation.

For example, a service might simultaneously ingest via WebRTC, SRT, RTMP, and/or a custom UDP protocol depending on the broadcaster.
The same service might then simultaneously distribute via WebRTC, LL-HLS, HLS, (or the DASH variants) and/or a custom UDP protocol depending on the viewer.

These media protocols are radically different and not interoperable; requiring transcoding or transmuxing.
This cost is further increased by the need to maintain separate stacks with different expertise requirements.

A goal of this draft is to cover a large spectrum of use-cases. Specifically:

* Consolidated contribution and distribution.
The primary difference between the two is the ability to fanout.
How does a CDN know how to forward media to N consumers and how does it reduce the encoded bitrate during congestion?
A single protocol can cover both use-cases provided intermediaries are informed on how to forward and drop media.

* A configurable latency versus quality trade-off.
The producer (broadcaster) chooses how to encode and transmit media based on the desired user experience.
Each consumer (viewer) chooses how long to wait for media based on their desired user experience and network.
We want an experience that can vary from real-time and lossy for one viewer, to delayed and loss-less for another viewer, without separate encodings or protocols.

## Intermediaries
The prevailing belief is that UDP-based protocols are more expensive and don't "scale".
While it's true that UDP is more difficult to optimize than TCP, QUIC itself is proof that it is is possible to reach performance parity.
In fact even some TCP-based protocols (ex. RTMP) don't "scale" either and are exclusively used for contribution as a result.

The truth is that the ability to scale a media protocol depends on intermediary support: proxies, caches, CDNs, SFUs, etc.
The success of HTTP-based media protocols is due to the ability to leverage traditional HTTP CDNs.

Meanwhile, it's difficult to build a CDN for media protocols that were not designed with intermediaries in mind.
For example, an intermediary has to parse the underlying codec to determine which RTP packets should be dropped first, and the decision is not deterministic or consistent for each hop.

A goal of this draft is to treat intermediaries as first class citizens.
Any identification, reliability, ordering, prioritization, caching, etc is written to the wire in header designed for intermediaries.
This ensures that intermediaries can easily route/fanout media to the final destination.
This also ensures that congestion response is consistent at every hop based on the preferences of the media producer.


# Layers
Warp is based on the concept of layered coding.
A layer is a combination of a media bitstream and a set of properties.

* The encoder determines how to split the encoded bitstream into layers ({{media}}).
* Each layer is transferred over a QUIC stream, which are delivered independently according to the layer properties ({{properties}}).
* The decoder receives each layer and skips any layers that do not arrive in time ({{decoder}}).

## Media
An encoder produces one or more codec bitstreams for each track.
The bitstream is then fed to the decoder on the other end, after being transported over the network, in the same order its produced.
The problem, as explained in motivation ({{latency}}), is that networks cannot sustain a continuous rate and thus queuing occurs.

Warp works by splitting the codec bitstream into layers that can be transmitted independently.
The producer determines how to split the bistream into layers: based on the track, GoP, frame/sample, or even slice.
Depending on how the layers are produced, the consumer has the ability to decode layers out of order and skip over gaps.
See the appendix for examples based on media encoding ({{appendix.examples}}).

TOOD specify CMAF

A layer MUST contain a single track.
A layer MAY contain any number of samples which MUST be in decode order (increasing DTS).
There MAY be gaps between samples, as specified by the presentation timestamp and duration within the container.

The goal of layers is to produce a hierarchy.
Layers MAY depend on any number of other layers and MAY overlap with other layers.

## Properties
Each layer has properties to go along with its contents.
These are written on the wire and inform how they layer should be transmitted at each hop.
This is primarily for the purpose of supporting intermediaries, but some of this information may also be used by the decoder.

All currently defined properties are optional.

* `id`.
A numeric identifier for the layer.
If non-zero, this value MUST be unique.
The default value is 0.

* `order`.
A numeric priority such that the smaller values take priority.
A sender SHOULD transmit layers with smallest value first, effectively starving layers with larger values during congestion.
If two layers use the same value, they SHOULD be round-robined.
Note that layers can still arrive out of the intended order due to packet loss.
The default value is 0.

* `depends`.
A list of numeric layer IDs.
This informs the decoder that it MUST receive and process the dependency layers first.
The decoder MAY support stream processing, such that it does not need to fully receive the dependency layers first.
The layer SHOULD have a larger `order` than its dependencies, if present.
The default value is 0, which means no dependency.

* `cache`.
TODO Indicates the layer should be cached for some amount of time since last access. What about fragments with an unbounded age? Should we send an `expire` message instead?

* `expires`.
TODO Indicates the layer should be dropped after some amount of time (ex. `RESET_STREAM`). Do we need clock sync for this? How does this interact with `cache`?

* `timestamp`.
TODO The presentation timestamp of the earliest (not always first) frame in the layer. What does an intermediary need this for?

* `track`
TODO The track identifier to be used in conjunction with the TRACK message.

See the appendix for some example layers and properties. {{appendix.examples}}

## Decoder
The consumer will receive multiple layers over the network in parallel.
The decoder MUST synchronize layers using presentation timestamps within the bitstream.
The decoder might not support decoding each layer independently, so the consumer MAY need to reorder prior to passing a bitstream to the decoder.

Layers are NOT REQUIRED to be aligned within or between tracks.
For example, a low quality rendition may have more frequent I-frames, and thus layers, than a higher quality rendition.
A decoder MUST be prepared to skip over any gaps between layers.


# QUIC

## Establishment
A connection is established using WebTransport {{WebTransport}}.

To summarize:
The client issues a HTTP CONNECT request with the intention of establishing a new WebTransport session.
The server returns an 200 OK response if the WebTransport session has been established, or an error status otherwise.

A WebTransport session exposes the basic QUIC service abstractions.
Specifically, either endpoint may create independent streams which are reliably delivered in order until canceled.

WebTransport can currently operate via HTTP/3 and HTTP/2, using QUIC or TCP under the hood respectively.
As mentioned in the motivation ({{motivation}}) section, TCP introduces head-of-line blocking and will result in a worse experience.
It is RECOMMENDED to use WebTransport over HTTP/3.

The application SHOULD use the CONNECT request for authentication and negotiation.
For example, including a authentication token and some identifier in the path.
The application MAY use QUIC streams for more complicated behavior.

TODO define auth inside the protocol?

## Streams
Warp endpoints communicate over unidirectional QUIC streams.
The application MAY use bidirectional QUIC streams for other purposes.

A stream consists of sequential messages.
See messages ({{messages}}) for the list of messages and their encoding.
These are similar to QUIC and HTTP/3 frames, but called messages to avoid the media terminology.

Each stream MUST start with a `HEADERS` message. TODO better name.
This message includes information on how intermediaries should proxy or cache the stream.
If a stream is used to transmit a layer, the header MUST match the layer properties ({{properties}}).

Messages SHOULD be sent over the same stream if ordering is desired.
For example, `PAUSE` and `PLAY` messages SHOULD be sent on the same stream to avoid a race.

## Prioritization
Warp utilizes stream prioritization to deliver the most important content during congestion.

The media producer SHOULD assign a numeric order to each stream, as contained in the HEADERS message ({{headers}}).
This is a strict prioritization scheme, such that any available bandwidth is allocated to streams in ascending order.
The order is determined at encode, written to the wire so it can be read by intermediaries, and will not be updated.
This effectively creates a priority queue that can be maintained over multiple hops.

QUIC supports stream prioritization but does not standardize any mechanisms; see Section 2.3 in {{QUIC}}.
QUIC libraries will need to expose a API to the application to set the priority of each stream.

Senders SHOULD support prioritized streams, although it is OPTIONAL on a path with no expected congestion.
Senders SHOULD use strict ordering, although relative weights MAY be acceptable if there are no other options.
Senders MUST obey the order as written to the wire.
Senders MAY choose to delay retransmitting lower priority streams when possible within QUIC flow control limits.

## Cancellation
QUIC streams can be canceled by either endpoint with an error code.

When using `order`, lower priority streams will be starved during congestion, perhaps indefinitely.
These streams will consume resources and flow control until they are canceled.
When nearing resource limits, an endpoint SHOULD cancel the lowest priority stream with error code 0.

When using `expires`, a stream SHOULD be canceled after the duration has elapsed.
This is not a full replacement for prioritization, but can provide some congestion response by clearing parts of the queue.

## Congestion Control
As covered in the motivation section ({{motivation}}), the ability to prioritize or cancel streams is a form of congestion response.
It's equally important to detect congestion via congestion control, which is handled in the QUIC layer.

Bufferbloat is caused by routers queueing packets for an indefinite amount of time rather than drop them.
This latency significantly reduces the ability for the application to prioritize or drop media in response to congestion.
Senders SHOULD use a congestion control algorithm that reduces this bufferbloat.
It is NOT RECOMMENDED to use a loss-based algorithm (ex. Reno, CUBIC) unless the network fully supports ECN.

Live media is application-limited, which means that the encoder determines the max bitrate rather than the network.
Most TCP congestion control algorithms will only increase the congestion window if it is full, limiting the upwards mobility when application-limited.
Senders SHOULD use a congestion control algorithm that is designed for application-limited flows (ex. GCC).
Senders MAY periodically pad the connection with QUIC PING frames to fill the congestion window.

## Termination
The QUIC connection can be terminated at any point with an error code.

The media producer MAY terminate the QUIC connection with an error code of 0 to indicate the clean termination of the broadcast.
The application SHOULD use a non-zero error code to indicate a fatal error.

|------|----------------------|
| Code | Reason               |
|-----:|:---------------------|
| 0x0  | Broadcast Terminated |
|------|----------------------|
| 0x1  | GOAWAY {{goaway}}    |
|------|----------------------|

TODO define more error codes

# Messages
Messages consist of a type identifier followed by contents, depending on the message type.

TODO document varint identifier
TODO more message types

|------|----------------------|
| ID   | Messages             |
|-----:|:---------------------|
| 0x0  | HEADERS {{headers}}  |
|------|----------------------|
| 0x1  | LAYER {{layer}}      |
|------|----------------------|
| 0x2  | APP {{app}}          |
|------|----------------------|
| 0x10 | GOAWAY {{goaway}}    |
|------|----------------------|



## HEADERS
The `HEADERS` message contains the information listed in layer properties ({{properties}}).

TODO better name
TODO document wire format
TODO use QPACK?

## LAYER
A `LAYER` message consists of the layer bitstream.
A `LAYER` message must be proceeded with a `HEADERS` message specifying the layer properties ({{properties}}).

TODO document CMAF
TODO document wire format
TODO support multiple container formats

## APP
The `APP` message contains arbitrary contents.
A stream containing `APP` message SHOULD be cached and forwarded by intermediaries like any other stream; based on the `HEADERS` message ({{headers}}).

TODO document wire format

## GOAWAY
The `GOAWAY` message is sent by the server to force the client to reconnect.
This is useful for server maintenance or reassignments without severing the QUIC connection.
A server MAY use QUIC load balancing instead of a GOAWAY message.

The server initiates the graceful shutdown by sending a GOAWAY message.
The server MUST close the QUIC connection after a timeout with the GOAWAY error code ({{termination}}).
The server MAY close the QUIC connection with a different error code if there is a fatal error before shutdown.
The server SHOULD wait until the `GOAWAY` message and any pending streams have been fully acknowledged, plus an extra delay to ensure they have been processed.

A client that receives a `GOAWAY` message should establish a new WebTransport session to the provided URL.
This session SHOULD be made in parallel and MUST use a different QUIC connection (not pooled).
The optimal client will be connected for two servers for a short period, potentially receiving layers from both in parallel.


# Security Considerations
TODO expand

## Resource Exhaustion
Live media requires significant bandwidth and resources.
Failure to set limits will quickly cause resource exhaustion.

Warp uses QUIC flow control to impose resource limits at the network layer.
Endpoints SHOULD set flow control limits based on the anticipated media bitrate.

The media producer prioritizes and transmits streams out of order.
Streams might be starved indefinitely during congestion and SHOULD be canceled after hitting some timeout or resource limit.

The media consumer might receive streams out of order.
If stream data is buffered, for example to decode segments in order, then the media consumer SHOULD cancel a stream after hitting some timeout or resource limit.

# IANA Considerations
TODO

# Appendix A. Layer Examples {#appendix.examples}
Warp offers a large degree of flexability on how layers are fragmented and prioritized.
There is no best solution; it depends on the desired complexity and user experience.

This section provides a summary of media encoding and some options available.

## Recommended
Before explaining all of the options, there is a recommended approach:

* a video layer per GoP ({{appendix.gop}})
* an audio layer at roughly the same timestamp ({{appendix.segments}})

TODO section on prioritization
* audio should be delivered before video
* for new media should be delivered before old media, or the opposite if reliability is desired


## Tracks
A broadcast consists of one or more tracks.
Each track has a type (audio, video, caption, etc) and uses a cooresponding codec.
There may be multiple tracks, including of the same type for a number of reasons.

For example:

* A track for each codec.
* A track for each resolution and bitrate.
* A track for each language.
* A track for each camera feed.

Traditionally, these tracks could be muxed together into a single container or stream.
The goal of Warp is to independently deliver tracks, and even parts of a track, so they must be demuxed.

The simplest configuration is a single, continuous layer per track.
This allows tracks to be prioritized during congestion, although no media can be dropped.
The next section covers how to further split layers based on the type of media.

## Video

### Encoding
Video is a sequence of frames with a display timestamp.
To improve compression, frames are encoded as deltas and can reference number of frames in the past (P-frames) and/or in the future (B-frames).
A frame with no dependencies (I-frame) is effectively an image file and is a seek point.

A common encoding structure is to only reference the previous frame, as it is simple and minimizes latency:

~~~
 I <- P <- P <- P   I <- P <- P <- P   I <- P ...
~~~

Another common encoding structure is to use B-frames in a fixed pattern, which is easier for hardware encoding.
B-frames reference one or more future frames, which improves the compression ratio but increases latency.

This example is referenced in later sections:

~~~
    B     B         B     B         B
   / \   / \       / \   / \       / \
  /   \ /   \     /   \ /   \     /   \
 I <-- P <-- P   I <-- P <-- P   I <-- P ...
~~~

Note that the B-frames reference I and P frames in this example, despite the lack of an arrow.
TODO better ASCII art

There is no such thing as an optimal encoding structure.
Encoders tuned for the best quality will produce a tangled spaghetti of references.
Encoders tuned for the lowest latency still have a lot of options for references.


### Decode Order
The encoder outputs the bitstream in decode order, which means that each frame is output after its dependencies.
This is only relevant for B-frames as they must be buffered until the frame they reference has been flushed.

A layer MUST be in decode order.

For the example above, this would look like:

~~~
encode order: I B P B P I B P B P I B P ..
decode order: I P B P B I P B P B I P B ..
~~~


### Group of Pictures {#appendix.gop}
A group of pictures (GoP) is consists of an I-frame and the frames that directly or indirectly reference it.
Each GoP can be decoded independently and thus can be transmitted independently.
It is also safe to drop the tail of the GoP (in decode order) without causing decode errors.

A layer MAY consist of an entire GoP.
A layer MAY consist of multiple sequential GoPs.

Our example GoP structure would be split into three layers.

~~~
     layer 1         layer 2      layer 3
+---------------+---------------+---------
| I  P  B  P  B | I  P  B  P  B | I  P  B
+---------------+---------------+---------
~~~


### Scalable Video Coding
The concept of layers is borrowed from scalable video coding (SVC).
When SVC is enabled, the encoder produces multiple bitstreams in a hierarchy.
Dropping the top layer degrades the user experience in a configured way, such as reducing the resolution, picture quality, and/or frame rate.

A layer MAY consist of an entire SVC layer.

Here is an example SVC encoding with 3 resolutions:

~~~
                layer 3              layer 6
      +-------------------------+---------------
   4k |  P <- P <- P <- P <- P  |  P <- P <- P
      |  |    |    |    |    |  |  |    |    |
      |  v    v    v    v    v  |  v    v    v
      +-------------------------+--------------

                layer 2              layer 5
      +-------------------------+---------------
1080p |  P <- P <- P <- P <- P  |  P <- P <- P
      |  |    |    |    |    |  |  |    |    |
      |  v    v    v    v    v  |  v    v    v
      +-------------------------+--------------

                layer 1              layer 4
      +-------------------------+---------------
 360p |  I <- P <- P <- P <- P  |  I <- P <- P
      +-------------------------+---------------
~~~


### Frames
With full knowledge of the encoding, the producer can split a GoP into multiple layers based on the frame.
However, this is highly dependent on the encoding, and the additional complexity might not improve the user experience.

A layer MAY consist of a single frame.

Our example GoP structure could be split into thirteen layers:

~~~
      2     4           7     9           12
+--------+--------+--------+--------+-----------+
|     B  |  B     |     B  |  B     |     B     |
|-----+--+--+-----+-----+--+--+-----+-----+-----+
|  I  |  P  |  P  |  I  |  P  |  P  |  I  |  P  |
+-----+-----+-----+-----+-----+-----+-----+-----+
   1     3     5     6     8     10    11    13
~~~

To reduce the number of layers, frames can be appended to a layer they depend on.
Layers are delivered in order so this is simpler and produces the same user experience.

A layer MAY consist of multiple frames within the same GoP.

The same GoP structure can be represented using eight layers:

~~~
      2     3           5     6           8
+--------+--------+-----------------+------------
|     B  |  B     |     B  |  B     |     B     |
+--------+--------+--------+--------+-----------+
|  I     P     P  |  I     P     P  |  I     P
+-----------------+-----------------+------------
         1                 4              7
~~~

We can further reduce the number of layers by combining some frames that don't depend on each other.
The only restriction is that frames can only reference frames earlier in the layer, or within a dependency layer.
For example, non-reference frames can have their own layer so they can be prioritized or dropped separate from reference frames.

The same GoP structure can also be represented using six layers, although we've removed our ability to drop individual B-frames:

~~~
    layer 2       layer 4     layer 6
+-------------+-------------+--------
|    B   B    |    B   B    |    B
+-------------+-------------+--------
|  I   P   P  |  I   P   P  |  I   P
+-------------+-------------+--------
    layer 1       layer 3     layer 5
~~~

Note that this is identical to our SVC example; we've effectively implemented our own temporal coding scheme.

### Slices
Frames actually consist of multiple slices that reference other slices.
It's conceptually simpler to work with frames instead of slices, but splitting slices into layers may be useful.
For example, intra-refresh splits an I-frame into multiple I-slices (TODO terminology) and spread over multiple frames to smooth out the bitrate.
TODO are slices necessary?

A layer MAY consist of a single slice.
A layer MAY consist of multiple slices that are part of the same GoP.

### Init
For the most byte-conscious applications, initialization data can be sent over its own layer.
Multiple layers can depend on this initialization layer to avoid redundant transmissions.
For example: this is the init segment in CMAF (`moov` with no samples), which contains the SPS/PPS NALUs for h.264.

A layer MAY consist of no samples.

Our example layer per GoP would have an extra layer added:

~~~
     layer 2         layer 3      layer 4
+---------------+---------------+---------
| I  P  B  P  B | I  P  B  P  B | I  P  B
+---------------+---------------+---------
|                     init
+-----------------------------------------
                     layer 1
~~~

An initialization layer MUST be cached in memory until it expires.
TODO How do we do this?

## Audio

### Encoding
Audio is dramatically simpler than video as it is not typically not delta encoded.
Audio samples are grouped together (group of samples) at a configured rate, also called a "frame".

In the below diagrams, each audio frame is denoted with an S.
The encoder spits out a continuous stream of samples:

~~~
S S S S S S S S S S S S S
~~~

### Simple
The simplest configuration is to use a single layer for each audio track.
This may seem inefficient given the ease of dropping audio samples.
However, the audio bitrate is low and gaps cause quite a poor user experience, when compared to video.

A layer SHOULD consist of multiple audio frames.

~~~
          layer 1
+---------------------------
| S S S S S S S S S S S S S
+---------------------------
~~~

### Periodic Refresh
An improvement is to periodically split audio samples into separate layers.
This gives the consumer the ability to skip ahead during severe congestion or temporary connectivity loss.

~~~
     layer 1         layer 2      layer 3
+---------------+---------------+---------
| S  S  S  S  S | S  S  S  S  S | S  S  S
+---------------+---------------+---------
~~~

This frequency of audio layers is configurable, at the cost of additional overhead.
It's NOT RECOMMENDED to create a layer for each audio frame because of this overhead.

### Segments {#appendix.segments}
Video can only recover from severe congestion with an I-frame, so there's not much point recovering audio at a separate interval.
It is RECOMMENDED to create a new audio layer at each video I-frame.

~~~
     layer 1         layer 3      layer 5
+---------------+---------------+---------
| S  S  S  S  S | S  S  S  S  S | S  S  S
+---------------+---------------+---------
| I  P  B  P  B | I  P  B  P  B | I  P  B
+---------------+---------------+---------
     layer 2         layer 4      layer 6
~~~

This is effectively how HLS/DASH segments work, with the exception that the most recent layers are still pending.


--- back

# Contributors
{:numbered="false"}

TODO
