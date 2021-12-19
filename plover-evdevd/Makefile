install:
	install -m755 plover-evdevd.py /usr/bin/plover-evdevd
	install -m644 plover-evdevd.service /usr/lib/systemd/system/plover-evdevd.service
	systemctl start --now plover-evdevd

uninstall:
	systemctl disable --now plover-evdevd
	rm -f /usr/bin/plover-evdevd /usr/lib/systemd/system/plover-evdevd.service

.PHONY: install uninstall
