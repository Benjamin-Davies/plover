all:
	cargo build --release
	sudo make install

install:
	install -m755 ./target/release/plover-evdevd /usr/bin/plover-evdevd
	chmod u+s /usr/bin/plover-evdevd

.PHONY: all install
