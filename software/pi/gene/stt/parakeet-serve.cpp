// Resident Parakeet: loads the model once, then for each line on stdin (a path to 16 kHz mono float32 raw
// audio) prints the transcript as one line on stdout. Driven by parakeet_server.py.
#include "parakeet.h"
#include "ggml-backend.h"
#include <cstdio>
#include <iostream>
#include <string>
#include <vector>

static void quiet(enum ggml_log_level, const char *, void *) {}

int main(int argc, char ** argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s model.bin [threads]\n", argv[0]); return 1; }
    int n_threads = argc > 2 ? atoi(argv[2]) : 4;
    ggml_backend_load_all();
    parakeet_log_set(quiet, nullptr);
    auto cp = parakeet_context_default_params();
    cp.use_gpu = false;          // the Pi 5 CPU (moved off the Jetson to free its memory for a bigger LLM)
    parakeet_context * ctx = parakeet_init_from_file_with_params(argv[1], cp);
    if (!ctx) { fprintf(stderr, "failed to load %s\n", argv[1]); return 1; }
    printf("READY\n"); fflush(stdout);
    std::string path;
    while (std::getline(std::cin, path)) {
        std::vector<float> pcm;
        if (FILE * f = fopen(path.c_str(), "rb")) {
            float buf[4096]; size_t n;
            while ((n = fread(buf, sizeof(float), 4096, f)) > 0) pcm.insert(pcm.end(), buf, buf + n);
            fclose(f);
        }
        std::string text;
        if (pcm.size() >= 1600) {
            auto fp = parakeet_full_default_params(PARAKEET_SAMPLING_GREEDY);
            fp.n_threads = n_threads;
            if (parakeet_full(ctx, fp, pcm.data(), pcm.size()) == 0)
                for (int i = 0; i < parakeet_full_n_segments(ctx); i++) {
                    if (!text.empty()) text += " ";
                    text += parakeet_full_get_segment_text(ctx, i);
                }
        }
        for (auto & c : text) if (c == 0x0a || c == 0x0d) c = 0x20;
        printf("%s\n", text.c_str()); fflush(stdout);
    }
    parakeet_free(ctx);
}
