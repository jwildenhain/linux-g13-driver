# Linux G13 Driver

This repository is a maintained fork of the original G13 Linux driver with an updated structure for Git and a small set of practical improvements, including live LCD system stats on supported firmware.

## Notes

- Originally based on the Google Code project layout.
- The driver runs as a userspace process and sends input events via `uinput`.
- LCD-capable builds write live status to the G13 display: CPU, memory, GPU, network and disk usage.
- The top 4 buttons under the LCD select the active bindings set.
- The joystick is currently mapped as directional keys in this branch.

## Ubuntu 22.04 (and Ubuntu-like) setup

### Requirements

- `libusb-1.0` development package
- `ant` (for GUI jar build)
- Java runtime/JDK (JDK 8+; on Ubuntu 22.04 `default-jdk`/`default-jre` is fine)

Install dependencies:

```bash
sudo apt update
sudo apt install -y git build-essential ant default-jdk default-jre libusb-1.0-0-dev
```

## Build

### 1) Build the C++ driver (required)

From the repository root:

```bash
./build_driver.sh --force
```

This builds `src/Linux-G13-Driver`.

### 2) Build the Java GUI (optional, for editing bindings/macros)

From the repository root:

```bash
cd src
ant
```

The GUI jar is produced in the deploy folder, for example:

- `deploy/Linux-G13_v1.0-r<revision>/Linux-G13-GUI.jar`

## Running

### 1) Generate/update config (`.properties`) files

Run the config tool:

```bash
java -jar deploy/Linux-G13_v1.0-r<revision>/Linux-G13-GUI.jar
```

The GUI creates and saves the config files on first run at:

- `~/.g13/bindings-0.properties` ... `~/.g13/bindings-3.properties`
- `~/.g13/macro-0.properties` and additional macro files as needed

You can also create them manually. Required format is Java properties text:

```properties
# ~/.g13/bindings-0.properties
color=255,255,255
G1=p,k.3
G2=p,k.4
...
G22=m,0,1
```

- `p,k.<linux_keycode>` = pass-through keycode
- `m,<macro_id>,<repeat_count>` = macro sequence playback

`macro-*.properties` examples use:

```properties
name=ALT-TAB
sequence=kd.56,kd.15,d.20,ku.15,ku.56
id=0
```

### 2) Start driver

From repository root:

```bash
cd src
sudo -E ./Linux-G13-Driver
```

`-E` preserves your environment so the driver reads `~/.g13` for your user.
To detach:

```bash
sudo -E ./Linux-G13-Driver &
```

### 3) Config changes while running

The driver reloads only on top-row bindings change keys (when supported by your build flow). For reliable results after edits, restart the driver.

## Linux-G13-Driver display output

The driver renders five lines and refreshes approximately every second:

- `CPU xx%`
- `MEM xx%`
- `GPU xx%` (or `GPU n/a`)
- `NET xx` (throughput in B/s / KB/s / MB/s)
- `DSK xx%`

If no source is available for a field, it shows `n/a`.
