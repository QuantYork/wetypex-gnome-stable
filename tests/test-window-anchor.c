#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <xcb/xcb.h>
static void check(xcb_connection_t*c,xcb_window_t w,int x,int y,int width){
 xcb_get_geometry_reply_t*r=xcb_get_geometry_reply(c,xcb_get_geometry(c,w),0);
 assert(r);printf("position=(%d,%d) width=%d\n",r->x,r->y,r->width);
 assert(r->x==x && r->y==y && r->width==width);free(r);
}
int main(void){
 xcb_connection_t*c=xcb_connect(0,0);assert(!xcb_connection_has_error(c));
 xcb_screen_t*s=xcb_setup_roots_iterator(xcb_get_setup(c)).data;
 xcb_window_t w=xcb_generate_id(c);
 uint32_t override=1;
 xcb_create_window(c,XCB_COPY_FROM_PARENT,w,s->root,0,0,80,30,0,XCB_WINDOW_CLASS_INPUT_OUTPUT,s->root_visual,XCB_CW_OVERRIDE_REDIRECT,&override);
 const char*name="Fcitx5 Input Window";
 xcb_change_property(c,XCB_PROP_MODE_REPLACE,w,XCB_ATOM_WM_NAME,XCB_ATOM_STRING,8,strlen(name),name);
 uint32_t first[]={100,150};xcb_configure_window(c,w,3,first);xcb_map_window(c,w);
 uint32_t moved[]={300,350,120};xcb_configure_window(c,w,7,moved);check(c,w,100,150,120);
 xcb_unmap_window(c,w);xcb_configure_window(c,w,3,moved);xcb_map_window(c,w);check(c,w,300,350,120);
 xcb_destroy_window(c,w);
 w=xcb_generate_id(c);xcb_create_window(c,XCB_COPY_FROM_PARENT,w,s->root,0,0,80,30,0,XCB_WINDOW_CLASS_INPUT_OUTPUT,s->root_visual,XCB_CW_OVERRIDE_REDIRECT,&override);
 xcb_configure_window(c,w,3,first);xcb_map_window(c,w);xcb_configure_window(c,w,7,moved);check(c,w,300,350,120);
 xcb_destroy_window(c,w);xcb_disconnect(c);puts("PASS: anchor, resize, reset, unrelated window");return 0;
}
