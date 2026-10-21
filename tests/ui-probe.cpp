#include <fcitx/inputcontext.h>
extern "C" __attribute__((noinline)) fcitx::Rect candidateRect(fcitx::InputContext *ic) {
    auto r = ic->cursorRect();
    asm volatile("" : : : "memory");
    return r;
}
