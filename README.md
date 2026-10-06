# 16-Bit Emulated Computer

A custom 16-bit computer architecture and emulator built in Python. Inspired by the **eZ80 processor**, this system features memory-mapped I/O (MMIO) ports for file access, graphics, and real-time keyboard/mouse inputs.

> **Note:** This project is no longer under active development.

---

## Overview & Features

- **eZ80-Inspired ISA:** Custom instruction set architecture handling 16-bit operations and port interfaces.
- **Memory-Mapped I/O (MMIO):** Dedicated virtual hardware ports for file reading/writing and peripherals.
- **GUI & Graphics Support:** Pygame-backed display rendering built to support windowed UI environments and custom color palettes.
- **Built-in Demos:** Pre-assembled operating routines including a version of Snake, interactive console tests, and animated displays.

---

## Getting Started

### Prerequisites

Make sure you have Python installed, along with `pygame` and `numpy`:

    pip install pygame numpy

### Running the Emulator

1. Clone the repository and navigate into the root directory:
    ```
    git clone https://github.com/itdish0/16bit-computer-emulator.git
    cd 16bit-computer-emulator
    ```
2. Launch the emulator:
    ```
    python main.py
    ```
3. When prompted in the terminal to select an executable program, press **Enter** to run the default program (`snake_os`), or enter one of the demo filenames below.

---

## Available Programs / Demos

| Executable | Description | Controls / Details |
| :--- | :--- | :--- |
| `snake_os` *(Default)* | Classic Snake game running directly on the simulated architecture. | Keyboard arrow keys. |
| `birthday_os` | Simple graphics program I made for my mom's birthday. | Non-interactive (sit back and watch). |
| `test_os` | Console-to-screen input test. | Type in the terminal, view output rendered on the emulator screen. |

---

## Assembly & Hardware Architecture

If you want to inspect or write assembly code for this system:

- **Port Constants & Specifications:** See `Assembly/port_constants.txt` for full documentation on available MMIO ports.
- **Changelog & Architecture Notes:** Check `changelog.txt` for development history and internal updates.
- **Graphics Assembly Routines:** See `Assembly/palette.txt`, `Assembly/font.txt`, and `Assembly/graphics_lib_core.txt` for default graphics setup and font printing.
- **Assembly Bootloader/OS Template:** See `Assembly/bios.txt` and `Assembly/os_header.txt` for the beginnings of a simple bootloader/bios and os header contract.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
