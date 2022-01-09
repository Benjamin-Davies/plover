// This file might be a derivative work of https://github.com/ndesh26/evdev-rs

use evdev_sys as sys;
use glob::glob;
use std::{
    ffi::CStr,
    fs::File,
    io,
    os::{raw::c_uint, unix::io::AsRawFd},
    path::Path,
    ptr,
};

macro_rules! unsafe_io {
    ($x:expr) => {{
        let res = unsafe { $x };
        if res < 0 {
            Err(io::Error::from_raw_os_error(-res))?
        } else {
            res
        }
    }};
}

pub struct Device {
    _file: File,
    raw: *mut sys::libevdev,
    name: String,
    grabbed: bool,
}

impl Device {
    pub fn list() -> impl Iterator<Item = Self> {
        glob("/dev/input/event*")
            .unwrap()
            .filter_map(|path| Some(Device::open(path.ok()?).ok()?))
    }

    pub fn open<P: AsRef<Path>>(path: P) -> io::Result<Self> {
        let file = File::open(path)?;

        let mut raw = ptr::null_mut();
        unsafe_io!(sys::libevdev_new_from_fd(file.as_raw_fd(), &mut raw));

        let raw_name = unsafe { sys::libevdev_get_name(raw) };
        let name = unsafe { CStr::from_ptr(raw_name) }
            .to_str()
            .unwrap()
            .to_owned();

        Ok(Self {
            _file: file,
            raw,
            name,
            grabbed: false,
        })
    }

    pub fn name(&self) -> &str {
        &self.name
    }

    pub fn has_key(&self, key: Key) -> bool {
        let Key(code) = key;
        unsafe { sys::libevdev_has_event_code(self.raw, EV_KEY as c_uint, code as c_uint) != 0 }
    }

    pub fn grab(&mut self) -> io::Result<()> {
        unsafe_io!(sys::libevdev_grab(self.raw, sys::LIBEVDEV_GRAB));
        self.grabbed = true;
        Ok(())
    }

    pub fn ungrab(&mut self) -> io::Result<()> {
        unsafe_io!(sys::libevdev_grab(self.raw, sys::LIBEVDEV_UNGRAB));
        self.grabbed = false;
        Ok(())
    }

    pub fn read_loop(&mut self) -> DeviceReadLoop {
        DeviceReadLoop(self)
    }
}

unsafe impl Send for Device {}

impl Drop for Device {
    fn drop(&mut self) {
        if self.grabbed {
            self.ungrab().unwrap();
        }
        unsafe {
            sys::libevdev_free(self.raw);
        }
    }
}

pub struct DeviceReadLoop<'a>(&'a mut Device);

impl<'a> Iterator for DeviceReadLoop<'a> {
    type Item = Event;

    fn next(&mut self) -> Option<Event> {
        let mut ev = sys::input_event {
            time: sys::timeval {
                tv_sec: 0,
                tv_usec: 0,
            },
            type_: 0,
            code: 0,
            value: 0,
        };
        unsafe {
            sys::libevdev_next_event(
                self.0.raw,
                (sys::LIBEVDEV_READ_FLAG_NORMAL | sys::LIBEVDEV_READ_FLAG_BLOCKING) as c_uint,
                &mut ev,
            );
        }
        Some(ev.into())
    }
}

pub struct UInput {
    raw: *mut sys::libevdev_uinput,
}

impl UInput {
    pub fn from_device(dev: &Device) -> io::Result<Self> {
        let mut raw = ptr::null_mut();
        unsafe_io!(sys::libevdev_uinput_create_from_device(
            dev.raw,
            sys::LIBEVDEV_UINPUT_OPEN_MANAGED,
            &mut raw
        ));

        Ok(Self { raw })
    }

    pub fn write_event(&mut self, event: Event) -> io::Result<()> {
        let ev: sys::input_event = event.into();
        unsafe_io!(sys::libevdev_uinput_write_event(
            self.raw,
            ev.type_ as c_uint,
            ev.code as c_uint,
            ev.value
        ));
        Ok(())
    }

    pub fn syn(&mut self) -> io::Result<()> {
        self.write_event(Event::Syn)
    }
}

unsafe impl Send for UInput {}

impl Drop for UInput {
    fn drop(&mut self) {
        unsafe {
            sys::libevdev_uinput_destroy(self.raw);
        }
    }
}

#[derive(Debug, PartialEq, Eq)]
pub enum Event {
    Syn,
    Key(Key, bool),
    Other(u16, u16, i32),
}

impl From<sys::input_event> for Event {
    fn from(ev: sys::input_event) -> Self {
        match ev.type_ {
            EV_SYN => Self::Syn,
            EV_KEY => Self::Key(Key(ev.code), ev.value != 0),
            t => Self::Other(t, ev.code, ev.value),
        }
    }
}

impl Into<sys::input_event> for Event {
    fn into(self: Event) -> sys::input_event {
        let time = sys::timeval {
            tv_sec: 0,
            tv_usec: 0,
        };
        match self {
            Self::Syn => sys::input_event {
                time,
                type_: EV_SYN,
                code: 0,
                value: 0,
            },
            Self::Key(Key(code), value) => sys::input_event {
                time,
                type_: EV_KEY,
                code,
                value: if value { 1 } else { 0 },
            },
            Self::Other(type_, code, value) => sys::input_event {
                time,
                type_,
                code,
                value,
            },
        }
    }
}

const EV_SYN: u16 = 0;
const EV_KEY: u16 = 1;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub struct Key(pub u16);

impl Key {
    pub const KEY_A: Key = Key(30);
    pub const KEY_LEFTSHIFT: Key = Key(42);
    pub const KEY_RIGHTSHIFT: Key = Key(54);
    pub const KEY_LEFTCTRL: Key = Key(29);
    pub const KEY_RIGHTCTRL: Key = Key(97);
    pub const KEY_LEFTALT: Key = Key(56);
    pub const KEY_RIGHTALT: Key = Key(100);
    pub const KEY_LEFTMETA: Key = Key(125);
    pub const KEY_RIGHTMETA: Key = Key(126);
}
