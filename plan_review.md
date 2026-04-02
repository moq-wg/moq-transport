The plan is to add support for single object subgroups that use Datagram-style framing. I will make the following specific edits to `draft-ietf-moq-transport.md`:

1.  **Change FETCH_HEADER Type to avoid collision**:
    -   In Section 2.4 (Unidirectional Stream Types), change `0x05` for `FETCH_HEADER` to `0x50` (or similar available type, like `0x50`).
    -   Update `FETCH_HEADER` definition (Section 7.3.2) from `0x05` to `0x50`.

2.  **Add `OBJECT_STREAM` to Stream Types**:
    -   In Section 2.4 (Unidirectional Stream Types), add a new entry:
        `| 0x00-0x0F / 0x20-0x2D | OBJECT_STREAM  ({{object-datagram}}) |`
    -   Update the text in Section 7 (Data Streams and Datagrams): "Data streams use SUBGROUP_HEADER, FETCH_HEADER, or OBJECT_STREAM types."

3.  **Rename Object Datagram to Single Object Delivery**:
    -   Rename Section 7.2.1 from `### Object Datagram` to `### Single Object Delivery`.
    -   Update the text to indicate that an Object can be sent in a Datagram or a Stream using this exact same format. When sent in a datagram, it is an `OBJECT_DATAGRAM` (Object Forwarding Preference = Datagram). When sent in a stream, it is an `OBJECT_STREAM` (Object Forwarding Preference = Subgroup).
    -   Update the format struct to `OBJECT_DATAGRAM / OBJECT_STREAM { Type (i) = 0x00..0x0F ... }`.
    -   Update the descriptive text indicating that the entirety of the datagram *or stream* following the Object header contains the payload.
    -   Ensure that references to `OBJECT_DATAGRAM` also account for `OBJECT_STREAM`.

4.  **Run Build and Tests**:
    -   Run `make all` to build the IETF specifications and check for errors, ensuring the markdown is perfectly formatted.

5.  **Pre-commit and Submission**:
    -   Call `pre_commit_instructions` and follow its instructions to complete pre-commit steps to make sure proper testing, verifications, reviews, and reflections are done.
    -   Submit the PR.
