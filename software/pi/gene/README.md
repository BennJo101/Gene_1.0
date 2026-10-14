# Gene's Pi software

Everything that runs Gene on the Raspberry Pi 5 (`~/gene` on the Pi). It covers listening, talking, the eye screens and cameras, memory, self-upgrades and the web control panel. `CLAUDE.md` is the full, detailed description; it is also what Claude Code reads when Gene upgrades himself.

| File | What it does |
| --- | --- |
| `gene_client.py` | The conversation loop: mic, speech-to-text, brain, Piper voice. Run by `gene.service`. |
| `gene_brain.py` | The only place that talks to a language model: Claude first, the Jetson's Ollama model as the fallback. |
| `gene_tts.py`, `piper/voices/gene.onnx` | Gene's own trained Piper voice, plus mouth shapes (visemes) for the jaw. |
| `gene_eyes.py` | The two round eye screens: faces, lids, winks, rotation. Run by `gene-eyes.service`. |
| `gene_cameras.py`, `gene_vision.py` | The eye cameras: object detection every few seconds, and real looks when asked. |
| `gene_memory.py`, `gene_graph.py` | Long-term memory and a knowledge graph. |
| `upgrade.py` | Self-upgrades. It runs Claude Code, restarts Gene and rolls back if he doesn't come back up. |
| `gene_teleop.py`, `teleop/index.html` | The web control panel on port 8080: live eyes and ears, face, speech, mouth, and live upgrades. |
| `brain/gene.Modelfile` | Gene's personality, used by both brains. |
| `stt/` | The Parakeet speech-to-text server. |
| The rest | Commands Gene handles himself: clock and timers, files, GPIO, music, sounds, USB, volume, web search. |

## Not in this folder

- Gene's memories, conversations and other state (`state/`), the Python venv, and the downloaded models (`models/`).
- Secrets. The Anthropic API key (`~/.config/gene/anthropic.env`) and the control panel password (`~/.config/gene/teleop.env`) live only on the Pi.

## History

This is a snapshot. The day-to-day history is in the Pi's own git repo in `~/gene`, where every voice upgrade is a commit.
