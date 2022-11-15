SOURCES?=${wildcard draft-*.md}
TEXT=${SOURCES:.md=.txt}
HTML=${SOURCES:.md=.html}
XML=${SOURCES:.md=.xml}

all:    html text
html:   $(HTML)
text:	$(TEXT)
xml:    $(XML)

%.xml:	%.md
	kramdown-rfc $< >$@.new
	mv $@.new $@

%.html: %.xml
	xml2rfc --html $<

%.txt:	%.xml
	xml2rfc $<
