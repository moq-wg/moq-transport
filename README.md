# MoQ Transport
MoQ Transport is a live media protocol that utilizes QUIC streams.

[Latest Draft](https://moq-wg.github.io/moq-transport/draft-lcurley-moq-transport.html)


## Contributing
All changes need to be made to the markdown file (.md).
You can find a reference for the synatax [here](https://kramdown.gettalong.org/syntax.html).
Each sentence is separated with a newline to reduce the number of merge conflicts.

If you want to locally build, you'll need to install [kramdown-rfc2629](https://github.com/cabo/kramdown-rfc) and [xml2rfc](https://github.com/ietf-tools/xml2rfc):

```bash
gem install kramdown-rfc
pip install xm2rfc
```

Then you can use the `Makefile` to build:

```bash
make html
```
