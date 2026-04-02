Ah, `0x40` is `RESERVED (CLIENT_SETUP for <= 10)`. So we can't use `0x40` for FETCH_HEADER, since it's reserved for backwards compatibility.
What if we use `0x42`?
```
| 0x42        | FETCH_HEADER  ({{fetch-header}})                |
```
Then `0x00..0x0F / 0x20..0x2F` can be used for `OBJECT_DATAGRAM / FETCH_HEADER`? Wait, no, we want to rename `OBJECT_DATAGRAM` to `FETCH_DATAGRAM`? No.
If we change `FETCH_HEADER` to `0x42` (or similar), we can just use `0x00..0x0F / 0x20..0x2F` for streams!
Let's see what the current Stream Types and Message Types are.
```
| 0x40   | RESERVED (CLIENT_SETUP for <= 10)             |                |
| 0x41   | RESERVED (SERVER_SETUP for <= 10)             |                |
```
We could use `0x42` for `FETCH_HEADER`. But wait, maybe we don't need to rename `FETCH_HEADER`.
What if `OBJECT_STREAM` uses `0b0101XXXX` (`0x50`..`0x5F`, etc)?
Let's see: `0b0101XXXX` is `0x50` to `0x5F` and `0x70` to `0x7F`.
Wait, why not just change `SUBGROUP_HEADER` to have `SUBGROUP_ID_MODE` = `0b11`?
Why did I think that would still need `Object ID Delta`?
Because `SUBGROUP_HEADER` is followed by Object Fields.
If we add a new mode `0b11`, we can just specify that for `0b11`, the stream contains ONE object, and the fields AFTER the header are ONLY the payload!
Wait, `SUBGROUP_HEADER` has:
```
SUBGROUP_HEADER {
  Type (i) = 0x10..0x15 / 0x18..0x1D / 0x30..0x35 / 0x38..0x3D,
  Track Alias (vi64),
  Group ID (vi64),
  [Subgroup ID (vi64),]
  [Publisher Priority (8),]
}
```
If we use `0b11`, we could say:
`* 0b11: The Subgroup ID field is absent. The stream contains exactly one Object, and the Object ID is the Object ID field in the header.`
Wait, there is NO Object ID field in the header!
So we'd have to ADD it!
```
SUBGROUP_HEADER {
  Type (i) = 0x10..0x17 / 0x18..0x1F / 0x30..0x37 / 0x38..0x3F,  # allow 0b11
  Track Alias (vi64),
  Group ID (vi64),
  [Subgroup ID (vi64),]
  [Object ID (vi64),]  # Present if SUBGROUP_ID_MODE is 0b11
  [Publisher Priority (8),]
}
```
And then what about `Properties` and `Object Status`?
Currently, properties are per-object, but `SUBGROUP_HEADER` has a `PROPERTIES` bit (0x01) which puts the properties on EVERY object.
If we just want "Single Object Subgroup" to act EXACTLY like Datagram, we might as well just use the Datagram format directly!
Let's see what happens if we change the Datagram section.
Section 7.2.1 Object Datagram
```
An `OBJECT_DATAGRAM` carries a single object in a datagram.
```
If we rename it to `OBJECT_DATAGRAM` and `FETCH_DATAGRAM`? No.
If we rename it to `OBJECT_DATAGRAM` and allow it to be a Stream Type?
Let's look at `Data Streams and Datagrams` (Section 7).
```
Unidirectional stream types are defined in {{stream-types}}. Data streams
use SUBGROUP_HEADER or FETCH_HEADER types.

All MOQT datagrams start with a variable-length integer indicating the type of
the datagram.  See {{object-datagram}}.
```
If we change it to:
```
Data streams use SUBGROUP_HEADER, FETCH_HEADER, or OBJECT_DATAGRAM types.
...
An Object received in an `OBJECT_DATAGRAM` message (whether sent in a Datagram or a Stream) has an `Object Forwarding Preference` = `Datagram`.
...
An `OBJECT_DATAGRAM` carries a single object in a datagram or stream.
```
Wait, if it's sent in a Stream, does it still have `Object Forwarding Preference` = `Datagram`?
No! "Single Object Subgroups don't need a Subgroup ID".
If it's a Subgroup, it has `Object Forwarding Preference` = `Subgroup`!
But datagram framing for a subgroup object?
Ah! "My strawman is to do what we do for Objects in Datagrams".
If we just make `SUBGROUP_ID_MODE = 0b11` mean "No Subgroup ID, only one object".
Let's trace what "do what we do for Objects in Datagrams" means. Datagrams don't have Subgroup ID. Datagrams have Object ID. Datagrams have the payload as the remainder of the datagram.
If we define `SINGLE_OBJECT_HEADER` or add it to `SUBGROUP_HEADER`.

Let's look at the PR 1405 again.
"A key purpose of a Subgroup ID is to allow the second half of a Subgroup to be delivered on a different stream and put together with the first half if the stream is unexpected terminated for any reason.
If a Stream only has one Object, there's no need for that."
This implies the object is sent on a stream.
"My strawman is to do what we do for Objects in Datagrams"

So we can define a `SINGLE_OBJECT_STREAM` that works exactly like `OBJECT_DATAGRAM` but for Streams, and has `Object Forwarding Preference = Subgroup`.
Wait, why not just redefine `OBJECT_DATAGRAM` to `OBJECT_MESSAGE` and say it can be sent on Datagrams or Streams? If sent on a Datagram, it has Forwarding Preference `Datagram`. If sent on a Stream, it has Forwarding Preference `Subgroup`?
Yes! That is elegant.
Wait, if we rename `OBJECT_DATAGRAM` to `OBJECT_MESSAGE`, what about the Stream Type collision?
If `FETCH_HEADER` is `0x05`. And `OBJECT_MESSAGE` is `0x00..0x0F / 0x20..0x2D`. Then `0x05` on a Stream is ambiguous.
Wait, if `0x05` is ambiguous, we can change `FETCH_HEADER` to `0x02`? No, `0x02` is also in `0x00..0x0F`.
What if we change `OBJECT_MESSAGE` to use `0b0100XXXX` and `0b0110XXXX` when on a stream?
No, the easiest is to just change `FETCH_HEADER` to `0x40`. `0x40` is `0b01000000`. And `0x40` is already reserved:
`| 0x40   | RESERVED (CLIENT_SETUP for <= 10)             |                |`
Wait, it's reserved for `<= 10`. Can we reuse it?
Actually, `0x05` was `FETCH_HEADER`. What if we move `FETCH_HEADER` to `0x01`? `0x01` is `RESERVED (SETUP for version 00)`.
What if we move `FETCH_HEADER` to `0x06`? Wait, `0x06` is also in `0x00..0x0F`.
We need a Stream Type OUTSIDE of `0x00..0x0F` and `0x20..0x2F` and `0x10..0x1F` and `0x30..0x3F`.
So we need `0x42`, `0x43`, etc.
`0x42` is perfect.
Let's check `0x42` in draft. It's not used.
If we change `FETCH_HEADER` to `0x42`, then `0x00..0x0F / 0x20..0x2F` can be used for Streams.
