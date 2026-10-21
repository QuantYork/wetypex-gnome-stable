// Model an XCB UI loaded with RTLD_LOCAL instead of linking XCB into main.
#include <assert.h>
#include <dlfcn.h>
int main(int argc, char **argv) {
    assert(argc == 2);
    void *module = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    assert(module);
    int (*test)(void) = (int (*)(void))dlsym(module, "anchor_test_main");
    assert(test);
    return test();
}
