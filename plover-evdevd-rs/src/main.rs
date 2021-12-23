mod evdev;

use evdev::*;
use std::{
    collections::HashSet,
    io::{self, BufRead, Write},
    sync::{Arc, Mutex},
    thread,
    time::Duration,
};

const UINPUT_NAME: &str = "Plover";

const MODIFIER_KEYS: [Key; 8] = [
    Key::KEY_LEFTSHIFT,
    Key::KEY_RIGHTSHIFT,
    Key::KEY_LEFTCTRL,
    Key::KEY_RIGHTCTRL,
    Key::KEY_LEFTALT,
    Key::KEY_RIGHTALT,
    Key::KEY_LEFTMETA,
    Key::KEY_RIGHTMETA,
];

fn is_keyboard(dev: &Device) -> bool {
    dev.name() != UINPUT_NAME && dev.has_key(Key::KEY_A)
}

fn find_first_keyboard() -> Device {
    Device::list()
        .find(is_keyboard)
        .expect("No keyboards found")
}

fn listen_kb(mut dev: Device, uinput: Arc<Mutex<UInput>>, suppress_keys: Arc<Mutex<HashSet<Key>>>) {
    let stdout = io::stdout();
    // stdout is only used in this method, so we may as well only lock it once
    let mut stdout = stdout.lock();

    let mut modifiers = Vec::new();

    for event in dev.read_loop() {
        if let Event::Key(key, pressed) = event {
            if MODIFIER_KEYS.contains(&key) {
                if pressed {
                    if modifiers.contains(&key) {
                        modifiers.push(key);
                    }
                } else {
                    modifiers.retain(|k| k != &key);
                }
            }

            if (*suppress_keys.lock().unwrap()).contains(&key) && modifiers.len() == 0 {
                let Key(code) = key;
                let prefix = if pressed { 'd' } else { 'u' };
                writeln!(stdout, "{}{}", prefix, code).unwrap();
                continue;
            }
        }

        {
            let mut uinput = uinput.lock().unwrap();
            (*uinput).write_event(event).unwrap();
        }
    }
}

fn listen_stdio(uinput: Arc<Mutex<UInput>>, suppress_keys: Arc<Mutex<HashSet<Key>>>) {
    let stdin = io::stdin();
    // stdin is only used in this method, so we may as well only lock it once
    let mut stdin = stdin.lock();

    let mut line = String::new();

    loop {
        line.clear();
        stdin.read_line(&mut line).unwrap();

        if let Some(first_char) = line.chars().next() {
            let content = &line[1..line.len() - 1];
            match first_char {
                'd' => {
                    if let Ok(code) = content.parse() {
                        let mut uinput = uinput.lock().unwrap();
                        (*uinput).write_event(Event::Key(Key(code), true)).unwrap();
                        (*uinput).syn().unwrap();
                    }
                }
                'u' => {
                    if let Ok(code) = content.parse() {
                        let mut uinput = uinput.lock().unwrap();
                        (*uinput).write_event(Event::Key(Key(code), false)).unwrap();
                        (*uinput).syn().unwrap();
                    }
                }
                's' => {
                    let mut new_suppressed = HashSet::new();
                    for substr in content.split(' ') {
                        if let Ok(code) = substr.parse() {
                            new_suppressed.insert(Key(code));
                        }
                    }
                    let mut suppress_keys = suppress_keys.lock().unwrap();
                    *suppress_keys = new_suppressed;
                }
                _ => {}
            }
        }
    }
}

fn main() {
    thread::sleep(Duration::from_millis(500));

    let mut dev = find_first_keyboard();
    dev.grab().unwrap();
    eprintln!("Using device: {}", dev.name());

    let uinput = Arc::new(Mutex::new(UInput::from_device(&dev).unwrap()));
    let uinput_ = uinput.clone();

    let suppress_keys = Arc::new(Mutex::new(HashSet::new()));
    let suppress_keys_ = suppress_keys.clone();

    thread::spawn(|| listen_kb(dev, uinput, suppress_keys));

    thread::spawn(|| listen_stdio(uinput_, suppress_keys_))
        .join()
        .unwrap();
}
