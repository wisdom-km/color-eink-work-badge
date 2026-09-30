#pragma once
#include "Arduino.h"
#include <cassert>
#include <deque>
#include <memory>
#define WIFI_OFF 0
#define WIFI_AP 2
struct IPAddress { unsigned a,b,c,d;IPAddress(unsigned w,unsigned x,unsigned y,unsigned z):a(w),b(x),c(y),d(z){} };
namespace fakephone {
struct Connection{std::string in,out;std::size_t pos=0;bool connected=true;};
extern std::deque<std::shared_ptr<Connection>> pending;
extern bool persistent,server_on,wifi_ok;
extern int wifi_mode;
extern unsigned rng_calls;
extern std::string ssid,password;
}
class WiFiClient {
public:
 std::shared_ptr<fakephone::Connection> c;
 WiFiClient()=default;explicit WiFiClient(std::shared_ptr<fakephone::Connection>x):c(x){}
 explicit operator bool()const{return c&&c->connected;}
 bool connected()const{return c&&c->connected;}
 int available()const{return connected()?static_cast<int>(c->in.size()-c->pos):0;}
 int read(){return available()?static_cast<unsigned char>(c->in[c->pos++]):-1;}
 std::size_t write(const std::uint8_t*p,std::size_t n){if(!connected())return 0;c->out.append(reinterpret_cast<const char*>(p),n);return n;}
 void stop(){if(c)c->connected=false;}
 void setTimeout(unsigned seconds){assert(seconds==1);}
};
class WiFiServer {
public:
 WiFiServer(unsigned port,unsigned clients){assert(port==80&&clients==1);}
 void begin(){fakephone::server_on=true;}
 void end(){fakephone::server_on=false;}
 void setNoDelay(bool){}
 WiFiClient available(){if(fakephone::pending.empty())return {};auto c=fakephone::pending.front();fakephone::pending.pop_front();return WiFiClient(c);}
};
class FakeWiFi {
public:
 void persistent(bool p){fakephone::persistent=p;}
 bool mode(int m){assert(m==WIFI_OFF||m==WIFI_AP);fakephone::wifi_mode=m;return fakephone::wifi_ok;}
 bool softAPConfig(IPAddress ip,IPAddress gw,IPAddress mask){assert(ip.a==192&&ip.b==168&&ip.c==4&&ip.d==1&&gw.d==1&&mask.a==255&&mask.d==0);return fakephone::wifi_ok;}
 bool softAP(const char*s,const char*p,unsigned channel,bool hidden,unsigned clients){assert(channel==1&&!hidden&&clients==1);fakephone::ssid=s;fakephone::password=p;assert(fakephone::password.size()==16);return fakephone::wifi_ok;}
 void softAPdisconnect(bool off){assert(off);fakephone::wifi_mode=WIFI_OFF;}
};
extern FakeWiFi WiFi;
