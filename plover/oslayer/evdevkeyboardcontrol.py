# -*- coding: utf-8 -*-
#
# Copyright (c) 2010 Joshua Harlan Lifton.
# See LICENSE.txt for details.
#
# keyboardcontrol.py - capturing and injecting X keyboard events
#
# This code requires the X Window System with the 'XInput2' and 'XTest'
# extensions and python-xlib with support for said extensions.

"""Keyboard capture and control using evdev.

This currently requires plover to be run as root.

This module provides an interface for basic keyboard event capture and
emulation. Set the key_up and key_down functions of the
KeyboardCapture class to capture keyboard input. Call the send_string
and send_backspaces functions of the KeyboardEmulation class to
emulate keyboard input.

"""

from functools import wraps
import errno
import os
import string
import select
import threading

from plover.key_combo import add_modifiers_aliases, parse_key_combo
from plover import log

from evdev import ecodes as e, UInput, InputDevice, KeyEvent
from evdev.util import list_devices, categorize

# The name assigned to the emulated keyboard
UINPUT_NAME = 'Plover'

def is_keyboard(path):
    dev = InputDevice(path)
    try:
        if dev.name.startswith == UINPUT_NAME:
            return False
        cap = dev.capabilities()
        return (e.EV_KEY in cap and
                e.KEY_A in cap[e.EV_KEY])
    finally:
        dev.close()


class KeyboardCapture(threading.Thread):
    """Listen to keyboard press and release events."""

    def __init__(self):
        """Prepare to listen for keyboard events."""
        super().__init__(name='capture')
        self.dev = None
        self.suppress_keys = ()
        self.key_down = lambda key: None
        self.key_up = lambda key: None

    def _capture_first_keyboard(self):
        path = next(filter(is_keyboard, list_devices()))
        print('Using device:', path)
        self.dev = InputDevice(path)
        print(self.dev.name)
        pass

    def run(self):
        try:
            self.dev.grab()

            for event in self.dev.read_loop():
                if event.type == e.EV_KEY and KeyEvent(event).scancode == e.KEY_ESC:
                    break
                print(categorize(event))

        finally:
            print("Goodbye")
            self.dev.ungrab()
            self.dev.close()

    def start(self):
        self._capture_first_keyboard()
        super().start()

    def cancel(self):
        pass

    def suppress_keyboard(self, suppressed_keys=()):
        print(suppressed_keys)
        self.suppress_keys = suppressed_keys


class KeyboardEmulation:
    """Emulate keyboard events."""

    def __init__(self):
        """Prepare to emulate keyboard events."""
        pass

    def send_backspaces(self, number_of_backspaces):
        """Emulate the given number of backspaces.

        The emulated backspaces are not detected by KeyboardCapture.

        Argument:

        number_of_backspace -- The number of backspaces to emulate.

        """
        pass

    def send_string(self, s):
        """Emulate the given string.

        The emulated string is not detected by KeyboardCapture.

        Argument:

        s -- The string to emulate.

        """
        pass

    def send_key_combination(self, combo_string):
        """Emulate a sequence of key combinations.

        KeyboardCapture instance would normally detect the emulated
        key events. In order to prevent this, all KeyboardCapture
        instances are told to ignore the emulated key events.

        Argument:

        combo_string -- A string representing a sequence of key
        combinations. Keys are represented by their names in the
        Xlib.XK module, without the 'XK_' prefix. For example, the
        left Alt key is represented by 'Alt_L'. Keys are either
        separated by a space or a left or right parenthesis.
        Parentheses must be properly formed in pairs and may be
        nested. A key immediately followed by a parenthetical
        indicates that the key is pressed down while all keys enclosed
        in the parenthetical are pressed and released in turn. For
        example, Alt_L(Tab) means to hold the left Alt key down, press
        and release the Tab key, and then release the left Alt key.

        """
        pass
