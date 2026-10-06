# Raspberry Pi 5 audio

The Pi 5 has no analog audio out, so Gene's two speakers run from a MAX98357A I2S amplifier on the GPIO header.

- `asound.conf`: ALSA config that adds a `Master` software volume in front of the I2S output. Its `max_dB` sets the loudest the speakers can go. Copy it to `/etc/asound.conf`.
- `volume.py`: reads or sets that volume.

```
python3 volume.py        # print the level
python3 volume.py 70     # set 70%
python3 volume.py +10    # step up (or -10 down)
```

From Python: `volume.get()`, `volume.set(70)`, `volume.step(-10)`.
