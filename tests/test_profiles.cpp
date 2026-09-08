#include <string>
#include <vector>
#include <map>
#include <cstdint>
#include <csignal>
#include <ctime>
#include <cassert>
#include <fstream>
#include <cstdlib>
#include <cstring>
#include <sys/stat.h>
#define private public
#include "G13.h"
#undef private
#include "PassThroughAction.h"
volatile sig_atomic_t g13_keep_running = 1;
extern "C" int __wrap_libusb_open(libusb_device *, libusb_device_handle **) { return -1; }
extern "C" int __wrap_libusb_control_transfer(libusb_device_handle *, uint8_t, uint8_t, uint16_t, uint16_t, unsigned char *, uint16_t length, unsigned int) { return length; }
extern "C" int __wrap_libusb_interrupt_transfer(libusb_device_handle *, unsigned char, unsigned char *, int length, int *actual, unsigned int) { *actual=length; return 0; }
class ReleaseProbe : public G13Action {
    bool *released;
public:
    ReleaseProbe(bool *r): released(r) {}
    void key_up() { *released=true; }
};
int main() {
    char directory[] = "/tmp/g13-profile-test-XXXXXX";
    assert(mkdtemp(directory));
    setenv("HOME",directory,1);
    std::string base = std::string(directory)+"/.g13";
    mkdir(base.c_str(),0700);
    for(int i=0;i<4;i++) {
        std::ofstream out((base+"/bindings-"+std::to_string(i)+".properties").c_str());
        out << "# regression: read beyond the first property\nmode_profiles=1\nlcd_mode=logiframe\n";
        out << "lcd_logiframe_page2_cmd=printf test\nlcd_logiframe_page3_cmd=printf test\nlcd_logiframe_page4_cmd=printf test\n";
        out << "#" << std::string(4096,'x') << "\n";
        out << "G0=p,k." << 16+i << "\nlcd_logiframe_page4_color=1,2,3\n";
    }
    G13 driver(NULL); // USB open is stubbed; no hardware touched.
    driver.loadBindings();
    assert(driver.mode_profiles);
    assert(driver.logiframe_page_colors[3][2] == 3);
    assert(dynamic_cast<PassThroughAction*>(driver.actions[0])->getKeyCode()==16);
    bool released=false;
    delete driver.actions[1];
    driver.actions[1]=new ReleaseProbe(&released);
    driver.actions[1]->set(1);
    unsigned char report[5]={0};
    report[30/8] |= 1 << (30%8); // Physical M2
    driver.parse_key(30,report);
    assert(released);
    assert(driver.bindings==1 && driver.logiframe_page==1);
    assert(dynamic_cast<PassThroughAction*>(driver.actions[0])->getKeyCode()==17);
    G13Action *action=driver.actions[0];
    driver.actions[0]->set(1);
    driver.parse_key(30,report); // Held selector must not reload.
    assert(driver.actions[0]==action && driver.actions[0]->isPressed());
    memset(report,0,sizeof(report)); driver.parse_key(30,report);
    report[32/8] |= 1 << (32%8); driver.parse_key(32,report);
    assert(driver.bindings==3 && driver.logiframe_page==3);
    memset(report,0,sizeof(report)); driver.parse_key(32,report);
    report[29/8] |= 1 << (29%8); driver.parse_key(29,report);
    assert(driver.bindings==0 && driver.logiframe_page==0);
    for(int i=0;i<4;i++) std::remove((base+"/bindings-"+std::to_string(i)+".properties").c_str());
    rmdir(base.c_str());rmdir(directory);
}
