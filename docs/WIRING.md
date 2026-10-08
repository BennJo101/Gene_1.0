# Wiring

Two diagrams: the audio chain (Pi 5 → I2S amp → speakers) and the power stack (pack → BMS → switch → bucks, with USB-C charging). Cable lengths to buy are in [`BOM.md`](BOM.md) section 5.

## Audio: Pi 5, MAX98357A, speakers

![Audio wiring](images/wiring_audio.svg)

| MAX98357A | Pi 5 header (2nd header on the splitter) | Notes |
|---|---|---|
| Vin | pin 4 (5 V) | |
| GND | pin 6 (GND) | Any GND pin works |
| BCLK | pin 12 (GPIO 18, PCM CLK) | |
| LRC | pin 35 (GPIO 19, PCM FS) | |
| DIN | pin 40 (GPIO 21, PCM DOUT) | |
| GAIN | not connected | Open = 9 dB |
| SD | not connected | Adafruit board: 1 MΩ pull-up gives the (L+R)/2 mono mix. Clone with no pull-up: add 1 MΩ SD → Vin |
| Speaker + / − | Both speakers in parallel (+ to +, − to −) | 2 × 8 Ω = 4 Ω. Bridged output: never connect a speaker wire to GND |

Pi setup: `dtparam=i2s=on` and `dtoverlay=hifiberry-dac` in `/boot/firmware/config.txt`, then copy [`software/pi/asound.conf`](../software/pi/asound.conf) to `/etc/asound.conf`.

The amp takes its 5 V from the Pi header, so the only cable it needs is the one to the splitter that's already routed. GPIO 12 (pin 32) stays free for the crown flashlight.

## Power: battery, BMS, charger, bucks

![Power wiring](images/wiring_power.svg)

| From | To | Wire |
|---|---|---|
| Pack B+ / BM / B− | BMS B+ / BM / B− (XT30 for B+/B−, JST-XH balance lead for BM) | 18 AWG main, balance lead as supplied |
| USB-C charge port (panel-mount extension, lower back of skull) | Charger board's USB-C input | The extension's right-angle male end plugs straight in, so there's nothing to solder |
| Charger BAT+ / BAT− | BMS P+ / P− | 18–22 AWG |
| BMS P+ | Switch → fuse (recommended, 10 A) → VIN of both bucks | 18 AWG |
| BMS P− | GND of both bucks | 18 AWG |
| Buck A (Pi rail) VOUT / GND | Pi 5 USB-C pigtail, both display micro-USB leads | Pi lead 20–22 AWG |
| Buck B (servo rail) VOUT / GND | XL330 VDD / GND, fed in at servo R | 18 AWG |

- The charger connects after the BMS and before the switch, so the pack charges with Gene switched off and the BMS still protects it.
- Many 2S BMS boards have no P+ pad and switch only the negative side. Then P+ is simply B+, so take the switch and charger feed from B+. Check your board's silkscreen.
- The D36V50F5 is a fixed 5 V part with no trim pot. Leave EN and PG unconnected.
- The Pi gets 5 V without USB-PD, so add `usb_max_current_enable=1` to `config.txt`, or its USB ports are capped at 600 mA.
- The U2D2 doesn't power the DYNAMIXEL bus. Its lead to servo L carries DATA and GND. Power from Buck B goes in at servo R.
- All grounds meet at P−. The Pi and servo grounds are also joined through the U2D2's USB lead.
- Before connecting anything, power the bucks with no loads and check for 5.0 V and the right polarity with a meter.

Not covered yet: the slip ring's fixed-side wires below the neck base, and where the power switch goes in the skull.
