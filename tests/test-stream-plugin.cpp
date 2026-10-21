#include "wetype.cpp"
#include <cassert>
#include <iostream>
#include <sstream>
class StreamContext:public fcitx::InputContext{
public:
 std::string visible,committed;unsigned commits=0,enters=0,releases=0;
 StreamContext(fcitx::InputContextManager&m):InputContext(m,"stream-plugin-test"){created();setCapabilityFlags(fcitx::CapabilityFlag::Preedit);}
 ~StreamContext(){destroy();}
 const char*frontend()const override{return "test";}
 void commitStringImpl(const std::string&s)override{committed+=s;++commits;}
 void deleteSurroundingTextImpl(int,unsigned)override{}
 void forwardKeyImpl(const fcitx::ForwardKeyEvent&e)override{assert(commits==1);if(e.isRelease())++releases;else ++enters;}
 void updatePreeditImpl()override{visible=inputPanel().clientPreedit().toString();}
};
int main(){
 char n[]="test",d[]="--disable=all";char*a[]={n,d,nullptr};fcitx::Instance instance(2,a);
 std::unique_ptr<StreamContext> ic;std::unique_ptr<WeType> engine;std::unique_ptr<fcitx::EventSourceTime> timer;
 fcitx::InputMethodEntry entry("wetypex","test","zh_CN","wetypex");unsigned stage=0;uint64_t id=0,epoch=0,oldEpoch=0,version=1;
 auto activate=[&](){fcitx::FocusInEvent e(ic.get());engine->activate(entry,e);};
 auto press=[&](){fcitx::KeyEvent e(ic.get(),fcitx::Key("Control+Super_L"));engine->keyEvent(entry,e);};
 auto token=[&](){std::ifstream f(getenv("VOICE_CALL_LOG"));std::string line;while(std::getline(f,line)){std::istringstream in(line);std::string action;uint64_t i,e;in>>action>>i>>e;if(action=="start"){id=i;epoch=e;}}return bool(id&&epoch);};
 auto message=[&](const char*kind,const char*text,uint64_t e){auto j=wire::object();wire::put(j.get(),"version",int64_t(++version));wire::put(j.get(),"session",int64_t(id));wire::put(j.get(),"epoch",int64_t(e));wire::put(j.get(),"kind",std::string(kind));wire::put(j.get(),"text",std::string(text));std::filesystem::path p=getenv("WETYPE_STATE_DIR");std::filesystem::create_directories(p);auto raw=wire::dump(j.get());std::string escaped;
for(size_t x=0;x<raw.size();){unsigned char b=raw[x++];if(b<128){escaped+=char(b);continue;}unsigned cp=b&15;assert((b&0xf0)==0xe0);for(int z=0;z<2;++z)cp=(cp<<6)|(raw[x++]&63);char out[7];snprintf(out,sizeof(out),"\\u%04x",cp);escaped+=out;}
std::ofstream(p/"voice-inbox.json")<<escaped;};
 auto deferred=instance.eventLoop().addDeferEvent([&](fcitx::EventSource*){
  ic=std::make_unique<StreamContext>(instance.inputContextManager());ic->focusIn();engine=std::make_unique<WeType>(&instance);activate();
  // A modifier pulse produced around a remapped copy must never start voice.
  press();fcitx::KeyEvent copy(ic.get(),fcitx::Key("Control+c"));engine->keyEvent(entry,copy);assert(!copy.accepted() && !copy.filtered());
  press();fcitx::KeyEvent release(ic.get(),fcitx::Key("Control+Super_L"),true);engine->keyEvent(entry,release);
  timer=instance.eventLoop().addTimeEvent(CLOCK_MONOTONIC,fcitx::now(CLOCK_MONOTONIC)+250000,0,[&](auto*s,uint64_t t){
   switch(stage++){
   case 0:{std::ifstream f(getenv("VOICE_CALL_LOG"));std::string line;while(std::getline(f,line))assert(line.rfind("start ",0)!=0);press();break;}
   case 1:if(!token()){--stage;break;}message("partial","错误会话",epoch+1);break;
   case 2:assert(ic->visible.empty()&&ic->commits==0);message("partial","今天天气温",epoch);break;
   case 3:assert(ic->visible=="今天天气温"&&ic->commits==0);assert(ic->inputPanel().clientPreedit().cursor()==int(ic->visible.size()));message("partial","今天天气很好",epoch);break;
   case 4:{assert(ic->visible=="今天天气很好"&&ic->commits==0);activate();assert(ic->visible=="今天天气很好");fcitx::KeyEvent e(ic.get(),fcitx::Key("Return"));engine->keyEvent(entry,e);assert(e.accepted());fcitx::KeyEvent repeat(ic.get(),fcitx::Key("Return"));engine->keyEvent(entry,repeat);fcitx::KeyEvent release(ic.get(),fcitx::Key("Return"),true);engine->keyEvent(entry,release);assert(release.accepted()&&ic->commits==0&&ic->visible=="今天天气很好");message("final","今天天气很好。",epoch);break;}
   case 5:if(!ic->enters){--stage;break;}assert(ic->enters==1&&ic->releases==1);assert(ic->visible.empty()&&ic->commits==1&&ic->committed=="今天天气很好。");message("final","重复结果",epoch);break;
   case 6:assert(ic->commits==1);oldEpoch=epoch;press();break;
   case 7:token();if(epoch==oldEpoch){--stage;break;}message("final","旧录音",oldEpoch);break;
   case 8:assert(ic->commits==1);message("partial","新录音",epoch);break;
   case 9:{assert(ic->visible=="新录音");fcitx::KeyEvent enter(ic.get(),fcitx::Key("Return"));engine->keyEvent(entry,enter);fcitx::FocusOutEvent out(ic.get());instance.postEvent(out);assert(ic->visible.empty());message("final","焦点外结果",epoch);break;}
   case 10:assert(ic->commits==1&&ic->enters==1&&ic->releases==1);engine.reset();ic.reset();std::cout<<"PASS: queued Enter commits final text before forwarding exactly once; repeated Enter coalesced; focus-out cancels pending submission; transient modifier/copy pulses do not start voice or swallow copy; genuine hold starts voice; actual plugin replaces streaming preedit, cursor at end, one final commit; stale epochs, duplicate final, backend panel refresh and focus-out protected. No microphone/network.\n";instance.exit();return false;
   }
   s->setTime(t+250000);s->setEnabled(true);return true;
  });return false;
 });return instance.exec();
}
