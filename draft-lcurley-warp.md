---
title: "Warp - Live Media Transport over QUIC"
abbrev: WARP
docname: draft-lcurley-warp-latest
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

  -
    ins: V. Vasiliev
    name: Victor Vasiliev
    organization: Google
    email: vasilvv@google.com


normative:
  QUIC: RFC9000
  QUIC-RECOVERY: RFC9002
  WebTransport: I-D.ietf-webtrans-http3
  URI: RFC3986

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

This document defines the core behavior for Warp, a live media transport protocol over QUIC.
Media is split into objects based on the underlying media encoding and transmitted independently over QUIC streams.
QUIC streams are prioritized based on the delivery order, allowing less important objects to be starved or dropped during congestion.

--- middle


## Introduction
Warp is a live media transport protocol that utilizes the QUIC network protocol {{QUIC}}.

* {{motivation}} covers the background and rationale behind Warp.
* {{objects}} covers how media is fragmented into objects.
* {{quic}} covers how QUIC is used to transfer media.
* {{messages}} covers how messages are encoded on the wire.
* {{containers}} covers how media tracks are packaged.


## Terms and Definitions

{::boilerplate bcp14-tagged}

Commonly used terms in this document are described below.

Bitstream:

: A continunous series of bytes.

Client:

: The party initiating a Warp session.

Codec:

: A compression algorithm for audio or video.

Congestion:

: Packet loss and queuing caused by degraded or overloaded networks.

Consumer:

: A QUIC endpoint receiving media over the network. This could be the media player or middleware.

Container:

: A file format containing timestamps and the codec bitstream

Decoder:

: A endpoint responsible for a deflating a compressed media stream into raw frames.

Decode Timestamp (DTS):

: A timestamp indicating the order that frames/samples should be fed to the decoder.

Encoder:

: A component responsible for creating a compressed media stream out of raw frames.

Frame:

: An video image or group of audio samples to be rendered at a specific point in time.

I-frame:

: A frame that does not depend on the contents of other frames; effectively an image.

Group of pictures (GoP):

: A I-frame followed by a sequential series of dependent frames.

Group of samples:

: A sequential series of audio samples starting at a given timestamp.

Player:

: A component responsible for presenting frames to a viewer based on the presentation timestamp.

Presentation Timestamp (PTS):

: A timestamp indicating when a frames/samples should be presented to the viewer.

Producer:

: A QUIC endpoint sending media over the network. This could be the media encoder or middleware.

Server:

: The party accepting an incoming Warp session.

Slice:

: A section of a video frame. There may be multiple slices per frame.

Track:

: An encoded bitstream, representing a single media component (ex. audio, video, subtitles) that makes up the larger broadcast.

Variant:

: A track with the same content but different encoding as another track. For example, a different bitrate, codec, language, etc.


## Notational Conventions

This document uses the conventions detailed in Section 1.3 of {{!RFC9000}} when describing the binary encoding.

This document also defines an additional field type for binary data:

x (b):
: Indicates that x consists of a variable length integer, followed by that many bytes of binary data.


                                                                                                      
# Data Model - Sessions, Media Streams, Tracks, Consumers and Relays

------ Christian's proposal starts here ------

Media applications are generally composed by combining multiple media streams to
present the desired experience to media users. The actual combination can vary
widely, from listening to a simple audio stream, to combining a mosaic of video
streams and multiple layers of audio possibly coming from multiple sources, to
immersion in a virtual reality experience combining multiple meshes, textures
and sound sources. Our goal is to build these experiences by combining a
series of "media streams", delivered either directly to the user or through
a network of relays.


## Media Streams, Tracks and Objects

When discussing the user experience, we focus on media streams, such as for example
the view of a participant in a video-conference. However, the media transport over QUIC
does not directly operate on the "abstract" view of a participant, but on the an encoding
of that view, suitable for transport over the Internet. In what follows, we call that
encoding a "Track".

### Tracks

A track is a transform of a media stream using a specific encoding process, a set of
parameters for that encoding, and possibly an encryption process. The MoQ transport
is designed to transport tracks.

### Objects and Groups

The binary content of a track is composed of a set of objects. The decomposition of the
track into objects is arbitrary. For real time applications, an object will often correspond
to an unit of capture, such as for example the encoding of a single video frame, but
different applications may well group several such units together, or follow whatever
arrangement makes sense for the application.

In the definition of the transport, we assume that objects may be encrypted, and that
relays will not be able to decrypt the object. Many applications are expected to use
authenticated encryption, which makes the transmission of the object an "all or nothing"
proposal, since truncated delivery would cause authentication failure and the rejection
of the message. The MoQ transport treats objects as atomic units.

The objects that compose a given track are organized as a series of "groups", each
containing a series of objects.

DISCUSS: we need to add here text on synchronization points, congestion responses,
and potentially priorities.

DISCUSS: we need to add here text on in order delivery, etc.

## Composition

Different applications will organize the user experience in different way. For
example, a conferencing application will let participants send and receive audio
and video streams from each other, as well as other media streams, such as maybe
a demonstration video, or sharing of a participant's computer screen. The number
of active streams in a conference will often vary over time, as new particpants
"get the floor" or start sharing screens. A broadcast
application may provide a set of video streams presenting different views of an
event, the corresponding sound tracks, and perhaps a running commentary. A
virtual reality application will have its own set of media streams. In some
cases, audio streams will be available in several languages, or subtitle streams
in different languages may complement the original videos and audio streams.

### Catalog and track selection

The MoQ transport tries to not make assumptions about the user experience, or the
number and type of media streams handled by an application. We simply assume that
the users will receive a "catalog" or "manifest" describing the broadcast. For some
applications, the content of this catalog will be established at the very beginning
of the session. In other case, the catalog will have to be updated by a stream of
events as new media streams get added or removed from the media experience.

The only assumption required by the MoQ transport is that users can select the tracks
that they want to receive, so they can subscribe to these tracks using MoQ. If a
media streams is available in multiple formats or multiple languages, we expect that
the catalog will provide sufficient information to let subscribers choose and request
the appropriate track. We will discuss later how subscribers who encounter congestion
could, for example, unsubscribe from the high definition track of a video media and
subscribe instead to a lower definition track, or maybe decide to forgo the video
experience and simply receive the audio track.

DISCUSS: some applications could consider the catalog as just a particular media track.
This provides an interesting simplification, because then the identifier of the
catalog track can be used to identify the "media session". 


## Relays, Subscribers, Publishers and Origins

User will receive the content of a track by "subscribing" to it. We expect
that they will in most case receive the track's object through relays, much
like readers of web pages often receive these pages through a content
distribution network.

### Subscribing through a relay

A subscriber will subscribe to a media track by sending to the relay a "subscribe"
command that carries the identifier of the desired track. The relay will have
to decide whether to authorize that query or not. If it decides to allow the subscription,
it will also have to find out how to provide the desired content.

The authorization process can be implemented in three stages: identifying the "origin"
of the requested track, verifying that the relay is willing to act on behalf of that
origin, and then asking that origin whether the subscriber is
authorized to access the specified content. This requires that the "origin" can
be obtained by parsing the track identifier. We thus assume that the track indentifier
includes two components: the origin identifier, and the track reference at the origin.

~~~
    +-----------+-----------------+
    | Origin ID | Track reference |
    +-----------+-----------------+
   -- Two parts track identifier --

~~~

Given the origin identifier, the rely will check whether it is authorized to service
that origin. This step depends on the way the relay is managed. Some relays will
accept all traffic from a set of subscribers, other will only accept traffic if they
have some business agreement with the origin. The only requirements for the MoQ transport
are to be able to identify the origin and, in some cases, the subscriber.

The relay will then have to check whether the origin is willing to let the subscriber
access the track. For example, if the track is part of a real time conference, the
origin will check whether the subscriber is an authorized participant to the conference.
The relay will do that by sending an "authorization request" towards the origin.
The authorization request may contain a track identifier and some client data, such as
for example some kind of token.

DISCUSS: authorization may require more than a single token provided by
the subscriber and passed to the origin. Many authorization processes involve multiple
rounds of challenges and responses. The subscriber may also want to verify that it
is in contact with the expected origin. At a minimum, this needs discussion in a
security section.

Many multimedia experiences involve multiple tracks, originating from the same origin.
Repeating the authorization process for each of these tracks seems wasteful. Some
origins may want to authorize the subscriber once per conference, or once per "broadcast",
instead of once per track. This can be implemented by using a hierarchical structure,
splitting the "track reference" into a "broadcast reference" and the actual "track reference".

~~~
    +-----------+---------------------+-----------------+
    | Origin ID | Broadcast reference | Track reference |
    +-----------+---------------------+-----------------+
    <----- Broadcast identifier ------>
    <---------------- Track identifier ----------------->

            -- Three parts track identifier --
~~~

The origin could then send to the relay an authorization response that would be valid for
all identifiers starting by the specified broadcast reference.

Structuring the track identifier as a three parts identifier may reduce the number of
transactions between relays and origin, but it also carry a small privacy risk, as the relays
can now track which users subscribe to what broadcast ID.

DISCUSS: does this discussion of subscribing and authorizing even belong in the data model?

### Publishing through relays

Some media publications clearly separate how content is uploaded to a "content management
center" (CMS) and then how that content is broadcast to subscribers. In that model, subscribers
can use the MoQ transport to obtain media streams from the CMS acting as "origin", while
uploading the content could use an entirely different "ingress" system. Some other media
experience are more symmetric. For example, in a video conference, participants may publish
their own video and audio tracks. These tracks will be "posted" by the participants, acting
as publishers.

Posting a track through the relay starts with a "post" transaction that describes the
track identifier. That transaction will have to be authorized by the origin, using mechanisms
similar to authorizing subscriptions.

DISCUSS: do we need more details here?

### Relays and caches

TODO: copy existing text.

### Restoring connections through relays

The transmission of a track can be interrupted by various events, such as loss of
connectivity between subscriber and relay. Once connectivity is restored, the subscriber
will want to resume reception, ideally with as few visible gaps in the transmission as possible,
and certainly without having to "replay" media that was already presented.

There is no guarantee that the restored connectivity will have the same characteristics
as the previous instance. The throughput might be lower, forcing the subscriber to select
a media track with lower definition. The network addresses might be different, with the
subscriber connecting to a different relay.

DISCUSS: do we need to describe here the "subscribe intent"? Do we want to reuse the
concept of "groups" or are these specific to tracks? Timestamps may be very useful,
but do we need to attach timestamps to objects? Or do we want to have some indirection,
such as "resume at timestamp T" is translated as "restart track X at group G"?


------ Christian's proposal ends here ------

>Note: This section address some of the shortcomings with the currently specified model by
- adding terminology that can be generically applicable across multiple MOQ application domains
- Clarifying the relationships between the entities of the data model
- Definining object grouping that enables variety of use-cases (low latency publish and retrieval,
   allowing for alternate forms of grouping (slices, tiles in a VR application) and so on
- Allow Relays to operate on data model independent of application logic 

>Note: Once the data model concepts are discussed, the PR will apply the decisions to the
       rest of the document as appropriate

This section defines a data model that expresses the relationship between various WARP 
resources for realizing the client (publishers and subscribers) and relay functionality
for executing the protocol defined in this specification. This section doesn't define 
mapping of the proposed data model to its transport mappings, but capture the entities 
that form a core part of WARP media delivery.                                                                                            


~~~~                                                                                          
                    ┌────────────────────────┐                                                
                    │     MediaSession       │                                                
                    └────────────────────────┘                                                
                      │                                                                       
                      │                                                                       
                      │                                                        
   ┌─────────────────┐│                                                                       
   │MediaStream-1     │├───┬───┬──┬───┬─────────────┬───┬────────────────▶  t                  
   └─────────────────┘│   │G1 │  │G2 │  ◉  ◉  ◉    │GN │                                      
                      │   └───┘  └───┘             └───┘                                      
                      │     ◉      ◉                 ◉                                        
                      │     ◉      ◉                                                          
                      │                                                       
   ┌─────────────────┐│                                                                       
   │MediaStream-2     │├───┬───┬─────┬───┬────┬───┬──────▶  t                                  
   └─────────────────┘│   │G1 │     │G2 │    │G3 │                                            
                      │   └─┬─┘     └─┬─┘    └─┬─┘                                            
                      │     │         │        │                                              
                      │   ┌─┴─┐     ┌─┴─┐    ┌─┴─┐                                            
                      │   │O1 │     │O1 │    │O1 │                             
   ┌─────────────────┐│   └───┘     └───┘    └───┘                                            
   │MediaStream-3     ││─────┬──────────┬───────┬──────────┬────────────┬──────────┬───▶   t   
   └─────────────────┘│     │ Group-1  │       │ Group-2  │   ◉  ◉  ◉  │ Group-N  │           
                      │     └────┬─────┘       └─────┬────┘            └─────┬────┘           
                      │          │                   │                       │                
                      │      ┌───┴───┐           ┌───┴───┐               ┌───┴───┐            
                      │      │object1│           │object1│               │object1│            
                      │      ├───────┤           ├───────┤               ├───────┤            
                             │object2│           │object2│               │object2│            
                             ├───────┤           ├───────┤               ├───────┤            
                             │object3│           │object3│               │object3│            
                             └───────┘           └───────┘               ├───────┤            
                                 ◉                                       │object4│            
                                 ◉                                       └───────┘            
                             ┌───────┐                                                        
                             │objectN│                                                        
                             └───────┘                                                        
~~~~

## MediaSession

MediaSession represents a highest level abstraction or a container from 
a media application perspective using WARP as the media delivery protocol. 
A MediaSession has a defined start and contains one or more MediaStreams produced by a publisher and optionally transferred by relays and consumed by subscribers over time. 

A MediaSession may represent a Broadcast for a live media 
session, an Interactive conference meeting session, a tile-based VR delivery or another media application. 

A MediaSession is described by an alphanumeric MediaSessionID. This mediaSessionID may be a URL, a number, or a combination of the two. A MediaSessionID MUST be globally unique when produced by a publisher. Relays MAY modify the MediaSessionID as objects transit their network, but the original MediaSession ID must be restored when the objects egress their newtwork. 

`
Example valid mediaSessionIDs:
  acme.tv/broadcasts/channel8/alice
  987239847238792871
  5fcf18f9-5f19-4f82-93e7-a4bf21e0bfa6
`

## MediaStream

MediaStreams are the children of MediaSessions. A MediaStream contains a sequential series of MediaGroups.

MediaStreams hold data of a consistent MimeType. Examples of MediaStreams would be 1080p video of a game, or AAC audio, or captions. 

MediaStreams are identified by an alphanumberic MediaStreamID and are independently subscrible assets within a MediaSession.

Examples of valid MediaStreamIDs:

`
  /hd/
  23
  desktopScreenShare
`

## MediaGroup

MediaGroups are the children of MediaSessions. A MediaGroup contains a sequence of MediaObjects
A MediaGroup represents an independent composition of objects, between which exist some form of 
dependency relationship, such as temporal dependency. Groups may be independently 
subscribeable. 

The scope and granularity of the grouping of MediaObjects objects is application defined 
and controlled. Some examples of how this grouping might be defined:

* Each video Group of Pictures (GOP) is mapped to a MediaGroup.  
  The MediaGroup would hold multiple MediaObjects, each holding one video frame.

* Each video frame boundary is mapped to a MediaGroup. 
  There would be a single MediaObject in each mediaGroup, containing a single video frame. 
  
* Each video frame boundary is mapped to a MediaGroup. 
  There would be a multiple MediaObjects in each mediaGroup, each containing a slice of a video frame. 

* A single MediaGroup is mapped to the entire GOP sequence spanning the lifetime of the MediaStream. Each 
Media Object contains a slice of that media Group. 

* Each audio frame is mapped to a MediaGroup. In this grouping, each 
   MediaGroup has a single audio frame as the MediaObject.
   
Each group is identified by its integer `MediaGroupId`. `MediaGroupId` always starts at 0 and increases sequentially 
at the original media publisher.

Examples of valid Group IDs
  0
  131
  278467


## Media Object

Media Objects are the children of MediaGroups and carry a binary payload. Payload examples would include encoded and 
encrypted media data, or caption data or the acceleration data of a racing car. Media Objects have associated 
header/metadata that is authenticated (but not end-to-end encrypted). The metadata contains priority/delivery order, 
time to live, and other information aiding the caching/forwarding decision at the Relays. 

Each MediaObject is identified by a sequentially increasing integer, called MediaObjectId, starting at 0. 

Media Objects represent the cacheable entity within the Warp architecture. For the purposes of publishing, 
caching and retrieval, a Media Object is fully identified by the combination of the following identifiers:

`
Object cache key :=   MediaSessionID | MediaStreamId | MediaGroupId | MediaObjectId
`
These identitiers are stored as separate fields in the header of each MediaObject, to facilitate unambiguous 
extraction by each relay. 

## Scope / Goals of the Data Model

### Subscribers

One of the goals of the proposed data model is to allow subscribers, 
within a MediaSession, to request the right granularity of the media 
resources in a way that is independent of application and a 
given transport mapping.

To that extent, the proposed data model enables following ways for the subscribers 
(end-points or Relays) to ask for the data:

    -  Request a specific MediaSession.  Such a request enables subscribers to 
       receive all future MediaStreams, MediaGroups and MediaoOjects under a 
       given MediaSession.
    -  Request a specific MediaStream. Such a request enables subscribers to 
       receive all future MediaGroups and MediaObjects under a 
       given MediaStream.
    -  Request a specific MediaStream starting at a specific MediaGroup. Since the MediaGroup 
       identification is ordinal, subscribers may request for example content starting from 
       the last, or 3rd last, MediaGroup available in the cache, or from the first one for 
       which MediaGroupID  > N
    - Request a specific MediaSession. Such a request enables subscribers to 
       receive all future MediaStreams, MediaGroups and MediaObjects under a 
       given MediaSession.
       
The MediSession ID to given to each subscriber via an out-of-band mechanism. The subscriber uses this 
MediaSessionID to request the CATALOG, which in turn provides information to the client about the 
MediaStreamIDs which it can use to construct its subscription requests. 


### Relays

Relays within the MoQ architecture take incoming published media objects and 
forward these objects to multiple subscribers with as minimal delay as is necessary. The relays may 
optionally cache the data.
In order for the relays to perform these functions, the data model must 
enable forwarding and/or caching strategies that allow for the appropriate 
retrieval semantics and efficient and  high performace relay operation. 

Let’s consider the example as show in the picture below, where a large number of 
subscribers are interested in media streams from the publisher Alice. In this scenario, 
the publisher Alice has a live brodcast on channel8 with video streams at 3 
different quality (HD, 4K and SD)

More specifically, 

1. Subscriber - S1 is interested in the just the low quality version of the media,
               and asks for the all the media groups/objects under the specific 
               representation for "sd" quality, starting at group 12

2. Subscriber - S2 is fine with receiving highest quality video streams published 
               by Alice, hence asks for the all the media objects under these 
               representations 4k.

3. Rest of the Subscribers (say Sn,…) are fine with getting just the Hi-def and 
low quality streams of the video from Alice, and asks for the representaions 
"sd" and "hd" qualities.

The edge Relay must forward all these subscription requests to the ingest origin in order to receive the content. 

Note: The notation for identifying the resources for subscription are for 
      illustration purposes only.

~~~~                                                                                                                            
                                                    
                                                      sub: acme.tv/brodcasts/channel8/alice/sd/group12                                                                          .    
                                                               ─────.                               
                                                      ┌──────(  S1   )                              
                                                      │       `─────'                               
                                                      │                                             
         sub: acme.tv/broadcasts/channel8/alice/4k.   |
         sub: acme.tv/brodcasts/channel8/alice/sd/12  | 
         sub: acme.tv/brodcasts/channel8/alice/hd     |
            │                                         |
┌──────────────┐                ┌──────────────┐      │   
│              │                │              │      │  sub: acme.tv/brodcasts/channel8/alice/4k
|              |                |              |      |             
│   Ingest     │ ◀──────────────┤  Relay-Edge  │◀─────┘       .─────.                               
│              │                │              │◀────────────(  S2   )                              
└──────▲───────┘                └──────────────┘◀─────┐       `─────'                               
     │                                              │          ◉                                  
     │                                              │          ◉                                  
  .─────.                                           │          ◉                                  
 ( Alice )                                          │                                             
  `─────'                                           │        .─────.                              
                                                    └───────(  SN   )                             
pub: acme.tv/broadcasts/channel8/alice/hd                    `─────'                              
pub: acme.tv/broadcasts/channel8/alice/sd                                                                   
pub: acme.tv/broadcasts/channel8/alice/4k            sub: acme.tv/brodcasts/channel8/alice/sd  
                                                     sub: acme.tv/brodcasts/channel8/alice/hd   

~~~~                                                                                                                             
  
The relay does not intercept and parse the CATALOG messages, therefore it does not know the entireity of 
the content being produced by Alice. It simply aggregates and forwards all subscription requests that 
it receives. 

Similarly, below example shows an Interactive media session 

~~~~ 
  pub: acme.com/meetings/m123/bob/video                                                     
  pub: acme.com/meetings/m123/bob/audio                    
                                                                             sub:acme.com/meetings/m123/bob/audio
              .─────.     sub:acme.com/meetings/m123/alice/audio             sub:acme.com/meetings/m123/alice/audio     
             (  Bob  )                                                       .─────.
              `─────'     sub:acme.com/meetings/m123/alice/video     ┌──────(  S1   )
                 │                                                   │       `─────'
                 │        sub:acme.com/meetings/m123/bob/audio       │
                 │                                                   │
                 │        sub:acme.com/meetings/m123/bob/video       │
                 │                                                   │
          ┌──────▼───────┐                ┌──────────────┐           │
          │              │                │              │           │
          │ Relay-Edge   │ ◀──────────────┤  Relay-Edge  │◀────------┘
          │              │                │              │
          └──────▲───────┘                └──────────────┘◀─────┐
                 │                                              │
                 │                                              │
                 │                                              │
                 │                                              │
              .─────.                                           │
             ( Alice )                                          │
              `─────'                                           │        .─────.
                                                                └───────(  S2   )
     pub: acme.com/meetings/m123/alice/video                             `─────'
     pub: acme.com/meetings/m123/alice/audio
                                                        sub:acme.com/meetings/m123/alice/audio
                                                        sub:acme.com/meetings/m123/alice/video
                                                        sub:acme.com/meetings/m123/bob/audio
                                                        sub:acme.com/meetings/m123/bob/video

~~~~

The above picture shows Warp media delivery, where 
a tree topography is formed with multiple relays in the network. 
The example  has 4 participants with Alice and Bob
being the publishers and S1 and S2 being the subscribers. 
Both Alice and Bob are capable of publishing audio and video
identified by their appropriate names. S1 subscribes 
to audio stream from alice, whereas S2 subscribes
to all the streams being published. The edge Relay
forwards the unique subscriptions to the downstream Realys,
as needed, to setup the delivery network.


### Publishers

Publishers generate media objects within a MediaSession. A 
publisher starts by obtaining a `MediaSessionId` via an out-of-band 
mechanism such as a session bootstrap with the Origin server.

Each MediaObject produced by a publisher contains header fields which identify the MediaSession 
and MediaStream to which it belongs. 

## Terminology Mappings

This section provides mapping of some commonly used terms across different 
application domains to data model used in WARP. Such a mapping is for
informative purposes only and provided for clarifying ambiguities.

### Media Objects

A Warp media object is similar in function to what is often referred 
to as "segments" or "chunks" or "media frames" in other media protocols; 
however, they are different from the traditional notion of chunks. The first 
key distinction is that Warp media objects are not always expected to be 
fully available, and thus any relays have to be able to 
convey partial media objects. The second key distinction is that 
Warp media objects may not be fully decodable by themselves; an 
object will contain a description of the prerequisites if that is the case.

### WarpMediaSession
TODO: Add details

### WarpStream
TODO: Add detials on the relationship between WarpStream and Tracks 


# Motivation

## Latency
In a perfect world, we could deliver live media at the same rate it is produced.
The end-to-end latency of a broadcast would be fixed and only subject to encoding and transmission delays.
Unfortunately, networks have variable throughput, primarily due to congestion.

Attempting to deliver media encoded at a higher bitrate than the network can support causes queuing.
This queuing can occur anywhere in the path between the encoder and decoder.
For example: the application, the OS socket, a wifi router, within an ISP, or generally anywhere in transit.

If nothing is done, new frames will be appended to the end of a growing queue and will take longer to arrive than their predecessors, increasing latency.
Our job is to minimize the growth of this queue, and if necessary, bypass the queue entirely by dropping content.

The speed at which a media protocol can detect and respond to queuing determines the latency.
We can generally classify existing media protocols into two categories based on the underlying network protocol:

* TCP-based media protocols (ex. RTMP, HLS, DASH) are popular due to their simplicity.
Media is served/consumed in decode order while any networking is handled by the TCP layer.
However, these protocols primarily see usage at higher latency targets due to their relatively slow detection and response to queuing.

* UDP-based media protocols (ex. RTP, WebRTC, SRT) can side-step the issues with TCP and provide lower latency with better queue management.
However the media protocol is now responsible for fragmentation, congestion control, retransmissions, receiver feedback, reassembly, and more.
This added complexity significantly raises the implementation difficulty and hurts interoperability.

A goal of this draft is to get the best of both worlds: a simple protocol that can still rapidly detect and respond to congestion.
This is possible with the emergence of QUIC, designed to fix the shortcomings of TCP.

## Universal
The media protocol ecosystem is fragmented; each protocol has it's own niche.
Specialization is often a good thing, but we believe there's enough overlap to warrant consolidation.

For example, a service might simultaneously ingest via WebRTC, SRT, RTMP, and/or a custom UDP protocol depending on the broadcaster.
The same service might then simultaneously distribute via WebRTC, LL-HLS, HLS, (or the DASH variants) and/or a custom UDP protocol depending on the viewer.

These media protocols are often radically different and not interoperable; requiring transcoding or transmuxing.
This cost is further increased by the need to maintain separate stacks with different expertise requirements.

A goal of this draft is to cover a large spectrum of use-cases. Specifically:

* Consolidated contribution and distribution.
The primary difference between the two is the ability to fanout.
How does a CDN know how to forward media to N consumers and how does it reduce the encoded bitrate during congestion?
A single protocol can cover both use-cases provided relays are informed on how to forward and drop media.

* A configurable latency versus quality trade-off.
The producer (broadcaster) chooses how to encode and transmit media based on the desired user experience.
Each consumer (viewer) chooses how long to wait for media based on their desired user experience and network.
We want an experience that can vary from real-time and lossy for one viewer, to delayed and loss-less for another viewer, without separate encodings or protocols.

A related goal is to not reinvent how media is encoded.
The same codec bitstream and container should be usable between different protocols.

## Relays
The prevailing belief is that UDP-based protocols are more expensive and don't "scale".
While it's true that UDP is more difficult to optimize than TCP, QUIC itself is proof that it is possible to reach performance parity.
In fact even some TCP-based protocols (ex. RTMP) don't "scale" either and are exclusively used for contribution as a result.

The ability to scale a media protocol actually depends on relay support: proxies, caches, CDNs, SFUs, etc.
The success of HTTP-based media protocols is due to the ability to leverage traditional HTTP CDNs.

It's difficult to build a CDN for media protocols that were not designed with relays in mind.
For example, an relay has to parse the underlying codec to determine which RTP packets should be dropped first, and the decision is not deterministic or consistent for each hop.
This is the fatal flaw of many UDP-based protocols.

A goal of this draft is to treat relays as first class citizens.
Any identification, reliability, ordering, prioritization, caching, etc is written to the wire in a header that is easy to parse.
This ensures that relays can easily route/fanout media to the final destination.
This also ensures that congestion response is consistent at every hop based on the preferences of the media producer.


# Objects
Warp works by splitting media into objects that can be transferred over QUIC streams

* The encoder determines how to fragment the encoded bitstream into objects ({{media}}).
* Objects are assigned an intended delivery order that should be obeyed during congestion ({{delivery-order}})
* The decoder receives each objects and skips any objects that do not arrive in time ({{decoder}}).

## Media
An encoder produces one or more codec bitstreams for each track.
The decoder processes the codec bitstreams in the same order they were produced, with some possible exceptions based on the encoding.
See the appendix for an overview of media encoding ({{appendix.encoding}}).

Warp works by fragmenting the bitstream into objects that can be transmitted somewhat independently.
Depending on how the objects are fragmented, the decoder has the ability to safely drop media during congestion.
See the appendix for fragmentation examples ({{appendix.examples}})

A media object:

* MUST contain a single track.
* MUST be in decode order. This means an increasing DTS.
* MAY contain any number of frames/samples.
* MAY have gaps between frames/samples.
* MAY overlap with other objects. This means timestamps may be interleaved between objects.

Media objects are encoded using a specified container ({{containers}}).

## Delivery Order
Media is produced with an intended order, both in terms of when media should be presented (PTS) and when media should be decoded (DTS).
As stated in motivation ({{latency}}), the network is unable to maintain this ordering during congestion without increasing latency.

The encoder determines how to behave during congestion by assigning each object a numeric delivery order.
The delivery order SHOULD be followed when possible to ensure that the most important media is delivered when throughput is limited.
Note that the contents within each object are still delivered in order; this delivery order only applies to the ordering between objects.

A sender MUST send each object over a dedicated QUIC stream.
The QUIC library should support prioritization ({{prioritization}}) such that streams are transmitted in delivery order.

A receiver MUST NOT assume that objects will be received in delivery order for a number of reasons:

* Newly encoded objects MAY have a smaller delivery order than outstanding objects.
* Packet loss or flow control MAY delay the delivery of individual streams.
* The sender might not support QUIC stream prioritization.


## Decoder
The decoder will receive multiple objects in parallel and out of order.

Objects arrive in delivery order, but media usually needs to be processed in decode order.
The decoder SHOULD use a buffer to reassmble objects into decode order and it SHOULD skip objects after a configurable duration.
The amount of time the decoder is willing to wait for an object (buffer duration) is what ultimately determines the end-to-end latency.

Objects MUST synchronize frames within and between tracks using presentation timestamps within the container.
Objects are NOT REQUIRED to be aligned and the decoder MUST be prepared to skip over any gaps.


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

## Authentication
The application SHOULD use the WebTransport CONNECT request for authentication.
For example, including an authentication token in the path.

An endpoint SHOULD terminate the connection with an error ({{termination}}) if the peer attempts an unauthorized action.
For example, attempting to use a different role than pre-negotated ({{role}}) or using an invalid broadcast URI ({{message-catalog}}).

## Streams
Warp endpoints communicate over QUIC streams. Every stream is a sequence of messages, framed as described in {{messages}}.

The first stream opened is a client-initiated bidirectional stream where the peers exchange SETUP messages ({{message-setup}}). The subsequent streams MAY be either unidirectional and bidirectional. For exchanging media, an application would typically send a unidirectional stream containing a single OBJECT message ({{message-object}}).

Messages SHOULD be sent over the same stream if ordering is desired.
Some messages MUST be sent over the same stream, for example SUBSCRIBE messages ({{message-subscribe}}) with the same broadcast URI.


## Prioritization
Warp utilizes stream prioritization to deliver the most important content during congestion.

The producer may assign a numeric delivery order to each object ({{delivery-order}})
This is a strict prioritization scheme, such that any available bandwidth is allocated to streams in ascending priority order.
The sender SHOULD prioritize streams based on the delivery order.
If two streams have the same delivery order, they SHOULD receive equal bandwidth (round-robin).

QUIC supports stream prioritization but does not standardize any mechanisms; see Section 2.3 in {{QUIC}}.
In order to support prioritization, a QUIC library MUST expose a API to set the priority of each stream.
This is relatively easy to implement; the next QUIC packet should contain a STREAM frame for the next pending stream in priority order.

The sender MUST respect flow control even if means delivering streams out of delivery order.
It is OPTIONAL to prioritize retransmissions.


## Cancellation
A QUIC stream MAY be canceled at any point with an error code.
The producer does this via a `RESET_STREAM` frame while the consumer requests cancellation with a `STOP_SENDING` frame.

When using `order`, lower priority streams will be starved during congestion, perhaps indefinitely.
These streams will consume resources and flow control until they are canceled.
When nearing resource limits, an endpoint SHOULD cancel the lowest priority stream with error code 0.

The sender MAY cancel streams in response to congestion.
This can be useful when the sender does not support stream prioritization.

## Relays
Warp encodes the delivery information for a stream via OBJECT headers ({{message-object}}).

A relay SHOULD prioritize streams ({{prioritization}}) based on the delivery order.
A relay MAY change the delivery order, in which case it SHOULD update the value on the wire for future hops.

A relay that reads from a stream and writes to stream in order will introduce head-of-line blocking.
Packet loss will cause stream data to be buffered in the QUIC library, awaiting in order delivery, which will increase latency over additional hops.
To mitigate this, a relay SHOULD read and write QUIC stream data out of order subject to flow control limits.
See section 2.2 in {{QUIC}}.

## Congestion Control
As covered in the motivation section ({{motivation}}), the ability to prioritize or cancel streams is a form of congestion response.
It's equally important to detect congestion via congestion control, which is handled in the QUIC layer {{QUIC-RECOVERY}}.

Bufferbloat is caused by routers queueing packets for an indefinite amount of time rather than drop them.
This latency significantly reduces the ability for the application to prioritize or drop media in response to congestion.
Senders SHOULD use a congestion control algorithm that reduces this bufferbloat (ex. {{BBR}}).
It is NOT RECOMMENDED to use a loss-based algorithm (ex. {{NewReno}}) unless the network fully supports ECN.

Live media is application-limited, which means that the encoder determines the max bitrate rather than the network.
Most TCP congestion control algorithms will only increase the congestion window if it is full, limiting the upwards mobility when application-limited.
Senders SHOULD use a congestion control algorithm that is designed for application-limited flows (ex. GCC).
Senders MAY periodically pad the connection with QUIC PING frames to fill the congestion window.

## Termination
The WebTransport session can be terminated at any point with CLOSE\_WEBTRANSPORT\_SESSION capsule, consisting of an integer code and string message.

The application MAY use any error message and SHOULD use a relevant code, as defined below:

|------|--------------------|
| Code | Reason             |
|-----:|:-------------------|
| 0x0  | Session Terminated |
|------|--------------------|
| 0x1  | Generic Error      |
|------|--------------------|
| 0x2  | Unauthorized       |
|------|--------------------|
| 0x10 | GOAWAY             |
|------|--------------------|

* Session Terminated
No error occured, however the endpoint no longer desires to send or receive media.

* Generic Error
An unclassified error occured.

* Unauthorized:
The endpoint breached an agreement, which MAY have been pre-negotiated by the application.

* GOAWAY:
The endpoint successfully drained the session after a GOAWAY was initiated ({{message-goaway}}).


# Messages
Both unidirectional and bidirectional Warp streams are sequences of length-deliminated messages.

~~~
Warp Message {
  Message Type (i),
  Message Length (i),
  Message Payload (..),
}
~~~
{: #warp-message-format title="Warp Message"}

The Message Length field contains the length of the Message Payload field in bytes.
A length of 0 indicates the message is unbounded and continues until the end of the stream.

|------|-----------------------------------|
| ID   | Messages                          |
|-----:|:----------------------------------|
| 0x0  | OBJECT ({{message-object}})       |
|------|-----------------------------------|
| 0x1  | SETUP ({{message-setup}})         |
|------|-----------------------------------|
| 0x2  | CATALOG ({{message-catalog}})     |
|------|-----------------------------------|
| 0x3  | SUBSCRIBE ({{message-subscribe}}) |
|------|-----------------------------------|
| 0x10 | GOAWAY ({{message-goaway}})       |
|------|-----------------------------------|

## SETUP {#message-setup}

The `SETUP` message is the first message that is exchanged by the client and the server; it allows the peers to establish the mutually supported version and agree on the initial configuration. It is a sequence of key-value pairs called *SETUP parameters*; the semantics and the format of individual parameter values MAY depend on what party is sending it.

The wire format of the SETUP message is as follows:

~~~
SETUP Parameter {
  Parameter Key (i),
  Parameter Value Length (i),
  Parameter Value (..),
}

Client SETUP Message Payload {
  Number of Supported Versions (i),
  Supported Version (i) ...,
  SETUP Parameters (..) ...,
}

Server SETUP Message Payload {
  Selected Version (i),
  SETUP Parameters (..) ...,
}
~~~
{: #warp-setup-format title="Warp SETUP Message"}

The Parameter Value Length field indicates the length of the Parameter Value.

The client offers the list of the protocol versions it supports; the server MUST reply with one of the versions offered by the client. If the server does not support any of the versions offered by the client, or the client receives a server version that it did not offer, the corresponding peer MUST close the connection.

The SETUP parameters are described in the {{setup-parameters}} section.


## OBJECT {#message-object}
A OBJECT message contains a single media object associated with a specified track, as well as associated metadata required to deliver, cache, and forward it.

The format of the OBJECT message is as follows:

~~~
OBJECT Message {
  Broadcast URI (b)
  Track ID (i),
  Group Sequence (i),
  Object Sequence (i),
  Object Delivery Order (i),
  Object Payload (b),
}
~~~
{: #warp-object-format title="Warp OBJECT Message"}

* Broadcast URI:
The broadcast URI as declared in CATALOG ({{message-catalog}}).

* Track ID:
The track identifier as declared in CATALOG ({{message-catalog}}).

* Group Sequence :
An integer always starts at 0 and increases sequentially at the original media publisher.
Group sequences are scoped under a Track.

* Object Sequence:
An integer always starts at 0 with in a Group and increases sequentially.
Object Sequences are scoped to a Group.

* Object Delivery Order:
An integer indicating the object delivery order ({{delivery-order}}).

* Object Payload:
The format depends on the track container ({{containers}}).
This is a media bitstream intended for the decoder and SHOULD NOT be processed by a relay.


## CATALOG {#message-catalog}
The sender advertises an available broadcast and its tracks via the CATALOG message.

The format of the CATALOG message is as follows:

~~~
CATALOG Message {
  Broadcast URI (b),
  Track Count (i),
  Track Descriptors (..)
}
~~~
{: #warp-catalog-format title="Warp CATALOG Message"}

* Broadcast URI:
A unique identifier {{URI}} for the broadcast within the session.

* Track Count:
The number of tracks in the broadcast.


For each track, there is a track descriptor with the format:

~~~
Track Descriptor {
  Track ID (i),
  Container Format (i),
  Container Init Payload (b)
}
~~~
{: #warp-track-descriptor title="Warp Track Descriptor"}

* Track ID:
A unique identifier for the track within the broadcast.

* Container Format:
The container format as defined in {{containers}}.

* Container Init Payload:
A container-specific payload as defined in {{containers}}.
This contains base information required to decode OBJECT messages, such as codec parameters.


An endpoint MUST NOT send multiple CATALOG messages with the same Broadcast URI.
A future draft will add the ability to add/remove/update tracks.

## SUBSCRIBE {#message-subscribe}
After receiving a CATALOG message ({{message-catalog}}, the receiver sends a SUBSCRIBE message to indicate that it wishes to receive the indicated tracks within a broadcast.

The format of SUBSCRIBE is as follows:

~~~
SUBSCRIBE Message {
  Broadcast URI (b),
  Track Count (i),
  Track IDs (..),
}
~~~
{: #warp-subscribe-format title="Warp SUBSCRIBE Message"}

* Broadcast URI:
The broadcast URI as defined in CATALOG ({{message-catalog}}).

* Track Count:
The number of track IDs that follow.
This MAY be zero to unsubscribe to all tracks.

* Track IDs:
A list of varint track IDs.


Only the most recent SUBSCRIBE message for a broadcast is active.
SUBSCRIBE messages MUST be sent on the same QUIC stream to preserve ordering.


## GOAWAY {#message-goaway}
The `GOAWAY` message is sent by the server to force the client to reconnect.
This is useful for server maintenance or reassignments without severing the QUIC connection.
The server MAY be a producer or consumer.

The server:

* MAY initiate a graceful shutdown by sending a GOAWAY message.
* MUST close the QUIC connection after a timeout with the GOAWAY error code ({{termination}}).
* MAY close the QUIC connection with a different error code if there is a fatal error before shutdown.
* SHOULD wait until the `GOAWAY` message and any pending streams have been fully acknowledged, plus an extra delay to ensure they have been processed.

The client:

* MUST establish a new WebTransport session to the provided URL upon receipt of a `GOAWAY` message.
* SHOULD establish the connection in parallel which MUST use different QUIC connection.
* SHOULD remain connected for two servers for a short period, processing objects from both in parallel.

# SETUP Parameters

The SETUP message ({{message-setup}}) allows the peers to exchange arbitrary parameters before any media is exchanged. It is the main extensibility mechanism of Warp. The peers MUST ignore unknown parameters. TODO: describe GREASE for those.

Every parameter MUST appear at most once within the SETUP message. The peers SHOULD verify that and close the connection if a parameter appears more than once.

The ROLE parameter is mandatory for the client. All of the other parameters are optional.

## ROLE parameter {#role}

The ROLE parameter (key 0x00) allows the client to specify what roles it expects the parties to have in the Warp connection. It has three possible values:

0x01:

: Only the client is expected to send media on the connection. This is commonly referred to as *the ingestion case*.

0x02:

: Only the server is expected to send media on the connection. This is commonly referred to as *the delivery case*.

0x03:

: Both the client and the server are expected to send media.

The client MUST send a ROLE parameter with one of the three values specified above. The server MUST close the connection if the ROLE parameter is missing, is not one of the three above-specified values, or it is different from what the server expects based on the application in question.

# Containers
The container format describes how the underlying codec bitstream is encoded.
This includes timestamps, metadata, and generally anything required to decode and display the media.

This draft currently specifies only a single container format.
Future drafts and extensions may specifiy additional formats.

|------|------------------|
| ID   | Container Format |
|-----:|:-----------------|
| 0x0  | fMP4 ({{fmp4}})  |
|------|------------------|

## fMP4
A fragmented MP4 container  {{ISOBMFF}}.

The "Container Init Payload" in a CATALOG message ({{message-catalog}}) MUST consist of a File Type Box (ftyp) followed by a Movie Box (moov).
This Movie Box (moov) consists of Movie Header Boxes (mvhd), Track Header Boxes (tkhd), Track Boxes (trak), followed by a final Movie Extends Box (mvex).
These boxes MUST NOT contain any samples and MUST have a duration of zero.
A Common Media Application Format Header {{CMAF}} meets all these requirements.

The "Object Payload" in an OBJECT message ({{message-object}}) MUST consist of a Segment Type Box (styp) followed by any number of media fragments.
Each media fragment consists of a Movie Fragment Box (moof) followed by a Media Data Box (mdat).
The Media Fragment Box (moof) MUST contain a Movie Fragment Header Box (mfhd) and Track Box (trak) with a Track ID (`track_ID`) matching a Track Box in the initialization fragment.
A Common Media Application Format Segment {{CMAF}} meets all these requirements.

Media fragments can be packaged at any frequency, causing a trade-off between overhead and latency.
It is RECOMMENDED that a media fragment consists of a single frame to minimize latency.


# Security Considerations

## Resource Exhaustion
Live media requires significant bandwidth and resources.
Failure to set limits will quickly cause resource exhaustion.

Warp uses QUIC flow control to impose resource limits at the network layer.
Endpoints SHOULD set flow control limits based on the anticipated media bitrate.

The media producer prioritizes and transmits streams out of order.
Streams might be starved indefinitely during congestion.
The producer and consumer MUST cancel a stream, preferably the lowest priority, after reaching a resource limit.

# IANA Considerations

TODO: fill out currently missing registries:
* Warp version numbers
* SETUP parameters
* Track format numbers
* Message types
* Object headers

# Appendix A. Video Encoding {#appendix.encoding}
In order to transport media, we first need to know how media is encoded.
This section is an overview of media encoding.

## Tracks
A broadcast consists of one or more tracks.
Each track has a type (audio, video, caption, etc) and uses a corresponding codec.
There may be multiple tracks, including of the same type for a number of reasons.

For example:

* A track for each codec.
* A track for each resolution and bitrate.
* A track for each language.
* A track for each camera feed.

Tracks can be muxed together into a single container or stream.
The goal of Warp is to independently deliver tracks, and even parts of a track, so this is not allowed.
Each Warp object MUST contain a single track.

## Init {#appendix.init}
Media codecs have a wide array of configuration options.
For example, the resolution, the color space, the features enabled, etc.

Before playback can begin, the decoder needs to know the configuration.
This is done via a short payload at the very start of the media file.
The initialization payload MAY be cached and reused between objects with the same configuration.

## Video {#appendix.video}
Video is a sequence of pictures (frames) with a presentation timestamp (PTS).

An I-frame is a frame with no dependencies and is effectively an image file.
These frames are usually inserted at a frequent interval to support seeking or joining a live stream.
However they can also improve compression when used at scene boundaries.

A P-frame is a frame that references on one or more earlier frames.
These frames are delta-encoded, such that they only encode the changes (motion).
This result in a massive file size reduction for most content outside of few notorious cases (ex. confetti).

A common encoding structure is to only reference the previous frame, as it is simple and minimizes latency:

~~~
 I <- P <- P <- P   I <- P <- P <- P   I <- P ...
~~~

There is no such thing as an optimal encoding structure.
Encoders tuned for the best quality will produce a tangled spaghetti of references.
Encoders tuned for the lowest latency can avoid reference frames to allow more to be dropped.

### B-Frames {#appendix.b-frame}
The goal of video codecs is to maximize compression.
One of the improvements is to allow a frame to reference later frames.

A B-frame is a frame that can reference one or more frames in the future, and any number of frames in the past.
These frames are more difficult to encode/decode as they require buffering and reordering.

A common encoding structure is to use B-frames in a fixed pattern.
Such a fixed pattern is not optimal, but it's simpler for hardware encoding:

~~~
    B     B         B     B         B
   / \   / \       / \   / \       / \
  v   v v   v     v   v v   v     v   v
 I <-- P <-- P   I <-- P <-- P   I <-- P ...
~~~

### Timestamps
Each frame is assigned a presentation timestamp (PTS), indicating when it should be shown relative to other frames.

The encoder outputs the bitstream in decode order, which means that each frame is output after its references.
This makes it easier for the decoder as all references are earlier in the bitstream and can be decoded immediately.

However, this causes problems with B-frames because they depend on a future frame, and some reordering has to occur.
In order to keep track of this, frames have a decode timestamp (DTS) in addition to a presentation timestamp (PTS).
A B-frame will have higher DTS value that its dependencies, while PTS and DTS will be the same for other frame types.

For the example above, this would look like:

~~~
     0 1 2 3 4 5 6 7 8 9 10
PTS: I B P B P I B P B P B
DTS: I   PB  PBI   PB  PB
~~~

B-frames add latency because of this reordering so they are usually not used for conversational latency.

### Group of Pictures {#appendix.gop}
A group of pictures (GoP) is an I-frame followed by any number of frames until the next I-frame.
All frames MUST reference, either directly or indirectly, only the most recent I-frame.

~~~
        GoP               GoP            GoP
+-----------------+-----------------+---------------
|     B     B     |     B     B     |     B
|    / \   / \    |    / \   / \    |    / \
|   v   v v   v   |   v   v v   v   |   v   v
|  I <-- P <-- P  |  I <-- P <-- P  |  I <-- P ...
+-----------------+-----------------+--------------
~~~

This is a useful abstraction because GoPs can always be decoded independently.

### Scalable Video Coding {#appendix.svc}
Some codecs support scalable video coding (SVC), in which the encoder produces multiple bitstreams in a hierarchy.
This layered coding means that dropping the top layer degrades the user experience in a configured way.
Examples include reducing the resolution, picture quality, and/or frame rate.

Here is an example SVC encoding with 3 resolutions:

~~~
      +-------------------------+------------------
   4k |  P <- P <- P <- P <- P  |  P <- P <- P ...
      |  |    |    |    |    |  |  |    |    |
      |  v    v    v    v    v  |  v    v    v
      +-------------------------+------------------
1080p |  P <- P <- P <- P <- P  |  P <- P <- P ...
      |  |    |    |    |    |  |  |    |    |
      |  v    v    v    v    v  |  v    v    v
      +-------------------------+------------------
 360p |  I <- P <- P <- P <- P  |  I <- P <- P ...
      +-------------------------+------------------
~~~

## Audio {#appendix.audio}
Audio is dramatically simpler than video as it is not typically delta encoded.
Audio samples are grouped together (group of samples) at a configured rate, also called a "frame".

The encoder spits out a continuous stream of samples (S):

~~~
S S S S S S S S S S S S S ...
~~~


# Appendix B. Object Examples {#appendix.examples}
Warp offers a large degree of flexibility on how objects are fragmented and prioritized.
There is no best solution; it depends on the desired complexity and user experience.

This section provides a summary of some options available.

## Video

### Group of Pictures
A group of pictures (GoP) is consists of an I-frame and all frames that directly or indirectly reference it ({{appendix.gop}}).
The tail of a GoP can be dropped without causing decode errors, even if the encoding is otherwise unknown, making this the safest option.

It is RECOMMENDED that each object consist of a single GoP.
For example:

~~~
     object 1        object 2     object 3
+---------------+---------------+---------
| I  P  B  P  B | I  P  B  P  B | I  P  B
+---------------+---------------+---------
~~~

Depending on the video encoding, this approach may introduce unnecessary ordering and dependencies.
A better option may be available below.

### Scalable Video Coding
Some codecs support scalable video coding (SVC), in which the encoder produces multiple bitstreams in a hierarchy ({{appendix.svc}}).

When SVC is used, it is RECOMMENDED that each object consist of a single layer and GoP.
For example:

~~~
                object 3              object 6
      +-------------------------+---------------
   4k |  P <- P <- P <- P <- P  |  P <- P <- P
      |  |    |    |    |    |  |  |    |    |
      |  v    v    v    v    v  |  v    v    v
      +-------------------------+--------------

                object 2              object 5
      +-------------------------+---------------
1080p |  P <- P <- P <- P <- P  |  P <- P <- P
      |  |    |    |    |    |  |  |    |    |
      |  v    v    v    v    v  |  v    v    v
      +-------------------------+--------------

                object 1              object 4
      +-------------------------+---------------
 360p |  I <- P <- P <- P <- P  |  I <- P <- P
      +-------------------------+---------------
~~~


### Frames
With full knowledge of the encoding, the encoder MAY can split a GoP into multiple objects based on the frame.
However, this is highly dependent on the encoding, and the additional complexity might not improve the user experience.

For example, we could split our example B-frame structure ({{appendix.b-frame}}) into 13 objects:

~~~
      2     4           7     9           12
+--------+--------+--------+--------+-----------+
|     B  |  B     |     B  |  B     |     B     |
|-----+--+--+-----+-----+--+--+-----+-----+-----+
|  I  |  P  |  P  |  I  |  P  |  P  |  I  |  P  |
+-----+-----+-----+-----+-----+-----+-----+-----+
   1     3     5     6     8     10    11    13
~~~

Objects can be merged with their dependency to reduce the total number of objects.
QUIC streams will deliver each object in order so the QUIC library performs the reordering.

The same GoP structure can be represented using eight objects:

~~~
      2     3           5     6           8
+--------+--------+-----------------+------------
|     B  |  B     |     B  |  B     |     B     |
+--------+--------+--------+--------+-----------+
|  I     P     P  |  I     P     P  |  I     P
+-----------------+-----------------+------------
         1                 4              7
~~~

We can further reduce the number of objects by combining frames that don't depend on each other.
The only restriction is that frames can only reference frames earlier in the object.
For example, non-reference frames can have their own object so they can be prioritized or dropped separate from reference frames.

The same GoP structure can also be represented using six objects, although we've removed the ability to drop individual B-frames:

~~~
    object 2      object 4    object 6
+-------------+-------------+---------
|    B   B    |    B   B    |    B
+-------------+-------------+---------
|  I   P   P  |  I   P   P  |  I   P
+-------------+-------------+---------
    object 1      object 3    object 5
~~~

### Init
Initialization data ({{appendix.init}}) is required to initialize the decoder.
Each object MAY start with initialization data although this adds overhead.

Instead, it is RECOMMENDED to create a init object.
Each media object can then depend on the init object to avoid the redundant overhead.
For example:

~~~
     object 2        object 3     object 5
+---------------+---------------+---------
| I  P  B  P  B | I  P  B  P  B | I  P  B
+---------------+---------------+---------
|              init             |  init
+-------------------------------+---------
              object 1            object 4
~~~


## Audio
Audio ({{appendix.audio}}) is much simpler than video so there's fewer options.

The simplest configuration is to use a single object for each audio track.
This may seem inefficient given the ease of dropping audio samples.
However, the audio bitrate is low and gaps cause quite a poor user experience, when compared to video.

~~~
          object 1
+---------------------------
| S S S S S S S S S S S S S
+---------------------------
~~~

An improvement is to periodically split audio samples into separate objects.
This gives the consumer the ability to skip ahead during severe congestion or temporary connectivity loss.

~~~
     object 1        object 2     object 3
+---------------+---------------+---------
| S  S  S  S  S | S  S  S  S  S | S  S  S
+---------------+---------------+---------
~~~

This frequency of audio objects is configurable, at the cost of additional overhead.
It's NOT RECOMMENDED to create a object for each audio frame because of this overhead.

Since video can only recover from severe congestion with an I-frame, so there's not much point recovering audio at a separate interval.
It is RECOMMENDED to create a new audio object at each video I-frame.

~~~
     object 1        object 3     object 5
+---------------+---------------+---------
| S  S  S  S  S | S  S  S  S  S | S  S  S
+---------------+---------------+---------
| I  P  B  P  B | I  P  B  P  B | I  P  B
+---------------+---------------+---------
     object 2        object 4     object 6
~~~

## Delivery Order {#appendix.delivery-order}
The delivery order ({{delivery-order}} depends on the desired user experience during congestion:

* if media should be skipped: delivery order = PTS
* if media should not be skipped: delivery order = -PTS
* if video should be skipped before audio: audio delivery order < video delivery order

The delivery order may be changed if the content changes.
For example, switching from a live stream (skippable) to an advertisement (unskippable).

# Contributors
{:numbered="false"}

- Alan Frindell
- Charles Krasic
- Cullen Jennings
- James Hurley
- Jordi Cenzano
- Mike English
- Will Law
- Ali Begen
