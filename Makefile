OPEN=$(word 1, $(wildcard /usr/bin/xdg-open /usr/bin/open /bin/echo))
SOURCES?=${wildcard *.md}
TEXT=${SOURCES:.md=.txt}
HTML=${SOURCES:.md=.html}

text:	$(TEXT)
html:   $(HTML)

%.xml:	%.md
	kramdown-rfc2629 $< >$@.new
	mv $@.new $@

%.html: %.xml
	xml2rfc --html $<
	$(OPEN) $@

%.txt:	%.xml
	xml2rfc $<
