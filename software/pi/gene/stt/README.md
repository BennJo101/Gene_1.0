# Gene's speech-to-text (on the Pi)

Parakeet TDT 0.6B v3 (multilingual NVIDIA ASR) via whisper.cpp's parakeet support, behind a whisper-server style
HTTP API on 127.0.0.1:8081 (`gene-stt.service`, user unit). Until 2026-10-02 this ran on the Jetson GPU; it moved
here to free ~1.9 GB of the Jetson's memory for a bigger LLM.

Rebuild from scratch (the build and model live outside the repo, in ~/gene-stt):

    git clone https://github.com/ggml-org/whisper.cpp ~/gene-stt/whisper.cpp && cd ~/gene-stt/whisper.cpp
    git checkout 6e4ab85
    cmake -B build -DCMAKE_BUILD_TYPE=Release -DWHISPER_BUILD_TESTS=OFF
    cmake --build build -j4 --target parakeet parakeet-cli parakeet-quantize
    cd ~/gene-stt && W=whisper.cpp && g++ -O2 -std=c++17 -o parakeet-serve ~/gene/stt/parakeet-serve.cpp \
      -I$W/include -I$W/ggml/include -L$W/build/bin -lparakeet -lggml -lggml-base -Wl,-rpath,$HOME/gene-stt/whisper.cpp/build/bin
    # model: copy ggml-parakeet-tdt-0.6b-v3-f16.bin from the Jetson (gene@<jetson-ip>:whisper.cpp/models/), then
    whisper.cpp/build/bin/parakeet-quantize ggml-parakeet-tdt-0.6b-v3-f16.bin models/ggml-parakeet-tdt-0.6b-v3-q8_0.bin q8_0

Benchmark 2026-10-02 (Pi 5, 4 threads, q8_0): identical transcripts to the Jetson's f16 on GPU on 9 clips;
0.46 s for a 2.3 s phrase, ~1.1 s for 8 s (Jetson was 0.3-0.45 s). f16 on the Pi was about twice as slow as q8_0.
