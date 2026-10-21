// Version-pinned Fcitx 5.1.19 compatibility preload. No text/key logging.
#include <dlfcn.h>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <unordered_map>
#include <fcitx/instance.h>
#include <fcitx/inputcontext.h>
#include <fcitx/inputpanel.h>
#include <fcitx/text.h>

namespace {
struct Anchor { fcitx::Rect rect; bool valid = false; bool reported = false; };
std::unordered_map<const fcitx::InputContext *, Anchor> &anchors() {
    static auto *map = new std::unordered_map<const fcitx::InputContext *, Anchor>;
    return *map;
}
using RectGetter = const fcitx::Rect &(*)(const fcitx::InputContext *);
RectGetter realRect() {
    static auto fn = reinterpret_cast<RectGetter>(dlsym(RTLD_NEXT,
        "_ZNK5fcitx12InputContext10cursorRectEv"));
    if (!fn) std::abort();
    return fn;
}
bool composing(fcitx::InputContext *ic) {
    const auto &p = ic->inputPanel();
    return !p.clientPreedit().empty() || !p.preedit().empty();
}
void before(fcitx::Event &e) {
    using namespace fcitx;
    switch (e.type()) {
    case EventType::InputContextKeyEvent: {
        auto &k = static_cast<KeyEvent &>(e);
        auto *ic = k.inputContext();
        if (!k.isRelease() && !composing(ic)) {
            const auto rect = realRect()(ic);
            // Zero width is a valid insertion caret; zero height is not.
            anchors()[ic] = Anchor{rect, rect.height() > 0};
        }
        break;
    }
    case EventType::InputContextFocusOut:
    case EventType::InputContextReset:
    case EventType::InputContextDestroyed:
    case EventType::InputContextSwitchInputMethod:
    case EventType::InputContextInputMethodDeactivated:
        anchors().erase(static_cast<InputContextEvent &>(e).inputContext());
        break;
    case EventType::InputContextUpdatePreedit:
    case EventType::InputContextUpdateUI: {
        auto *ic = static_cast<InputContextEvent &>(e).inputContext();
        if (!composing(ic)) anchors().erase(ic);
        break;
    }
    default: break;
    }
}
}
namespace fcitx {
int Instance::exec() {
    // The distro core binds its own internal calls locally; register supported
    // event watchers rather than trying to interpose Instance::postEvent.
    std::vector<std::unique_ptr<HandlerTableEntry<EventHandler>>> handlers;
    handlers.push_back(watchEvent(EventType::InputContextKeyEvent,
        EventWatcherPhase::PreInputMethod, before));
    for (auto type : {EventType::InputContextFocusOut, EventType::InputContextReset,
                     EventType::InputContextDestroyed,
                     EventType::InputContextSwitchInputMethod,
                     EventType::InputContextInputMethodDeactivated,
                     EventType::InputContextUpdatePreedit,
                     EventType::InputContextUpdateUI}) {
        handlers.push_back(watchEvent(type, EventWatcherPhase::PreInputMethod, before));
    }
    using Fn = int (*)(Instance *);
    static auto fn = reinterpret_cast<Fn>(dlsym(RTLD_NEXT, "_ZN5fcitx8Instance4execEv"));
    if (!fn) std::abort();
    const int result = fn(this);
    anchors().clear();
    return result;
}
const Rect &InputContext::cursorRect() const {
    Dl_info info{};
    const auto caller = __builtin_extract_return_addr(__builtin_return_address(0));
    // Only the candidate UI (classic or GNOME Kimpanel) sees the saved rectangle. Frontends and
    // engines continue to read the actual application cursor coordinates.
    if (dladdr(caller, &info) && info.dli_fname) {
        const char *base = std::strrchr(info.dli_fname, '/');
        base = base ? base + 1 : info.dli_fname;
        if ((std::strcmp(base, "libclassicui.so") == 0 ||
             std::strcmp(base, "libkimpanel.so") == 0)) {
            const auto it = anchors().find(this);
            if (it != anchors().end() && it->second.valid) {
                if (std::getenv("FCITX_PREKEY_TRACE") && !it->second.reported) {
                    const auto &saved = it->second.rect;
                    const auto &live = realRect()(this);
                    std::fprintf(stderr, "prekey-anchor app=%s saved=(%d,%d,%d) live=(%d,%d,%d)\n",
                        program().c_str(), saved.left(), saved.top(), saved.height(),
                        live.left(), live.top(), live.height());
                    it->second.reported = true;
                }
                return it->second.rect;
            }
        }
    }
    return realRect()(this);
}
}
