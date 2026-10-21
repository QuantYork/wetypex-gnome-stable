#include <cassert>
#include <iostream>
#include <fcitx/instance.h>
#include <fcitx-utils/event.h>
#include <fcitx-utils/eventloopinterface.h>
#include <fcitx/inputcontext.h>
#include <fcitx/inputcontextmanager.h>
#include <fcitx/inputpanel.h>
#include <fcitx/text.h>
using namespace fcitx;
extern "C" Rect candidateRect(InputContext *);
static Rect caret(int x,int y,int w,int h) { Rect r; r.setPosition(x,y); r.setSize(w,h); return r; }
class Context : public InputContext {
public:
    Context(InputContextManager &m, const std::string &program = "anchor-probe") : InputContext(m, program) { created(); setCapabilityFlags(CapabilityFlag::Preedit); }
    ~Context() { destroy(); }
    const char *frontend() const override { return "anchor-probe"; }
    void commitStringImpl(const std::string &) override {}
    void deleteSurroundingTextImpl(int, unsigned) override {}
    void forwardKeyImpl(const ForwardKeyEvent &) override {}
    void updatePreeditImpl() override {}
};
int main() {
    char name[] = "anchor-probe", disable[] = "--disable", all[] = "all";
    char *args[] = {name, disable, all, nullptr};
    Instance instance(3, args);
    auto deferred = instance.eventLoop().addDeferEvent([&](EventSource *) {
    Context ic(instance.inputContextManager()), other(instance.inputContextManager());
    ic.focusIn(); other.focusIn();
    bool inlineMode = true;
    int calls = 0;
    auto engine = instance.watchEvent(EventType::InputContextKeyEvent,
        EventWatcherPhase::PreInputMethod, [&](Event &e) {
        auto &key = static_cast<KeyEvent &>(e);
        auto *context = key.inputContext();
        if (inlineMode) context->inputPanel().setClientPreedit(Text("ni"));
        else context->inputPanel().setPreedit(Text("ni"));
        const auto r = context->cursorRect();
        context->setCursorRect(caret(r.left()+14, r.top()+2, 0, r.height()+4));
        context->updatePreedit();
        ++calls;
        key.filterAndAccept();
    });
    auto press = [&](Context &c) { KeyEvent key(&c, Key("n")); c.keyEvent(key); };
    auto end = [&](Context &c) { c.inputPanel().reset(); c.updatePreedit(); c.updateUserInterface(UserInterfaceComponent::InputPanel, true); };
    auto check = [&](Context &c, int x, int y, int h) {
        auto r=candidateRect(&c); std::cerr << "actual=" << r.left() << "," << r.top() << "," << r.height() << " expected=" << x << "," << y << "," << h << "\n"; assert(r.left()==x && r.top()==y && r.height()==h);
    };
    ic.setCursorRect(caret(100,200,0,20));
    check(ic,100,200,20);
    press(ic); check(ic,100,200,20);
    assert(ic.cursorRect().left()==114 && ic.cursorRect().height()==24);
    press(ic); check(ic,100,200,20);
    assert(ic.cursorRect().left()==128);
    other.setCursorRect(caret(500,600,2,30)); check(other,500,600,30);
    press(other); check(other,500,600,30); check(ic,100,200,20);
    end(ic); check(ic,128,204,28);
    press(ic); check(ic,128,204,28);
    FocusOutEvent focusOut(&ic); instance.postEvent(focusOut);
    check(ic,142,206,32);
    end(ic); inlineMode=false;
    ic.setCursorRect(caret(-50,50,0,18)); press(ic); check(ic,-50,50,18);
    end(ic); check(ic,-36,52,22);
    ic.setCursorRect(caret(0,0,0,0)); press(ic);
    check(ic,14,2,4); // Invalid initial rectangle must fall back to live data.
    end(ic);
    Context compositor(instance.inputContextManager(), "gnome-shell");
    compositor.focusIn();
    compositor.setCursorRect(caret(70,80,0,20));
    press(compositor); check(compositor,70,80,20);
    press(compositor); check(compositor,70,80,20);
    end(compositor);
    assert(calls==8);
    std::cout << "PASS: pre-key anchor, repeated keys, real caret, contexts, commit/reset, focus-out, popup preedit, negative x, invalid geometry, compositor pre-key anchor\n";
    instance.exit();
    return false;
    });
    return instance.exec();
}
