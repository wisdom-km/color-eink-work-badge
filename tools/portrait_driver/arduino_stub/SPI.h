#pragma once
#include "Arduino.h"
#define MSBFIRST 1
#define SPI_MODE0 0
struct SPISettings {unsigned rate,order,mode;SPISettings(unsigned r,unsigned o,unsigned m):rate(r),order(o),mode(m){} };
class SPIClass {
public:
    bool active=false,transaction=false;
    void begin(int sck,int miso,int mosi,int cs){assert(sck==6&&miso==-1&&mosi==7&&cs==-1);active=true;}
    void beginTransaction(SPISettings s){assert(active&&s.rate==1000000&&s.order==MSBFIRST&&s.mode==SPI_MODE0);transaction=true;}
    std::uint8_t transfer(std::uint8_t b){
        assert(active&&transaction&&stub::pins[2].value==LOW&&stub::pins[10].value==LOW);
        const bool data=stub::pins[20].value==HIGH;
        stub::events.push_back({data,b});
        if(!data){stub::command=b;stub::trigger=stub::clock;}
        return 0;
    }
    void endTransaction(){assert(stub::pins[2].value==HIGH);transaction=false;}
    void end(){assert(stub::pins[2].value==HIGH);active=false;++stub::end_calls;}
};
extern SPIClass SPI;
