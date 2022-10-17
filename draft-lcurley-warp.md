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

For example, a service might similtaniously ingest via WebRTC, SRT, RTMP, and/or a custom UDP protocol depending on the broadcaster.
The same service might then similtaniously distribute via WebRTC, LL-HLS, HLS, (or the DASH variants) and/or a custom UDP protocol depending on the viewer.

These media protocols are radically different and not interopable; requiring transcoding or transmuxing.
This cost is further increased by the need to maintain seperate stacks with different expertise requirements.

A goal of this draft is to cover a large spectrum of use-cases. Specifically:

* Consolidated contribution and distribution.
The difference between the two has historically been push versus pull.
This is an over-simplification, as the real difference is the ability to fanout, which is much easier with HTTP GET.
A single protocol can cover both use-cases with adequate information on how an intermediary should forward media.

* A configurable latency versus quality trade-off.
The broadcaster (producer) chooses how to encode and transmit media based on the desired user experience.
Each viewer (consumer) chooses how long to wait for media based on their desired user experience and network.
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
Warp is based on a concept of layers.
A layer is a bitstream that is decoded in order and without gaps.

The goal is to deliver layers such that the least important media is dropped during congestion.
This is done by assigning dependencies and/or priority to each layer, as covered in the properties ({{properties}}) section.
Each layer is then transmitted over a QUIC stream, as covered in the streams ({{streams}}) section.
QUIC will ensure that the layer arrives in order until canceled by either endpoint.

Media is broken up into layers based on the underlying encoding.
The contents and properties of each layer is determined by the producer based on the desired user experience.

## Properties
Each layer has properties to go along with its contents.
These are written on the wire and inform how they layer should be transmitted at each hop.
This is primarily for the purpose of supporting intermediaries, but this information may also be used by the decoder.

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

* `dependency`.
A numeric value that indicates this layer depends on the specified layer id.
TODO do we need multiple dependencies?
This informs the decoder that it MUST receive and process the dependency layer first.
The decoder SHOULD support stream processing, such that it does not need to receive the entire dependency layer first.
The layer MUST have a larger `order` than its dependency, if present.
The default value is 0, which means no dependency.

* `cache`.
TODO Indicates the layer should be cached for some amount of time since last access. What about fragments with an unbounded age? Should we send an `expire` message instead?

* `expires`.
TODO Indicates the layer should be dropped after some amount of time (ex. `RESET_STREAM`). Do we need clock sync for this? How does this interact with `cache`?

* `timestamp`.
TODO The presentation timestamp of the earliest (not always first) frame in the layer. What does an intermediary need this for?


## Tracks
The simplest configuration is a single layer spanning the entire broadcast.
This is effectively a TCP stream and is a direct replacement for RTMP.
The downside of a single layer is that it can only respond to congestion by modifying the encoder bitrate, so it SHOULD NOT be used over networks with congestion.

Each track (audio and/or video) can be split into separate layers.
This improves user experience as individual tracks can be prioritized during congestion.
For example, audio could be prioritized before video, and/or a lower bitrate rendition could be prioritized before a higher bitrate rendition.

A layer MAY contain multiple tracks.
A layer SHOULD contain a single track.

A single layer per track means that all media within the track is ordered.
Multiple layers per track allow sections to be dropped or prioritized, which is necessary to skip media and reduce queuing.
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


### Group of Pictures
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

Our example GoP structure would be split into six layers, assuming the B frames are part of a SVC layer:

~~~
    layer 2       layer 4     layer 6
+-------------+-------------+--------
|    B   B    |    B   B    |    B
+-------------+-------------+--------
|  I   P   P  |  I   P   P  |  I   P
+-------------+-------------+--------
    layer 1       layer 3     layer 5
~~~

Note that SVC encoding is more complicated than this; our example is a simple temporal encoding scheme.


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
Audio is dramatically simpler than video as it is not delta encoded.
Audio samples are grouped together (group of samples) at a configured rate, also called a "frame".
Frames do not depend on other frames and have a timestamp for sychronization.

In the below diagrams, each audio frame is denonated with an S.
The encoder spits out a continous stream of samples:

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

### Refresh
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

## Synchronization
Different layers and tracks can use their layering scheme.
Even with the same scheme, timestamps will not always line up, especially since audio and video use different frame rates.

A decoder MUST support sychronized playback of non-aligned layers.


# QUIC

## Establishment
A connection is established using WebTransport over HTTP/3 {{WebTransport}}.
To summarize, this involves establishing a HTTP/3 connection, issuing a CONNECT request to establish the session, and exposing the underlying QUIC stream API while the session is active.

TODO Do we support native QUIC?

The application is responsible for authentication based on the CONNECT request.
TODO Perform authentication in the protocol instead?

The application is responsible for determining if an endpoint is a media producer, consumer, or both.
TODO negotiate version?

## Streams
Endpoints communicate over unidirectional QUIC streams.
The application MAY use bidirectional QUIC streams for other purposes.

TODO Each stream consists of a message. Ideally multiple messages, so control messages can arrive in order (ex. PAUSE then PLAY will not race).

Each layer is delivered over a separate QUIC stream, ensuring reliable and ordered delivery of the layer.
TODO elaborate more on layers, since it's the most important concept for prioritization/reliability

## Prioritization
Warp utilizes stream prioritization to deliver the most important content during congestion.

The media producer assigns a numeric order to each stream.
This is a strict prioritization scheme, such that any available bandwidth is allocated to streams in ascending order.
The order is determined at encode, written to the wire so it can be read by intermediaries, and will not be updated.
This effectively creates a priority queue that can be maintained over multiple hops.

QUIC supports stream prioritization but does not standardize any mechanisms; see Section 2.3 in {{QUIC}}.
QUIC libraries will need to expose a API to the application to set the priority of each stream.

The media sender SHOULD support prioritized streams, although it is OPTIONAL on a path with no expected congestion.
The media sender SHOULD use strict ordering, although relative weights MAY be acceptable if there are no other options.
The media sender MUST obey the order as written to the wire.
The media sender MAY choose to delay retransmitting lower priority streams when possible within QUIC flow control limits.

TODO examples priorities in the layer section

## Reliability
QUIC streams containing layers SHOULD be canceled based on the layer properties.
The sender SHOULD cancel layers based on the `expires` property.

When using the `order` property, incomplete streams can be starved indefinitely.
Either endpoint SHOULD cancel the lowest priority stream when nearing resource limits.
The sender can do this by sending a `RESET_STREAM` frame with error code 0.
The receiver can do this by sending a `STOP_SENDING` frame with error code 0.


## Termination
The QUIC connection can be terminated at any point with an error code.

The media producer MAY terminate the QUIC connection with an error code of 0 to indicate the end of the media stream.
An endpoint SHOULD use a non-zero error code to indicate a fatal error.

TODO define some error codes


# Messages
TODO document message types; "layer" is a message type

## Layer
Each layer is divided into two parts: a layer header and the media container

TODO Wire format for {{properties}}
TODO Document container options (CMAF)

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


--- back

# Contributors
{:numbered="false"}

TODO
