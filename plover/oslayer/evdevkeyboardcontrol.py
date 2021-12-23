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
from subprocess import Popen, PIPE
import threading

from plover.key_combo import add_modifiers_aliases, parse_key_combo
from plover import log

# List of keys with index = key id
# I'm unsure if all of these are available to Plover, but they're here for completeness sake
# See also /usr/include/linux/input-event-codes.h
# TODO: check existing names for KP and Meta
KEYS = '''
Reserved
  Escape 1 2 3 4 5 6 7 8 9 0 - = BackSpace
    Tab   q w e r t y u i o p [ ] Return
 control_l a s d f g h j k l ; ' `
 shift_l \\ z x c v b n m , . / shift_r
        _* alt_l space CapsLock
F1 F2 F3 F4 F5 F6 F7 F8 F9 F10
NumLock ScrollLock
    _7 _8 _9 _-
    _4 _5 _6 _+
    _1 _2 _3
    _0 _. _

ZenkakuHankaku 102nd
F11 F12 RO
Katakana Hiragana Henkan KatakanaHiragana Muhenkan
_JP, _Return control_r _/ SysRq alt_r LineFeed
    Home  Up  PageUp
    Left      Right
    End  Down PageDown
    Insert Delete Macro
Mute VolumeDown VolumeUp Power
_= _+/- Pause Scale

_, Hangeul Hanja Yen
super_l super_r Compose
'''.split()
KEYS_TO_SCANCODE = {key: scancode for scancode, key in enumerate(KEYS)}
add_modifiers_aliases(KEYS_TO_SCANCODE)

# Keys other than capitals requiring the shift key
SHIFTED_KEYS = {
    '~': '`',
    '!': '1', '@': '2', '#': '3', '$': '4', '%': '5',
    '&': '7', '^': '6', '*': '8', '(': '9', ')': '0',
    '_': '-', '+': '=',
    '{': '[', '}': ']', '|': '\\',
    ':': ';', '"': '\'',
    '<': ',', '>': '.', '?': '/',
}
# Keys who's ascii representation does not match their key-name
SPECIAL_KEYS = {
    ' ': 'space',
    '\n': 'Return',
    '\t': 'Tab',
}

# Save some codes that we use explicitly
BACKSPACE = KEYS_TO_SCANCODE['BackSpace']
SHIFT = KEYS_TO_SCANCODE['shift']

p = None
p_refcount = 0

def start():
    global p, p_refcount
    p_refcount += 1
    if not p:
        p = Popen('plover-evdevd', stdout=PIPE, stdin=PIPE, text=True)

def stop():
    global p, p_refcount
    p_refcount -= 1
    if p_refcount <= 0:
        p_refcount = 0
        if p:
            p.terminate()
            p = None


def plover_key(name):
    return KEYS[int(name)]


def evdev_key(name):
    return str(KEYS_TO_SCANCODE[name])


class KeyboardCapture(threading.Thread):
    """Listen to keyboard press and release events."""

    def __init__(self):
        """Prepare to listen for keyboard events."""
        super().__init__(name='capture')
        self.key_down = lambda key: None
        self.key_up = lambda key: None

    def run(self):
        while True:
            line = p.stdout.readline()
            first_char = line[0]
            content = line[1:-1]
            if first_char == 'u':
                self.key_up(plover_key(content))
            elif first_char == 'd':
                self.key_down(plover_key(content))

    def start(self):
        start()
        super().start()

    def cancel(self):
        stop()

    def suppress_keyboard(self, suppressed_keys=()):
        try:
            p.stdin.write('s' + ' '.join(map(evdev_key, suppressed_keys)) + '\n')
            p.stdin.flush()
        except Exception as e:
            log.warn(e)
            stop()


def key_event(keycode, pressed):
    if pressed:
        p.stdin.write('d')
    else:
        p.stdin.write('u')
    p.stdin.write(str(keycode))
    p.stdin.write('\n')


class KeyboardEmulation:
    """Emulate keyboard events."""

    def __init__(self):
        """Prepare to emulate keyboard events."""
        start()

    def __del__(self):
        stop()

    def send_backspaces(self, number_of_backspaces):
        """Emulate the given number of backspaces.

        The emulated backspaces are not detected by KeyboardCapture.

        Argument:

        number_of_backspace -- The number of backspaces to emulate.

        """
        for _ in range(number_of_backspaces):
            key_event(BACKSPACE, True)
            key_event(BACKSPACE, False)
        p.stdin.flush()

    def send_string(self, s):
        """Emulate the given string.

        The emulated string is not detected by KeyboardCapture.

        Argument:

        s -- The string to emulate.

        """
        for c in s:
            upper = c.isupper()
            if upper:
                c = c.lower()
            elif c in SHIFTED_KEYS:
                upper = True
                c = SHIFTED_KEYS[c]
            elif c in SPECIAL_KEYS:
                c = SPECIAL_KEYS[c]

            keycode = evdev_key(c)

            if upper:
                key_event(SHIFT, True)
            key_event(keycode, True)
            key_event(keycode, False)
            if upper:
                key_event(SHIFT, False)
        p.stdin.flush()

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
        key_events = parse_key_combo(combo_string,
                                     key_name_to_key_code=evdev_key)
        for keycode, pressed in key_events:
            key_event(keycode, pressed)
        p.stdin.flush()
