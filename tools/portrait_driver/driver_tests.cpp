// SPDX-License-Identifier: MIT
#include "epd_3in6e.h"
#include "portrait_frame.h"
#include <fstream>
#include <iterator>
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <limits>
#include <string>
#include <vector>
struct Event { bool data; std::uint8_t value;
    bool operator==(const Event& b) const { return data==b.data && value==b.value; }
};
#include "vendor_oracle.h"
namespace {
enum class Stage { Reset, Init, PowerOn, Refresh, PowerOff };
enum class Fault { None, High, Low };
struct Fake final : epd36::IO {
    std::vector<Event> events;
    std::vector<std::pair<bool,std::uint32_t>> resets;
    bool powered=false,active=false,parked=true,begin_ok=true;
    bool global_high=false,global_low=false;
    std::uint32_t time=0,trigger=0,ack_delay=2,busy_duration=5;
    std::size_t attempted=0,fail_byte=std::numeric_limits<std::size_t>::max();
    unsigned off_calls=0;
    Stage stage=Stage::Reset,fault_stage=Stage::Reset;
    Fault fault=Fault::None;
    void hard_off() override { powered=false; active=false; parked=true; ++off_calls; }
    bool begin_bus() override { active=begin_ok; return begin_ok; }
    void rail_on() override { powered=true; parked=false; }
    void reset(bool high) override { resets.push_back({high,time}); stage=Stage::Reset; }
    bool write(bool data,std::uint8_t b) override {
        assert(powered && active);
        if (attempted++==fail_byte) return false;
        events.push_back({data,b});
        if (!data) {
            if (b==0x84) stage=Stage::Init;
            else if (b==0x04) stage=Stage::PowerOn;
            else if (b==0x12) stage=Stage::Refresh;
            else if (b==0x02) stage=Stage::PowerOff;
            trigger=time;
        }
        return true;
    }
    bool busy_high() override {
        if (global_high) return true;
        if (global_low) return false;
        if (stage==fault_stage) {
            if (fault==Fault::High) return true;
            if (fault==Fault::Low) return false;
        }
        if (stage==Stage::Reset || stage==Stage::Init) return true;
        const auto elapsed=static_cast<std::uint32_t>(time-trigger);
        return elapsed<ack_delay || elapsed>=ack_delay+busy_duration;
    }
    std::uint32_t now_ms() override { return time; }
    void delay_ms(std::uint32_t n) override { time+=n; }
    void check_off() const { assert(!powered && !active && parked && off_calls>=2); }
};
unsigned cases=0;
void expect(epd36::Result got,epd36::Result wanted,Fake& f) {
    if (got!=wanted) {
        std::cerr<<"got="<<epd36::result_name(got)<<" want="<<epd36::result_name(wanted)<<"\n";
        std::abort();
    }
    f.check_off(); ++cases;
}
std::vector<Event> golden(const std::vector<std::uint8_t>& bytes) {
    auto e=oracle_init; e.push_back({false,0x10});
    for (auto b:bytes) e.push_back({true,b});
    e.insert(e.end(),oracle_turn_on.begin(),oracle_turn_on.end());
    e.insert(e.end(),oracle_sleep.begin(),oracle_sleep.end()); return e;
}
std::uint8_t last_command(const Fake& f) {
    for(auto i=f.events.rbegin();i!=f.events.rend();++i) if(!i->data)return i->value;
    return 0;
}
}
int main(int argc,char** argv) {
    using R=epd36::Result;
    // All six native codes; complete exact command and data transcript, byte count,
    // no OOB bytes, reset polarity/timing, and hard rail cutoff on success.
    for(auto code : {0,1,2,3,5,6}) {
        Fake f; epd36::Driver d(f);
        expect(d.refresh_solid(code),R::Ok,f);
        std::vector<std::uint8_t> bytes(epd36::kFrameBytes,(code<<4)|code);
        assert(f.events==golden(bytes)); assert(f.events.size()==120061);
        assert(f.resets.size()==3 && f.resets[0].first && !f.resets[1].first && f.resets[2].first);
        assert(f.resets[1].second-f.resets[0].second==200);
        assert(f.resets[2].second-f.resets[1].second==20);
    }
    std::vector<std::uint8_t> frame(epd36::kFrameBytes);
    const unsigned colors[]={0,1,2,3,5,6};
    for(std::size_t i=0;i<frame.size();++i) frame[i]=(colors[i%6]<<4)|colors[(i+1)%6];
    { Fake f; epd36::Driver d(f);expect(d.refresh(frame.data(),frame.size()),R::Ok,f);assert(f.events==golden(frame)); }
    // Count checks run before dereferencing; first/last invalid nibble rejected
    // before powering the panel or emitting any SPI.
    for(auto count : {std::size_t(0),std::size_t(1),frame.size()-1,frame.size()+1,std::numeric_limits<std::size_t>::max()}) {
        Fake f;epd36::Driver d(f);expect(d.refresh(frame.data(),count),R::WrongSize,f);assert(f.events.empty());
    }
    {Fake f;epd36::Driver d(f);expect(d.refresh(nullptr,frame.size()),R::NullFrame,f);assert(f.events.empty());}
    for(unsigned code=0;code<256;++code) {
        if (epd36::valid_color(code)) continue;
        Fake f;epd36::Driver d(f);expect(d.refresh_solid(code),R::InvalidColor,f);assert(f.events.empty());
    }
    for(unsigned nibble=0;nibble<16;++nibble) for(unsigned half=0;half<2;++half) {
        if(epd36::valid_color(nibble))continue;
        for(auto pos : {std::size_t(0),frame.size()-1}) {
            const auto saved=frame[pos];frame[pos]=half ? ((nibble<<4)|1) : (0x10|nibble);
            Fake f;epd36::Driver d(f);expect(d.refresh(frame.data(),frame.size()),R::InvalidColor,f);
            assert(f.events.empty());frame[pos]=saved;
        }
    }
    {Fake f;f.begin_ok=false;epd36::Driver d(f);expect(d.refresh_solid(1),R::BusFailure,f);assert(f.events.empty());}
    {Fake f;f.global_low=true;epd36::Driver d(f);expect(d.refresh_solid(1),R::ResetTimeout,f);assert(f.events.empty()&&f.time<6000);}
    {Fake f;f.global_high=true;epd36::Driver d(f);expect(d.refresh_solid(1),R::PowerOnNoAck,f);assert(last_command(f)==0x04&&f.time<3000);}
    {Fake f;f.fault_stage=Stage::Init;f.fault=Fault::Low;epd36::Driver d(f);expect(d.refresh_solid(1),R::InitTimeout,f);assert(last_command(f)==0x84&&f.time<6000);}
    for(auto stage : {Stage::PowerOn,Stage::Refresh,Stage::PowerOff}) for(auto fault:{Fault::High,Fault::Low}) {
        Fake f;f.fault_stage=stage;f.fault=fault;epd36::Driver d(f);
        const bool high=fault==Fault::High;
        const R want=stage==Stage::PowerOn?(high?R::PowerOnNoAck:R::PowerOnTimeout):stage==Stage::Refresh?(high?R::RefreshNoAck:R::RefreshTimeout):(high?R::PowerOffNoAck:R::PowerOffTimeout);
        expect(d.refresh_solid(1),want,f);
        const auto command=stage==Stage::PowerOn?0x04:stage==Stage::Refresh?0x12:0x02;
        assert(last_command(f)==command&&f.time<70000);
    }
    // Every initialization byte and every control byte can fail; representative
    // first/middle/last full-frame failures exercise cleanup without refresh.
    std::vector<std::size_t> failures;
    for(std::size_t i=0;i<oracle_init.size()+1;++i) failures.push_back(i);
    for(auto i:{std::size_t(0),std::size_t(1),std::size_t(59999),std::size_t(119999)})failures.push_back(oracle_init.size()+1+i);
    for(std::size_t i=120049;i<120061;++i)failures.push_back(i);
    for(auto pos:failures) {
        Fake f;f.fail_byte=pos;epd36::Driver d(f);expect(d.refresh_solid(1),R::BusFailure,f);assert(f.events.size()==pos);
    }
    // Unsigned clock wrap during waits must not turn bounded waits into hangs.
    {Fake f;f.time=UINT32_MAX-900;epd36::Driver d(f);expect(d.refresh_solid(1),R::Ok,f);}
    {Fake f;f.time=UINT32_MAX-900;f.fault_stage=Stage::Refresh;f.fault=Fault::Low;epd36::Driver d(f);expect(d.refresh_solid(1),R::RefreshTimeout,f);}
    // Delayed acknowledgement within the bound; short pulses sampled immediately.
    for(auto ack:{0u,1u,999u}) {Fake f;f.ack_delay=ack;f.busy_duration=1;epd36::Driver d(f);expect(d.refresh_solid(1),R::Ok,f);}
    {Fake f;f.ack_delay=1001;epd36::Driver d(f);expect(d.refresh_solid(1),R::PowerOnNoAck,f);}
    // Recovery after a failure, repeated calls, no stale failure or bus state.
    {Fake f;epd36::Driver d(f);f.global_high=true;expect(d.refresh_solid(1),R::PowerOnNoAck,f);f.global_high=false;f.events.clear();f.attempted=0;expect(d.refresh_solid(6),R::Ok,f);}
    if(argc==3) {
        std::ifstream input(argv[1],std::ios::binary); assert(input.good());
        std::vector<std::uint8_t> sample((std::istreambuf_iterator<char>(input)),{});
        const auto crc=static_cast<std::uint32_t>(std::stoul(argv[2],nullptr,16));
        assert(portrait::validate_3in6e_frame(sample.data(),sample.size(),crc)==portrait::FrameStatus::Valid);
        Fake f; epd36::Driver d(f); expect(d.refresh(sample.data(),sample.size()),R::Ok,f);
        assert(f.events==golden(sample));
    }
    std::cout<<"{\"passed_cases\":"<<cases<<",\"golden_bytes_per_refresh\":120061,\"frame_bytes\":120000,\"all_returns_rail_off\":true}\n";
}
