# installs kramdown-rfc and xml2rfc
FROM ubuntu:latest

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
	apt-get install -y \
	pip \
	ruby

RUN gem install kramdown-rfc
RUN pip install xml2rfc

ENTRYPOINT [ "make" ]
