// Incremental voice transport; speech stays on stdout only, never in diagnostics.
#include <deque>
struct StreamReply { uint64_t order; int error; std::vector<unsigned char> bytes; };
static std::mutex stream_mutex;
static std::deque<StreamReply> stream_replies;
static void stream_callback(void *user,int,int error,const char *data,uint32_t size,const char*,uint32_t,const char*,uint32_t) {
  StreamReply r{uint64_t(reinterpret_cast<uintptr_t>(user)),error,{}};
  if(data && size && size<=1048576)r.bytes.assign(data,data+size);
  std::lock_guard lock(stream_mutex);stream_replies.push_back(std::move(r));
}
static uint64_t stream_ms(){timespec t{};clock_gettime(CLOCK_MONOTONIC,&t);return uint64_t(t.tv_sec)*1000+t.tv_nsec/1000000;}
static void stream_emit(const char *type,const std::string &text,bool verified=false){
  auto j=wire::object();wire::put(j.get(),"type",std::string(type));wire::put(j.get(),"text",text);wire::put(j.get(),"verified_final",verified);
  auto s=wire::dump(j.get());fwrite(s.data(),1,s.size(),stdout);fputc('\n',stdout);fflush(stdout);
}
template<class Start,class Option> static void voice_stream_run(Start start,const Option *option){
  timespec stamp{};clock_gettime(CLOCK_REALTIME,&stamp);
  const std::string id=std::to_string(business_init_uin.load())+"-"+std::to_string(stamp.tv_sec)+"-"+std::to_string(stamp.tv_nsec);
  uint64_t order=0,highest=0,total=0;uint32_t sequence=0;bool ended=false,final=false;uint64_t deadline=stream_ms()+600000,next_poll=0;
  std::string last,input;
  auto send=[&](const std::string &audio,bool end,uint32_t seq){
    std::vector<unsigned char> inner,outer;protobuf_string(inner,2,id);protobuf_uint(inner,3,0);protobuf_string(inner,4,audio);protobuf_uint(inner,5,5);protobuf_uint(inner,6,end);protobuf_uint(inner,7,seq);protobuf_uint(inner,11,total);protobuf_uint(inner,14,!getenv("WETYPE_VOICE_POLISH") || strcmp(getenv("WETYPE_VOICE_POLISH"),"0"));protobuf_uint(inner,19,0);protobuf_string(outer,1,std::string(inner.begin(),inner.end()));
    int task=start(4547,0,reinterpret_cast<const char*>(outer.data()),outer.size(),reinterpret_cast<void*>(uintptr_t(++order)),stream_callback,option);
    return task>=0;
  };
  stream_emit("ready","");
  while(stream_ms()<deadline && !final){
    std::deque<StreamReply> replies;{std::lock_guard lock(stream_mutex);replies.swap(stream_replies);}
    for(auto &r:replies){
      if(r.error){stream_emit("error","");_exit(1);}if(r.order<highest)continue;highest=r.order;
      auto nested=protobuf_string_field(r.bytes,1);std::vector<unsigned char> p(nested.begin(),nested.end());
      auto text=protobuf_string_field(p,4);auto end_flag=protobuf_uint_field(p,5,0);
      if(ended && end_flag){auto polished=protobuf_string_field(p,13);if(!polished.empty())text=polished;final=true;}
      if(!text.empty() && text!=last){last=text;stream_emit("partial",last);}
      if(final){stream_emit("final",last,true);break;}
    }
    if(final)break;
    if(ended){if(stream_ms()>=next_poll){if(!send("",true,0))break;next_poll=stream_ms()+400;}usleep(20000);continue;}
    pollfd fd{STDIN_FILENO,POLLIN,0};int n=poll(&fd,1,50);if(n<0 && errno==EINTR)continue;if(n<0)break;
    if(n && (fd.revents&(POLLIN|POLLHUP))){
      char b[16384];auto count=read(STDIN_FILENO,b,sizeof(b));if(count<=0)break;input.append(b,count);if(input.size()>65536)break;
      size_t pos;
      while(!ended && (pos=input.find('\n'))!=std::string::npos){
        auto line=input.substr(0,pos);input.erase(0,pos+1);auto j=wire::parse(line);if(!j){stream_emit("error","");_exit(1);}
        std::string hex=wire::str(j.get(),"audio_hex"),audio;if(hex.size()%2 || hex.size()>12000){stream_emit("error","");_exit(1);}
        auto digit=[](char c)->int{return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;};
        for(size_t i=0;i<hex.size();i+=2){int a=digit(hex[i]),b=digit(hex[i+1]);if(a<0||b<0){stream_emit("error","");_exit(1);}audio.push_back(char(a*16+b));}
        bool end=json_object_get_boolean(wire::get(j.get(),"end"));total+=audio.size();if(total>8388608)break;
        if(!send(audio,end,++sequence)){stream_emit("error","");_exit(1);}
        if(end){ended=true;deadline=stream_ms()+12000;next_poll=stream_ms()+400;}
      }
    }
  }
  if(!final){if(ended && !last.empty()){stream_emit("final",last,false);}else stream_emit("error","");}
  _exit(final|| (ended&&!last.empty())?0:1);
}
