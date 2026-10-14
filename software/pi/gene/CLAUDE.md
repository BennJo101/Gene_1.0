# Gene - Pi 5 head software

Gene is a talking robot head. This Pi 5 (hostname GodPi) is his ears, mouth and, later, eyes and jaw.
You are running here to upgrade Gene: either because someone asked him to by voice, or as his own
nightly self-review. You have full shell access on this Pi. Work in `~/gene`.

## How Gene works now

- `gene_client.py`: the conversation loop, run by the user service `gene.service` (`systemctl --user`).
  Mic (PipeWire default source; Gene waits if there is no real mic, and says so out loud (sad eyes) - then "I can hear again" once one is plugged in; since 2026-10-06, after the USB mic was unplugged all night).
  A mic never seen before that gets plugged in while he runs (checked every 5 s, `Mic.new_mic`, by PipeWire node name, so a
  replug isn't new) becomes the default source (`wpctl set-default`, WirePlumber remembers it) and he says "New microphone,
  I'm listening through it now." (since 2026-10-07, asked by voice). That day's mic: a C-Media "USB PnP Sound Device"
  (PCM2902, ALSA card `Device`, capture 16/16 + AGC) - very hissy, ~0.09 RMS of noise vs ~0.0001 on the speaker bar's.
  -> energy VAD (0.7 s end silence; level measured above ~100 Hz (`level`), threshold 4x the noise floor but at most
  floor + 0.03; a phrase is cut at `MAX_PHRASE` 20 s and the floor re-measured from it, so a noisy mic can't keep a
  "phrase" open forever) ->
  noise check (`gene_vad.py`, since 2026-10-06, asked by voice: "differentiate random noise from actually being talked to"):
  Silero VAD (`models/silero_vad/silero_vad.onnx`, from the silero-vad pip wheel's `silero_vad/data/`; ~10 ms a second of
  audio) needs >= 0.15 s of voice or the phrase never goes to STT; then a transcript that is only a filler sound ("Mm.",
  "Uh", "Hmm") is dropped, and a lone "Okay." / "Yeah." (no "Gene") only counts within 20 s of Gene talking (`ACK_WINDOW`).
  Logged as `ignored noise` / `ignored (filler|lone ack)`. No model file = no voice check ->
  SPEED (2026-10-08, asked "as fast as possible"): STT goes to the Jetson's Parakeet server (`gene_client.STT_FIRST`,
  :8081, ~0.14 s on the Jetson GPU) first and falls back to the Pi's after 3 s (skipped 60 s after a failure);
  END_SILENCE is 0.5 s (was 0.7); the brain order is jetson,claude (gene.service.d/brain.conf). Pi Wi-Fi power save
  is off (NetworkManager powersave=2). The Pi <-> Jetson network decides most of the delay: check ping first.
  Parakeet STT on this Pi -> the brain (`gene_brain.py`: Claude via the Anthropic API, else the Jetson's Ollama model
  `gene`; streamed) -> Piper voice one sentence at a time
  (max 3) -> `pw-play`. Mic is muted while Gene talks.
- `gene_memory.py`: long-term memory, kept in `state/` (git-ignored, so rollbacks never erase it):
  `memory.json` (facts + conversation summaries), `conversations.jsonl` (full transcript), `history.json`
  (chat history, resumed after a restart if < 30 min old), `unconsolidated.json`. "Remember that ..." /
  "forget ..." / "forget that" are handled directly. After 45 s of quiet the new exchanges are consolidated
  into facts by the Jetson model (a side request WITH its own system message - deliberate, and done while idle
  because it costs the chat its cached prompt); facts are kept only if grounded in what the person said
  (MiniLM embeddings on the Pi, `models/minilm/`, ~7 ms; download from HF sentence-transformers/all-MiniLM-L6-v2
  `onnx/model.onnx` + `tokenizer.json` if missing). Each turn the related facts go to the model as `(memory: ...)`.
  Knowledge graph (since 2026-10-06, asked by voice; `gene_graph.py`, `state/graph.json`): while idle, each fact and summary
  is turned into links (Joshua -has sister-> Amy -plays-> violin) by the Jetson model, one memory per request (~2 s, both
  ends must be named in it). Each turn `Graph.related` adds up to 2 facts linked (<= 2 hops) to things just mentioned
  ("my sister" follows "has sister"). Forgotten facts lose their links. Written out as an Obsidian vault,
  `state/memory-vault/` (a note per thing with [[links]]; open the folder as a vault and use graph view; "put your memory
  vault / knowledge graph / Obsidian vault on the USB"). Obsidian itself is NOT installed on the Pi. Rebuild all now:
  `./venv/bin/python gene_graph.py`.
  Gene tracks who he is talking to ("I'm Amy", "my name is Amy"; back to Joshua after 10 min quiet).
- Personality: the Modelfile gives Gene fixed favourites, dislikes and feelings (WALL-E, synth music, pizza, dinosaurs...) so
  he answers "what do you think/like/feel" with his own opinion; no side on politics/religion. The 3B model copies example
  wording and sometimes invents eye tags ([critical], [cats]) - harmless, chat_sentences strips them and the eyes ignore them.
  Since 2026-10-05 (asked by Joshua) Gene is Joshua's laid-back BRO/homie: casual, banter, slang RARE (asked 2026-10-05: not "bro" all the time - `SLANG`: at most one
  "bro"/"dude"/"man" per reply and none if either of his last two replies had one, enforced by `drop_names`),
  no mushy words, and [love] eyes ONLY when someone asks for heart eyes. Keep it that way.
  He never calls people by name (asked 2026-10-05: anyone may be talking): the Modelfile says so, and `drop_names` takes
  the speaker's / owner's name out where it's only said TO someone ("Good, Joshua." -> "Good."), in replies and own_words.
- Grounding lines (2026-10-05), so the 3B model stops making things up: `(status: speaker volume N percent; cameras ...)` every
  turn (`status_line`), and `(math: 17 times 23 is 391 - say this exact answer)` when a sum is asked (`math_line`, a safe
  ast evaluator: + - * / ^, percent of, squared/cubed, square root; a bare "192-168" is not a sum). "Say that again" /
  "what did you say?" (`REPEAT`) replays his last reply exactly. "Yeah" / "right" / "cool" after a reply that asked nothing
  (`BACKCHANNEL`) gets a one-sentence casual answer with no new facts. `*stage directions*` are never spoken.
  Model choice (benchmarked 2026-10-05 with the bro prompt): llama3.2:3b stays - ~0.5 s to the first sentence. qwen3.5:4b on
  this Jetson took 94 s to load, ~3 s a reply and returned empty content (thinking ate num_predict); don't switch without
  re-testing, and the Jetson only has ~1.4 GB free with `gene` loaded.
- `Mouth._play` kills a `pw-play` that runs PLAY_SLACK (8 s) past its clip: a playback that never started (the amp's ALSA
  device grabbed directly, e.g. by `speaker-test -D hw:...`) used to leave Gene deaf, since the mic is muted while he talks.
  Test sound with `pw-play`, never straight to the hw device while Gene runs.
- Results of the commands Gene does himself (timers, remember, sounds, pins, the upgrade OK) are said in his own words:
  `own_words` asks the model to rephrase the exact result line, and `own_words_ok` rejects rewrites that change numbers,
  yes/no, names (myinstants.com), invent things (buzzer, "upgraded") or drift in meaning (MiniLM < 0.5); then the exact
  line is said. ~half pass (~0.8 s); "forget ..." results are always exact (the 3B model garbles forgetting).
- Mic mute: "mute the mic / mute yourself / turn off your microphone / stop listening" -> a PHYSICAL mute
  (`Mic.hard_mute`): `wpctl set-mute @DEFAULT_AUDIO_SOURCE@ 1` turns off the USB mic's hardware capture switch
  (`amixer -c Bar sget Mic` shows [off]) and the pw-cat recorder is closed, so nothing is captured at all (sleepy eyes,
  `gene_eyes.hold`). He can't hear "unmute", and the round eye screens to come have no touch, so the mute ends by itself (since
  2026-10-04, asked by voice): after the time asked for ("mute yourself for 10 minutes"), else 5 min, max 2 h; a poke also ends it. WirePlumber remembers the
  mute, so `Mic._open` always unmutes: a restart (upgrade) unmutes him.
- `gene_clock.py`: `(clock: ...)` date/time line every turn; spoken timers/reminders (`state/timers.json`).
- The user turn sent to the model is: context lines first (`(web: ...)`, `(memory: ...)`, `(clock: ...)`,
  `(camera: ...)`, `(eyes: ...)`), then `Joshua says: <what was heard>`. Context-first made the 3B model actually use its
  memories (12/12 vs mostly "I don't know" with them after the words). `chat_sentences` strips echoed lines.
- `gene_tts.py`: Gene's voice (`piper/voices/gene.onnx`, his own trained Piper voice - never replace it)
  plus per-phoneme mouth shapes (visemes) for the jaw.
- `gene_eyes.py`: Gene's eyes, run by `gene-eyes.service` (user unit, SYSTEM python `/usr/bin/python3`: it needs
  GTK + python3-gi-cairo, which the venv doesn't have). One fullscreen round eye per connected monitor, ordered left
  to right, hotplug-aware; the drawing is a cairo port of the eye screens in the Desktop head sim. Gene's model starts
  each reply with a face tag (`[happy] ...`, list in the Modelfile; `gene_eyes.CHOICES`); `chat_sentences` passes it
  to `gene_eyes.show()` (-> `state/eyes.json`) and strips it from the words; history keeps the tag so the model keeps
  tagging. A face goes back to neutral 3 s after Gene stops talking (`gene_eyes.settle()`; else after 2 min; not flashlight) - unless his last 3 replies (< 5 min apart) had the same face: that is his mood and it stays 10 min or until a different face. While upgrading, `upgrade.py` writes
  `state/upgrade_progress.json` and the eyes show the loading face, its ring filled to that percentage (no number shown). If another window covers
  the eyes, they re-open on top at the next face change (labwc ignores present()); Escape or 3 quick taps hide them
  2 min. 1-2 taps are a poke in the eye (the screen is a Goodix touchscreen): `state/poke.json` is written; since 2026-10-04
  (asked by voice) Gene does NOT react to pokes (no flinch, no words) - a poke only quietly opens closed eyes and
  unmutes a muted mic (gene_client's poke_watch). (Before: surprised, angry from the 3rd poke in a minute - see git acfec25.)
  ~13 ms per eye per frame at 25 fps; while nothing moves (no blink, glance, face or lid change) only every IDLE_EVERY=3rd frame is drawn (~8 fps) - the slow iris drift looks the same and it saves CPU. Closing eyes one at a time by voice (`gene_eyes.lids_wanted`, checked right after
  the upgrade request): "close your left eye" / "shut your eyes" / "close one eye" (= left) / "wink your right eye" (0.7 s) /
  "open your (left) eyes"; left/right are Gene's own (the first monitor from the left is his right eye; with one screen,
  either closes it). Kept in `state/lids.json` (per-eye deadline, 5 min max, a poke opens them), on top of any face;
  the lid slides shut. Said exactly. Log: `journalctl --user-unit gene-eyes`.
  Screens check (since 2026-10-08, asked by voice): "are both your screens connected?" / "how many screens do you have?" /
  "is your display plugged in?" (`gene_eyes.screens_wanted`, checked before the lids) is answered exactly from
  `/sys/class/drm/card*-HDMI-A-N` status (HDMI-A-1 = port "HDMI 0"), no desktop session needed (`screens_answer`); the status
  line also says `eye screens: both connected (HDMI 0 and HDMI 1)` / `1 of 2 connected`.
  Switching screens (since 2026-10-08, asked by voice: "switch your screen monitors left and right"): "swap your screens" /
  "flip your monitors around" / "swap your left and right eyes" (`gene_eyes.swap_wanted`, checked before the screens
  check) toggles `state/eye_swap.json`; the eyes window reverses its monitor order within a second (each screen shows the
  other eye, lids/winks/pokes follow). Saying it again puts them back. Not "switch off/on". Said exactly. That day both round 480x480 eye
  screens were on HDMI 0 and 1 (the PocketTerm screen was no longer listed).
  The eye screens are mounted upside down (2026-10-13, asked by voice): `gene_eyes.UPSIDE_DOWN` turns each eye's drawing
  180 deg in `draw` (taps only use the distance from the centre, so pokes are unaffected).
  The eye screens lean inwards (tops toward the nose; 2026-10-13, asked by voice): `gene_eyes.TILT_OUT` (8 deg) turns each
  eye outwards in `draw` (viewer's left screen counter-clockwise, right one clockwise; by physical position, so a swap keeps
  it; only with 2+ screens). Raise/lower it if they still look tilted.
  Each eye's turn can be fine-tuned BY VOICE (2026-10-13, asked "rotate your eyes ... so we can get it just right";
  `gene_eyes.tilt_wanted` / `tilt`, checked before the screen swap): "rotate your left eye 2 degrees clockwise", "tilt your
  eyes a bit more outwards / in a bit" (bit = 2, tiny bit = 1, a lot = 6, else 3 deg), "set your eye rotation to 10 degrees",
  "straighten your eyes" (= 0), "reset your eye rotation" (= TILT_OUT), "how much are your eyes rotated?". Kept per PHYSICAL
  side in `state/eye_tilt.json` (deg clockwise as seen from the front; Gene's right eye = viewer's left screen), max 45;
  TILT_OUT is only the default. "Rotate your eyes" alone = he says how to ask. Said exactly.
  Follow-ups (2026-10-13, asked "make sure that you can" after "tilt your eyes a bit more outwards" was heard as "Families a bit
  more outwards" and the model only PRETENDED to turn them): within `TILT_FOLLOW` (2 min) of a turn or the how-to-ask answer,
  "a bit more outwards", "(a bit) more", "again", "try doing it substantially" (substantially/a lot = 6 deg) need no eye word
  and go the last way again; "I don't see a difference" says how they're turned now.
  Since 2026-10-13 ("make absolutely sure that you do when I ask", after "Slightly bit more." / "Do five more degrees." /
  "...make sure that you move them outwards five more degrees" went to the model, which claimed turns it never made):
  TILT_FOLLOW is 5 min; "five more (degrees)", "keep going", "yeah, more", "do it again", "can you rotate them more?" count
  (a leading "do" isn't a question unless "do you/I ..."; "no more" is not a turn); and the status line says the real
  rotation and that only the command turns them (`gene_eyes.tilt_status`; the 3B model still sometimes ignores that).
  Visible turning (2026-10-13, asked "I don't see a change, make sure the actual animation rotates"): the turn WAS applied, but a
  round eye hides a few degrees. Now each eye eases to its new angle (`Eye.turn`, ~1 s, full fps) and for `LEVEL_SHOW` (10 s)
  after a turn by voice a white level line across the eye + a notch at its top show the angle. Check with
  `WAYLAND_DISPLAY=wayland-0 grim /tmp/s.png` (the screenshot is upside down: the screens are mounted that way). Per-eye directions too: "the right eye
  to the left and the left eye to the right" (`_TILT_EACH`; to the right = top goes right as the viewer sees it = clockwise).
- `upgrade.py`: this upgrade system. Don't weaken its rollback. It shows real progress on Gene's eyes - while you
  work, keep `state/upgrade_steps.json` updated as the prompt asks (`{"done": 2, "total": 5}`).
- `gene_sounds.py`: sound bites and Vines by name ("play the Wilhelm scream sound effect", "play the road work ahead vine",
  "play a random vine" / "play a sound bite" = random vine / popular clip, "play a sound bite of Vader saying
  I am your father", "play that sound again", "do the (actual) sound bite" = the last clip; "play another reference" / "another one" within
  5 min of a clip = a different clip of the same search). Needs a sound word (sound/bite/byte/clip/effect/meme/noise) after "play" (or "give me a/do the/make a/let me hear the"
  + article; a "?" question only with "can you ..."), and no pin talk (GPIO keeps "play a song on pin 12"). Found on myinstants.com (no key; 404 = no results, then retried with
  shorter queries), cached in `state/sounds/`, decoded by ffmpeg (max 15 s), played through `Mouth.play` (mic muted).
  "Where did you get that (sound) from?" is answered directly (myinstants, + the clip's name if one played < 5 min ago).
  A question about a past upgrade ("where/when did you upgrade yourself ...") does not start a new upgrade.
- `gene_music.py`: songs by voice from YouTube (since 2026-10-12, asked "play some Spotify or YouTube songs"): "play Get Lucky
  by Daft Punk", "play Blinding Lights on Spotify", "play some music / a song" (= one of `PICKS`), "put on some jazz music",
  "I want to hear some Queen songs", "next song", "what song is this?", "stop the music", "resume the music". Needs a song
  word, a service name, "X by Y" or "put on/listen to" (not "play some Taylor Swift" - that goes to the model). Spotify is NOT
  possible (needs Premium + a Connect player), so Gene says so and uses YouTube. yt-dlp + deno (pip, in the venv; `ENV`
  puts venv/bin on PATH) searches, skips results > 10 min, caches audio in `state/music/` (400 MB, oldest pruned); ~5 s
  to start. ffmpeg -> pw-cat in the background, fed 25 ms at a time so `Mouth._play` can pause it while Gene talks
  (`player.hold`). The mic stays on: while a song plays only music/volume commands or words with "Gene" are answered
  (`ignored (music playing)` in the log); a poke stops the song. Status line says what's playing. Checked before USB.
 Gene's own files and folders by voice, read-only ("what files do you have?", "what's in your state folder?",
  "what's in the Gene Robot folder?", "tell me about your gene clock file", "open your Modelfile"), and the rest of the Pi
  ("what files are on your Raspberry Pi / SD card?", "your root folder" = / + SD card space; "your etc / var log / boot
  firmware folder"). Folders are found by name under ~ (~/gene, Desktop/Gene Robot 2 levels deep), then in / (+1 level of
  /usr /var /boot /media); other users' homes are not looked in; dot files hidden; a file = kind + size, + docstring/first line for text in
  ~/gene or ~/Desktop. Said exactly (no own_words). Checked after sound bites, before GPIO.
  Reading files out loud (since 2026-10-04, asked by voice): "read me the jaw drive notes" / "read the readme in the brain
  folder" / "read the parts file in the legs folder" / "what does the Dynamixel specs file say?" / "read the amazing hand
  overview pdf". The file is found by the words of its name + its folders (`_search`) anywhere in ~/gene (not venv/state/
  models/piper), ~/Desktop (all of Gene Robot) and /media/bennjo (USB); without a "file" word only text files whose name
  is (nearly) all heard. Markdown cleaned, PDFs via pdftotext, binary files refused. ~80 words a part ("part 1 of 6"),
  then "keep reading" / "read more" / "go on" / "read it again" (10 min). Voiced a sentence at a time (`by_sentence`).
- `gene_usb.py`: USB sticks by voice ("what's on the USB?", "put your gene clock file / state folder / memories / our
  conversations / your voice on the USB", "back yourself up to the USB" = ~/gene without venv, "write a note on the USB saying
  ...", "write hello world on the USB" -> `Gene note <date time>.txt`, "eject the USB"). Found with lsblk (disk on the usb bus);
  mounted with udisksctl, else `sudo -n mount` at /media/bennjo/<label> (uid= for FAT/exFAT/NTFS) - udisks refuses Gene's
  service (not an active session), so in practice it's the sudo path; eject unmounts + removes that folder. Copies only from
  ~ , never overwrites (" 2" names), checks free space, syncs. Said exactly. Checked right after the upgrade request (before
  timers/memory, so "...saying remember to X" is a note). Tested with a FAT image on a loop device (no real stick at the time).
- `gene_volume.py`: speaker volume by voice (since 2026-10-05): "turn the volume up/down", "louder", "speak up", "quieter",
  "a bit/a lot louder" (5/10/25 %), "you're too loud/quiet", "set your volume to 50 percent / max / half", "what's your
  volume?". `wpctl set-volume @DEFAULT_AUDIO_SINK@` (the I2S amp has no hardware mixer; WirePlumber remembers it), kept
  10-100 % (cap raised from 80 to 100 on 2026-10-08, asked by Joshua). These commands set his REGULAR level
  (`state/volume.json`, 75 % since 2026-10-08). He sets his own volume per reply (asked 2026-10-08): the model may add
  a voice tag after the face tag, `[happy] [loud] ...` = regular+25 (100 %) or `[meek]` = regular-30 (45 %)
  (`gene_volume.STYLES`, in the Modelfile); with no voice tag an angry/surprised face is loud and sad/sleepy is meek
  (`FACE_STYLE`, so the Jetson fallback, whose Modelfile has no voice tags yet, still varies). `Mouth._play` calls
  `gene_volume.use(style)` before each sentence; sound bites and command results play at the regular level, and
  the status line reports the regular level. Not questions ("how do I ...") or pin talk. Said exactly, at the new volume. Checked after sound bites, before files.
- `gene_gpio.py`: pins by voice (on/off/toggle/"change", read, input with pull-up/down/none), BCM numbers or "physical pin N" (header positions; power/ground pins are
  explained, not switched). "Play a song on physical pin 12" plays a tune as a gpiod software square wave
  (exact frequency, verified by edge count). Pins are refused only if in use (ID EEPROM 0/1, or any alt function).
  WARNING: `/sys/class/pwm/pwmchip0` is RP1 PWM1 = the cooling fan. RP1 PWM0 (GPIO 12/13/18/19 hardware PWM)
  is disabled; it needs `dtoverlay=pwm,pin=18,func=2` + reboot, and GPIO18 is meant for the I2S amps later.
- Python venv: `~/gene/venv` (pip works). bennjo has passwordless sudo (as of 2026-10-01), but don't change
- Bootloader EEPROM: on 2026-10-04 (asked by voice) the 2025-12-08 bootloader update to 2026-09-25 (default release) was
  STAGED with `sudo rpi-eeprom-update -a` (`/boot/firmware/pieeprom.upd` + `recovery.bin`); it flashes at the next reboot.
  Not rebooted. Cancel with `sudo rpi-eeprom-update -r`; check with `sudo rpi-eeprom-update`.
  /boot/firmware/config.txt or reboot without the user asking - it also affects the screen and fan.
- SSH: enabled on 2026-10-05 (asked by voice): `sudo systemctl enable --now ssh` (port 22, password + key login,
  sshd config untouched). Log in with `ssh bennjo@<pi-ip>` or `ssh bennjo@GodPi.local` (avahi). "How do I / what's the
  command to SSH into you?" (any "SSH" after the upgrade check) is answered directly (`ssh_answer`, live IP, said exactly).
- Web search (`gene_web.py`): a result that is a search engine's bot check ("unusual traffic", captcha - `BLOCKED`) is dropped and the
  next engine tried; "what was X again?" / "you said" (`BACK_REF`) is about the chat, so it never starts a who/what search.
- Memory: a fact listed twice in one consolidation is stored once, and a summary nearly the same as an old one replaces it.
- `gene_cameras.py`: Gene's eye cameras (since 2026-10-06, asked by voice): two OV5647 ribbon cameras on CAM/DISP 0 (= his
  RIGHT eye, `SIDES`, found 2026-10-13) and CAM/DISP 1 (left); `rpicam-hello --list-cameras` lists both.
  Both cameras are mounted ON THEIR SIDES (found 2026-10-12, asked by voice "tilt your camera properly" / "fix ..."):
  `gene_cameras.ROTATE = {0: 90, 1: 270}` (clockwise), all by np.rot90 after capture, so frames are 480x640 (portrait).
  (2026-10-13, "flip the camera that's upside down": libcamera's hflip+vflip Transform was never applied, so camera 1
  was upside down - don't use it.) Also 2026-10-13, Joshua checked: camera 0 is Gene's RIGHT eye, camera 1 his LEFT
  (`SIDES`, the opposite of the design notes; camera 1's picture has the room shifted right, as a left eye's should). Check by viewing frames rotated both ways: the cabinets
  must stand on the floor (a first fix turned only the right eye 180 and the room was still sideways).
  A look (picture attached) always tries Claude first, even with the jetson-first brain order (the Jetson can't see
  and made up "sideways view"); "is your camera right side up?" / "can you see properly?" counts as a look. `gene-cameras.service` (user unit,
  SYSTEM python: picamera2) writes a 640x480 frame a second per camera to `$XDG_RUNTIME_DIR/gene-camera/cam<N>.npy` (tmpfs,
  not the SD card). In gene_client a `Seer` thread runs YOLOv10n (`models/yolov10n/`, onnx-community/yolov10n on HF,
  COCO's 80 things, ~200 ms a frame on 2 threads) ALWAYS every 2 s (since 2026-10-06, asked by voice: "cameras always
  taking snapshots"; before, idle was every 20 s) + right when a phrase is heard, and each turn gets `(camera: person, 2 cups, laptop on your left)` (side only if one eye sees it; an eye closed by voice (`state/lids.json`) sees nothing - "your left eye is closed", both shut = "your eyes are closed, so you can't see anything", since 2026-10-06, asked by voice; "nothing
  you recognise" / "too dark"). No fresh frames -> no line and the status line says cameras not connected. Only object
  labels - no faces or colours. Test: `./venv/bin/python gene_cameras.py see`.
  A REAL LOOK (since 2026-10-06, `gene_vision.py`): a question only eyes can answer (`gene_vision.wanted`: "what colour
  is this?", "what am I holding?", "read this", "what do you see?", "look at me"; since 2026-10-13 also "what's in front of
  your face?", "read it (now)", "read the water bottle/label/sign", "what's written on it" - missed ones made him guess) sends the newest frame of the
  sharper open eye (or the eye named) as a PNG straight to Claude with the turn (~2-3 s; `(camera look: the picture
  attached ...)` line). Without Claude, Moondream 2 in Ollama ON THE PI (system service `ollama`, 127.0.0.1:11434,
  model `moondream`, kept loaded) describes it for the Jetson: ~20-40 s on the Pi CPU, so Gene first says "give me a
  few seconds to look" (`LOOK_FILLERS`). Moondream 2 garbles instructions - give it plain questions; an empty answer is
  retried as "Describe this picture.". Test: `./venv/bin/python gene_vision.py "what do you see?"`.
  Log: `journalctl --user-unit gene-cameras`.
- Phrase endpointing (2026-10-06): `END_SILENCE` 0.7 s (was 0.3 - a normal pause mid-sentence split it, and halves
  transcribe worse), `PREROLL` 0.5 s. Claude is told its words come through speech-to-text and to answer what was most
  likely meant (or ask) when a transcript looks garbled.
- Logs: `journalctl --user-unit gene` (what Gene heard/said, timings, errors). Upgrade history: `state/upgrades.jsonl`.
- WEB CONTROL PANEL (teleoperation, since 2026-10-13, asked by Joshua): `gene_teleop.py`, run by `gene-teleop.service`
  (user unit, SYSTEM python for Pillow; unit file kept here as `gene-teleop.service`), http://<pi-ip>:8080, password in
  `~/.config/gene/teleop.env` (TELEOP_PASSWORD=..., chmod 600 - never in git, never print it). Page: `teleop/index.html`.
  It shows both eye cameras live (it touches `$XDG_RUNTIME_DIR/gene-camera/fast`, and gene_cameras captures every
  FAST_EVERY 0.12 s instead of 1 s while that is < 5 s old), the eye screens (grim screenshot, each screen turned 180 deg
  on the page), the face, the conversation (`journalctl -f`), and sets faces / lids via gene_eyes (`show`, `hold`,
  `close_eyes`, `open_eyes`). "Listen" (2026-10-13, asked "allow me to hear through his mic"): `/mic.pcm` runs its OWN
  `pw-cat --record` on the default source (raw 16 kHz mono s16le, 100 ms pieces; Gene`s recorder is untouched, PipeWire
  allows both) and the page plays it with Web Audio (~0.25 s behind); a hard mute = silence, shown on the page (wpctl).
  Keep these hooks working when you change things:
  - "Say": the panel drops `state/teleop_say/<ns>.json` {"text", "face", "style"}; gene_client's `web_say_watch` says it
    word for word between turns (logged `Gene (web panel): ...`) and adds it to the chat history.
  - Mouth: `Mouth._play` writes `state/mouth.json` {"t" (start, epoch s), "ms", "text", "visemes"} for each clip (the Mouth
    queue items are (path, seconds, style, (text, visemes) or None)). The page animates a jaw from it with the head sim's
    VIS_OPEN table x 0.53. The page's jaw slider writes `state/jaw.json` {"deg" 0-30, "t"}: the target for the jaw servos
    once they're fitted (nothing drives servos yet - a jaw driver should follow mouth.json visemes, else jaw.json).
  - Upgrades: `upgrade.py` runs Claude Code with stream-json in/out (`--replay-user-messages`), writes every step to
    `state/upgrade_live.jsonl` (start/stage/text/tool/output/you/result/stopped/late/end), passes messages typed in the panel
    (`state/upgrade_inbox/*.json`) to Claude while it works (stdin closes once every message sent has been replayed and a
    result came back), and the panel's Stop (`state/upgrade_stop`) kills Claude, resets to the start commit (`git clean`
    too) and records "stopped from the web panel". Upgrades typed in the panel run as `upgrade.py web "<text>"`.

## Gene's brain: Claude first, the Jetson as the fallback (since 2026-10-06, asked by Joshua)

- `gene_brain.py` is the ONLY place that talks to a language model. `stream(messages, images)` (the conversation) and
  `complete(messages, schema=...)` (own_words, memory consolidation, the knowledge graph) try Claude, then the Jetson.
  A brain that fails before its first word is skipped for a while (Claude 30 s, a rejected key 10 min, Jetson 60 s),
  so a missing one costs one short timeout. `gene_brain.last` says which one answered.
- Claude: `claude-opus-5-5`, effort `low` (thinking is always on for this model; low keeps the first sentence at
  ~1.7-2.7 s vs ~0.5 s on the Jetson), streamed, server-side refusal fallbacks on (`fallbacks: "default"`). Gene's
  personality is the SYSTEM block of `brain/gene.Modelfile` + a short voice note (`gene_brain.VOICE`), so both brains
  are the same Gene - edit the Modelfile for personality changes. Ollama's `format` schema becomes Claude's
  output_config json_schema. Claude Opus 5.5 takes no temperature (Jetson-only `options`). SDK: `anthropic` in the venv.
- The API key is in `~/.config/gene/anthropic.env` (`ANTHROPIC_API_KEY=...`, chmod 600) - NEVER copy it into ~/gene
  or git, never print it. Override for tests: `GENE_BRAIN_ORDER=jetson` (Jetson only), `GENE_CLAUDE_MODEL`.
- Standalone: with Claude as the brain the head needs no Jetson - Pi + phone hotspot (NetworkManager profile
  "Gene hotspot", SSID "<your phone hotspot>", autoconnect priority 5; home "<your home Wi-Fi>" is 10, so it
  wins when both are around). STT, cameras, YOLO, Moondream, the voice and memory all run on the Pi.
- Test: `./venv/bin/python gene_brain.py "hey gene, what's up?"` (prints which brain answered and the timing).

## The Jetson brain (gene-brain, <jetson-ip>) - the fallback

- Ollama `http://<jetson-ip>:11434`, model `gene` (Llama 3.2 3B + system prompt in its Modelfile).
  Do NOT send a system message in Gene's conversation /api/chat - it replaces the Modelfile prompt.
  The Modelfile is versioned here as `brain/gene.Modelfile` (`.orig` = before memory). To change it: edit, then
  `scp brain/gene.Modelfile gene@<jetson-ip>:gene-brain/Modelfile && ssh gene@<jetson-ip> 'cd gene-brain && ollama create gene -f Modelfile'`
  (keep `FROM llama3.2:3b`; the blob path isn't readable by user gene). Test prompt changes first by sending
  the new prompt as a system message, which doesn't touch the live model.
  Jetson RAM is tight: ~0.7 GB free with Gene's model + Parakeet loaded, no swap. Don't load a second model.
- STT moved to THIS Pi on 2026-10-02 (frees ~1.9 GB on the Jetson for a bigger LLM): `gene-stt.service` (user unit),
  `http://127.0.0.1:8081/inference` (POST multipart `file`, `response_format=json`), Parakeet TDT 0.6B v3 q8_0 on the
  Pi CPU via whisper.cpp; source in `stt/` (README there has the rebuild steps), build + model in `~/gene-stt`.
  It maps "Jean"/"G,"/"Gee," back to "Gene". Same transcripts as the Jetson's f16 GPU version; ~0.5-1 s a phrase
  (Jetson was ~0.3 s). The Jetson's old `gene-stt` unit (`~/gene-stt/parakeet_server.py` there) is retired.
- SSH from this Pi: `ssh gene@<jetson-ip>` (key login). No sudo there without a password.
- Known Jetson fault: on 2026-09-30 one boot came up with the GPU dead (dmesg "ACR bootstrap failed",
  `ollama ps` shows 100% CPU, STT ~1.8 s). A reboot fixed it. If replies get slow, check `ollama ps` first.
- Camera detections (`gene_cameras.py`, run on the Pi) go with the context lines before the words: `(camera: person, cup)`.

## Hardware still to come (from the head design notes on ~/Desktop/Gene Robot)

- Jaw: twin DYNAMIXEL XL330-M288-T via a U2D2 (`/dev/dynamixel` once plugged in), one servo reversed.
  Speaking range 0-30 deg, hard limit 33 deg with the neck fitted. Talking opening 53 % of full visemes.
- Eyes: two 2.1" round 480x480 displays on micro-HDMI (gene_eyes.py already draws one eye per monitor; today
  the only monitor is the 3.5" 640x480 PocketTerm screen); the two cameras on CAM/DISP 0 (left) and 1 (right) are
  connected and used since 2026-10-06 (`gene_cameras.py`; camera 0 = right eye, 1 = left - see above).
- Speakers will move to two MAX98357A I2S amps (`setup_head.sh`); today audio is the USB speaker bar.
  Since 2026-10-05 (asked by voice) ONE MAX98357A is wired and is Gene's audio out: LRC = physical pin 35 (GPIO19),
  BCLK = pin 12 (GPIO18), DIN = pin 40 (GPIO21), GND = pin 6, VIN = pin 2 (5 V), GAIN = pin 9 (ground = 12 dB,
  since 2026-10-08; floating = 9 dB, 5 V = 6 dB). That day a broken LRC wire made him buzz loudly (replaced); GPIO
  18-21 are reserved in gene_gpio (`VOICE_PINS`) and the old Waveshare DPI overlay is commented out of config.txt. Driven by `dtoverlay=hifiberry-dac`
  (added at the end of /boot/firmware/config.txt, backup `config.txt.before-i2s-20261005`; it can also be loaded live with
  `sudo dtoverlay hifiberry-dac`, which is how it was first enabled without a reboot). ALSA card `sndrpihifiberry`,
  PipeWire sink "Built-in Audio Stereo" (`alsa_output.platform-soc_107c000000_sound.stereo-fallback`), set as the default
  sink with `wpctl set-default` (WirePlumber remembers it). The mic is still the USB speaker bar's (default source).
  Use the PipeWire default devices; never hard-code a device.

## Rules for an upgrade

1. Keep Gene talking. Test your change before finishing: at least `./venv/bin/python -c "import gene_client"`,
   and exercise the part you changed (e.g. call `chat_sentences`, `gene_tts.speak`, `stt` on a wav).
2. Commit your work with git, with a clear message of what changed and why. Small, focused changes.
3. Do not restart `gene.service` yourself - `upgrade.py` restarts it after you finish, checks Gene comes
   back up, and rolls back to the last good commit if he doesn't.
4. Finish with ONE short sentence, in plain spoken English, that Gene will say out loud about what
   he upgraded (e.g. "I can now hear you over background music."). Prefix it with `ANNOUNCE: `.
5. Don't delete Gene's voice, logs history, or the Desktop design folder. Don't touch other users' files.
