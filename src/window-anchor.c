#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <string.h>
#include <xcb/xcb.h>

/* Loaded into fcitx5 only. Never inspect keys or application text. */
typedef struct {
    xcb_connection_t *connection;
    xcb_window_t window;
    int mapped, have_x, have_y;
    uint32_t x, y;
} Anchor;
static Anchor anchors[16];
static Anchor *find(xcb_connection_t *c, xcb_window_t w) {
    for (unsigned i=0; i<16; ++i)
        if (anchors[i].connection==c && anchors[i].window==w) return &anchors[i];
    return 0;
}
static void identify(xcb_connection_t *c, xcb_window_t w, xcb_atom_t property,
                     uint8_t format, uint32_t length, const void *data) {
    static const char name[]="Fcitx5 Input Window";
    if (property!=XCB_ATOM_WM_NAME || format!=8 || length!=sizeof(name)-1 ||
        !data || memcmp(data,name,sizeof(name)-1)) return;
    if (find(c,w)) return;
    for (unsigned i=0; i<16; ++i) if (!anchors[i].connection) {
        anchors[i]=(Anchor){.connection=c,.window=w}; return;
    }
}
xcb_void_cookie_t xcb_change_property(xcb_connection_t *c,uint8_t mode,
        xcb_window_t w,xcb_atom_t property,xcb_atom_t type,uint8_t format,
        uint32_t length,const void *data) {
    static typeof(&xcb_change_property) next;
    if (!next) next=dlsym(RTLD_NEXT,"xcb_change_property");
    identify(c,w,property,format,length,data);
    return next(c,mode,w,property,type,format,length,data);
}
static void position(xcb_connection_t *c,xcb_window_t w,uint16_t mask,
                     const void *input,uint32_t output[7]) {
    Anchor *a=find(c,w);
    unsigned index=0;
    for (unsigned bit=0;bit<7;++bit) if (mask & (1u<<bit)) {
        uint32_t value=((const uint32_t *)input)[index];
        if (a && bit==0) {
            if (a->mapped && a->have_x) value=a->x;
            else {a->x=value;a->have_x=1;}
        }
        if (a && bit==1) {
            if (a->mapped && a->have_y) value=a->y;
            else {a->y=value;a->have_y=1;}
        }
        output[index++]=value;
    }
}
#define CONFIGURE(suffix) \
xcb_void_cookie_t xcb_configure_window##suffix(xcb_connection_t *c,xcb_window_t w,uint16_t mask,const void *values) { \
    static typeof(&xcb_configure_window##suffix) next; \
    if (!next) next=dlsym(RTLD_NEXT,"xcb_configure_window" #suffix); \
    uint32_t updated[7];position(c,w,mask,values,updated); \
    return next(c,w,mask,updated); \
}
CONFIGURE()
CONFIGURE(_checked)
#define MAP(suffix) \
xcb_void_cookie_t xcb_map_window##suffix(xcb_connection_t *c,xcb_window_t w) { \
    static typeof(&xcb_map_window##suffix) next; \
    if (!next) next=dlsym(RTLD_NEXT,"xcb_map_window" #suffix); \
    Anchor *a=find(c,w);if(a) a->mapped=1; \
    return next(c,w); \
}
MAP()
MAP(_checked)
#define UNMAP(suffix) \
xcb_void_cookie_t xcb_unmap_window##suffix(xcb_connection_t *c,xcb_window_t w) { \
    static typeof(&xcb_unmap_window##suffix) next; \
    if (!next) next=dlsym(RTLD_NEXT,"xcb_unmap_window" #suffix); \
    Anchor *a=find(c,w);if(a){a->mapped=0;a->have_x=a->have_y=0;} \
    return next(c,w); \
}
UNMAP()
UNMAP(_checked)
#define DESTROY(suffix) \
xcb_void_cookie_t xcb_destroy_window##suffix(xcb_connection_t *c,xcb_window_t w) { \
    static typeof(&xcb_destroy_window##suffix) next; \
    if (!next) next=dlsym(RTLD_NEXT,"xcb_destroy_window" #suffix); \
    Anchor *a=find(c,w);if(a) memset(a,0,sizeof(*a)); \
    return next(c,w); \
}
DESTROY()
DESTROY(_checked)
